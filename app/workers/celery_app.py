from __future__ import annotations

# app/workers/celery_app.py: 创建 document_jobs Celery 应用并集中读取 Redis 队列配置。

from app.core.config import Settings


def create_celery_app(settings: Settings | None = None):
    """创建 Celery app；未安装 Celery 时给出明确配置错误。"""

    try:
        from celery import Celery
    except ModuleNotFoundError as exc:
        raise RuntimeError("Celery 依赖未安装，请先安装 requirements.txt。") from exc

    resolved_settings = settings or Settings()
    result_backend = resolved_settings.document_jobs_celery_result_backend or None
    celery_app = Celery(
        "md2word_document_jobs",
        broker=resolved_settings.document_jobs_celery_broker_url,
        backend=result_backend,
        include=("app.workers.document_tasks",),
    )
    celery_app.conf.update(
        accept_content=("json",),
        enable_utc=True,
        result_serializer="json",
        task_soft_time_limit=resolved_settings.p0_document_job_timeout_seconds,
        task_time_limit=resolved_settings.p0_document_job_timeout_seconds + 60,
        task_default_queue=resolved_settings.document_jobs_celery_queue,
        task_routes={
            "document_jobs.run": {"queue": resolved_settings.document_jobs_celery_queue},
            "document_jobs.translate_batch": {
                "queue": resolved_settings.document_jobs_translation_batch_celery_queue,
            },
        },
        task_serializer="json",
        task_track_started=True,
        timezone="UTC",
        # build_runtime 会重建 StreamHandler；保留真实 stderr，避免 LoggingProxy 递归丢日志。
        worker_redirect_stdouts=False,
    )
    return celery_app


celery_app = create_celery_app()
