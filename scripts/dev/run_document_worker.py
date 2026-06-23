#!/usr/bin/env python3
from __future__ import annotations

# scripts/dev/run_document_worker.py: PyCharm 友好的 document_jobs Celery Worker 入口。

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
from app.workers.celery_app import create_celery_app


def main() -> None:
    settings = Settings()
    celery_app = create_celery_app(settings)
    celery_app.worker_main(
        [
            "worker",
            "--loglevel=INFO",
            "-Q",
            settings.document_jobs_celery_queue,
        ]
    )


if __name__ == "__main__":
    main()
