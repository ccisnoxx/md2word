from __future__ import annotations

# 文件：app/domains/document_jobs/service.py
# 用途：创建、投递、查询 document_jobs 并记录任务事件。

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol, get_args
from uuid import uuid4

from bs4 import BeautifulSoup
from fastapi import status

from app.core.config import Settings
from app.domains.document_jobs.models import (
    DocumentJobEventLevel,
    DocumentJobEventRecord,
    DocumentJobEventType,
    DocumentJobMode,
    DocumentJobRecord,
    DocumentJobStage,
    DocumentJobStatus,
    DocumentJobTranslationBatchRecord,
    DocumentJobTranslationQaIssueType,
    DocumentJobTranslationQaStatus,
)
from app.domains.document_jobs.schemas import (
    DocumentJobAvailableActionResponse,
    DocumentJobTranslationQaAiCallResponse,
    DocumentJobTranslationQaArtifactsResponse,
    DocumentJobTranslationQaResponse,
    DocumentJobTranslationQaSegmentResponse,
    DocumentJobTranslationQaStateResponse,
    DocumentJobTranslationQaSummaryResponse,
    DocumentJobTranslationQaTermTraceResponse,
)
from app.domains.document_jobs.workflow import (
    ARCHIVABLE_DOCUMENT_JOB_STATUSES,
    CANCELABLE_DOCUMENT_JOB_STATUSES,
    DOCUMENT_JOB_STATUS_GROUPS,
)
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord, DocumentFileType
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import ConversionOptions
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError
from app.domains.resources.models import utc_now
from app.domains.translation.modes import (
    TranslationMode,
    document_job_mode_for_translation_mode,
    is_translation_document_job_mode,
    normalize_translation_mode,
    spec_for_document_job_mode,
    translation_mode_for_document_job_mode,
)
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
)
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.services.document_ir.models import DocumentIR
from app.services.auth.models import AuthenticatedUser


DOCUMENT_JOB_LIST_SORTS = {"created_at_desc", "created_at_asc", "updated_at_desc", "updated_at_asc"}
DOCUMENT_JOB_DOWNLOAD_FILE_TYPES: set[DocumentFileType] = {
    "source_pdf",
    "mineru_raw_result",
    "document_ir",
    "image_assets_archive",
    "generated_word",
    "ai_call_log",
    "ai_debug_archive",
}
DOCUMENT_JOB_FILE_TYPE_ORDER = {
    "source_pdf": 0,
    "generated_word": 10,
    "mineru_raw_result": 20,
    "document_ir": 30,
    "image_assets_archive": 40,
    "ai_call_log": 50,
    "ai_debug_archive": 60,
}
DOCUMENT_JOB_DELETE_TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
DEFAULT_DOCUMENT_JOB_DELETE_REASON = "admin_preview_confirm_delete"


@dataclass(frozen=True)
class DocumentJobListResult:
    """document_jobs 列表查询的分页结果和面向工作台的统计投影。"""

    items: list[DocumentJobRecord]
    total: int
    summary: dict[str, int]
    filtered_summary: dict[str, int]
    translation_qa_summary: dict[str, int]


@dataclass(frozen=True)
class DocumentJobDeletePlanFile:
    """任务删除计划中的单个文件决策，不暴露 object_key 或本地路径。"""

    file_id: str
    file_type: str | None
    storage_provider: str | None
    status_before: str | None
    status_after: str | None
    size_bytes: int | None
    action: str
    outcome: str
    reason: str
    deleted: bool = False
    metadata_updated: bool = False
    s3_delete_contract: dict[str, Any] | None = None

    def to_response_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "file_type": self.file_type,
            "storage_provider": self.storage_provider,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "size_bytes": self.size_bytes,
            "action": self.action,
            "outcome": self.outcome,
            "reason": self.reason,
            "deleted": self.deleted,
            "metadata_updated": self.metadata_updated,
            "s3_delete_contract": self.s3_delete_contract,
        }


@dataclass(frozen=True)
class DocumentJobDeletePlan:
    """任务删除预览或执行结果；router 负责转换为 API response model。"""

    job: DocumentJobRecord
    action_mode: str
    confirmation_phrase: str
    preview_hash: str
    totals: dict[str, int]
    files: list[DocumentJobDeletePlanFile]
    safety: dict[str, bool]


class _DocumentJobSearchable(Protocol):
    id: str
    source_file_id: str
    request_snapshot: dict[str, Any]
    error_code: str | None
    error_message: str | None


