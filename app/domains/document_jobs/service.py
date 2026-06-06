from __future__ import annotations

# File: app/domains/document_jobs/service.py
# Purpose: 创建、投递、查询 document_jobs 并记录任务事件。

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, get_args
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
    DocumentJobTranslationQaIssueType,
    DocumentJobTranslationQaStatus,
)
from app.domains.document_jobs.schemas import (
    DocumentJobTranslationQaAiCallResponse,
    DocumentJobTranslationQaArtifactsResponse,
    DocumentJobTranslationQaResponse,
    DocumentJobTranslationQaSegmentResponse,
    DocumentJobTranslationQaStateResponse,
    DocumentJobTranslationQaSummaryResponse,
    DocumentJobTranslationQaTermTraceResponse,
)
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord, DocumentFileType
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import ConversionOptions, utc_now
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
)
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.services.document_ir.models import DocumentIR
from app.services.auth.models import AuthenticatedUser


ARCHIVABLE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = {"succeeded", "failed", "canceled"}
CANCELABLE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = {"pending", "queued", "running"}
DOCUMENT_JOB_LIST_SORTS = {"created_at_desc", "created_at_asc", "updated_at_desc", "updated_at_asc"}
DOCUMENT_JOB_DOWNLOAD_FILE_TYPES: set[DocumentFileType] = {
    "source_pdf",
    "mineru_raw_result",
    "document_ir",
    "image_asset",
    "generated_word",
    "ai_call_log",
    "ai_debug_archive",
}
DOCUMENT_JOB_FILE_TYPE_ORDER = {
    "source_pdf": 0,
    "generated_word": 10,
    "mineru_raw_result": 20,
    "document_ir": 30,
    "image_asset": 40,
    "ai_call_log": 50,
    "ai_debug_archive": 60,
}


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
        self.file_upload_service = file_upload_service

    def create_job(
        self,
        *,
        user: AuthenticatedUser,
        source_file_id: str,
        mode: DocumentJobMode,
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
        self._ensure_resource_selection_allowed(
            user=user,
            template_version_id=template_version_id,
            term_version_id=term_version_id,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
            translation_profile_id=translation_profile_id,
            translation_profile_version=translation_profile_version,
        )
        normalized_template_version_id = self._resolve_template_version_id(template_version_id)
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
                translation_term_set_id=translation_term_set_id,
                translation_term_version=translation_term_version,
                translation_profile_id=translation_profile_id,
                translation_profile_version=translation_profile_version,
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
        translation_qa_status: str | None = None,
        q: str | None = None,
        sort: str = "created_at_desc",
        include_archived: bool = False,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> tuple[list[DocumentJobRecord], int, dict[str, int]]:
        """返回当前用户可见的 document_jobs 分页列表。"""

        if status_filter is not None and status_filter not in get_args(DocumentJobStatus):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 查询参数非法。")
        if translation_qa_status is not None and translation_qa_status not in get_args(DocumentJobTranslationQaStatus):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "translation_qa_status 查询参数非法。")
        if sort not in DOCUMENT_JOB_LIST_SORTS:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "sort 查询参数非法。")
        if created_from is not None and created_to is not None and created_from > created_to:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "created_from 不能晚于 created_to。")
        normalized_q = self._normalize_optional_text(q)
        visible_jobs = [
            job
            for job in self.job_repository.list_document_jobs()
            if self._is_visible(job, user) and (include_archived or job.archived_at is None)
        ]
        summary = dict(Counter(job.status for job in visible_jobs))
        filtered_jobs = [
            job
            for job in visible_jobs
            if (status_filter is None or job.status == status_filter)
            and self._matches_translation_qa_status(job, translation_qa_status)
            and self._matches_document_job_query(job, normalized_q)
            and self._matches_created_range(job, created_from=created_from, created_to=created_to)
        ]
        filtered_jobs.sort(key=lambda job: self._document_job_sort_key(job, sort), reverse=sort.endswith("_desc"))
        start = (page - 1) * page_size
        return filtered_jobs[start:start + page_size], len(filtered_jobs), summary

    def list_events(self, job_id: str, *, user: AuthenticatedUser) -> list[DocumentJobEventRecord]:
        """先按任务权限校验，再返回事件列表。"""

        self.get_job(job_id, user=user)
        return self.event_repository.list_document_job_events(job_id)

    def list_files(self, job_id: str, *, user: AuthenticatedUser) -> list[DocumentFileRecord]:
        """先按任务权限校验，再返回任务上下文内可展示的文件元数据。"""

        job = self.get_job(job_id, user=user)
        return self._list_files_for_job(job)

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
        if job.mode != "en2zh_pdf_to_word":
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
        if job.mode != "en2zh_pdf_to_word":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "翻译 QA 仅支持 en2zh_pdf_to_word 任务。")
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
        return job, self._get_completed_result_file(job)

    def get_file_for_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        file_id: str | None,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """按可见任务签发文件下载前，校验文件归属、状态、过期和类型。"""

        job = self.get_job(job_id, user=user)
        if file_id is None:
            return job, self._get_completed_result_file(job)
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
        file = self._get_completed_result_file(job)
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
            stage="uploaded",
            level="info",
            message="文档任务已请求重试。",
            payload={
                "retry_count": retry_count,
                "reason": self._normalize_optional_text(reason),
                "previous_error_code": job.error_code,
                "previous_failed_stage": job.failed_stage,
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

    def archive_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """归档终态 document_job，仅隐藏列表记录，不删除文件或事件。"""

        job = self.get_job(job_id, user=user)
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

    def cancel_job(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """把未终态 document_job 标记为 canceled，保留所有文件和事件。"""

        job = self.get_job(job_id, user=user)
        if job.archived_at is not None:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "已归档文档任务不允许取消。")
        if job.status not in CANCELABLE_DOCUMENT_JOB_STATUSES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 pending、queued、running 任务允许取消。")
        now = utc_now()
        canceled = self.job_repository.update_document_job(
            job.id,
            status="canceled",
            stage="canceled",
            canceled_at=now,
            updated_at=now,
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
        if job.status != "failed":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 failed 文档任务允许重试。")
        if job.retry_count >= self.settings.p0_document_job_max_retries:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文档任务重试次数已达上限。")
        if not self._is_retryable_failure(job):
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"该失败不可重试: {job.error_code or 'unknown'}",
            )

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
        translation_term_set_id: str | None,
        translation_term_version: str | None,
    ) -> dict:
        patch = {
            "status": "queued" if self.task_queue is not None else "pending",
            "stage": "uploaded",
            "progress": 5 if self.task_queue is not None else 0,
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
        return DocumentJobTranslationQaArtifactsResponse(
            document_ir_file_id=document_ir_file.id if document_ir_file is not None else None,
            ai_call_log_file_ids=[file.id for file in ai_log_files],
            ai_debug_archive_file_ids=[file.id for file in debug_archive_files],
        )

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

    def _get_completed_result_file(self, job: DocumentJobRecord) -> DocumentFileRecord:
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

    def _list_files_for_job(self, job: DocumentJobRecord) -> list[DocumentFileRecord]:
        files = [
            file
            for file in self.file_repository.list_document_files()
            if file.tenant_id == job.tenant_id
            and file.company_id == job.company_id
            and file.file_type in DOCUMENT_JOB_DOWNLOAD_FILE_TYPES
            and self._file_belongs_to_job(job, file)
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
        file = self.file_repository.get_document_file(file_id)
        if file is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"文件不存在: {file_id}")
        if file.tenant_id != job.tenant_id or file.company_id != job.company_id:
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载文件与文档任务不匹配。")
        if not self._file_belongs_to_job(job, file):
            raise ApiError(status.HTTP_403_FORBIDDEN, "forbidden", "下载文件与文档任务不匹配。")
        if file.file_type not in DOCUMENT_JOB_DOWNLOAD_FILE_TYPES:
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "该文件类型不支持从任务详情下载。")
        if file.status != "uploaded":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文件尚未完成上传，不能下载。")
        if file.expires_at is not None and file.expires_at <= utc_now():
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "文件已过期，不能下载。")
        return file

    def _file_belongs_to_job(self, job: DocumentJobRecord, file: DocumentFileRecord) -> bool:
        return file.job_id == job.id or file.id == job.source_file_id

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

    def _matches_translation_qa_status(
        self,
        job: DocumentJobRecord,
        translation_qa_status: str | None,
    ) -> bool:
        """按任务级翻译 QA 状态筛选；direct 任务不参与 QA 工作台筛选。"""

        if translation_qa_status is None:
            return True
        return job.mode == "en2zh_pdf_to_word" and job.translation_qa_status == translation_qa_status

    def _document_job_search_values(self, job: DocumentJobRecord) -> list[str]:
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
            translation_term_set_id=self._normalize_optional_text(translation_term_set_id),
            translation_term_version=self._normalize_optional_text(translation_term_version),
            translation_profile_id=self._normalize_optional_text(translation_profile_id),
            translation_profile_version=self._normalize_optional_text(translation_profile_version),
            translation_mode="en2zh" if mode == "en2zh_pdf_to_word" else "direct",
            document_language=document_language,
        )
        try:
            snapshot = self.job_resource_snapshot_service.build_snapshot(
                options=options,
                source_kind="source_pdf",
                job_id=job_id,
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

    def _legacy_translation_term_version_id(
        self,
        mode: DocumentJobMode,
        term_version_id: str | None,
        translation_term_version: str | None,
    ) -> str | None:
        if mode != "en2zh_pdf_to_word":
            return term_version_id
        normalized_translation_term_version = self._normalize_optional_text(translation_term_version)
        if normalized_translation_term_version is None:
            return term_version_id
        if "@" in normalized_translation_term_version:
            return normalized_translation_term_version
        return f"en2zh@{normalized_translation_term_version}"

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _resolve_template_version_id(self, template_version_id: str | None) -> str:
        if self.template_read_service is None:
            return template_version_id or self.settings.default_template_id
        try:
            return self.template_read_service.resolve_template_version(template_version_id).template_version_id
        except FileNotFoundError as exc:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", str(exc)) from exc
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc

    def _resolve_term_version_id(self, mode: DocumentJobMode, term_version_id: str | None) -> str | None:
        if self.term_version_service is None:
            return term_version_id
        language_pair = "en2zh" if mode == "en2zh_pdf_to_word" else None
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
        if mode != "en2zh_pdf_to_word":
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "debug_full_text 仅支持 en2zh_pdf_to_word。")
        if not self.settings.translation_debug_archive_enabled:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                "TRANSLATION_DEBUG_ARCHIVE_ENABLED 未开启，不能保存翻译全文调试归档。",
            )
        return True
