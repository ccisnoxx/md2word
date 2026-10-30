from __future__ import annotations

# app/workers/document_tasks.py: document_jobs Celery task 定义。

from celery.signals import worker_ready

from app.domains.document_jobs.recovery import is_mineru_polling_job
from app.main import build_runtime
from app.workers.celery_app import celery_app


@celery_app.task(name="document_jobs.ping")
def ping() -> str:
    """Celery/Redis Worker 连通性测试任务。"""

    return "pong"


@celery_app.task(bind=True, name="document_jobs.run", acks_late=True, max_retries=None)
def run_document_job(_task, job_id: str, *, trace_id: str | None = None) -> dict | None:
    """单次推进任务；等待 MinerU 时延时续投，由绝对任务期限限制总时长。"""

    runtime = build_runtime()
    job = runtime.document_job_execution_service.execute_job(job_id, trace_id=trace_id)
    if job is None:
        return None
    if is_mineru_polling_job(runtime.settings, job):
        # broker 续投不增加业务 retry_count，也不在 Worker 槽位内等待。
        raise _task.retry(countdown=runtime.settings.mineru_poll_interval_seconds)
    return job.model_dump(mode="json")


@celery_app.task(bind=True, name="document_jobs.translate_batch", acks_late=True)
def run_document_translation_batch(_task, batch_id: str, *, trace_id: str | None = None) -> dict | None:
    """按 batch_id 执行 translation provider 批次任务。"""

    runtime = build_runtime()
    batch = runtime.document_job_execution_service.execute_translation_batch(batch_id, trace_id=trace_id)
    if batch is None:
        return None
    return batch.model_dump(mode="json")


@worker_ready.connect(weak=False)
def recover_mineru_polling_jobs(sender=None, **_kwargs) -> None:
    """Worker 就绪后复用现有恢复入口，仅唤醒已知 MinerU 批次。"""

    runtime = build_runtime()
    if runtime.settings.mineru_callback_url.strip():
        return
    result = runtime.document_job_recovery_service.run_startup_recovery(
        trace_id="worker_startup", polling_only=True,
    )
    runtime.document_job_recovery_service.logger.info(
        "[document_jobs_recovery=worker_startup scanned_jobs=%s queued_jobs=%s failed_jobs=%s] 已完成已知 MinerU 批次恢复。",
        result.scanned_jobs, result.queued_jobs, result.failed_jobs,
    )