class DocumentJobService:
    """P0 document_jobs 应用服务；按配置创建任务后投递 Worker。"""

    def __init__(
        self,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        event_repository: DocumentJobEventRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        task_queue: DocumentJobTaskQueueProtocol | None = None,
        template_read_service: Any | None = None,
        term_version_service: Any | None = None,
        job_resource_snapshot_service: Any | None = None,
        document_job_translation_batch_repository: DocumentJobTranslationBatchRepositoryProtocol | None = None,
        file_upload_service: Any | None = None,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.file_repository = file_repository
        self.task_queue = task_queue
        self.template_read_service = template_read_service
        self.term_version_service = term_version_service
        self.job_resource_snapshot_service = job_resource_snapshot_service
        self.document_job_translation_batch_repository = document_job_translation_batch_repository
        self.file_upload_service = file_upload_service

    def create_job(
        self,
        *,
        user: AuthenticatedUser,
        source_file_id: str,
        mode: DocumentJobMode | None,
        translation_mode: TranslationMode | None,
        document_language: str,
        template_version_id: str | None,
        term_version_id: str | None,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
        translation_profile_id: str | None,
        translation_profile_version: str | None,
        debug_full_text: bool,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """创建待处理 document_job，并在启用 Worker 后按 job_id 投递。"""

        source_file = self._get_source_file_for_create(source_file_id, user)
        mode = self._resolve_document_job_mode(mode=mode, translation_mode=translation_mode)
        self._ensure_document_language_allowed(mode, document_language)
        self._ensure_debug_full_text_allowed(user, debug_full_text)
        self._ensure_direct_translation_selection_absent(
            mode,
            term_version_id=term_version_id,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            debug_full_text=debug_full_text,
        )
        normalized_template_version_id = self._resolve_template_version_id(
            template_version_id,
            allow_draft=user.role == "admin",
        )
        normalized_term_version_id = self._resolve_term_version_id(
            mode,
            self._legacy_translation_term_version_id(mode, term_version_id, translation_term_version),
        )
        debug_full_text_enabled = self._resolve_debug_full_text_enabled(mode, debug_full_text)
        now = utc_now()
        job_id = f"docjob_{uuid4().hex[:12]}"
        request_snapshot = self._build_request_snapshot(
            source_file,
            mode=mode,
            document_language=document_language,
            template_version_id=normalized_template_version_id,
            term_version_id=normalized_term_version_id,
            debug_full_text_enabled=debug_full_text_enabled,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            resource_snapshot=self._build_resource_snapshot(
                job_id=job_id,
                mode=mode,
                document_language=document_language,
                template_version_id=normalized_template_version_id if self._normalize_optional_text(template_version_id) else None,
                term_rule_set_id=term_rule_set_id,
                term_rule_set_version=term_rule_set_version,
                term_rule_department_id=user.department_id,
                translation_term_set_id=translation_term_set_id,
                translation_term_version=translation_term_version,
                translation_profile_id=translation_profile_id,
                translation_profile_version=translation_profile_version,
                allow_draft_template=user.role == "admin",
            ),
        )
        job = DocumentJobRecord(
            id=job_id,
            tenant_id=user.tenant_id,
            company_id=user.company_id,
            created_by=user.id,
            source_file_id=source_file.id,
            mode=mode,
            document_language=document_language,
            status="pending",
            stage="uploaded",
            progress=0,
            template_version_id=normalized_template_version_id,
            term_version_id=normalized_term_version_id,
            debug_full_text_enabled=debug_full_text_enabled,
            timeout_at=now + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
            request_snapshot=request_snapshot,
            created_at=now,
            updated_at=now,
        )
        self.job_repository.create_document_job(job)
        self.file_repository.update_document_file(source_file.id, job_id=job.id, updated_at=now)
        self.record_event(
            job,
            event_type="job_created",
            stage="uploaded",
            level="info",
            message="文档任务已创建，等待投递 Worker。",
            payload={
                "source_file_id": source_file.id,
                "mode": mode,
                "translation_mode": translation_mode_for_document_job_mode(mode),
                "template_version_id": normalized_template_version_id,
                "term_version_id": normalized_term_version_id,
                "term_assets": request_snapshot.get("term_assets"),
                "resources": request_snapshot.get("resources"),
                "debug_full_text_enabled": debug_full_text_enabled,
            },
            trace_id=trace_id,
        )
        if self.task_queue is None:
            return job
        return self._enqueue_created_job(job, trace_id=trace_id)

    def get_job(self, job_id: str, *, user: AuthenticatedUser) -> DocumentJobRecord:
        """按 owner/admin 规则读取 document_job。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文档任务不存在: {job_id}")
        self._ensure_visible(job, user)
        return job

    def list_jobs(
        self,
        *,
        user: AuthenticatedUser,
        page: int,
        page_size: int,
        status_filter: str | None,
        status_group: str | None = None,
        translation_qa_status: str | None = None,
        q: str | None = None,
        sort: str = "created_at_desc",
        include_archived: bool = False,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> DocumentJobListResult:
        """返回当前用户可见的 document_jobs 分页列表。"""

        if status_filter is not None and status_group is not None:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 与 status_group 不能同时使用。")
        if status_filter is not None and status_filter not in get_args(DocumentJobStatus):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 查询参数非法。")
        if status_group is not None and status_group not in DOCUMENT_JOB_STATUS_GROUPS:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status_group 查询参数非法。")
        translation_qa_filters = set(get_args(DocumentJobTranslationQaStatus)) | {"all"}
        if translation_qa_status is not None and translation_qa_status not in translation_qa_filters:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "translation_qa_status 查询参数非法。")
        if sort not in DOCUMENT_JOB_LIST_SORTS:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "sort 查询参数非法。")
        if created_from is not None and created_to is not None and created_from > created_to:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "created_from 不能晚于 created_to。")
        normalized_q = self._normalize_optional_text(q)
        visible_jobs = [
            job
            for job in self.job_repository.list_document_jobs()
            if self._is_visible(job, user)
            and job.deleted_at is None
            and (include_archived or job.archived_at is None)
        ]
        summary = dict(Counter(job.status for job in visible_jobs))
        qa_summary_jobs = [
            job
            for job in visible_jobs
            if self._matches_status_filter(job, status_filter=status_filter, status_group=status_group)
            and self._matches_document_job_query(job, normalized_q)
            and self._matches_created_range(job, created_from=created_from, created_to=created_to)
            and is_translation_document_job_mode(job.mode)
        ]
        filtered_jobs = [
            job
            for job in visible_jobs
            if self._matches_status_filter(job, status_filter=status_filter, status_group=status_group)
            and self._matches_translation_qa_status(job, translation_qa_status)
            and self._matches_document_job_query(job, normalized_q)
            and self._matches_created_range(job, created_from=created_from, created_to=created_to)
        ]
        filtered_summary = dict(Counter(job.status for job in filtered_jobs))
        filtered_jobs.sort(key=lambda job: self._document_job_sort_key(job, sort), reverse=sort.endswith("_desc"))
        start = (page - 1) * page_size
        return DocumentJobListResult(
            items=filtered_jobs[start:start + page_size],
            total=len(filtered_jobs),
            summary=summary,
            filtered_summary=filtered_summary,
            translation_qa_summary=self._count_translation_qa_statuses(qa_summary_jobs),
        )

    def list_events(self, job_id: str, *, user: AuthenticatedUser) -> list[DocumentJobEventRecord]:
        """先按任务权限校验，再返回事件列表。"""

        self.get_job(job_id, user=user)
        return self.event_repository.list_document_job_events(job_id)

    def list_translation_batches(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> list[DocumentJobTranslationBatchRecord]:
        """只读返回任务当前 retry_count generation 的翻译 provider 批次诊断。"""

        job = self.get_job(job_id, user=user)
        if self.document_job_translation_batch_repository is None:
            raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "翻译批次诊断仓储未配置。")
        return self.document_job_translation_batch_repository.list_translation_batches(
            job.id,
            generation=job.retry_count,
        )

    def list_visible_jobs(
        self,
        *,
        user: AuthenticatedUser,
        include_archived: bool = False,
    ) -> list[DocumentJobRecord]:
        """Return document_jobs visible to the user for read-only projections."""

        return [
            job
            for job in self.job_repository.list_document_jobs()
            if self._is_visible(job, user)
            and job.deleted_at is None
            and (include_archived or job.archived_at is None)
        ]

    def document_job_search_values(self, job: _DocumentJobSearchable) -> list[str]:
        """Return the shared document_job search fields used by queue projections."""

        return self._document_job_search_values(job)

    def list_files(self, job_id: str, *, user: AuthenticatedUser) -> list[DocumentFileRecord]:
        """先按任务权限校验，再返回任务上下文内可展示的文件元数据。"""

        job = self.get_job(job_id, user=user)
        return self._list_files_for_job(job)

    def build_available_actions(
        self,
        job: DocumentJobRecord,
        *,
        user: AuthenticatedUser,
    ) -> dict[str, DocumentJobAvailableActionResponse]:
        """返回前端展示用的动作可用性投影；真正执行仍由各 endpoint 校验。"""

        retry_disabled_reason = self._retry_disabled_reason(job)
        return {
            "download": self._available_action(self._download_disabled_reason(job)),
            "retry": self._available_action(retry_disabled_reason, retryable=retry_disabled_reason is None),
            "cancel": self._available_action(self._cancel_disabled_reason(job)),
            "archive": self._available_action(self._archive_disabled_reason(job)),
            "unarchive": self._available_action(self._unarchive_disabled_reason(job)),
            "clone": self._available_action(self._clone_disabled_reason(job, user=user)),
            "delete": self._available_action(self._delete_disabled_reason(job, user=user)),
        }

    def get_translation_qa(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        limit: int,
    ) -> DocumentJobTranslationQaResponse:
        """读取翻译 QA 证据摘要；只消费已有 artifact，不触发任何任务执行。"""

        job = self.get_job(job_id, user=user)
        qa = self._build_translation_qa_state(job)
        if not is_translation_document_job_mode(job.mode):
            return self._build_unavailable_translation_qa(job, qa, reason="unsupported_mode")
        self._ensure_file_reader_available()

        files = self._list_files_for_job(job)
        ai_log_files = self._uploaded_files_by_type(files, "ai_call_log")
        debug_archive_files = self._uploaded_files_by_type(files, "ai_debug_archive")
        ai_calls, term_traces = self._read_ai_call_log_summaries(ai_log_files)
        source_texts, ai_translation_texts, source_reason = self._read_debug_archive_texts(debug_archive_files)
        document_ir_file = self._select_document_ir_file(job, files)
        artifacts = self._build_translation_qa_artifacts(
            document_ir_file=document_ir_file,
            ai_log_files=ai_log_files,
            debug_archive_files=debug_archive_files,
        )
        if document_ir_file is None:
            return self._build_unavailable_translation_qa(
                job,
                qa,
                reason="document_ir_missing",
                artifacts=artifacts,
                ai_calls=ai_calls,
                term_traces=term_traces,
                source_reason=source_reason,
            )

        document_ir = self._read_document_ir(document_ir_file)
        if document_ir is None:
            return self._build_unavailable_translation_qa(
                job,
                qa,
                reason="document_ir_unreadable",
                artifacts=artifacts,
                ai_calls=ai_calls,
                term_traces=term_traces,
                source_reason=source_reason,
            )

        all_segments = self._build_translation_qa_segments(
            document_ir,
            source_texts=source_texts,
            ai_translation_texts=ai_translation_texts,
        )
        returned_segments = all_segments[:limit]
        summary = DocumentJobTranslationQaSummaryResponse(
            final_segment_count=len(all_segments),
            returned_segment_count=len(returned_segments),
            quality_flags=document_ir.quality_flags,
            ai_call_count=len(ai_calls),
            ai_call_statuses=dict(Counter(call.status or "unknown" for call in ai_calls)),
            term_trace_count=len(term_traces),
            debug_full_text_enabled=job.debug_full_text_enabled,
            source_comparison_available=source_reason is None,
            source_comparison_reason=source_reason,
        )
        return DocumentJobTranslationQaResponse(
            job_id=job.id,
            available=True,
            availability_reason=None,
            qa=qa,
            artifacts=artifacts,
            summary=summary,
            segments=returned_segments,
            term_traces=term_traces,
            ai_calls=ai_calls,
        )

    def update_translation_qa(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        qa_status: DocumentJobTranslationQaStatus,
        issue_type: DocumentJobTranslationQaIssueType | None,
        note: str | None,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """保存任务级翻译 QA 结论，并只记录非敏感事件摘要。"""

        job = self.get_job(job_id, user=user)
        if not is_translation_document_job_mode(job.mode):
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "翻译 QA 仅支持翻译任务。")
        now = utc_now()
        normalized_note = self._normalize_optional_text(note)
        patch: dict[str, Any] = {
            "translation_qa_status": qa_status,
            "translation_qa_issue_type": issue_type,
            "translation_qa_note": normalized_note,
            "updated_at": now,
        }
        if qa_status == "unreviewed":
            patch.update(
                translation_qa_issue_type=None,
                translation_qa_note=None,
                translation_qa_reviewed_by=None,
                translation_qa_reviewed_at=None,
            )
        else:
            patch.update(
                translation_qa_reviewed_by=user.id,
                translation_qa_reviewed_at=now,
            )
        updated = self.job_repository.update_document_job(job.id, **patch)
        self.record_event(
            updated,
            event_type="translation_qa_updated",
            stage=updated.stage,
            level="info",
            message="翻译 QA 复核状态已更新。",
            payload={
                "status": updated.translation_qa_status,
                "issue_type": updated.translation_qa_issue_type,
                "reviewed_by": updated.translation_qa_reviewed_by,
                "note_length": len(updated.translation_qa_note or ""),
            },
            trace_id=trace_id,
        )
        return updated

    def get_result_file_for_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """校验任务权限和完成状态后返回生成 Word 文件。"""

        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        return job, self._get_downloadable_completed_result_file(job)

    def get_file_for_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        file_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """按可见任务签发文件下载前，校验文件归属、状态、过期和类型。"""

        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if file_id is None:
            return job, self._get_downloadable_completed_result_file(job)
        return job, self._get_downloadable_task_file(job, file_id=file_id)

    def get_result_file_for_authorized_download(
        self,
        job_id: str,
        *,
        file_id: str,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """临时下载 URL 已验签后使用，不再要求 Bearer token。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文档任务不存在: {job_id}")
        self._ensure_job_not_deleted(job)
        file = self._get_downloadable_completed_result_file(job)
        if file.id != file_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载链接与结果文件不匹配。")
        return job, file

    def get_file_for_authorized_download(
        self,
        job_id: str,
        *,
        file_id: str,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """临时下载 URL 已验签后，按 token 中的 file_id 重新校验文件合同。"""

        job = self.job_repository.get_document_job(job_id)
        if job is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文档任务不存在: {job_id}")
        self._ensure_job_not_deleted(job)
        return job, self._get_downloadable_task_file(job, file_id=file_id)

    def retry_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        reason: str | None,
        use_latest_term_assets: bool = False,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        trace_id: str | None = None,
    ) -> DocumentJobRecord:
        """对可重试失败任务按原 job_id 重新投递，保留既有中间产物用于幂等恢复。"""

        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        self._ensure_resource_selection_allowed(
            user=user,
            use_latest_term_assets=use_latest_term_assets,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        if job.archived_at is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "已归档文档任务不允许重试。")
        self._ensure_retry_allowed(job)
        self._ensure_direct_translation_selection_absent(
            job.mode,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        now = utc_now()
        retry_count = job.retry_count + 1
        patch = self._build_retry_patch(
            job,
            retry_count=retry_count,
            now=now,
            use_latest_term_assets=use_latest_term_assets,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        retried = self.job_repository.update_document_job(job.id, **patch)
        self.record_event(
            retried,
            event_type="retry_requested",
            stage=retried.stage,
            level="info",
            message="文档任务已请求重试。",
            payload={
                "retry_count": retry_count,
                "reason": self._normalize_optional_text(reason),
                "previous_error_code": job.error_code,
                "previous_failed_stage": job.failed_stage,
                "resume_stage": retried.stage,
                "use_latest_term_assets": use_latest_term_assets,
                "term_assets": retried.request_snapshot.get("term_assets"),
                "resources": retried.request_snapshot.get("resources"),
            },
            trace_id=trace_id,
        )
        if self.task_queue is None:
            return retried
        try:
            self.task_queue.enqueue(retried.id, trace_id=trace_id)
        except RuntimeError as exc:
            failed = self._mark_enqueue_failed(retried, str(exc), trace_id=trace_id)
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "service_unavailable",
                f"Worker 投递失败: {failed.error_message}",
            ) from exc
        return self.job_repository.get_document_job(job.id) or retried

    def clone_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        reason: str | None,
        config_strategy: str,
        document_language: str | None = None,
        template_version_id: str | None = None,
        term_version_id: str | None = None,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
        debug_full_text: bool | None = None,
        trace_id: str | None = None,
    ) -> DocumentJobRecord:
        """把源任务复制为一个新 document_job；不修改源任务，也不复用 retry 语义。"""

        source_job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(source_job)
        source_file = self._get_source_file_for_clone(source_job)
        explicit_values = {
            "template_version_id": template_version_id,
            "term_version_id": term_version_id,
            "term_rule_set_id": term_rule_set_id,
            "term_rule_set_version": term_rule_set_version,
            "translation_term_set_id": translation_term_set_id,
            "translation_term_version": translation_term_version,
            "translation_profile_id": translation_profile_id,
            "translation_profile_version": translation_profile_version,
        }
        if config_strategy != "select_published_versions" and any(
            self._normalize_optional_text(value) for value in explicit_values.values()
        ):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "只有 select_published_versions 支持显式资源版本。")
        if config_strategy == "select_published_versions":
            self._ensure_resource_selection_allowed(user=user, **explicit_values)
        elif config_strategy not in {"keep_source_snapshot", "use_current_defaults"}:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "config_strategy 非法。")
        requested_debug_full_text = bool(debug_full_text)
        inherited_debug_full_text = (
            config_strategy == "keep_source_snapshot"
            and debug_full_text is None
            and source_job.debug_full_text_enabled
        )
        self._ensure_debug_full_text_allowed(user, requested_debug_full_text or inherited_debug_full_text)
        self._ensure_direct_translation_selection_absent(
            source_job.mode,
            term_version_id=term_version_id,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            debug_full_text=requested_debug_full_text,
        )

        now = utc_now()
        new_job_id = f"docjob_{uuid4().hex[:12]}"
        normalized_document_language = document_language or source_job.document_language
        self._ensure_document_language_allowed(source_job.mode, normalized_document_language)
        clone_config = self._resolve_clone_config(
            source_job,
            source_file,
            new_job_id=new_job_id,
            config_strategy=config_strategy,
            document_language=normalized_document_language,
            template_version_id=template_version_id,
            term_version_id=term_version_id,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
            debug_full_text=debug_full_text,
            reason=reason,
        )
        cloned = DocumentJobRecord(
            id=new_job_id,
            tenant_id=source_job.tenant_id,
            company_id=source_job.company_id,
            created_by=user.id,
            source_file_id=source_file.id,
            source_job_id=source_job.id,
            mode=source_job.mode,
            document_language=normalized_document_language,
            status="pending",
            stage="uploaded",
            progress=0,
            template_version_id=clone_config["template_version_id"],
            term_version_id=clone_config["term_version_id"],
            debug_full_text_enabled=clone_config["debug_full_text_enabled"],
            timeout_at=now + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
            request_snapshot=clone_config["request_snapshot"],
            created_at=now,
            updated_at=now,
        )
        self.job_repository.create_document_job(cloned)
        self.record_event(
            cloned,
            event_type="job_cloned",
            stage="uploaded",
            level="info",
            message="文档任务已重新发起为新任务。",
            payload={
                "source_job_id": source_job.id,
                "source_file_id": source_file.id,
                "config_strategy": config_strategy,
                "reason": self._normalize_optional_text(reason),
            },
            trace_id=trace_id,
        )
        if self.task_queue is None:
            return cloned
        return self._enqueue_created_job(cloned, trace_id=trace_id)

    def archive_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """归档终态 document_job，仅隐藏列表记录，不删除文件或事件。"""

        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if job.archived_at is not None:
            return job
        if job.status not in ARCHIVABLE_DOCUMENT_JOB_STATUSES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 succeeded、failed、canceled 终态任务允许归档。")
        now = utc_now()
        archived = self.job_repository.update_document_job(
            job.id,
            archived_at=now,
            archived_by=user.id,
            updated_at=now,
        )
        self.record_event(
            archived,
            event_type="job_archived",
            stage=archived.stage,
            level="info",
            message="文档任务已归档并从默认列表隐藏。",
            payload={"archived_by": user.id, "status": archived.status},
            trace_id=trace_id,
        )
        return archived

    def unarchive_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """恢复误归档 document_job；只更新归档元数据，不触碰文件或状态。"""

        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if job.archived_at is None:
            return job
        now = utc_now()
        restored = self.job_repository.update_document_job(
            job.id,
            archived_at=None,
            archived_by=None,
            updated_at=now,
        )
        self.record_event(
            restored,
            event_type="job_unarchived",
            stage=restored.stage,
            level="info",
            message="文档任务已取消归档并恢复到默认列表。",
            payload={"restored_by": user.id, "status": restored.status},
            trace_id=trace_id,
        )
        return restored

    def preview_delete_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> DocumentJobDeletePlan:
        """构建 Admin-only 任务删除计划；不修改任务、文件、事件或审计。"""

        job = self.get_job(job_id, user=user)
        self._ensure_delete_allowed(job, user=user)
        return self._build_delete_plan(job, action_mode="delete_preview")

    def delete_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        reason: str | None,
        confirmation: str | None,
        preview_hash: str,
        trace_id: str | None,
    ) -> DocumentJobDeletePlan:
        """按预览 hash 执行 Admin-only 任务删除，保留任务 metadata 和审计证据。"""

        job = self.get_job(job_id, user=user)
        self._ensure_delete_allowed(job, user=user)
        normalized_reason = self._normalize_optional_text(reason) or DEFAULT_DOCUMENT_JOB_DELETE_REASON
        if confirmation is not None:
            expected_confirmation = self._delete_confirmation_phrase(job)
            if confirmation != expected_confirmation:
                raise ApiError(
                    status.HTTP_400_BAD_REQUEST,
                    "invalid_request",
                    f"confirmation 必须为 {expected_confirmation}。",
                )
        preview = self._build_delete_plan(job, action_mode="delete_preview")
        if preview.preview_hash != preview_hash:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "删除预览已过期，请重新预览后再执行。")

        delete_file_ids = [item.file_id for item in preview.files if item.action == "delete"]
        executed_files = preview.files
        if delete_file_ids:
            if self.file_upload_service is None:
                raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", "文件清理服务不可用，无法删除任务文件。")
            physical_delete = self.file_upload_service.execute_document_job_physical_delete(delete_file_ids)
            physical_items = {item.file_id: item for item in physical_delete.items}
            executed_files = [
                self._delete_plan_file_from_physical_item(physical_items[item.file_id], action="delete")
                if item.file_id in physical_items
                else item
                for item in preview.files
            ]

        now = utc_now()
        deleted = self.job_repository.update_document_job(
            job.id,
            deleted_at=now,
            deleted_by=user.id,
            delete_reason=normalized_reason,
            updated_at=now,
        )
        self.record_event(
            deleted,
            event_type="job_deleted",
            stage=deleted.stage,
            level="info",
            message="文档任务已删除，任务 metadata、事件和审计证据已保留。",
            payload={
                "deleted_by": user.id,
                "delete_reason_length": len(normalized_reason),
                "files": self._delete_plan_totals(executed_files),
            },
            trace_id=trace_id,
        )
        return self._build_delete_plan(
            deleted,
            action_mode="delete_execute",
            files=executed_files,
            physical_delete_executed=bool(delete_file_ids),
            metadata_mutated=True,
            audit_events_written=True,
            preview_hash=preview.preview_hash,
        )

    def cancel_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """把未终态 document_job 标记为 canceled，保留所有文件和事件。"""

        job = self.get_job(job_id, user=user)
        self._ensure_job_not_deleted(job)
        if job.archived_at is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "已归档文档任务不允许取消。")
        if job.status not in CANCELABLE_DOCUMENT_JOB_STATUSES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 pending、queued、running 任务允许取消。")
        now = utc_now()
        canceled = self.job_repository.update_document_job_if_current(
            job.id,
            allowed_statuses=CANCELABLE_DOCUMENT_JOB_STATUSES,
            allowed_stages={"uploaded", "parsing", "parsed", "ir_converting", "rendering", "uploading"},
            expected_retry_count=job.retry_count,
            status="canceled",
            stage="canceled",
            canceled_at=now,
            updated_at=now,
        )
        if canceled is None:
            latest = self.job_repository.get_document_job(job.id) or job
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"任务状态已变化，无法取消: status={latest.status} stage={latest.stage}",
            )
        self.record_event(
            canceled,
            event_type="job_canceled",
            stage="canceled",
            level="info",
            message="文档任务已取消，文件和事件记录已保留。",
            payload={
                "canceled_by": user.id,
                "previous_status": job.status,
                "previous_stage": job.stage,
            },
            trace_id=trace_id,
        )
        return canceled

    def record_download_authorized(
        self,
        job: DocumentJobRecord,
        file: DocumentFileRecord,
        *,
        expires_at: str,
        trace_id: str | None,
    ) -> None:
        """记录结果下载授权事件，不写入长期 URL。"""

        self.record_event(
            job,
            event_type="download_authorized",
            stage=job.stage,
            level="info",
            message="任务文件下载链接已授权。",
            payload={"file_id": file.id, "file_type": file.file_type, "expires_at": expires_at},
            trace_id=trace_id,
        )

    def record_event(
        self,
        job: DocumentJobRecord,
        *,
        event_type: DocumentJobEventType,
        stage: DocumentJobStage,
        level: DocumentJobEventLevel,
        message: str,
        payload: dict,
        trace_id: str | None,
        duration_ms: int | None = None,
    ) -> DocumentJobEventRecord:
        """写入 document_job 事件；调用方负责保证 payload 不包含敏感全文。"""

        event = DocumentJobEventRecord(
            id=f"event_{uuid4().hex[:12]}",
            tenant_id=job.tenant_id,
            company_id=job.company_id,
            job_id=job.id,
            created_by=job.created_by,
            stage=stage,
            level=level,
            event_type=event_type,
            message=message,
            payload=payload,
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        self.event_repository.append_document_job_event(job.id, event)
        return event

    def _enqueue_created_job(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        queued = self._mark_created_job_queued(job, trace_id=trace_id)
        try:
            self.task_queue.enqueue(queued.id, trace_id=trace_id)
        except RuntimeError as exc:
            failed = self._mark_enqueue_failed(queued, str(exc), trace_id=trace_id)
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "service_unavailable",
                f"Worker 投递失败: {failed.error_message}",
            ) from exc
        return self.job_repository.get_document_job(job.id) or queued

    def _mark_created_job_queued(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        now = utc_now()
        queued = self.job_repository.update_document_job(
            job.id,
            status="queued",
            stage="uploaded",
            progress=max(job.progress, 5),
            updated_at=now,
        )
        self.record_event(
            queued,
            event_type="stage_started",
            stage="uploaded",
            level="info",
            message="文档任务已投递 Worker。",
            payload={"worker_backend": self.settings.document_jobs_worker_backend},
            trace_id=trace_id,
        )
        return queued

    def _mark_enqueue_failed(
        self,
        job: DocumentJobRecord,
        error_message: str,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        now = utc_now()
        failed = self.job_repository.update_document_job(
            job.id,
            status="failed",
            stage="failed",
            failed_stage="uploaded",
            error_code="worker_enqueue_failed",
            error_message=error_message,
            completed_at=now,
            updated_at=now,
        )
        self.record_event(
            failed,
            event_type="stage_failed",
            stage="uploaded",
            level="error",
            message="Worker 投递失败。",
            payload={"error_code": "worker_enqueue_failed"},
            trace_id=trace_id,
        )
        return failed

    def _ensure_retry_allowed(self, job: DocumentJobRecord) -> None:
        reason = self._retry_disabled_reason(job)
        if reason is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", reason)

    def _is_retryable_failure(self, job: DocumentJobRecord) -> bool:
        if job.error_code in {"document_job_invalid_input"}:
            return False
        return True

    def _build_retry_patch(
        self,
        job: DocumentJobRecord,
        *,
        retry_count: int,
        now,
        use_latest_term_assets: bool,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        term_rule_department_id: str | None = None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
    ) -> dict:
        resume_status, resume_stage, resume_progress = self._retry_resume_state(job)
        patch = {
            "status": resume_status,
            "stage": resume_stage,
            "progress": resume_progress,
            "failed_stage": None,
            "error_code": None,
            "error_message": None,
            "retry_count": retry_count,
            "timeout_at": now + timedelta(seconds=self.settings.p0_document_job_timeout_seconds),
            "started_at": None,
            "completed_at": None,
            "updated_at": now,
        }
        next_request_snapshot = self._build_retry_request_snapshot(
            job,
            use_latest_term_assets=use_latest_term_assets,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
        )
        if next_request_snapshot is not None:
            patch["request_snapshot"] = next_request_snapshot
            selected_term_version = self._legacy_translation_term_version_id(
                job.mode,
                None if use_latest_term_assets else job.term_version_id,
                None if use_latest_term_assets else translation_term_version,
            )
            patch["term_version_id"] = self._resolve_term_version_id(job.mode, selected_term_version)
        if job.failed_stage == "parsing" and job.mineru_raw_result_file_id is None:
            patch["mineru_batch_id"] = None
            patch["mineru_data_id"] = None
            patch["mineru_callback_seed"] = None
        return patch

    def _retry_resume_state(self, job: DocumentJobRecord) -> tuple[str, str, int]:
        """Choose the earliest valid workflow stage that preserves completed artifacts."""

        if job.result_file_id is not None:
            return "running", "uploading", max(job.progress, 90)
        if job.document_ir_file_id is not None:
            return "running", "rendering", max(job.progress, 60)
        if job.mineru_raw_result_file_id is not None:
            return "running", "parsed", max(job.progress, 30)
        return ("queued", "uploaded", 5) if self.task_queue is not None else ("pending", "uploaded", 0)

    def _build_translation_qa_state(self, job: DocumentJobRecord) -> DocumentJobTranslationQaStateResponse:
        return DocumentJobTranslationQaStateResponse(
            status=job.translation_qa_status,
            issue_type=job.translation_qa_issue_type,
            note=job.translation_qa_note,
            reviewed_by=job.translation_qa_reviewed_by,
            reviewed_at=job.translation_qa_reviewed_at,
        )

    def _build_unavailable_translation_qa(
        self,
        job: DocumentJobRecord,
        qa: DocumentJobTranslationQaStateResponse,
        *,
        reason: str,
        artifacts: DocumentJobTranslationQaArtifactsResponse | None = None,
        ai_calls: list[DocumentJobTranslationQaAiCallResponse] | None = None,
        term_traces: list[DocumentJobTranslationQaTermTraceResponse] | None = None,
        source_reason: str | None = None,
    ) -> DocumentJobTranslationQaResponse:
        ai_call_items = ai_calls or []
        term_trace_items = term_traces or []
        return DocumentJobTranslationQaResponse(
            job_id=job.id,
            available=False,
            availability_reason=reason,
            qa=qa,
            artifacts=artifacts or DocumentJobTranslationQaArtifactsResponse(),
            summary=DocumentJobTranslationQaSummaryResponse(
                ai_call_count=len(ai_call_items),
                ai_call_statuses=dict(Counter(call.status or "unknown" for call in ai_call_items)),
                term_trace_count=len(term_trace_items),
                debug_full_text_enabled=job.debug_full_text_enabled,
                source_comparison_available=False,
                source_comparison_reason=source_reason,
            ),
            segments=[],
            term_traces=term_trace_items,
            ai_calls=ai_call_items,
        )

    def _ensure_file_reader_available(self) -> None:
        if self.file_upload_service is not None:
            return
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "service_unavailable",
            "翻译 QA 需要文件读取服务。",
        )

    def _uploaded_files_by_type(self, files: list[DocumentFileRecord], file_type: DocumentFileType) -> list[DocumentFileRecord]:
        return [
            file
            for file in files
            if file.file_type == file_type and file.status == "uploaded"
        ]

    def _select_document_ir_file(
        self,
        job: DocumentJobRecord,
        files: list[DocumentFileRecord],
    ) -> DocumentFileRecord | None:
        if job.document_ir_file_id:
            file = self.file_repository.get_document_file(job.document_ir_file_id)
            if file is not None and file.job_id == job.id and file.file_type == "document_ir" and file.status == "uploaded":
                return file
        candidates = self._uploaded_files_by_type(files, "document_ir")
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (item.created_at, item.id))[-1]

    def _build_translation_qa_artifacts(
        self,
        *,
        document_ir_file: DocumentFileRecord | None,
        ai_log_files: list[DocumentFileRecord],
        debug_archive_files: list[DocumentFileRecord],
    ) -> DocumentJobTranslationQaArtifactsResponse:
        latest_debug_archive = self._latest_file(debug_archive_files)
        now = utc_now()
        return DocumentJobTranslationQaArtifactsResponse(
            document_ir_file_id=document_ir_file.id if document_ir_file is not None else None,
            ai_call_log_file_ids=[file.id for file in ai_log_files],
            ai_debug_archive_file_ids=[file.id for file in debug_archive_files],
            ai_debug_archive_expires_at=latest_debug_archive.expires_at if latest_debug_archive is not None else None,
            ai_debug_archive_expired=(
                latest_debug_archive.expires_at is not None and latest_debug_archive.expires_at <= now
                if latest_debug_archive is not None
                else False
            ),
            ai_debug_archive_contains_full_text=bool(
                latest_debug_archive is not None
                and latest_debug_archive.metadata.get("contains_full_text") is True
            ),
        )

    def _latest_file(self, files: list[DocumentFileRecord]) -> DocumentFileRecord | None:
        if not files:
            return None
        return sorted(files, key=lambda item: (item.created_at, item.id))[-1]

    def _read_document_ir(self, file: DocumentFileRecord) -> DocumentIR | None:
        try:
            return DocumentIR.model_validate_json(self.file_upload_service.read_file_content(file))
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def _read_ai_call_log_summaries(
        self,
        files: list[DocumentFileRecord],
    ) -> tuple[list[DocumentJobTranslationQaAiCallResponse], list[DocumentJobTranslationQaTermTraceResponse]]:
        ai_calls: list[DocumentJobTranslationQaAiCallResponse] = []
        term_traces: list[DocumentJobTranslationQaTermTraceResponse] = []
        for file in files:
            payload = self._read_json_file(file)
            if payload is None:
                continue
            request_summary = self._read_record(payload.get("request"))
            error = self._read_record(payload.get("error"))
            ai_calls.append(
                DocumentJobTranslationQaAiCallResponse(
                    file_id=file.id,
                    call_id=self._read_string(payload.get("call_id")),
                    status=self._read_string(payload.get("status")),
                    provider=self._read_record(payload.get("provider")) or {},
                    language_pair=self._read_string(payload.get("language_pair")),
                    source_language=self._read_string(payload.get("source_language")),
                    target_language=self._read_string(payload.get("target_language")),
                    term_version_id=self._read_string(payload.get("term_version_id")),
                    term_snapshot_hash=self._read_string(payload.get("term_snapshot_hash")),
                    term_count=self._read_int(payload.get("term_count")),
                    item_count=self._read_int(request_summary.get("item_count") if request_summary else None),
                    char_count=self._read_int(request_summary.get("char_count") if request_summary else None),
                    duration_ms=self._read_optional_int(payload.get("duration_ms")),
                    created_at=self._read_string(payload.get("created_at")),
                    error_type=self._read_string(error.get("type") if error else None),
                    error_message=self._read_string(error.get("message") if error else None),
                )
            )
            for raw_trace in self._read_list(payload.get("glossary_trace")):
                trace = self._read_record(raw_trace)
                if trace is None:
                    continue
                term_traces.append(
                    DocumentJobTranslationQaTermTraceResponse(
                        segment_id=self._read_string(trace.get("segment_id")),
                        batch_id=self._read_string(trace.get("batch_id")),
                        translation_term_set_id=self._read_string(trace.get("translation_term_set_id")),
                        translation_term_version=self._read_string(trace.get("translation_term_version")),
                        source_term=self._read_string(trace.get("source_term")),
                        target_term=self._read_string(trace.get("target_term")),
                        match_start=self._read_optional_int(trace.get("match_start")),
                        match_end=self._read_optional_int(trace.get("match_end")),
                        context=self._read_record(trace.get("context")),
                        injected_to_glossary=bool(trace.get("injected_to_glossary")),
                        provider_trace_id=self._read_string(trace.get("provider_trace_id")),
                    )
                )
        return ai_calls, term_traces

    def _read_debug_archive_texts(
        self,
        files: list[DocumentFileRecord],
    ) -> tuple[dict[str, str], dict[str, str], str | None]:
        if not files:
            return {}, {}, "ai_debug_archive_missing"
        now = utc_now()
        available_files = [
            file
            for file in files
            if file.expires_at is None or file.expires_at > now
        ]
        if not available_files:
            return {}, {}, "ai_debug_archive_expired"
        source_texts: dict[str, str] = {}
        ai_translation_texts: dict[str, str] = {}
        for file in available_files:
            payload = self._read_json_file(file)
            if payload is None:
                continue
            prompt = self._read_record(payload.get("prompt")) or {}
            response = self._read_record(payload.get("response")) or {}
            source_texts.update(self._items_text_map(prompt.get("items")))
            ai_translation_texts.update(self._items_text_map(response.get("items")))
        if not source_texts and not ai_translation_texts:
            return {}, {}, "ai_debug_archive_no_text"
        return source_texts, ai_translation_texts, None

    def _read_json_file(self, file: DocumentFileRecord) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.file_upload_service.read_file_content(file).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _items_text_map(self, value: Any) -> dict[str, str]:
        result: dict[str, str] = {}
        for raw_item in self._read_list(value):
            item = self._read_record(raw_item)
            if item is None:
                continue
            item_id = self._read_string(item.get("id"))
            text = self._read_string(item.get("text"))
            if item_id is not None and text is not None:
                result[item_id] = text
        return result

    def _build_translation_qa_segments(
        self,
        document_ir: DocumentIR,
        *,
        source_texts: dict[str, str],
        ai_translation_texts: dict[str, str],
    ) -> list[DocumentJobTranslationQaSegmentResponse]:
        segments: list[DocumentJobTranslationQaSegmentResponse] = []
        for block in sorted(document_ir.blocks, key=lambda item: item.order):
            if self._normalize_optional_text(block.text):
                item_id = f"{block.id}.text"
                segments.append(
                    self._build_translation_qa_segment(
                        item_id=item_id,
                        block_id=block.id,
                        page_index=block.page_index,
                        order=block.order,
                        block_type=block.type,
                        field="text",
                        index=None,
                        final_text=block.text or "",
                        source_texts=source_texts,
                        ai_translation_texts=ai_translation_texts,
                    )
                )
            for index, text in enumerate(block.list_items or []):
                if not self._normalize_optional_text(text):
                    continue
                item_id = f"{block.id}.list_items.{index:04d}"
                segments.append(
                    self._build_translation_qa_segment(
                        item_id=item_id,
                        block_id=block.id,
                        page_index=block.page_index,
                        order=block.order,
                        block_type=block.type,
                        field="list_items",
                        index=index,
                        final_text=text,
                        source_texts=source_texts,
                        ai_translation_texts=ai_translation_texts,
                    )
                )
            for index, text in enumerate(self._extract_html_text_nodes(block.html)):
                if not self._normalize_optional_text(text):
                    continue
                item_id = f"{block.id}.html.{index:04d}"
                segments.append(
                    self._build_translation_qa_segment(
                        item_id=item_id,
                        block_id=block.id,
                        page_index=block.page_index,
                        order=block.order,
                        block_type=block.type,
                        field="html",
                        index=index,
                        final_text=text,
                        source_texts=source_texts,
                        ai_translation_texts=ai_translation_texts,
                    )
                )
        return segments

    def _build_translation_qa_segment(
        self,
        *,
        item_id: str,
        block_id: str,
        page_index: int | None,
        order: int,
        block_type: str,
        field: str,
        index: int | None,
        final_text: str,
        source_texts: dict[str, str],
        ai_translation_texts: dict[str, str],
    ) -> DocumentJobTranslationQaSegmentResponse:
        source_text = source_texts.get(item_id)
        ai_translation_text = ai_translation_texts.get(item_id)
        return DocumentJobTranslationQaSegmentResponse(
            id=item_id,
            block_id=block_id,
            page_index=page_index,
            order=order,
            block_type=block_type,
            field=field,
            index=index,
            source_text=source_text,
            ai_translation_text=ai_translation_text,
            final_text=final_text,
            source_available=source_text is not None or ai_translation_text is not None,
        )

    def _extract_html_text_nodes(self, html: str | None) -> list[str]:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        return [str(node).strip() for node in soup.find_all(string=True) if str(node).strip()]

    def _read_record(self, value: Any) -> dict[str, Any] | None:
        return value if isinstance(value, dict) else None

    def _read_list(self, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def _read_string(self, value: Any) -> str | None:
        return value if isinstance(value, str) else None

    def _read_int(self, value: Any) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    def _read_optional_int(self, value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def _get_source_file_for_create(self, file_id: str, user: AuthenticatedUser) -> DocumentFileRecord:
        source_file = self.file_repository.get_document_file(file_id)
        if source_file is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"源文件不存在: {file_id}")
        if source_file.file_type != "source_pdf":
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "document_job 只能使用 source_pdf 文件创建。")
        if source_file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源文件尚未完成上传。")
        if source_file.job_id is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源文件已绑定其他任务。")
        if source_file.tenant_id != user.tenant_id or source_file.company_id != user.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "无权限使用该源文件。")
        if user.role != "admin" and source_file.created_by != user.id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "operator 只能使用自己上传的源文件。")
        return source_file

    def _get_source_file_for_clone(self, job: DocumentJobRecord) -> DocumentFileRecord:
        source_file = self.file_repository.get_document_file(job.source_file_id)
        if source_file is None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源任务的 source_pdf 文件不存在，不能重新发起。")
        if source_file.file_type != "source_pdf":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源任务文件不是 source_pdf，不能重新发起。")
        if source_file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源 PDF 尚不可用，不能重新发起。")
        if source_file.tenant_id != job.tenant_id or source_file.company_id != job.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "源 PDF 与任务租户不匹配。")
        if source_file.expires_at is not None and source_file.expires_at <= utc_now():
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "源 PDF 已过期，不能重新发起。")
        return source_file

    def _get_completed_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        self._ensure_job_not_deleted(job)
        if job.status != "succeeded" or job.stage != "completed" or job.result_file_id is None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文档任务尚未成功完成，生成 Word 不可下载。")
        file = self.file_repository.get_document_file(job.result_file_id)
        if file is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"结果文件不存在: {job.result_file_id}")
        if file.job_id != job.id or file.file_type != "generated_word":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "结果文件与文档任务不匹配。")
        if file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "结果文件尚未完成上传。")
        return file

    def _get_downloadable_completed_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
        file = self._get_completed_result_file(job)
        self._ensure_file_not_expired(file)
        return file

    def _list_files_for_job(self, job: DocumentJobRecord) -> list[DocumentFileRecord]:
        files = [
            file
            for file in self.file_repository.list_document_files()
            if file.tenant_id == job.tenant_id
            and file.company_id == job.company_id
            and file.file_type in DOCUMENT_JOB_DOWNLOAD_FILE_TYPES
            and self._file_belongs_to_job(job, file)
            and self._is_current_downloadable_job_file(job, file)
        ]
        return sorted(
            files,
            key=lambda file: (
                DOCUMENT_JOB_FILE_TYPE_ORDER.get(file.file_type, 100),
                file.created_at,
                file.id,
            ),
        )

    def _get_downloadable_task_file(self, job: DocumentJobRecord, *, file_id: str) -> DocumentFileRecord:
        self._ensure_job_not_deleted(job)
        file = self.file_repository.get_document_file(file_id)
        if file is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文件不存在: {file_id}")
        if file.tenant_id != job.tenant_id or file.company_id != job.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载文件与文档任务不匹配。")
        if not self._file_belongs_to_job(job, file):
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载文件与文档任务不匹配。")
        if file.file_type not in DOCUMENT_JOB_DOWNLOAD_FILE_TYPES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "该文件类型不支持从任务详情下载。")
        if not self._is_current_downloadable_job_file(job, file):
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "该文件不属于当前任务重试轮次，不能从任务详情下载。")
        if file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文件尚未完成上传，不能下载。")
        self._ensure_file_not_expired(file)
        return file

    def _ensure_file_not_expired(self, file: DocumentFileRecord) -> None:
        if file.expires_at is not None and file.expires_at <= utc_now():
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文件已过期，不能下载。")

    def _file_belongs_to_job(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        return file.job_id == job.id or file.id == job.source_file_id

    def _is_current_downloadable_job_file(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        if file.file_type == "source_pdf":
            return file.id == job.source_file_id
        if file.file_type == "mineru_raw_result" and file.id == job.mineru_raw_result_file_id:
            return True
        if file.file_type == "document_ir":
            if file.id == job.document_ir_file_id:
                return True
            return job.document_ir_file_id is None and file.id == job.source_document_ir_file_id
        if file.file_type == "generated_word" and file.id == job.result_file_id:
            return True
        return self._file_matches_current_retry_count(job, file)

    def _file_matches_current_retry_count(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        retry_count = self._file_retry_count(file)
        if retry_count is None:
            return job.retry_count == 0
        return retry_count == job.retry_count

    @staticmethod
    def _file_retry_count(file: DocumentFileRecord) -> int | None:
        raw_value = (file.metadata or {}).get("retry_count")
        if isinstance(raw_value, bool):
            return None
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, str) and raw_value.isdigit():
            return int(raw_value)
        return None

    def _ensure_delete_allowed(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> None:
        if user.role != "admin":
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "只有 admin 可以删除文档任务。")
        self._ensure_job_not_deleted(job)
        if job.status not in DOCUMENT_JOB_DELETE_TERMINAL_STATUSES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有终态任务允许删除；处理中任务请先取消。")

    def _ensure_job_not_deleted(self, job: DocumentJobRecord) -> None:
        if job.deleted_at is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文档任务已删除。")

    def _build_delete_plan(
        self,
        job: DocumentJobRecord,
        *,
        action_mode: str,
        files: list[DocumentJobDeletePlanFile] | None = None,
        physical_delete_executed: bool = False,
        metadata_mutated: bool = False,
        audit_events_written: bool = False,
        preview_hash: str | None = None,
    ) -> DocumentJobDeletePlan:
        plan_files = files if files is not None else self._build_delete_plan_files(job)
        return DocumentJobDeletePlan(
            job=job,
            action_mode=action_mode,
            confirmation_phrase=self._delete_confirmation_phrase(job),
            preview_hash=preview_hash or self._delete_preview_hash(job, plan_files),
            totals=self._delete_plan_totals(plan_files),
            files=plan_files,
            safety={
                "physical_delete_executed": physical_delete_executed,
                "metadata_mutated": metadata_mutated,
                "audit_events_written": audit_events_written,
                "s3_delete_executed": False,
                "deleted_job_metadata_retained": True,
            },
        )

    def _build_delete_plan_files(self, job: DocumentJobRecord) -> list[DocumentJobDeletePlanFile]:
        return [self._build_delete_plan_file(job, file) for file in self._list_files_for_job(job)]

    def _build_delete_plan_file(self, job: DocumentJobRecord, file: DocumentFileRecord) -> DocumentJobDeletePlanFile:
        keep_reason = self._delete_keep_reason(job, file)
        if keep_reason is not None:
            return DocumentJobDeletePlanFile(
                file_id=file.id,
                file_type=file.file_type,
                storage_provider=file.storage_provider,
                status_before=file.status,
                status_after=file.status,
                size_bytes=file.size_bytes,
                action="keep",
                outcome="kept",
                reason=keep_reason,
                s3_delete_contract=self._delete_s3_contract_summary(file),
            )
        return DocumentJobDeletePlanFile(
            file_id=file.id,
            file_type=file.file_type,
            storage_provider=file.storage_provider,
            status_before=file.status,
            status_after=file.status,
            size_bytes=file.size_bytes,
            action="delete",
            outcome="deletable",
            reason="任务删除将清理该文件。",
        )

    def _delete_keep_reason(self, job: DocumentJobRecord, file: DocumentFileRecord) -> str | None:
        if file.status == "deleted":
            return "文件 metadata 已是 deleted。"
        if self._file_is_shared_with_other_job(job, file):
            return "文件仍被其他任务引用，已保留。"
        if file.status == "pending_upload":
            return "文件仍处于 pending_upload，未执行物理删除。"
        if file.storage_provider not in {"local_file", "local_object"}:
            return f"暂不支持物理删除 storage_provider={file.storage_provider}。"
        if not file.object_key.strip():
            return "文件缺少 object_key，不能物理删除。"
        return None

    def _file_is_shared_with_other_job(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        for other_job in self.job_repository.list_document_jobs():
            if other_job.id == job.id or other_job.deleted_at is not None:
                continue
            if self._file_belongs_to_job(other_job, file):
                return True
        return False

    def _delete_plan_file_from_physical_item(
        self,
        item: Any,
        *,
        action: str,
    ) -> DocumentJobDeletePlanFile:
        s3_contract = item.s3_delete_contract.to_dict() if item.s3_delete_contract is not None else None
        return DocumentJobDeletePlanFile(
            file_id=item.file_id,
            file_type=item.file_type,
            storage_provider=item.storage_provider,
            status_before=item.status_before,
            status_after=item.status_after,
            size_bytes=item.size_bytes,
            action=action,
            outcome=item.outcome,
            reason=item.reason,
            deleted=item.deleted,
            metadata_updated=item.metadata_updated,
            s3_delete_contract=s3_contract,
        )

    def _delete_s3_contract_summary(self, file: DocumentFileRecord) -> dict[str, Any] | None:
        if file.storage_provider != "s3":
            return None
        return {
            "contract_version": "s3-delete-fake-v1",
            "adapter_mode": "fake",
            "target_exact": bool(file.bucket.strip() and file.object_key.strip()),
            "expected_outcome": "fake_skipped",
            "safety": {
                "real_s3_delete_executed": False,
                "fake_s3_delete_executed": True,
                "metadata_mutated": False,
                "audit_events_written": False,
                "requires_future_real_adapter": True,
            },
        }

    def _delete_plan_totals(self, files: list[DocumentJobDeletePlanFile]) -> dict[str, int]:
        return {
            "files": len(files),
            "delete": sum(1 for item in files if item.action == "delete"),
            "keep": sum(1 for item in files if item.action == "keep"),
            "deleted": sum(1 for item in files if item.deleted),
            "skipped": sum(1 for item in files if item.outcome.startswith("skipped_") or item.outcome == "kept"),
            "failed": sum(1 for item in files if item.outcome == "failed"),
            "metadata_updated": sum(1 for item in files if item.metadata_updated),
        }

    def _delete_preview_hash(self, job: DocumentJobRecord, files: list[DocumentJobDeletePlanFile]) -> str:
        payload = {
            "job_id": job.id,
            "updated_at": job.updated_at.isoformat(),
            "confirmation_phrase": self._delete_confirmation_phrase(job),
            "files": [item.to_response_dict() for item in files],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _delete_confirmation_phrase(self, job: DocumentJobRecord) -> str:
        return f"DELETE {job.id}"

    def _ensure_visible(self, job: DocumentJobRecord, user: AuthenticatedUser) -> None:
        if self._is_visible(job, user):
            return
        raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "无权限访问该文档任务。")

    def _is_visible(self, job: DocumentJobRecord, user: AuthenticatedUser) -> bool:
        if job.tenant_id != user.tenant_id or job.company_id != user.company_id:
            return False
        if user.role == "admin":
            return True
        return job.created_by == user.id

    def _matches_document_job_query(self, job: DocumentJobRecord, q: str | None) -> bool:
        if q is None:
            return True
        needle = q.casefold()
        return any(needle in value.casefold() for value in self._document_job_search_values(job))

    def _matches_status_filter(
        self,
        job: DocumentJobRecord,
        *,
        status_filter: str | None,
        status_group: str | None,
    ) -> bool:
        if status_filter is not None:
            return job.status == status_filter
        if status_group is not None:
            return job.status in DOCUMENT_JOB_STATUS_GROUPS[status_group]
        return True

    def _matches_translation_qa_status(
        self,
        job: DocumentJobRecord,
        translation_qa_status: str | None,
    ) -> bool:
        """按任务级翻译 QA 状态筛选；direct 任务不参与 QA 工作台筛选。"""

        if translation_qa_status is None:
            return True
        if translation_qa_status == "all":
            return is_translation_document_job_mode(job.mode)
        return is_translation_document_job_mode(job.mode) and job.translation_qa_status == translation_qa_status

    def _count_translation_qa_statuses(self, jobs: list[DocumentJobRecord]) -> dict[str, int]:
        counts = Counter(job.translation_qa_status for job in jobs)
        return {qa_status: counts.get(qa_status, 0) for qa_status in get_args(DocumentJobTranslationQaStatus)}

    def _document_job_search_values(self, job: _DocumentJobSearchable) -> list[str]:
        source_file = job.request_snapshot.get("source_file")
        source_filename = None
        if isinstance(source_file, dict):
            raw_filename = source_file.get("original_filename")
            if isinstance(raw_filename, str):
                source_filename = raw_filename
        return [
            value
            for value in (
                job.id,
                job.source_file_id,
                source_filename,
                job.error_code,
                job.error_message,
            )
            if value
        ]

    def _matches_created_range(
        self,
        job: DocumentJobRecord,
        *,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> bool:
        if created_from is not None and job.created_at < created_from:
            return False
        if created_to is not None and job.created_at > created_to:
            return False
        return True

    def _document_job_sort_key(self, job: DocumentJobRecord, sort: str) -> tuple[datetime, str]:
        if sort.startswith("updated_at"):
            return job.updated_at, job.id
        return job.created_at, job.id

    def _available_action(
        self,
        disabled_reason: str | None,
        *,
        retryable: bool = False,
    ) -> DocumentJobAvailableActionResponse:
        return DocumentJobAvailableActionResponse(
            enabled=disabled_reason is None,
            disabled_reason=disabled_reason,
            retryable=retryable,
        )

    def _download_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.status != "succeeded":
            return "只有 succeeded 文档任务允许下载结果。"
        if job.result_file_id is None:
            return "任务结果文件尚未登记，不能下载。"
        return None

    def _retry_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "已归档文档任务不允许重试。"
        if job.status != "failed":
            return "只有 failed 文档任务允许重试。"
        if job.retry_count >= self.settings.p0_document_job_max_retries:
            return "文档任务重试次数已达上限。"
        if not self._is_retryable_failure(job):
            return f"该失败不可重试: {job.error_code or 'unknown'}"
        return None

    def _cancel_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "已归档文档任务不允许取消。"
        if job.status not in CANCELABLE_DOCUMENT_JOB_STATUSES:
            return "只有 pending、queued、running 任务允许取消。"
        return None

    def _archive_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is not None:
            return "任务已归档。"
        if job.status not in ARCHIVABLE_DOCUMENT_JOB_STATUSES:
            return "只有 succeeded、failed、canceled 终态任务允许归档。"
        return None

    def _unarchive_disabled_reason(self, job: DocumentJobRecord) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.archived_at is None:
            return "任务未归档。"
        return None

    def _clone_disabled_reason(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> str | None:
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if not self._is_visible(job, user):
            return "无权限访问该文档任务。"
        try:
            self._get_source_file_for_clone(job)
        except ApiError as exc:
            return exc.message
        return None

    def _delete_disabled_reason(self, job: DocumentJobRecord, *, user: AuthenticatedUser) -> str | None:
        if user.role != "admin":
            return "只有 admin 可以删除文档任务。"
        if job.deleted_at is not None:
            return "文档任务已删除。"
        if job.status not in DOCUMENT_JOB_DELETE_TERMINAL_STATUSES:
            return "只有终态任务允许删除；处理中任务请先取消。"
        return None

    def _build_request_snapshot(
        self,
        source_file: DocumentFileRecord,
        *,
        mode: DocumentJobMode,
        document_language: str,
        template_version_id: str,
        term_version_id: str | None,
        debug_full_text_enabled: bool,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
        resource_snapshot: dict | None = None,
    ) -> dict:
        return {
            "source_file": {
                "id": source_file.id,
                "object_key": source_file.object_key,
                "original_filename": source_file.original_filename,
                "mime_type": source_file.mime_type,
                "size_bytes": source_file.size_bytes,
                "checksum_sha256": source_file.checksum_sha256,
            },
            "mode": mode,
            "translation_mode": translation_mode_for_document_job_mode(mode),
            "document_language": document_language,
            "template_version_id": template_version_id,
            "term_version_id": term_version_id,
            "term_assets": {
                "term_rule_set_id": self._normalize_optional_text(term_rule_set_id),
                "term_rule_set_version": self._normalize_optional_text(term_rule_set_version),
                "translation_term_set_id": self._normalize_optional_text(translation_term_set_id),
                "translation_term_version": self._normalize_optional_text(translation_term_version),
            },
            "translation_profile": {
                "translation_profile_id": self._normalize_optional_text(translation_profile_id),
                "translation_profile_version": self._normalize_optional_text(translation_profile_version),
            },
            "resources": resource_snapshot,
            "debug_full_text_enabled": debug_full_text_enabled,
        }

    def _resolve_clone_config(
        self,
        source_job: DocumentJobRecord,
        source_file: DocumentFileRecord,
        *,
        new_job_id: str,
        config_strategy: str,
        document_language: str,
        template_version_id: str | None,
        term_version_id: str | None,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
        translation_profile_id: str | None,
        translation_profile_version: str | None,
        debug_full_text: bool | None,
        reason: str | None,
    ) -> dict[str, Any]:
        if config_strategy == "keep_source_snapshot":
            source_assets = self._read_snapshot_record(source_job.request_snapshot, "term_assets")
            source_profile = self._read_snapshot_record(source_job.request_snapshot, "translation_profile")
            resolved_debug = self._resolve_debug_full_text_enabled(
                source_job.mode,
                source_job.debug_full_text_enabled if debug_full_text is None else debug_full_text,
            )
            request_snapshot = self._build_request_snapshot(
                source_file,
                mode=source_job.mode,
                document_language=document_language,
                template_version_id=source_job.template_version_id,
                term_version_id=source_job.term_version_id,
                debug_full_text_enabled=resolved_debug,
                term_rule_set_id=self._read_snapshot_string(source_assets, "term_rule_set_id"),
                term_rule_set_version=self._read_snapshot_string(source_assets, "term_rule_set_version"),
                translation_term_set_id=self._read_snapshot_string(source_assets, "translation_term_set_id"),
                translation_term_version=self._read_snapshot_string(source_assets, "translation_term_version"),
                translation_profile_id=self._read_snapshot_string(source_profile, "translation_profile_id"),
                translation_profile_version=self._read_snapshot_string(source_profile, "translation_profile_version"),
                resource_snapshot=self._read_snapshot_record(source_job.request_snapshot, "resources"),
            )
            request_snapshot["clone"] = self._build_clone_snapshot(source_job, config_strategy, reason)
            return {
                "template_version_id": source_job.template_version_id,
                "term_version_id": source_job.term_version_id,
                "debug_full_text_enabled": resolved_debug,
                "request_snapshot": request_snapshot,
            }

        selected_template_version_id = template_version_id if config_strategy == "select_published_versions" else None
        selected_term_version_id = term_version_id if config_strategy == "select_published_versions" else None
        selected_term_rule_set_id = term_rule_set_id if config_strategy == "select_published_versions" else None
        selected_term_rule_set_version = term_rule_set_version if config_strategy == "select_published_versions" else None
        selected_translation_term_set_id = translation_term_set_id if config_strategy == "select_published_versions" else None
        selected_translation_term_version = translation_term_version if config_strategy == "select_published_versions" else None
        selected_translation_profile_id = translation_profile_id if config_strategy == "select_published_versions" else None
        selected_translation_profile_version = translation_profile_version if config_strategy == "select_published_versions" else None
        resolved_template_version_id = self._resolve_template_version_id(selected_template_version_id)
        resolved_term_version_id = self._resolve_term_version_id(
            source_job.mode,
            self._legacy_translation_term_version_id(
                source_job.mode,
                selected_term_version_id,
                selected_translation_term_version,
            ),
        )
        resolved_debug = self._resolve_debug_full_text_enabled(source_job.mode, bool(debug_full_text))
        request_snapshot = self._build_request_snapshot(
            source_file,
            mode=source_job.mode,
            document_language=document_language,
            template_version_id=resolved_template_version_id,
            term_version_id=resolved_term_version_id,
            debug_full_text_enabled=resolved_debug,
            term_rule_set_id=selected_term_rule_set_id,
            term_rule_set_version=selected_term_rule_set_version,
            translation_term_set_id=selected_translation_term_set_id,
            translation_term_version=selected_translation_term_version,
            translation_profile_id=selected_translation_profile_id,
            translation_profile_version=selected_translation_profile_version,
            resource_snapshot=self._build_resource_snapshot(
                job_id=new_job_id,
                mode=source_job.mode,
                document_language=document_language,
                template_version_id=resolved_template_version_id if self._normalize_optional_text(selected_template_version_id) else None,
                term_rule_set_id=selected_term_rule_set_id,
                term_rule_set_version=selected_term_rule_set_version,
                translation_term_set_id=selected_translation_term_set_id,
                translation_term_version=selected_translation_term_version,
                translation_profile_id=selected_translation_profile_id,
                translation_profile_version=selected_translation_profile_version,
            ),
        )
        request_snapshot["clone"] = self._build_clone_snapshot(source_job, config_strategy, reason)
        return {
            "template_version_id": resolved_template_version_id,
            "term_version_id": resolved_term_version_id,
            "debug_full_text_enabled": resolved_debug,
            "request_snapshot": request_snapshot,
        }

    def _build_clone_snapshot(self, source_job: DocumentJobRecord, config_strategy: str, reason: str | None) -> dict[str, Any]:
        return {
            "source_job_id": source_job.id,
            "config_strategy": config_strategy,
            "reason": self._normalize_optional_text(reason),
            "source_status": source_job.status,
            "source_stage": source_job.stage,
            "source_template_version_id": source_job.template_version_id,
            "source_term_version_id": source_job.term_version_id,
        }

    def _read_snapshot_record(self, snapshot: dict, key: str) -> dict[str, Any] | None:
        value = snapshot.get(key)
        return value if isinstance(value, dict) else None

    def _read_snapshot_string(self, snapshot: dict[str, Any] | None, key: str) -> str | None:
        if snapshot is None:
            return None
        value = snapshot.get(key)
        return value if isinstance(value, str) else None

    def _build_retry_request_snapshot(
        self,
        job: DocumentJobRecord,
        *,
        use_latest_term_assets: bool,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
    ) -> dict | None:
        has_selection = any(
            self._normalize_optional_text(value)
            for value in (term_rule_set_id, term_rule_set_version, translation_term_set_id, translation_term_version)
        )
        if not use_latest_term_assets and not has_selection:
            return None
        snapshot = dict(job.request_snapshot)
        resource_snapshot = self._build_resource_snapshot(
            job_id=job.id,
            mode=job.mode,
            document_language=job.document_language,
            template_version_id=None,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=None if use_latest_term_assets else term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=None if use_latest_term_assets else translation_term_version,
            translation_profile_id=None,
            translation_profile_version=None,
        )
        resource_snapshot = self._preserve_retry_template_and_profile(job.request_snapshot, resource_snapshot)
        snapshot["term_assets"] = {
            "use_latest_term_assets": use_latest_term_assets,
            "term_rule_set_id": self._normalize_optional_text(term_rule_set_id),
            "term_rule_set_version": self._normalize_optional_text(term_rule_set_version),
            "translation_term_set_id": self._normalize_optional_text(translation_term_set_id),
            "translation_term_version": self._normalize_optional_text(translation_term_version),
        }
        snapshot["resources"] = resource_snapshot
        return snapshot

    def _build_resource_snapshot(
        self,
        *,
        job_id: str,
        mode: DocumentJobMode,
        document_language: str,
        template_version_id: str | None,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
        translation_profile_id: str | None,
        translation_profile_version: str | None,
        term_rule_department_id: str | None = None,
        allow_draft_template: bool = False,
    ) -> dict | None:
        if self.job_resource_snapshot_service is None:
            return None
        has_explicit_selection = any(
            self._normalize_optional_text(value)
            for value in (
                template_version_id,
                term_rule_set_id,
                term_rule_set_version,
                translation_term_set_id,
                translation_term_version,
                translation_profile_id,
                translation_profile_version,
            )
        )
        template_id, template_version = self._split_template_version_id(template_version_id)
        options = ConversionOptions(
            template_id=template_id,
            template_version=template_version,
            term_rule_set_id=self._normalize_optional_text(term_rule_set_id),
            term_rule_set_version=self._normalize_optional_text(term_rule_set_version),
            term_rule_department_id=self._normalize_optional_text(term_rule_department_id),
            translation_term_set_id=self._normalize_optional_text(translation_term_set_id),
            translation_term_version=self._normalize_optional_text(translation_term_version),
            translation_profile_id=self._normalize_optional_text(translation_profile_id),
            translation_profile_version=self._normalize_optional_text(translation_profile_version),
            translation_mode=translation_mode_for_document_job_mode(mode),
            document_language=document_language,
        )
        try:
            snapshot = self.job_resource_snapshot_service.build_snapshot(
                options=options,
                source_kind="source_pdf",
                job_id=job_id,
                allow_draft_template=allow_draft_template,
            )
        except JobResourceSnapshotError as exc:
            if not has_explicit_selection:
                return None
            raise ApiError(exc.status_code, exc.code, exc.message) from exc
        if snapshot is None:
            return None
        return snapshot.model_dump(mode="json")

    def _ensure_resource_selection_allowed(
        self,
        *,
        user: AuthenticatedUser,
        use_latest_term_assets: bool = False,
        template_version_id: str | None = None,
        term_version_id: str | None = None,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
    ) -> None:
        if user.role == "admin":
            return
        selected: list[str] = []
        for name, value in {
            "use_latest_term_assets": use_latest_term_assets,
            "template_version_id": template_version_id,
            "term_version_id": term_version_id,
            "term_rule_set_id": term_rule_set_id,
            "term_rule_set_version": term_rule_set_version,
            "translation_term_set_id": translation_term_set_id,
            "translation_term_version": translation_term_version,
            "translation_profile_id": translation_profile_id,
            "translation_profile_version": translation_profile_version,
        }.items():
            if isinstance(value, bool):
                if value:
                    selected.append(name)
                continue
            if self._normalize_optional_text(value):
                selected.append(name)
        if selected:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                f"operator 不能选择任务资源版本: {', '.join(selected)}。",
            )

    def _split_template_version_id(self, template_version_id: str | None) -> tuple[str | None, str | None]:
        normalized = self._normalize_optional_text(template_version_id)
        if normalized is None:
            return None, None
        template_id, separator, version = normalized.partition("@")
        if not separator:
            return normalized, None
        return template_id or None, version or None

    def _preserve_retry_template_and_profile(self, request_snapshot: dict, resource_snapshot: dict | None) -> dict | None:
        if resource_snapshot is None:
            return None
        previous_resources = request_snapshot.get("resources")
        if not isinstance(previous_resources, dict):
            return resource_snapshot
        preserved = dict(resource_snapshot)
        if isinstance(previous_resources.get("template"), dict):
            preserved["template"] = previous_resources["template"]
        if isinstance(previous_resources.get("translation_profile"), dict):
            preserved["translation_profile"] = previous_resources["translation_profile"]
            for key in (
                "translation_prompt_id",
                "translation_prompt_content_hash",
            ):
                if key in previous_resources:
                    preserved[key] = previous_resources[key]
                else:
                    preserved.pop(key, None)
        return preserved

    def _snapshot_resource_id(self, request_snapshot: dict, key: str) -> str | None:
        resources = request_snapshot.get("resources")
        if not isinstance(resources, dict):
            return None
        resource = resources.get(key)
        if not isinstance(resource, dict):
            return None
        raw = resource.get("resource_id") or resource.get("set_id")
        return raw if isinstance(raw, str) else None

    def _snapshot_resource_version(self, request_snapshot: dict, key: str) -> str | None:
        resources = request_snapshot.get("resources")
        if not isinstance(resources, dict):
            return None
        resource = resources.get(key)
        if not isinstance(resource, dict):
            return None
        raw = resource.get("version")
        return raw if isinstance(raw, str) else None

    def _resolve_document_job_mode(
        self,
        *,
        mode: DocumentJobMode | None,
        translation_mode: TranslationMode | None,
    ) -> DocumentJobMode:
        if translation_mode is not None:
            try:
                translation_mode = normalize_translation_mode(translation_mode)
            except ValueError as exc:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        if mode is None and translation_mode is None:
            return "direct_pdf_to_word"
        if mode is None:
            try:
                return document_job_mode_for_translation_mode(translation_mode)
            except ValueError as exc:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        try:
            resolved_translation_mode = translation_mode_for_document_job_mode(mode)
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        if translation_mode is not None and translation_mode != resolved_translation_mode:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"translation_mode 与 mode 不一致: translation_mode={translation_mode} mode={mode}。",
            )
        return mode

    def _ensure_direct_translation_selection_absent(
        self,
        mode: DocumentJobMode,
        *,
        term_version_id: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
        debug_full_text: bool = False,
    ) -> None:
        """只校验新写入意图；历史 direct 快照的惰性字段不参与资源选择。"""

        if is_translation_document_job_mode(mode):
            return
        has_translation_selection = any(
            self._normalize_optional_text(value)
            for value in (
                term_version_id,
                translation_term_set_id,
                translation_term_version,
                translation_profile_id,
                translation_profile_version,
            )
        )
        if has_translation_selection or debug_full_text:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                "原文转换（direct）不能绑定翻译资源或开启翻译全文调试。",
            )

    def _ensure_document_language_allowed(self, mode: DocumentJobMode, document_language: str) -> None:
        spec = spec_for_document_job_mode(mode)
        if not spec.is_translation:
            return
        allowed = {"auto", spec.default_document_language}
        if document_language not in allowed:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                (
                    f"{spec.translation_mode} 只支持 "
                    f"document_language=auto 或 {spec.default_document_language}。"
                ),
            )

    def _legacy_translation_term_version_id(
        self,
        mode: DocumentJobMode,
        term_version_id: str | None,
        translation_term_version: str | None,
    ) -> str | None:
        if not is_translation_document_job_mode(mode):
            return term_version_id
        normalized_translation_term_version = self._normalize_optional_text(translation_term_version)
        if normalized_translation_term_version is None:
            return term_version_id
        if "@" in normalized_translation_term_version:
            return normalized_translation_term_version
        spec = spec_for_document_job_mode(mode)
        return f"{spec.language_pair}@{normalized_translation_term_version}"

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _resolve_template_version_id(self, template_version_id: str | None, *, allow_draft: bool = False) -> str:
        if self.template_read_service is None:
            return template_version_id or self.settings.default_template_id
        try:
            return self.template_read_service.resolve_template_version(
                template_version_id,
                allow_draft=allow_draft,
            ).template_version_id
        except FileNotFoundError as exc:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", str(exc)) from exc
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc

    def _resolve_term_version_id(self, mode: DocumentJobMode, term_version_id: str | None) -> str | None:
        """direct 在调用术语服务前返回，历史字段不能触发翻译资源加载。"""

        language_pair = spec_for_document_job_mode(mode).language_pair
        if language_pair is None:
            return None
        if self.term_version_service is None:
            return term_version_id
        try:
            snapshot = self.term_version_service.resolve_for_job(term_version_id, language_pair=language_pair)
        except FileNotFoundError as exc:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", str(exc)) from exc
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        return snapshot.term_version_id if snapshot is not None else None

    def _resolve_debug_full_text_enabled(self, mode: DocumentJobMode, debug_full_text: bool) -> bool:
        if not debug_full_text:
            return False
        if not is_translation_document_job_mode(mode):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "debug_full_text 仅支持翻译任务。")
        if not self.settings.translation_debug_archive_enabled:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                "TRANSLATION_DEBUG_ARCHIVE_ENABLED 未开启，不能保存翻译全文调试归档。",
            )
        return True

    def _ensure_debug_full_text_allowed(self, user: AuthenticatedUser, debug_full_text: bool) -> None:
        if debug_full_text and user.role != "admin":
            raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "只有 admin 可以开启翻译全文调试归档。")
