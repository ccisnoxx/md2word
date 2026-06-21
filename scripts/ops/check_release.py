from __future__ import annotations

# scripts/ops/check_release.py: 发布前聚合检查入口。

import subprocess
import sys
import urllib.error
import urllib.request
import json
import os
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
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_p0_document_jobs_when_production_uses_non_mysql_metadata_store",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_p0_document_jobs_when_production_uses_eager_worker",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_allows_p0_document_jobs_when_production_config_is_complete",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_metrics_reports_runtime_counters",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_metrics_reports_default_resource_versions_in_mysql_mode",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_detail_list_and_events_for_operator",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_create_rejects_unready_required_execution",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_list_supports_workbench_filters_without_running_worker",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_response_includes_server_action_availability",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_download_url_returns_temporary_generated_word_link",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_operator_scope_and_admin_visibility",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_delete_requires_admin_preview_and_removes_owned_files",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_worker_translates_ir_and_saves_ai_audit_artifacts",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_debug_full_text_is_admin_only",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_reads_existing_artifacts_and_updates_review_state",
    "tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_clone_rejects_operator_inheriting_debug_full_text",
    "tests.test_metadata_shadow_copy.MetadataShadowCopyTests.test_shadow_copy_writes_mysql_and_validates_all_metadata",
    "tests.test_metadata_shadow_copy.MetadataShadowCopyTests.test_shadow_copy_to_mysql_refuses_non_empty_target_by_default",
    "tests.test_database_job_repository.PersistenceAdapterTests.test_build_runtime_switches_to_database_repository_and_readiness",
    "tests.test_database_job_repository.PersistenceAdapterTests.test_build_runtime_switches_to_mysql_repository_and_readiness",
    "tests.test_database_job_repository.PersistenceAdapterTests.test_build_runtime_keeps_file_repository_as_local_default",
    "tests.test_internal_user_management",
    "tests.test_acceptance_center_api",
    "tests.test_text_render_characterization",
    "tests.test_document_ir_word_renderer_layout",
    "tests.test_page_layout_characterization",
    "tests.test_render_table_from_html_characterization",
    "tests.test_golden_sample_manifest",
    "tests.test_p1_translation_sample_manifest",
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
    golden_sample_preflight: bool = False,
    golden_sample_preflight_output_path: Path | None = None,
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
    items.append(check_frontend_contracts(openapi_output_path or (REPO_ROOT / "docs/api/openapi.json")))
    items.append(check_frontend_smoke_mock_contracts())

    if unittest_targets:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *unittest_targets],
            cwd=REPO_ROOT,
            env=_build_unittest_environment(),
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

    if golden_sample_preflight:
        items.append(check_golden_sample_preflight(golden_sample_preflight_output_path))

    return ReleaseCheckReport(items=tuple(items))


