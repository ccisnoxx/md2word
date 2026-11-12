from __future__ import annotations

# app/domains/document_jobs/use_cases/dispatcher.py: 新建/重试任务的 Worker 投递与投递失败收口。


from app.core.config import Settings
from app.core.errors import ApplicationError
from app.domains.document_jobs.execution import DocumentJobTaskQueueProtocol
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.use_cases.events import DocumentJobEventWriter
from app.domains.resources.models import utc_now


class DocumentJobDispatcher:
    """新建/重试任务的 Worker 投递与投递失败收口。"""

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        task_queue: DocumentJobTaskQueueProtocol | None,
        events: DocumentJobEventWriter,
    ) -> None:
        self.settings = settings
        self.job_repository = job_repository
        self.task_queue = task_queue
        self.events = events

    def enqueue_created_job(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        queued = self.mark_created_job_queued(job, trace_id=trace_id)
        try:
            self.task_queue.enqueue(queued.id, trace_id=trace_id)
        except RuntimeError as exc:
            failed = self.mark_enqueue_failed(queued, str(exc), trace_id=trace_id)
            raise ApplicationError(
                "service_unavailable",
                f"Worker 投递失败: {failed.error_message}",
            ) from exc
        return self.job_repository.get_document_job(job.id) or queued

    def mark_created_job_queued(self, job: DocumentJobRecord, *, trace_id: str | None) -> DocumentJobRecord:
        now = utc_now()
        queued = self.job_repository.update_document_job_if_current(
            job.id, allowed_statuses={"pending"}, allowed_stages={"uploaded"},
            expected_retry_count=job.retry_count, require_no_prepared_result=True,
            status="queued",
            stage="uploaded",
            progress=max(job.progress, 5),
            updated_at=now,
        )
        if queued is None:
            return self.job_repository.get_document_job(job.id) or job
        self.events.record_event(
            queued,
            event_type="stage_started",
            stage="uploaded",
            level="info",
            message="文档任务已投递 Worker。",
            payload={"worker_backend": self.settings.document_jobs_worker_backend},
            trace_id=trace_id,
        )
        return queued

    def mark_enqueue_failed(
        self,
        job: DocumentJobRecord,
        error_message: str,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        now = utc_now()
        failed = self.job_repository.update_document_job_if_current(
            job.id, allowed_statuses={job.status}, allowed_stages={job.stage},
            expected_retry_count=job.retry_count, require_no_prepared_result=True,
            status="failed",
            stage="failed",
            failed_stage="uploaded",
            error_code="worker_enqueue_failed",
            error_message=error_message,
            completed_at=now,
            updated_at=now,
        )
        if failed is None:
            return self.job_repository.get_document_job(job.id) or job
        self.events.record_event(
            failed,
            event_type="stage_failed",
            stage="uploaded",
            level="error",
            message="Worker 投递失败。",
            payload={"error_code": "worker_enqueue_failed"},
            trace_id=trace_id,
        )
        return failed
