from __future__ import annotations

# app/domains/document_jobs/service.py: 创建、投递、查询 document_jobs 并记录任务事件。

from collections import Counter
from datetime import timedelta
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
from app.domains.jobs.models import utc_now
from app.domains.document_jobs.repository import (
    DocumentJobEventRepositoryProtocol,
    DocumentJobRepositoryProtocol,
)
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.services.auth.models import AuthenticatedUser


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
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.event_repository = event_repository
        self.file_repository = file_repository
        self.task_queue = task_queue
        self.template_read_service = template_read_service
        self.term_version_service = term_version_service

    def create_job(
        self,
        *,
        user: AuthenticatedUser,
        source_file_id: str,
        mode: DocumentJobMode,
        document_language: str,
        template_version_id: str | None,
        term_version_id: str | None,
        debug_full_text: bool,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """创建待处理 document_job，并在启用 Worker 后按 job_id 投递。"""

        source_file = self._get_source_file_for_create(source_file_id, user)
        normalized_template_version_id = self._resolve_template_version_id(template_version_id)
        normalized_term_version_id = self._resolve_term_version_id(mode, term_version_id)
        debug_full_text_enabled = self._resolve_debug_full_text_enabled(mode, debug_full_text)
        now = utc_now()
        job = DocumentJobRecord(
            id=f"docjob_{uuid4().hex[:12]}",
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
            request_snapshot=self._build_request_snapshot(
                source_file,
                mode=mode,
                document_language=document_language,
                template_version_id=normalized_template_version_id,
                term_version_id=normalized_term_version_id,
                debug_full_text_enabled=debug_full_text_enabled,
            ),
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
    ) -> tuple[list[DocumentJobRecord], int, dict[str, int]]:
        """返回当前用户可见的 document_jobs 分页列表。"""

        if status_filter is not None and status_filter not in get_args(DocumentJobStatus):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "status 查询参数非法。")
        visible_jobs = [job for job in self.job_repository.list_document_jobs() if self._is_visible(job, user)]
        summary = dict(Counter(job.status for job in visible_jobs))
        filtered_jobs = [
            job
            for job in visible_jobs
            if status_filter is None or job.status == status_filter
        ]
        filtered_jobs.sort(key=lambda job: (job.created_at, job.id), reverse=True)
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
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """对可重试失败任务按原 job_id 重新投递，保留既有中间产物用于幂等恢复。"""

        job = self.get_job(job_id, user=user)
        self._ensure_retry_allowed(job)
        now = utc_now()
        retry_count = job.retry_count + 1
        patch = self._build_retry_patch(job, retry_count=retry_count, now=now)
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
        if job.failed_stage == "parsing" and job.mineru_raw_result_file_id is None:
            patch["mineru_batch_id"] = None
            patch["mineru_data_id"] = None
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

    def _build_request_snapshot(
        self,
        source_file: DocumentFileRecord,
        *,
        mode: DocumentJobMode,
        document_language: str,
        template_version_id: str,
        term_version_id: str | None,
        debug_full_text_enabled: bool,
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
            "debug_full_text_enabled": debug_full_text_enabled,
        }

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
