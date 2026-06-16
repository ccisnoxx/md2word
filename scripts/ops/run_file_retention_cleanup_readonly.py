#!/usr/bin/env python3
# File: scripts/ops/run_file_retention_cleanup_readonly.py
# Purpose: Generate read-only document_files retention cleanup plans for operators or future schedulers.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.runtime import AppRuntime
from app.domains.files.retention import DocumentFileRetentionPlanner
from app.domains.files.scheduled_cleanup import FileRetentionReadonlyCleanupRunner
from app.domains.files.storage_usage import DocumentFileStorageUsageReporter
from app.main import build_runtime


def build_runner(runtime: AppRuntime) -> FileRetentionReadonlyCleanupRunner:
    """从当前运行时构建只读 cleanup runner，不创建 FastAPI app 或触发生命周期 replay。"""

    dependency_checks = runtime.health_service.build_dependency_checks()
    artifact_disk_free = dependency_checks.get("artifact_disk_free_bytes")
    retention_planner = DocumentFileRetentionPlanner(
        runtime.document_file_repository,
        retention_days=runtime.settings.oss_file_retention_days,
    )
    storage_usage_reporter = DocumentFileStorageUsageReporter(
        runtime.document_file_repository,
        artifact_storage=str(dependency_checks.get("artifact_storage") or runtime.settings.jobs_artifact_storage_backend),
        artifact_root_writable=dependency_checks.get("artifact_root_writable") if isinstance(dependency_checks.get("artifact_root_writable"), bool) else None,
        artifact_disk_free_bytes=artifact_disk_free if isinstance(artifact_disk_free, int) else None,
    )
    return FileRetentionReadonlyCleanupRunner(retention_planner, storage_usage_reporter)


def run_readonly_cleanup_report(runtime: AppRuntime, *, output_path: Path | None = None) -> dict[str, Any]:
    """生成只读 cleanup 报告；可选写入指定 JSON 文件。"""

    report = build_runner(runtime).build_report().to_dict()
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    """CLI 入口：默认输出 JSON 到 stdout，可选写入 --output。"""

    parser = argparse.ArgumentParser(description="Generate a read-only document_files retention cleanup plan.")
    parser.add_argument("--output", help="Optional JSON report output path.")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None
    report = run_readonly_cleanup_report(build_runtime(), output_path=output_path)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
