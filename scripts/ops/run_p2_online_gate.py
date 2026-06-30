from __future__ import annotations

# scripts/ops/run_p2_online_gate.py: hostdzire P2 internal release evidence gate.

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urljoin

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.check_release import DEFAULT_UNITTEST_TARGETS, check_release, format_release_report
from scripts.ops.run_golden_sample_regression import RegressionConfig, build_preflight_report as build_p0_preflight_report
from scripts.ops.run_p1_translation_regression import (
    P1RegressionConfig,
    build_preflight_report as build_p1_preflight_report,
    format_preflight_report as format_p1_preflight_report,
)


DEFAULT_RUNS_DIR = REPO_ROOT / "tests" / "tmp" / "p2_online_runs"


@dataclass(frozen=True, slots=True)
class P2OnlineGateConfig:
    """P2 online gate config; values come from P2_ONLINE_* env vars by default."""

    base_url: str = os.environ.get("P2_ONLINE_BASE_URL", "http://127.0.0.1:8000")
    public_url: str = os.environ.get("P2_ONLINE_PUBLIC_URL", "")
    username: str = os.environ.get("P2_ONLINE_USERNAME", "admin")
    password: str = os.environ.get("P2_ONLINE_PASSWORD", "")
    bearer_token: str = os.environ.get("P2_ONLINE_BEARER_TOKEN", "")
    admin_token: str = os.environ.get("P2_ONLINE_ADMIN_TOKEN", os.environ.get("ADMIN_TOKEN", ""))
    runs_dir: Path = Path(os.environ.get("P2_ONLINE_RUNS_DIR", str(DEFAULT_RUNS_DIR)))
    request_timeout_seconds: int = int(os.environ.get("P2_ONLINE_REQUEST_TIMEOUT_SECONDS", "30"))
    run_release_check: bool = os.environ.get("P2_ONLINE_SKIP_RELEASE_CHECK", "0") != "1"
    run_p0_preflight: bool = os.environ.get("P2_ONLINE_SKIP_P0_PREFLIGHT", "0") != "1"
    run_p1_preflight: bool = os.environ.get("P2_ONLINE_SKIP_P1_PREFLIGHT", "0") != "1"
    sync_acceptance: bool = os.environ.get("P2_ONLINE_SYNC_ACCEPTANCE", "0") == "1"
    acceptance_run_id: str = os.environ.get("P2_ACCEPTANCE_RUN_ID", "acceptance_p2_online_gate_current")
    acceptance_environment: str = os.environ.get("P2_ACCEPTANCE_ENVIRONMENT", "hostdzire")
    acceptance_review_decision: str = os.environ.get("P2_ACCEPTANCE_REVIEW_DECISION", "")
    acceptance_review_note: str = os.environ.get("P2_ACCEPTANCE_REVIEW_NOTE", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the hostdzire P2 internal single-tenant online gate.")
    parser.add_argument("--base-url", default="", help="Runtime API base URL, e.g. http://127.0.0.1:18000")
    parser.add_argument("--public-url", default="", help="Optional public API base URL through dmit, e.g. https://md2word.962850.xyz")
    parser.add_argument("--output-dir", default="", help="Directory to write the P2 run evidence.")
    parser.add_argument("--skip-release-check", action="store_true", help="Skip check_release.py aggregation.")
    parser.add_argument("--skip-p0-preflight", action="store_true", help="Skip P0 Golden Sample preflight.")
    parser.add_argument("--skip-p1-preflight", action="store_true", help="Skip P1 translation preflight.")
    parser.add_argument(
        "--no-release-check-unittests",
        action="store_true",
        help="Run release check without targeted unittests. Use only for narrow script/debug checks.",
    )
    parser.add_argument(
        "--sync-acceptance",
        action="store_true",
        help="Upsert this P2 report into Acceptance Center after collecting the gate evidence.",
    )
    parser.add_argument("--acceptance-run-id", default="", help="Acceptance Center run id to upsert.")
    parser.add_argument("--acceptance-environment", default="", help="Acceptance Center environment label.")
    parser.add_argument(
        "--acceptance-review-decision",
        choices=["", "approved", "rejected", "needs_changes"],
        default="",
        help="Optional admin review decision to record after upsert.",
    )
    parser.add_argument("--acceptance-review-note", default="", help="Optional admin review note.")
    args = parser.parse_args()

    env_config = P2OnlineGateConfig()
    config = P2OnlineGateConfig(
        base_url=args.base_url or env_config.base_url,
        public_url=args.public_url or env_config.public_url,
        username=env_config.username,
        password=env_config.password,
        bearer_token=env_config.bearer_token,
        admin_token=env_config.admin_token,
        runs_dir=Path(args.output_dir) if args.output_dir else env_config.runs_dir,
        request_timeout_seconds=env_config.request_timeout_seconds,
        run_release_check=env_config.run_release_check and not args.skip_release_check,
        run_p0_preflight=env_config.run_p0_preflight and not args.skip_p0_preflight,
        run_p1_preflight=env_config.run_p1_preflight and not args.skip_p1_preflight,
        sync_acceptance=env_config.sync_acceptance or args.sync_acceptance,
        acceptance_run_id=args.acceptance_run_id or env_config.acceptance_run_id,
        acceptance_environment=args.acceptance_environment or env_config.acceptance_environment,
        acceptance_review_decision=args.acceptance_review_decision or env_config.acceptance_review_decision,
        acceptance_review_note=args.acceptance_review_note or env_config.acceptance_review_note,
    )
    unittest_targets: Sequence[str] = () if args.no_release_check_unittests else DEFAULT_UNITTEST_TARGETS
    report = run_p2_online_gate(config, release_check_unittest_targets=unittest_targets)
    print(format_console_report(report))
    acceptance_ok = not config.sync_acceptance or bool((report.get("acceptance_sync") or {}).get("ok"))
    raise SystemExit(0 if report["summary"]["p2_online_gate_ready"] and acceptance_ok else 1)


def run_p2_online_gate(
    config: P2OnlineGateConfig,
    *,
    release_check_unittest_targets: Sequence[str] = DEFAULT_UNITTEST_TARGETS,
) -> dict[str, Any]:
    """Collect P2 online evidence from an already running hostdzire deployment."""

    run_dir = create_run_dir(config.runs_dir)
    session = build_authenticated_session(config)
    live_check = fetch_json_check(config, requests.Session(), config.base_url, "/api/v1/health/live", "live")
    ready_check = fetch_json_check(config, requests.Session(), config.base_url, "/api/v1/health/ready", "ready")
    metrics_check = fetch_json_check(config, requests.Session(), config.base_url, "/api/v1/health/metrics", "metrics")
    ops_alerts_check = fetch_json_check(config, session, config.base_url, "/api/v1/health/ops-alerts", "ops_alerts")
    public_checks = build_public_checks(config)
    release_check = build_release_check(config, release_check_unittest_targets) if config.run_release_check else skipped_check("release_check")
    p0_preflight = build_p0_preflight(config) if config.run_p0_preflight else skipped_check("p0_preflight")
    p1_preflight = build_p1_preflight(config) if config.run_p1_preflight else skipped_check("p1_preflight")
    summary = build_summary(
        checks=[live_check, ready_check, metrics_check, ops_alerts_check, release_check, p0_preflight, p1_preflight],
        public_checks=public_checks,
        ready_payload=ready_check.get("payload") if ready_check["ok"] else {},
        ops_alerts_payload=ops_alerts_check.get("payload") if ops_alerts_check["ok"] else {},
    )
    report = {
        "schema_version": 1,
        "run_dir": str(run_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": redacted_config(config),
        "summary": summary,
        "checks": {
            "live": live_check,
            "ready": ready_check,
            "metrics": metrics_check,
            "ops_alerts": ops_alerts_check,
            "public": public_checks,
            "release_check": release_check,
            "p0_preflight": p0_preflight,
            "p1_preflight": p1_preflight,
        },
    }
    write_report_files(run_dir, report)
    if config.sync_acceptance:
        report["acceptance_sync"] = sync_acceptance_run(config, session, report)
        write_report_files(run_dir, report)
    return report


def create_run_dir(runs_dir: Path) -> Path:
    run_dir = runs_dir / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def build_authenticated_session(config: P2OnlineGateConfig) -> requests.Session:
    session = requests.Session()
    if config.bearer_token.strip() or config.password.strip():
        token = config.bearer_token.strip() or login_for_token(config, session)
        session.headers.update({"Authorization": f"Bearer {token}"})
    elif config.admin_token.strip():
        session.headers.update({"X-Admin-Token": config.admin_token.strip()})
    else:
        raise RuntimeError("请设置 P2_ONLINE_PASSWORD、P2_ONLINE_BEARER_TOKEN 或 P2_ONLINE_ADMIN_TOKEN/ADMIN_TOKEN。")
    return session


def login_for_token(config: P2OnlineGateConfig, session: requests.Session) -> str:
    if not config.password.strip():
        raise RuntimeError("请设置 P2_ONLINE_PASSWORD，或设置 P2_ONLINE_BEARER_TOKEN。")
    response = session.post(
        api_url(config.base_url, "/api/v1/auth/login"),
        json={"username": config.username, "password": config.password},
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    token = str(response.json().get("access_token") or "")
    if not token:
        raise RuntimeError("登录响应缺少 access_token。")
    return token


def fetch_json_check(
    config: P2OnlineGateConfig,
    session: requests.Session,
    base_url: str,
    path: str,
    name: str,
) -> dict[str, Any]:
    url = api_url(base_url, path)
    try:
        response = session.get(url, timeout=config.request_timeout_seconds)
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - online gate must report every failed check.
        return {
            "name": name,
            "ok": False,
            "url": url,
            "status_code": None,
            "blockers": [f"{name}_request_failed"],
            "details": {"error": str(exc)},
        }
    ok = response.status_code == 200
    return {
        "name": name,
        "ok": ok,
        "url": url,
        "status_code": response.status_code,
        "blockers": [] if ok else [f"{name}_http_{response.status_code}"],
        "payload": payload,
    }


def build_public_checks(config: P2OnlineGateConfig) -> dict[str, Any]:
    if not config.public_url.strip():
        return {"enabled": False, "ok": True, "checks": [], "blockers": []}
    session = requests.Session()
    checks = [
        fetch_json_check(config, session, config.public_url, "/api/v1/health/live", "public_live"),
        fetch_json_check(config, session, config.public_url, "/api/v1/health/ready", "public_ready"),
    ]
    blockers = [blocker for check in checks for blocker in check["blockers"]]
    return {"enabled": True, "ok": all(check["ok"] for check in checks), "checks": checks, "blockers": blockers}


def build_release_check(
    config: P2OnlineGateConfig,
    unittest_targets: Sequence[str],
) -> dict[str, Any]:
    try:
        report = check_release(runtime_url=config.base_url, unittest_targets=unittest_targets)
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "release_check",
            "ok": False,
            "blockers": ["release_check_failed"],
            "details": {"error": str(exc)},
        }
    return {
        "name": "release_check",
        "ok": report.ok,
        "blockers": [] if report.ok else [f"release_check_{item.name}_failed" for item in report.items if not item.ok],
        "items": [asdict(item) for item in report.items],
        "formatted": format_release_report(report),
    }


def build_p0_preflight(config: P2OnlineGateConfig) -> dict[str, Any]:
    p0_config = RegressionConfig(
        base_url=config.base_url,
        username=config.username,
        password=config.password,
        bearer_token=config.bearer_token,
        admin_token=config.admin_token,
    )
    try:
        report = build_p0_preflight_report(p0_config)
    except Exception as exc:  # noqa: BLE001
        return {"name": "p0_preflight", "ok": False, "blockers": ["p0_preflight_failed"], "details": {"error": str(exc)}}
    return {"name": "p0_preflight", "ok": bool(report.get("ok")), "blockers": report.get("blockers") or [], "report": report}


def build_p1_preflight(config: P2OnlineGateConfig) -> dict[str, Any]:
    p1_config = P1RegressionConfig(
        base_url=config.base_url,
        username=config.username,
        password=config.password,
        bearer_token=config.bearer_token,
        admin_token=config.admin_token,
    )
    try:
        report = build_p1_preflight_report(p1_config)
    except Exception as exc:  # noqa: BLE001
        return {"name": "p1_preflight", "ok": False, "blockers": ["p1_preflight_failed"], "details": {"error": str(exc)}}
    return {
        "name": "p1_preflight",
        "ok": bool(report.get("ok")),
        "blockers": report.get("blockers") or [],
        "report": report,
        "formatted": format_p1_preflight_report(report),
    }


def skipped_check(name: str) -> dict[str, Any]:
    return {"name": name, "ok": True, "skipped": True, "blockers": []}


def build_summary(
    *,
    checks: list[dict[str, Any]],
    public_checks: dict[str, Any],
    ready_payload: dict[str, Any],
    ops_alerts_payload: dict[str, Any],
) -> dict[str, Any]:
    ready_checks = ready_payload.get("dependency_checks") if isinstance(ready_payload, dict) else {}
    ready_checks = ready_checks if isinstance(ready_checks, dict) else {}
    deployment = ready_payload.get("deployment") if isinstance(ready_payload, dict) else {}
    deployment = deployment if isinstance(deployment, dict) else {}
    ops_alerts = ops_alerts_payload.get("alerts") if isinstance(ops_alerts_payload, dict) else []
    ops_alerts = ops_alerts if isinstance(ops_alerts, list) else []
    critical_alerts = [
        item.get("code")
        for item in ops_alerts
        if isinstance(item, dict) and item.get("severity") == "critical"
    ]
    blockers = [blocker for check in checks for blocker in check.get("blockers", [])]
    blockers.extend(public_checks.get("blockers") or [])
    if critical_alerts:
        blockers.append("ops_alerts_critical_present")
    if not str(ready_checks.get("document_jobs_translation_batch_celery_queue") or "").strip():
        blockers.append("document_jobs_translation_batch_celery_queue_missing")
    blockers = list(dict.fromkeys(str(blocker) for blocker in blockers if str(blocker).strip()))
    return {
        "p2_online_gate_ready": not blockers,
        "blockers": blockers,
        "warnings": build_warnings(deployment=deployment, ops_alerts_payload=ops_alerts_payload),
        "deployment": deployment,
        "runtime": {
            "deployment_init_ready": ready_checks.get("deployment_init_ready"),
            "p0_document_jobs_ready": ready_checks.get("p0_document_jobs_ready"),
            "effective_repository_backend": ready_checks.get("effective_repository_backend"),
            "document_jobs_worker_backend": ready_checks.get("document_jobs_worker_backend"),
            "document_jobs_celery_queue": ready_checks.get("document_jobs_celery_queue"),
            "document_jobs_translation_batch_celery_queue": ready_checks.get("document_jobs_translation_batch_celery_queue"),
            "translation_available": ready_checks.get("translation_available"),
            "readiness_blockers": ready_checks.get("readiness_blockers") or [],
            "readiness_warnings": ready_checks.get("readiness_warnings") or [],
        },
        "ops_alert_status": ops_alerts_payload.get("status") if isinstance(ops_alerts_payload, dict) else None,
        "critical_ops_alerts": critical_alerts,
    }


def build_warnings(*, deployment: dict[str, Any], ops_alerts_payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not deployment.get("deployment_id"):
        warnings.append("deployment_id_missing")
    if not deployment.get("version") or deployment.get("version") == "dev":
        warnings.append("deployment_version_not_set")
    ops_alerts = ops_alerts_payload.get("alerts") if isinstance(ops_alerts_payload, dict) else []
    ops_alerts = ops_alerts if isinstance(ops_alerts, list) else []
    warning_alerts = [
        item.get("code")
        for item in ops_alerts
        if isinstance(item, dict) and item.get("severity") in {"warning", "info"}
    ]
    warnings.extend(str(code) for code in warning_alerts if code)
    return list(dict.fromkeys(warnings))


def redacted_config(config: P2OnlineGateConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["runs_dir"] = str(config.runs_dir)
    payload["password"] = "***" if config.password else ""
    payload["bearer_token"] = "***" if config.bearer_token else ""
    payload["admin_token"] = "***" if config.admin_token else ""
    payload["acceptance_review_note"] = "***" if config.acceptance_review_note else ""
    return payload


def sync_acceptance_run(
    config: P2OnlineGateConfig,
    session: requests.Session,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Upsert the redacted P2 report summary into Acceptance Center."""

    run_id = config.acceptance_run_id.strip() or "acceptance_p2_online_gate_current"
    payload = build_acceptance_run_payload(config, report)
    url = api_url(config.base_url, "/api/v1/acceptance/runs")
    result: dict[str, Any] = {"run_id": run_id, "url": url, "ok": False, "blockers": []}
    try:
        response = session.post(url, json=payload, timeout=config.request_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - release evidence should report sync failures.
        result["blockers"] = ["acceptance_sync_request_failed"]
        result["details"] = {"error": str(exc)}
        return result

    result["status_code"] = response.status_code
    result["ok"] = response.status_code in {200, 201}
    if not result["ok"]:
        result["blockers"] = [f"acceptance_sync_http_{response.status_code}"]
        result["details"] = _safe_response_details(response)
        return result

    result["run"] = _safe_response_json(response)
    review_decision = config.acceptance_review_decision.strip()
    if review_decision:
        review_result = review_acceptance_run(config, session, run_id, review_decision)
        result["review"] = review_result
        result["ok"] = bool(review_result.get("ok"))
        result["blockers"] = review_result.get("blockers") or []
    return result


def review_acceptance_run(
    config: P2OnlineGateConfig,
    session: requests.Session,
    run_id: str,
    decision: str,
) -> dict[str, Any]:
    """Record an optional Acceptance Center review after P2 evidence upsert."""

    url = api_url(config.base_url, f"/api/v1/acceptance/runs/{run_id}/review")
    payload = {"decision": decision}
    note = config.acceptance_review_note.strip()
    if note:
        payload["review_note"] = note
    result: dict[str, Any] = {"url": url, "ok": False, "blockers": []}
    try:
        response = session.post(url, json=payload, timeout=config.request_timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        result["blockers"] = ["acceptance_review_request_failed"]
        result["details"] = {"error": str(exc)}
        return result
    result["status_code"] = response.status_code
    result["ok"] = response.status_code == 200
    if result["ok"]:
        result["run"] = _safe_response_json(response)
    else:
        result["blockers"] = [f"acceptance_review_http_{response.status_code}"]
        result["details"] = _safe_response_details(response)
    return result


def build_acceptance_run_payload(config: P2OnlineGateConfig, report: dict[str, Any]) -> dict[str, Any]:
    """Build the compact Acceptance Center payload from a P2 online gate report."""

    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    blockers = _string_list(summary.get("blockers"))
    warnings = _string_list(summary.get("warnings"))
    ready = bool(summary.get("p2_online_gate_ready")) and not blockers
    deployment = summary.get("deployment") if isinstance(summary.get("deployment"), dict) else {}
    runtime = summary.get("runtime") if isinstance(summary.get("runtime"), dict) else {}
    title_suffix = deployment.get("deployment_id") or deployment.get("version") or "current"
    generated_at = str(report.get("generated_at") or "")
    return {
        "id": config.acceptance_run_id.strip() or "acceptance_p2_online_gate_current",
        "title": _truncate(f"P2 online gate - hostdzire {title_suffix}", 240),
        "tier": "P2",
        "status": "passed" if ready else "failed",
        "environment": config.acceptance_environment.strip() or "hostdzire",
        "source": "manual_import:p2_online_gate",
        "report_path_or_url": str(Path(str(report.get("run_dir") or "")) / "report.md"),
        "finished_at": generated_at or None,
        "summary": _truncate(_build_acceptance_summary(summary, deployment, runtime), 4000),
        "blockers": blockers,
        "warnings": warnings,
    }


def _build_acceptance_summary(
    summary: dict[str, Any],
    deployment: dict[str, Any],
    runtime: dict[str, Any],
) -> str:
    checks = [
        f"p2_online_gate_ready={bool(summary.get('p2_online_gate_ready'))}",
        f"deployment_id={deployment.get('deployment_id') or '-'}",
        f"version={deployment.get('version') or '-'}",
        f"repository={runtime.get('effective_repository_backend') or '-'}",
        f"worker_backend={runtime.get('document_jobs_worker_backend') or '-'}",
        f"document_jobs_queue={runtime.get('document_jobs_celery_queue') or '-'}",
        f"translation_batch_queue={runtime.get('document_jobs_translation_batch_celery_queue') or '-'}",
        f"translation_available={runtime.get('translation_available')}",
        f"ops_alert_status={summary.get('ops_alert_status') or '-'}",
    ]
    return "P2 internal online gate evidence. " + "; ".join(checks) + "."


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [normalized for value in values if (normalized := str(value).strip())]


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _safe_response_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        return None


def _safe_response_details(response: requests.Response) -> dict[str, Any]:
    payload = _safe_response_json(response)
    if payload is not None:
        return {"response": payload}
    return {"text": response.text[:1000]}


def write_report_files(run_dir: Path, report: dict[str, Any]) -> None:
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(format_markdown_report(report), encoding="utf-8")


def format_console_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "P2 online gate\n"
        f"run_dir: {report['run_dir']}\n"
        f"ready: {summary['p2_online_gate_ready']}\n"
        f"blockers: {', '.join(summary['blockers']) or 'none'}\n"
        f"warnings: {', '.join(summary['warnings']) or 'none'}"
    ]
    acceptance_sync = report.get("acceptance_sync")
    if isinstance(acceptance_sync, dict):
        lines.append(f"\nacceptance_sync: {acceptance_sync.get('ok')} run_id: {acceptance_sync.get('run_id')}")
    return "".join(lines)


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    deployment = summary.get("deployment") or {}
    runtime = summary.get("runtime") or {}
    lines = [
        "# P2 online gate report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Run dir: `{report['run_dir']}`",
        f"- P2 online gate ready: `{summary['p2_online_gate_ready']}`",
        f"- Blockers: `{', '.join(summary['blockers']) or 'none'}`",
        f"- Warnings: `{', '.join(summary['warnings']) or 'none'}`",
        "",
        "## Deployment",
        "",
        f"- environment: `{deployment.get('environment') or '-'}`",
        f"- public_deployment_mode: `{deployment.get('public_deployment_mode') or '-'}`",
        f"- version: `{deployment.get('version') or '-'}`",
        f"- deployment_id: `{deployment.get('deployment_id') or '-'}`",
        f"- started_at: `{deployment.get('started_at') or '-'}`",
        "",
        "## Runtime",
        "",
        f"- deployment_init_ready: `{runtime.get('deployment_init_ready')}`",
        f"- p0_document_jobs_ready: `{runtime.get('p0_document_jobs_ready')}`",
        f"- effective_repository_backend: `{runtime.get('effective_repository_backend')}`",
        f"- document_jobs_worker_backend: `{runtime.get('document_jobs_worker_backend')}`",
        f"- document_jobs_celery_queue: `{runtime.get('document_jobs_celery_queue')}`",
        f"- document_jobs_translation_batch_celery_queue: `{runtime.get('document_jobs_translation_batch_celery_queue')}`",
        f"- translation_available: `{runtime.get('translation_available')}`",
        f"- ops_alert_status: `{summary.get('ops_alert_status')}`",
        f"- critical_ops_alerts: `{', '.join(summary.get('critical_ops_alerts') or []) or 'none'}`",
        "",
        "## Checks",
        "",
    ]
    for name, check in report.get("checks", {}).items():
        if name == "public":
            lines.append(f"- public: `{check.get('ok')}` enabled=`{check.get('enabled')}` blockers=`{', '.join(check.get('blockers') or []) or 'none'}`")
            continue
        lines.append(f"- {name}: `{check.get('ok')}` blockers=`{', '.join(check.get('blockers') or []) or 'none'}`")
    acceptance_sync = report.get("acceptance_sync")
    if isinstance(acceptance_sync, dict):
        lines.extend(
            [
                "",
                "## Acceptance Center Sync",
                "",
                f"- run_id: `{acceptance_sync.get('run_id') or '-'}`",
                f"- ok: `{acceptance_sync.get('ok')}`",
                f"- status_code: `{acceptance_sync.get('status_code') or '-'}`",
                f"- blockers: `{', '.join(acceptance_sync.get('blockers') or []) or 'none'}`",
            ]
        )
    return "\n".join(lines) + "\n"


def api_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


if __name__ == "__main__":
    main()
