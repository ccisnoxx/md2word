from __future__ import annotations

# scripts/ops/check_release.py: 发布前聚合检查入口。

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.export_openapi import check_openapi_export, format_pretty_report


DEFAULT_UNITTEST_TARGETS: tuple[str, ...] = (
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_metrics_reports_runtime_counters",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_metrics_reports_default_resource_versions_in_mysql_mode",
    "tests.test_metadata_shadow_copy.MetadataShadowCopyTests.test_shadow_copy_writes_mysql_and_validates_all_metadata",
    "tests.test_metadata_shadow_copy.MetadataShadowCopyTests.test_shadow_copy_to_mysql_refuses_non_empty_target_by_default",
    "tests.test_database_job_repository.DatabaseJobRepositoryTests.test_jobs_api_pdf_callback_flow_uses_mysql_repository",
    "tests.test_database_job_repository.DatabaseJobRepositoryTests.test_build_runtime_switches_to_mysql_repository_and_readiness",
    "tests.test_job_workflow_policy",
    "tests.test_backend_logging",
)


@dataclass(frozen=True, slots=True)
class ReleaseCheckItem:
    name: str
    ok: bool
    summary: str
    details: str = ""


@dataclass(frozen=True, slots=True)
class ReleaseCheckReport:
    items: tuple[ReleaseCheckItem, ...]

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.items)


def check_release(
    openapi_output_path: Path | None = None,
    *,
    unittest_targets: Sequence[str] = DEFAULT_UNITTEST_TARGETS,
) -> ReleaseCheckReport:
    items: list[ReleaseCheckItem] = []

    openapi_report = (
        check_openapi_export(include_diff=False)
        if openapi_output_path is None
        else check_openapi_export(openapi_output_path, include_diff=False)
    )
    items.append(
        ReleaseCheckItem(
            name="openapi",
            ok=openapi_report.ok,
            summary="OpenAPI snapshot is current" if openapi_report.ok else "OpenAPI snapshot is stale",
            details=format_pretty_report(openapi_report),
        )
    )

    if unittest_targets:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *unittest_targets],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        items.append(
            ReleaseCheckItem(
                name="targeted-unittest",
                ok=result.returncode == 0,
                summary=(
                    f"Targeted unittest passed: {len(unittest_targets)} target(s)"
                    if result.returncode == 0
                    else f"Targeted unittest failed with exit code {result.returncode}"
                ),
                details=details.strip(),
            )
        )

    return ReleaseCheckReport(items=tuple(items))


def format_release_report(report: ReleaseCheckReport) -> str:
    lines = [
        "Release check report",
        f"ok: {report.ok}",
    ]
    for item in report.items:
        lines.append("")
        lines.append(f"[{item.name}] ok: {item.ok}")
        lines.append(item.summary)
        if item.details:
            lines.append(item.details)
    return "\n".join(lines)


def main() -> None:
    report = check_release()
    print(format_release_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
