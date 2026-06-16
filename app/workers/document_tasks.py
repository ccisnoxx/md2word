from __future__ import annotations

# app/workers/document_tasks.py: document_jobs Celery task 定义。

from app.main import build_runtime
from app.workers.celery_app import celery_app


@celery_app.task(name="document_jobs.ping")
def ping() -> str:
    """Celery/Redis Worker 连通性测试任务。"""

    return "pong"


@celery_app.task(bind=True, name="document_jobs.run", acks_late=True)
def run_document_job(_task, job_id: str, *, trace_id: str | None = None) -> dict | None:
    """按 job_id 执行 document_jobs 幂等骨架。"""

    runtime = build_runtime()
    try:
        job = runtime.document_job_execution_service.execute_job(job_id, trace_id=trace_id)
    except _soft_time_limit_error():
        runtime.document_job_execution_service.mark_job_timed_out(job_id, trace_id=trace_id)
        raise
    if job is None:
        return None
    return job.model_dump(mode="json")


def _soft_time_limit_error():
    """延迟解析 Celery soft timeout 异常，避免测试环境强依赖 billiard import。"""

    try:
        from billiard.exceptions import SoftTimeLimitExceeded
    except ModuleNotFoundError:  # pragma: no cover - Celery 运行环境才会进入
        return TimeoutError
    return SoftTimeLimitExceeded
