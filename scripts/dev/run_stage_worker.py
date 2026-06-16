#!/Users/sc/miniconda3/envs/md2word/bin/python
from __future__ import annotations

# scripts/dev/run_stage_worker.py: PyCharm 友好的独立 stage worker 进程入口。

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

from app.main import build_runtime
from app.workers.stage_worker import StageWorker


def main() -> None:
    runtime = build_runtime()
    if runtime.settings.jobs_worker_mode != "external":
        logging.getLogger("system").warning(
            "JOBS_WORKER_MODE=%s；独立 worker 通常应与 API 一起配置为 external，避免同进程和独立进程重复消费。",
            runtime.settings.jobs_worker_mode,
        )
    StageWorker(runtime).run_forever()


if __name__ == "__main__":
    main()
