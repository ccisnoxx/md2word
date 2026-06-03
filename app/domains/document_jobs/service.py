from __future__ import annotations

# app/domains/document_jobs/service.py: 创建、投递、查询 document_jobs 并记录任务事件。

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, get_args
from uuid import uuid4

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
)
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import ConversionOptions, utc_now
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
)
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.services.auth.models import AuthenticatedUser


ARCHIVABLE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = {"succeeded", "failed", "canceled"}
CANCELABLE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = {"pending", "queued", "running"}
DOCUMENT_JOB_LIST_SORTS = {"created_at_desc", "created_at_asc", "updated_at_desc", "updated_at_asc"}


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
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.file_repository = file_repository
        self.task_queue = task_queue
        self.template_read_service = template_read_service
        self.term_version_service = term_version_service
        self.job_resource_snapshot_service = job_resource_snapshot_service

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
        debug_full_text: bool,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """创建待处理 document_job，并在启用 Worker 后按 job_id 投递。"""

        source_file = self._get_source_file_for_create(source_file_id, user)
        self._ensure_term_asset_selection_allowed(
            user=user,
            use_latest_term_assets=False,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=translation_term_version,
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
            resource_snapshot=self._build_resource_snapshot(
                job_id=job_id,
                mode=mode,
                document_language=document_language,
                term_rule_set_id=term_rule_set_id,
                term_rule_set_version=term_rule_set_version,
                translation_term_set_id=translation_term_set_id,
                translation_term_version=translation_term_version,
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
        q: str | None = None,
        sort: str = "created_at_desc",
        include_archived: bool = False,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> tuple[list[DocumentJobRecord], int, dict[str, int]]:
        """返回当前用户可见的 document_jobs 分页列表。"""

        if status_filter is not None and status_filter not in get_args(DocumentJobStatus):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 查询参数非法。")
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

    def get_result_file_for_download(
        self,
        job_id: str,
        *,
        user: AuthenticatedUser,
    ) -> tuple[DocumentJobRecord, DocumentFileRecord]:
        """校验任务权限和完成状态后返回生成 Word 文件。"""

        job = self.get_job(job_id, user=user)
        return job, self._get_completed_result_file(job)

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
        self._ensure_term_asset_selection_allowed(
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
            stage="completed",
            level="info",
            message="生成 Word 下载链接已授权。",
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
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=None if use_latest_term_assets else term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=None if use_latest_term_assets else translation_term_version,
        )
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
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
    ) -> dict | None:
        if self.job_resource_snapshot_service is None:
            return None
        has_explicit_selection = any(
            self._normalize_optional_text(value)
            for value in (term_rule_set_id, term_rule_set_version, translation_term_set_id, translation_term_version)
        )
        options = ConversionOptions(
            term_rule_set_id=self._normalize_optional_text(term_rule_set_id),
            term_rule_set_version=self._normalize_optional_text(term_rule_set_version),
            translation_term_set_id=self._normalize_optional_text(translation_term_set_id),
            translation_term_version=self._normalize_optional_text(translation_term_version),
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

    def _ensure_term_asset_selection_allowed(
        self,
        *,
        user: AuthenticatedUser,
        use_latest_term_assets: bool,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
    ) -> None:
        if user.role == "admin":
            return
        selected = [
            name
            for name, value in {
                "use_latest_term_assets": use_latest_term_assets,
                "term_rule_set_id": term_rule_set_id,
                "term_rule_set_version": term_rule_set_version,
                "translation_term_set_id": translation_term_set_id,
                "translation_term_version": translation_term_version,
            }.items()
            if value
        ]
        if selected:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                f"operator 不能选择术语资产历史版本: {', '.join(selected)}。",
            )

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
