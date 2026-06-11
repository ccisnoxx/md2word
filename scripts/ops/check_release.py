from __future__ import annotations

# scripts/ops/check_release.py: 发布前聚合检查入口。

import subprocess
import sys
import urllib.error
import urllib.request
import json
from argparse import ArgumentParser
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
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_detail_list_and_events_for_operator",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_response_includes_server_action_availability",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_download_url_returns_temporary_generated_word_link",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_operator_scope_and_admin_visibility",
    "tests.test_metadata_shadow_copy.MetadataShadowCopyTests.test_shadow_copy_writes_mysql_and_validates_all_metadata",
    "tests.test_metadata_shadow_copy.MetadataShadowCopyTests.test_shadow_copy_to_mysql_refuses_non_empty_target_by_default",
    "tests.test_database_job_repository.PersistenceAdapterTests.test_build_runtime_switches_to_mysql_repository_and_readiness",
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
    runtime_url: str | None = None,
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

    if runtime_url:
        items.append(check_runtime_readiness(runtime_url))

    return ReleaseCheckReport(items=tuple(items))


def check_runtime_readiness(runtime_url: str) -> ReleaseCheckItem:
    ready_url = _build_ready_url(runtime_url)
    try:
        with urllib.request.urlopen(ready_url, timeout=5) as response:
            status_code = response.status
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return ReleaseCheckItem(
            name="runtime-readiness",
            ok=False,
            summary=f"Runtime readiness request failed: {ready_url}",
            details=str(exc),
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return ReleaseCheckItem(
            name="runtime-readiness",
            ok=False,
            summary=f"Runtime readiness returned invalid JSON: HTTP {status_code}",
            details=str(exc),
        )

    checks = payload.get("dependency_checks")
    if not isinstance(checks, dict):
        return ReleaseCheckItem(
            name="runtime-readiness",
            ok=False,
            summary="Runtime readiness response is missing dependency_checks",
            details=body,
        )

    blockers = _string_list(checks.get("readiness_blockers"))
    p0_blockers = _string_list(checks.get("p0_document_jobs_blockers"))
    deployment_ready = checks.get("deployment_init_ready") is True
    p0_ready = checks.get("p0_document_jobs_ready") is True
    ok = deployment_ready and p0_ready
    details = {
        "url": ready_url,
        "deployment_init_ready": deployment_ready,
        "p0_document_jobs_ready": p0_ready,
        "readiness_blockers": blockers,
        "p0_document_jobs_blockers": p0_blockers,
    }
    return ReleaseCheckItem(
        name="runtime-readiness",
        ok=ok,
        summary="Runtime readiness passed" if ok else "Runtime readiness failed",
        details=json.dumps(details, ensure_ascii=False, indent=2),
    )


def _build_ready_url(runtime_url: str) -> str:
    base = runtime_url.rstrip("/")
    if base.endswith("/api/v1/health/ready"):
        return base
    if base.endswith("/api/v1"):
        return f"{base}/health/ready"
    return f"{base}/api/v1/health/ready"


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


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
    parser = ArgumentParser(description="Run md2word release checks.")
    parser.add_argument(
        "--runtime-url",
        default="",
        help="Optional running API base URL. When set, /api/v1/health/ready must pass deployment and P0 gates.",
    )
    args = parser.parse_args()
    report = check_release(runtime_url=args.runtime_url or None)
    print(format_release_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