def check_frontend_contracts(openapi_path: Path) -> ReleaseCheckItem:
    """检查 document_jobs 核心 OpenAPI 字段和前端手写类型保持最小一致。"""

    missing: list[str] = []
    try:
        payload = json.loads(openapi_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ReleaseCheckItem(
            name="frontend-contract",
            ok=False,
            summary=f"Cannot read OpenAPI contract: {openapi_path}",
            details=str(exc),
        )

    paths = payload.get("paths") if isinstance(payload, dict) else None
    schemas = payload.get("components", {}).get("schemas", {}) if isinstance(payload, dict) else {}
    document_jobs_get = paths.get("/api/v1/document-jobs", {}).get("get", {}) if isinstance(paths, dict) else {}
    auth_change_password = paths.get("/api/v1/auth/change-password", {}).get("post", {}) if isinstance(paths, dict) else {}
    users_path = paths.get("/api/v1/users", {}) if isinstance(paths, dict) else {}
    acceptance_runs_path = paths.get("/api/v1/acceptance/runs", {}) if isinstance(paths, dict) else {}
    acceptance_latest_summary_path = paths.get("/api/v1/acceptance/runs/latest-summary", {}) if isinstance(paths, dict) else {}
    acceptance_run_path = paths.get("/api/v1/acceptance/runs/{run_id}", {}) if isinstance(paths, dict) else {}
    acceptance_review_path = paths.get("/api/v1/acceptance/runs/{run_id}/review", {}) if isinstance(paths, dict) else {}
    parameter_names = {
        parameter.get("name")
        for parameter in document_jobs_get.get("parameters", [])
        if isinstance(parameter, dict)
    }
    for name in ("status_group", "translation_qa_status", "include_archived"):
        if name not in parameter_names:
            missing.append(f"OpenAPI GET /document-jobs parameter: {name}")

    list_properties = schemas.get("DocumentJobListResponse", {}).get("properties", {})
    for name in ("items", "summary", "filtered_summary", "translation_qa_summary"):
        if name not in list_properties:
            missing.append(f"OpenAPI DocumentJobListResponse field: {name}")

    job_properties = schemas.get("DocumentJobResponse", {}).get("properties", {})
    for name in ("status", "stage", "failed_stage", "error_code", "error_message", "available_actions"):
        if name not in job_properties:
            missing.append(f"OpenAPI DocumentJobResponse field: {name}")

    if not auth_change_password:
        missing.append("OpenAPI POST /auth/change-password")
    if "get" not in users_path or "post" not in users_path:
        missing.append("OpenAPI /users list/create operations")
    user_properties = schemas.get("InternalUserResponse", {}).get("properties", {})
    for name in ("id", "username", "role", "status", "display_name", "updated_at"):
        if name not in user_properties:
            missing.append(f"OpenAPI InternalUserResponse field: {name}")
    if "password_hash" in user_properties:
        missing.append("OpenAPI InternalUserResponse must not expose password_hash")

    if "get" not in acceptance_runs_path:
        missing.append("OpenAPI GET /acceptance/runs")
    if "get" not in acceptance_latest_summary_path:
        missing.append("OpenAPI GET /acceptance/runs/latest-summary")
    if "get" not in acceptance_run_path:
        missing.append("OpenAPI GET /acceptance/runs/{run_id}")
    if "post" not in acceptance_review_path:
        missing.append("OpenAPI POST /acceptance/runs/{run_id}/review")
    acceptance_properties = schemas.get("AcceptanceRunResponse", {}).get("properties", {})
    for name in (
        "id",
        "title",
        "tier",
        "status",
        "environment",
        "report_path_or_url",
        "blockers",
        "warnings",
        "reviewer",
        "decision",
        "reviewed_at",
        "review_note",
    ):
        if name not in acceptance_properties:
            missing.append(f"OpenAPI AcceptanceRunResponse field: {name}")
    acceptance_review_properties = schemas.get("AcceptanceRunReviewRequest", {}).get("properties", {})
    for name in ("decision", "review_note"):
        if name not in acceptance_review_properties:
            missing.append(f"OpenAPI AcceptanceRunReviewRequest field: {name}")
    acceptance_latest_properties = schemas.get("AcceptanceLatestSummaryResponse", {}).get("properties", {})
    for name in ("overall_status", "missing_tiers", "blocker_count", "warning_count", "latest_reviewed_run", "tiers", "generated_at"):
        if name not in acceptance_latest_properties:
            missing.append(f"OpenAPI AcceptanceLatestSummaryResponse field: {name}")

    types_path = REPO_ROOT / "frontend/src/api/types.ts"
    try:
        frontend_types = types_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ReleaseCheckItem(
            name="frontend-contract",
            ok=False,
            summary=f"Cannot read frontend contract: {types_path}",
            details=str(exc),
        )

    for needle in (
        'export type DocumentJobStatusGroup = "active"',
        "available_actions: Record<DocumentJobActionId, DocumentJobAvailableAction>",
        "filtered_summary?: Record<string, number>",
        "translation_qa_summary?: Partial<Record<TranslationQaStatus, number>>",
        "ai_debug_archive_expires_at: string | null",
        "debug_full_text_enabled: boolean",
        "export type AuthChangePasswordRequest",
        "export type InternalUserResponse",
        "export type InternalUserResetPasswordRequest",
        "export type AcceptanceRunResponse",
        "export type AcceptanceRunListResponse",
        "export type AcceptanceLatestSummaryResponse",
        "export type AcceptanceReviewRequest",
        'export type AcceptanceReviewDecision = "approved"',
        'export type AcceptanceRunStatus = "passed"',
        'export type AcceptanceLatestOverallStatus = "accepted"',
        "review_note: string | null",
    ):
        if needle not in frontend_types:
            missing.append(f"frontend types missing: {needle}")

    acceptance_wrapper_path = REPO_ROOT / "frontend/src/api/acceptance.ts"
    try:
        acceptance_wrapper = acceptance_wrapper_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ReleaseCheckItem(
            name="frontend-contract",
            ok=False,
            summary=f"Cannot read frontend acceptance wrapper: {acceptance_wrapper_path}",
            details=str(exc),
        )

    for needle in (
        'url: "/api/v1/acceptance/runs"',
        'url: "/api/v1/acceptance/runs/latest-summary"',
        "`/api/v1/acceptance/runs/${runId}`",
        "`/api/v1/acceptance/runs/${runId}/review`",
        "review_note",
    ):
        if needle not in acceptance_wrapper:
            missing.append(f"frontend acceptance wrapper missing: {needle}")

    return ReleaseCheckItem(
        name="frontend-contract",
        ok=not missing,
        summary="Frontend API contracts match core OpenAPI fields" if not missing else "Frontend API contracts drifted",
        details="\n".join(missing),
    )


def check_frontend_smoke_mock_contracts() -> ReleaseCheckItem:
    """检查核心 smoke mock 是否覆盖产品成熟化验收场景。"""

    smoke_path = REPO_ROOT / "frontend/tests/smoke/core-flow.spec.ts"
    user_auth_smoke_path = REPO_ROOT / "frontend/tests/smoke/user-auth.spec.ts"
    try:
        smoke_source = smoke_path.read_text(encoding="utf-8")
        user_auth_smoke_source = user_auth_smoke_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ReleaseCheckItem(
            name="frontend-smoke-mock",
            ok=False,
            summary="Cannot read frontend smoke mock",
            details=str(exc),
        )

    required_needles = {
        "document_jobs_list": "/api/v1/document-jobs",
        "document_job_detail": "/api/v1/document-jobs/docjob_smoke_001",
        "document_job_files": "/api/v1/document-jobs/docjob_smoke_001/files",
        "document_job_events": "/api/v1/document-jobs/docjob_smoke_001/events",
        "config_summary_blocker": "config_summary_unavailable",
        "download_conflict": "document_job_not_downloadable",
        "translation_qa_detail": "/api/v1/document-jobs/docjob_qa_001/translation-qa",
        "translation_qa_unavailable": "translationQaUnavailable",
        "file_retention_workspace": "/api/v1/files/retention/plan",
        "ops_recovery_actions": "/api/v1/ops/recovery-actions",
        "ops_real_send_preview": "real_send_preview",
        "danger_confirmation": "confirmation_phrase",
    }
    missing = [
        f"{name}: {needle}"
        for name, needle in required_needles.items()
        if needle not in smoke_source
    ]
    user_auth_required_needles = {
        "managed_users_list": "/api/v1/users",
        "auth_change_password": "/api/v1/auth/change-password",
        "password_changed_notice": "password_changed",
        "dangerous_user_confirmation": "确认停用",
        "forbidden_default_route": "返回可访问页面",
    }
    missing.extend(
        f"{name}: {needle}"
        for name, needle in user_auth_required_needles.items()
        if needle not in user_auth_smoke_source
    )
    forbidden_needles = ("storage_backend", "storage_path", "media_type", "retention_until")
    stale = [f"stale file mock field: {needle}" for needle in forbidden_needles if needle in smoke_source]
    failures = missing + stale
    return ReleaseCheckItem(
        name="frontend-smoke-mock",
        ok=not failures,
        summary="Frontend smoke mock covers core contract scenarios" if not failures else "Frontend smoke mock contract drifted",
        details="\n".join(failures),
    )


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
    metadata_store = checks.get("effective_repository_backend")
    worker_backend = checks.get("document_jobs_worker_backend")
    production_baseline_ready = metadata_store == "mysql" and worker_backend == "celery"
    ok = deployment_ready and p0_ready and production_baseline_ready
    details = {
        "url": ready_url,
        "deployment_init_ready": deployment_ready,
        "p0_document_jobs_ready": p0_ready,
        "effective_repository_backend": metadata_store,
        "document_jobs_worker_backend": worker_backend,
        "readiness_blockers": blockers,
        "p0_document_jobs_blockers": p0_blockers,
    }
    return ReleaseCheckItem(
        name="runtime-readiness",
        ok=ok,
        summary=(
            "Runtime readiness passed with MySQL + Celery P0 baseline"
            if ok
            else "Runtime readiness failed P0 MySQL + Celery baseline"
        ),
        details=json.dumps(details, ensure_ascii=False, indent=2),
    )


def check_golden_sample_preflight(
    output_path: Path | None = None,
    *,
    config: object | None = None,
) -> ReleaseCheckItem:
    """Run the fast Golden Sample release preflight without submitting jobs."""

    from scripts.ops.run_golden_sample_regression import (
        RegressionConfig,
        build_preflight_report,
        format_preflight_report,
        write_preflight_report,
    )

    preflight_config = config or RegressionConfig()
    report = build_preflight_report(preflight_config)
    if output_path is not None:
        write_preflight_report(output_path, report)
    return ReleaseCheckItem(
        name="golden-sample-preflight",
        ok=bool(report.get("ok")),
        summary=(
            "Golden Sample preflight passed"
            if report.get("ok")
            else "Golden Sample preflight failed"
        ),
        details=format_preflight_report(report),
    )


def _build_unittest_environment() -> dict[str, str]:
    """Keep release-check credentials from changing targeted unittest expectations."""

    env = dict(os.environ)
    for key in tuple(env):
        if key.startswith("GOLDEN_SAMPLE_"):
            env.pop(key, None)
    return env


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
    parser.add_argument(
        "--golden-sample-preflight",
        action="store_true",
        help="Also run the fast Golden Sample preflight: manifest, admin auth, /health/ready, MySQL and Celery gates.",
    )
    parser.add_argument(
        "--golden-sample-preflight-output",
        default="",
        help="Optional path to write Golden Sample preflight JSON evidence.",
    )
    args = parser.parse_args()
    report = check_release(
        runtime_url=args.runtime_url or None,
        golden_sample_preflight=args.golden_sample_preflight,
        golden_sample_preflight_output_path=(
            Path(args.golden_sample_preflight_output)
            if args.golden_sample_preflight_output
            else None
        ),
    )
    print(format_release_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
