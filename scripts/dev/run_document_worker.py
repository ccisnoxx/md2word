#!/usr/bin/env python3
from __future__ import annotations

# scripts/dev/run_document_worker.py: PyCharm 友好的 document_jobs Celery Worker 入口。

import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
root_path = str(ROOT)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

VENDOR_DIR = ROOT / ".python_packages"
if VENDOR_DIR.exists():
    vendor_path = str(VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

from app.core.config import Settings
from app.infrastructure.pdf_crop import poppler_tools_available
from app.workers.celery_app import create_celery_app


def _required_queue(name: str, value: str) -> str:
    queue = value.strip()
    if not queue:
        raise RuntimeError(f"{name} must be configured before starting document worker.")
    return queue


def build_worker_main_args(settings: Settings) -> list[str]:
    """Build Celery worker args for every queue used by document job execution."""

    queues = list(
        dict.fromkeys(
            [
                _required_queue("DOCUMENT_JOBS_CELERY_QUEUE", settings.document_jobs_celery_queue),
                _required_queue(
                    "DOCUMENT_JOBS_TRANSLATION_BATCH_CELERY_QUEUE",
                    settings.document_jobs_translation_batch_celery_queue,
                ),
            ]
        )
    )
    return [
        "worker",
        "--loglevel=INFO",
        "-Q",
        ",".join(queues),
    ]


def check_poppler_tools(settings: Settings) -> None:
    """图片回退和整页降级依赖 Poppler，缺失时任务要到页面失败才暴露问题。

    必须在启动入口检查：Celery 的 worker_ready 信号会捕获接收方异常，Worker 仍会继续运行。
    """

    if poppler_tools_available():
        return
    message = "缺少 Poppler（pdfinfo、pdftoppm），图片回退和整页降级不可用。"
    if settings.production_like:
        raise RuntimeError(message)
    logging.getLogger(__name__).warning(message)


def main() -> None:
    settings = Settings()
    check_poppler_tools(settings)
    celery_app = create_celery_app(settings)
    celery_app.worker_main(build_worker_main_args(settings))


if __name__ == "__main__":
    main()
