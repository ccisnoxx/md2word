from __future__ import annotations

# scripts/ops/run_p1_translation_regression.py: hostdzire 上运行 P1 en2zh PDF->Word beta 回归。

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.renderer.docx_quality import analyze_docx_quality_file, build_docx_quality_flags
from scripts.ops.run_golden_sample_regression import absolute_url, api_url, is_docx_openable, is_same_origin


DEFAULT_MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "p1_translation_samples" / "manifest.yaml"
DEFAULT_RUNS_DIR = REPO_ROOT / "tests" / "tmp" / "p1_translation_runs"
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
ACTIVE_TRANSLATION_BATCH_STATUSES = {"pending", "queued", "running"}
TRANSLATION_BATCH_ERROR_MESSAGE_LIMIT = 240
TRANSIENT_REQUEST_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


@dataclass(frozen=True, slots=True)
class P1RegressionConfig:
    """P1 翻译回归配置；通过 P1_TRANSLATION_* 环境变量覆盖。"""

    base_url: str = os.environ.get("P1_TRANSLATION_BASE_URL", "http://127.0.0.1:8000")
    username: str = os.environ.get("P1_TRANSLATION_USERNAME", "admin")
    password: str = os.environ.get("P1_TRANSLATION_PASSWORD", "")
    bearer_token: str = os.environ.get("P1_TRANSLATION_BEARER_TOKEN", "")
    admin_token: str = os.environ.get("P1_TRANSLATION_ADMIN_TOKEN", os.environ.get("ADMIN_TOKEN", ""))
    manifest_path: Path = Path(os.environ.get("P1_TRANSLATION_MANIFEST", str(DEFAULT_MANIFEST_PATH)))
    runs_dir: Path = Path(os.environ.get("P1_TRANSLATION_RUNS_DIR", str(DEFAULT_RUNS_DIR)))
    request_timeout_seconds: int = int(os.environ.get("P1_TRANSLATION_REQUEST_TIMEOUT_SECONDS", "30"))
    poll_interval_seconds: float = float(os.environ.get("P1_TRANSLATION_POLL_INTERVAL_SECONDS", "5"))
    job_timeout_seconds: int = int(os.environ.get("P1_TRANSLATION_JOB_TIMEOUT_SECONDS", "1800"))
    download_outputs: bool = os.environ.get("P1_TRANSLATION_DOWNLOAD_OUTPUTS", "1") != "0"
    debug_full_text: bool = os.environ.get("P1_TRANSLATION_DEBUG_FULL_TEXT", "1") != "0"
    formal: bool = os.environ.get("P1_TRANSLATION_FORMAL", "0") == "1"
    manual_signoff_path: str = os.environ.get("P1_TRANSLATION_MANUAL_SIGNOFF", "")


@dataclass(slots=True)
class P1SampleResult:
    sample_id: str
    filename: str
    title: str
    tags: list[str]
    status: str
    source_status: str
    expected_terms: list[str] = field(default_factory=list)
    job_id: str | None = None
    file_id: str | None = None
    result_file_id: str | None = None
    failure_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    elapsed_seconds: float = 0.0
    docx_path: str | None = None
    docx_sha256: str | None = None
    docx_openable: bool | None = None
    docx_quality: dict[str, Any] = field(default_factory=dict)
    docx_quality_flags: list[str] = field(default_factory=list)
    qa_available: bool = False
    qa_availability_reason: str | None = None
    ai_call_count: int = 0
    term_trace_count: int = 0
    term_hit_rate: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    debug_full_text_enabled: bool = False
    debug_archive_file_count: int = 0
    debug_archive_expires_at: str | None = None
    debug_archive_expired: bool = False
    debug_archive_contains_full_text: bool = False
    source_comparison_available: bool = False
    source_comparison_reason: str | None = None
    translation_batch_diagnostics_available: bool = False
    translation_batch_diagnostics_error: str | None = None
    translation_batch_generation: int | None = None
    translation_batch_summary: dict[str, Any] = field(default_factory=dict)
    translation_batches: list[dict[str, Any]] = field(default_factory=list)
    translation_batch_warnings: list[str] = field(default_factory=list)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run P1 en2zh translation QA/governance regression.")
    parser.add_argument("--preflight", action="store_true", help="Check P1 prerequisites without creating jobs.")
    parser.add_argument("--preflight-output", metavar="PATH", help="Write --preflight JSON evidence to this path.")
    parser.add_argument("--apply-manual-signoff", metavar="RUN_DIR", help="Apply admin signoff YAML to an existing P1 run.")
    parser.add_argument("--manual-signoff", metavar="PATH", help="Path to admin manual signoff YAML.")
    args = parser.parse_args()

    config = P1RegressionConfig()
    if args.preflight:
        report = build_preflight_report(config)
        if args.preflight_output:
            write_json(Path(args.preflight_output), report)
        print(format_preflight_report(report))
        if not report["ok"]:
            raise SystemExit(1)
        return

    if args.apply_manual_signoff:
        run_dir = Path(args.apply_manual_signoff)
        signoff_path = Path(args.manual_signoff) if args.manual_signoff else run_dir / "manual-signoff.yaml"
        report = apply_manual_signoff(run_dir, signoff_path)
        print(format_console_report(report))
        if not report["summary"]["p1_beta_ready"]:
            raise SystemExit(1)
        return

    report = run_regression(config)
    print(format_console_report(report))
    if not report["summary"]["automated_chain_met_target"]:
        raise SystemExit(1)


def run_regression(config: P1RegressionConfig) -> dict[str, Any]:
    manifest = load_manifest(config.manifest_path)
    sample_root = resolve_sample_root(config.manifest_path, manifest)
    run_dir = create_run_dir(config.runs_dir)
    samples = [sample for sample in manifest["samples"] if sample.get("source_status") == "available"]
    results = [run_one_sample(config, build_authenticated_session(config), sample_root, run_dir, manifest, sample) for sample in samples]
    pending_samples = [sample for sample in manifest["samples"] if sample.get("source_status") != "available"]
    manual_signoff = load_manual_signoff(Path(config.manual_signoff_path)) if config.manual_signoff_path.strip() else None
    report = build_report(config, manifest, run_dir, results, pending_samples, manual_signoff)
    write_report_files(run_dir, report)
    return report


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"P1 manifest 不存在: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("schema_version") != 1:
        raise ValueError("P1 manifest schema_version 必须为 1。")
    if payload.get("default_mode") != "en2zh_pdf_to_word":
        raise ValueError("P1 manifest default_mode 必须为 en2zh_pdf_to_word。")
    if not isinstance(payload.get("samples"), list) or not payload["samples"]:
        raise ValueError("P1 manifest 必须包含 samples。")
    return payload


def resolve_sample_root(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    raw_root = str(manifest.get("sample_root") or "tests/fixtures/p1_translation_samples/pdfs")
    candidate = Path(raw_root)
    if candidate.is_absolute():
        return candidate
    return (REPO_ROOT / candidate).resolve() if manifest_path == DEFAULT_MANIFEST_PATH else (manifest_path.parent / candidate).resolve()


def create_run_dir(runs_dir: Path) -> Path:
    run_dir = runs_dir / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def build_authenticated_session(config: P1RegressionConfig) -> requests.Session:
    session = requests.Session()
    token = config.bearer_token.strip() or login_for_token(config, session)
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def login_for_token(config: P1RegressionConfig, session: requests.Session) -> str:
    if not config.password:
        raise RuntimeError("请设置 P1_TRANSLATION_PASSWORD，或设置 P1_TRANSLATION_BEARER_TOKEN。")
    response = session.post(
        api_url(config, "/api/v1/auth/login"),
        json={"username": config.username, "password": config.password},
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    token = str(response.json().get("access_token") or "")
    if not token:
        raise RuntimeError("登录响应缺少 access_token。")
    return token


def get_with_transient_retries(
    config: P1RegressionConfig,
    session: requests.Session,
    url: str,
    *,
    attempts: int = 3,
) -> requests.Response:
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=config.request_timeout_seconds)
            response.raise_for_status()
            return response
        except TRANSIENT_REQUEST_ERRORS as exc:
            last_error = exc
            if attempt >= attempts:
                break
            time.sleep(min(config.poll_interval_seconds, 2.0))
    assert last_error is not None
    raise last_error


def run_one_sample(
    config: P1RegressionConfig,
    session: requests.Session,
    sample_root: Path,
    run_dir: Path,
    manifest: dict[str, Any],
    sample: dict[str, Any],
) -> P1SampleResult:
    started = time.monotonic()
    sample_path = sample_root / sample["filename"]
    result = P1SampleResult(
        sample_id=str(sample["id"]),
        filename=str(sample["filename"]),
        title=str(sample.get("title") or ""),
        tags=[str(tag) for tag in sample.get("tags", [])],
        status="running",
        source_status=str(sample.get("source_status") or ""),
        expected_terms=[str(term) for term in sample.get("expected_terms", [])],
    )
    try:
        if not sample_path.exists():
            raise FileNotFoundError(f"样本 PDF 不存在: {sample_path}")
        result.file_id = upload_source_pdf(config, session, sample_path)
        job = create_document_job(config, session, manifest, sample, result.file_id)
        result.job_id = str(job["id"])
        final_job = wait_for_terminal_job(config, session, result.job_id)
        result.status = str(final_job.get("status") or "unknown")
        result.failure_stage = final_job.get("failed_stage")
        result.error_code = final_job.get("error_code")
        result.error_message = final_job.get("error_message")
        result.result_file_id = final_job.get("result_file_id")
        read_translation_batch_diagnostics(config, session, result)
        if result.status == "succeeded":
            read_qa_evidence(config, session, result)
            docx_path = download_result_docx(config, session, run_dir, sample, result.job_id)
            result.docx_path = str(docx_path) if docx_path is not None else None
            result.docx_sha256 = sha256_file(docx_path) if docx_path is not None else None
            result.docx_openable = is_docx_openable(docx_path)
            result.docx_quality = analyze_docx_quality_file(docx_path) if result.docx_openable else {}
            result.docx_quality_flags = build_docx_quality_flags(result.docx_quality) if result.docx_openable else ["docx_not_openable"]
    except Exception as exc:  # noqa: BLE001 - 单样本异常需要进入报告，不能中断整批。
        result.status = "failed"
        result.error_code = exc.__class__.__name__
        result.error_message = str(exc)
    finally:
        result.elapsed_seconds = round(time.monotonic() - started, 3)
    return result


def upload_source_pdf(config: P1RegressionConfig, session: requests.Session, sample_path: Path) -> str:
    content = sample_path.read_bytes()
    response = session.post(
        api_url(config, "/api/v1/files/upload-url"),
        json={
            "filename": sample_path.name,
            "mime_type": "application/pdf",
            "size_bytes": len(content),
            "file_type": "source_pdf",
            "checksum_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
        },
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    authorization = response.json()
    upload_url = absolute_url(config, authorization["upload_url"])
    headers = dict(authorization.get("headers") or {})
    if is_same_origin(upload_url, config.base_url):
        headers["Authorization"] = session.headers["Authorization"]
    upload_response = requests.put(upload_url, data=content, headers=headers, timeout=config.request_timeout_seconds)
    upload_response.raise_for_status()
    return str(authorization["file_id"])


def create_document_job(
    config: P1RegressionConfig,
    session: requests.Session,
    manifest: dict[str, Any],
    sample: dict[str, Any],
    file_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source_file_id": file_id,
        "mode": sample.get("mode") or manifest.get("default_mode"),
        "document_language": sample.get("document_language") or manifest.get("default_document_language") or "en",
        "debug_full_text": config.debug_full_text,
    }
    for key in (
        "translation_term_set_id",
        "translation_term_version",
        "translation_profile_id",
        "translation_profile_version",
    ):
        value = sample.get(key) if key in sample else manifest.get(f"default_{key}")
        if value:
            payload[key] = value
    response = session.post(api_url(config, "/api/v1/document-jobs"), json=payload, timeout=config.request_timeout_seconds)
    response.raise_for_status()
    return response.json()["job"]


def wait_for_terminal_job(config: P1RegressionConfig, session: requests.Session, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + config.job_timeout_seconds
    last_transient_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            response = session.get(api_url(config, f"/api/v1/document-jobs/{job_id}"), timeout=config.request_timeout_seconds)
            response.raise_for_status()
        except TRANSIENT_REQUEST_ERRORS as exc:
            last_transient_error = exc
            time.sleep(config.poll_interval_seconds)
            continue
        job = response.json()
        if job.get("status") in TERMINAL_STATUSES:
            return job
        time.sleep(config.poll_interval_seconds)
    raise TimeoutError(f"等待 P1 翻译任务完成超时: {job_id}") from last_transient_error


def read_qa_evidence(config: P1RegressionConfig, session: requests.Session, result: P1SampleResult) -> None:
    response = get_with_transient_retries(
        config,
        session,
        api_url(config, f"/api/v1/document-jobs/{result.job_id}/translation-qa"),
    )
    payload = response.json()
    summary = payload.get("summary") or {}
    artifacts = payload.get("artifacts") or {}
    result.qa_available = bool(payload.get("available"))
    result.qa_availability_reason = payload.get("availability_reason")
    result.ai_call_count = int(summary.get("ai_call_count") or 0)
    result.term_trace_count = int(summary.get("term_trace_count") or 0)
    result.debug_full_text_enabled = bool(summary.get("debug_full_text_enabled"))
    result.source_comparison_available = bool(summary.get("source_comparison_available"))
    result.source_comparison_reason = summary.get("source_comparison_reason")
    result.debug_archive_file_count = len(artifacts.get("ai_debug_archive_file_ids") or [])
    result.debug_archive_expires_at = artifacts.get("ai_debug_archive_expires_at")
    result.debug_archive_expired = bool(artifacts.get("ai_debug_archive_expired"))
    result.debug_archive_contains_full_text = bool(artifacts.get("ai_debug_archive_contains_full_text"))
    observed_terms = {
        str(trace.get("source_term") or "").casefold()
        for trace in payload.get("term_traces") or []
        if str(trace.get("source_term") or "").strip()
    }
    expected = [term for term in result.expected_terms if term.strip()]
    result.matched_terms = [term for term in expected if term.casefold() in observed_terms]
    result.missing_terms = [term for term in expected if term.casefold() not in observed_terms]
    result.term_hit_rate = round(len(result.matched_terms) / len(expected), 4) if expected else 1.0


def read_translation_batch_diagnostics(config: P1RegressionConfig, session: requests.Session, result: P1SampleResult) -> None:
    if not result.job_id:
        return
    try:
        response = get_with_transient_retries(
            config,
            session,
            api_url(config, f"/api/v1/document-jobs/{result.job_id}/translation-batches"),
        )
        diagnostics = build_translation_batch_diagnostics(response.json())
    except Exception as exc:  # noqa: BLE001 - diagnostics must not hide the job's terminal result.
        record_translation_batch_diagnostics_unavailable(result, exc)
        return
    result.translation_batch_diagnostics_available = True
    result.translation_batch_diagnostics_error = None
    result.translation_batch_generation = diagnostics["generation"]
    result.translation_batch_summary = diagnostics["summary"]
    result.translation_batches = diagnostics["items"]
    result.translation_batch_warnings = diagnostics["warnings"]


def build_translation_batch_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    raw_items = payload.get("items") or []
    items = [sanitize_translation_batch_item(item) for item in raw_items if isinstance(item, dict)]
    status_counts: dict[str, int] = {}
    for item in items:
        status = item["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    parent_ids = {item["parent_batch_id"] for item in items if item["parent_batch_id"]}
    leaf_items = [item for item in items if item["batch_id"] not in parent_ids]
    provider_budgets = [item["provider_call_budget"] for item in items if item["provider_call_budget"] > 0]
    deterministic_counts = [item["deterministic_batch_count"] for item in items if item["deterministic_batch_count"] > 0]
    attention_count = sum(1 for item in items if is_translation_batch_attention(item))
    truncation_observed = any(
        item["truncation_retry"] or item["finish_reason"] == "length" or item["status"] == "split"
        for item in items
    )
    warnings: list[str] = []
    if not items:
        warnings.append("translation_batches_empty")
    if any(item["status"] == "failed" for item in items):
        warnings.append("translation_batches_failed")
    if any(item["status"] in ACTIVE_TRANSLATION_BATCH_STATUSES for item in items):
        warnings.append("translation_batches_active")
    if truncation_observed:
        warnings.append("translation_batch_truncation_observed")

    return {
        "generation": read_optional_int(payload.get("generation")),
        "summary": {
            "total": len(items),
            "status_counts": status_counts,
            "succeeded": status_counts.get("succeeded", 0),
            "failed": status_counts.get("failed", 0),
            "split": status_counts.get("split", 0),
            "active": sum(status_counts.get(status, 0) for status in ACTIVE_TRANSLATION_BATCH_STATUSES),
            "attention": attention_count,
            "leaf_total": len(leaf_items),
            "leaf_succeeded": sum(1 for item in leaf_items if item["status"] == "succeeded"),
            "leaf_failed": sum(1 for item in leaf_items if item["status"] == "failed"),
            "leaf_active": sum(1 for item in leaf_items if item["status"] in ACTIVE_TRANSLATION_BATCH_STATUSES),
            "item_count": sum(item["item_count"] for item in items),
            "char_count": sum(item["char_count"] for item in items),
            "ai_call_log_file_count": sum(item["ai_call_log_file_count"] for item in items),
            "provider_call_budget": max(provider_budgets) if provider_budgets else None,
            "deterministic_batch_count": max(deterministic_counts) if deterministic_counts else None,
            "truncation_observed": truncation_observed,
        },
        "items": items,
        "warnings": warnings,
    }


def sanitize_translation_batch_item(item: dict[str, Any]) -> dict[str, Any]:
    ai_call_log_file_ids = item.get("ai_call_log_file_ids") if isinstance(item.get("ai_call_log_file_ids"), list) else []
    return {
        "batch_id": read_string(item.get("batch_id")) or "unknown",
        "status": read_string(item.get("status")) or "unknown",
        "page_start": read_optional_int(item.get("page_start")),
        "page_end": read_optional_int(item.get("page_end")),
        "item_count": read_int(item.get("item_count")),
        "char_count": read_int(item.get("char_count")),
        "attempt_count": read_int(item.get("attempt_count")),
        "max_attempts": read_int(item.get("max_attempts")),
        "split_level": read_int(item.get("split_level")),
        "parent_batch_id": read_string(item.get("parent_batch_id")) or None,
        "root_batch_id": read_string(item.get("root_batch_id")) or None,
        "finish_reason": read_string(item.get("finish_reason")) or None,
        "retryable": bool(item.get("retryable")),
        "truncation_retry": bool(item.get("truncation_retry")),
        "provider_call_budget": read_int(item.get("provider_call_budget")),
        "deterministic_batch_count": read_int(item.get("deterministic_batch_count")),
        "error_code": read_string(item.get("error_code")) or None,
        "error_message": shorten_report_text(read_string(item.get("error_message"))),
        "result_file_id": read_string(item.get("result_file_id")) or None,
        "ai_call_log_file_count": len(ai_call_log_file_ids),
        "updated_at": read_string(item.get("updated_at")) or None,
    }


def is_translation_batch_attention(item: dict[str, Any]) -> bool:
    if item["status"] in {"failed", "split"}:
        return True
    return bool(item["truncation_retry"] or item["retryable"] or item["finish_reason"] == "length")


def record_translation_batch_diagnostics_unavailable(result: P1SampleResult, exc: BaseException) -> None:
    result.translation_batch_diagnostics_available = False
    result.translation_batch_diagnostics_error = f"{exc.__class__.__name__}: {shorten_report_text(str(exc)) or '-'}"
    result.translation_batch_generation = None
    result.translation_batch_summary = {}
    result.translation_batches = []
    result.translation_batch_warnings = ["translation_batch_diagnostics_unavailable"]


def read_string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def read_int(value: Any) -> int:
    parsed = read_optional_int(value)
    return parsed if parsed is not None else 0


def read_optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def shorten_report_text(value: str, limit: int = TRANSLATION_BATCH_ERROR_MESSAGE_LIMIT) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def download_result_docx(
    config: P1RegressionConfig,
    session: requests.Session,
    run_dir: Path,
    sample: dict[str, Any],
    job_id: str,
) -> Path | None:
    if not config.download_outputs:
        return None
    response = get_with_transient_retries(config, session, api_url(config, f"/api/v1/document-jobs/{job_id}/download-url"))
    payload = response.json()
    download_response = get_with_transient_retries(
        config,
        requests.Session(),
        absolute_url(config, payload["download_url"]),
    )
    output_path = run_dir / f"{sample['id']}-{job_id}.docx"
    output_path.write_bytes(download_response.content)
    return output_path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def build_report(
    config: P1RegressionConfig,
    manifest: dict[str, Any],
    run_dir: Path,
    results: list[P1SampleResult],
    pending_samples: list[dict[str, Any]],
    manual_signoff: dict[str, Any] | None,
) -> dict[str, Any]:
    result_payloads = [asdict(item) for item in results]
    succeeded = [item for item in results if p1_automated_sample_passed(item, config)]
    failed = [item for item in results if item not in succeeded]
    batch_diagnostics_summary = summarize_report_translation_batch_diagnostics(results)
    required_count = int(manifest.get("target_sample_count") or 3) if config.formal else 1
    automated_chain_met_target = len(results) >= required_count and not failed
    manual_quality = evaluate_manual_signoff(result_payloads, manual_signoff)
    p1_beta_ready = bool(config.formal and automated_chain_met_target and manual_quality["valid"])
    return {
        "run_dir": str(run_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            **asdict(config),
            "manifest_path": str(config.manifest_path),
            "runs_dir": str(config.runs_dir),
            "password": "***" if config.password else "",
            "bearer_token": "***" if config.bearer_token else "",
            "admin_token": "***" if config.admin_token else "",
        },
        "summary": {
            "configured_samples": len(manifest.get("samples") or []),
            "available_samples": len(results),
            "pending_samples": len(pending_samples),
            "pending_sample_ids": [sample.get("id") for sample in pending_samples],
            "required_sample_count": required_count,
            "formal": config.formal,
            "succeeded": len(succeeded),
            "failed": len(failed),
            "automated_chain_met_target": automated_chain_met_target,
            "manual_translation_quality_required": True,
            "manual_translation_quality": manual_quality,
            "p1_beta_ready": p1_beta_ready,
            "p1_beta_blocker": p1_beta_blocker_for(config, automated_chain_met_target, manual_quality),
            "debug_full_text_requested": config.debug_full_text,
            "translation_batch_diagnostics": batch_diagnostics_summary,
        },
        "results": result_payloads,
    }


def summarize_report_translation_batch_diagnostics(results: list[P1SampleResult]) -> dict[str, Any]:
    jobs_with_ids = [item for item in results if item.job_id]
    unavailable = [item for item in jobs_with_ids if not item.translation_batch_diagnostics_available]
    empty = [
        item
        for item in jobs_with_ids
        if item.translation_batch_diagnostics_available and not item.translation_batch_summary.get("total")
    ]
    truncation = [
        item
        for item in jobs_with_ids
        if item.translation_batch_summary.get("truncation_observed") is True
    ]
    failed_batches = [
        item
        for item in jobs_with_ids
        if int(item.translation_batch_summary.get("failed") or 0) > 0
    ]
    blockers: list[str] = []
    if unavailable:
        blockers.append("translation_batch_diagnostics_unavailable")
    if empty:
        blockers.append("translation_batch_diagnostics_empty")
    if failed_batches:
        blockers.append("translation_batches_failed")
    return {
        "jobs_checked": len(jobs_with_ids),
        "available": len(jobs_with_ids) - len(unavailable),
        "unavailable": len(unavailable),
        "empty": len(empty),
        "truncation_observed": len(truncation),
        "jobs_with_failed_batches": len(failed_batches),
        "blockers": blockers,
        "warnings": ["translation_batch_truncation_not_observed"] if jobs_with_ids and not truncation else [],
    }


def p1_automated_sample_passed(result: P1SampleResult, config: P1RegressionConfig) -> bool:
    debug_ok = True
    if config.debug_full_text:
        debug_ok = (
            result.debug_full_text_enabled
            and result.debug_archive_file_count > 0
            and result.debug_archive_contains_full_text
            and not result.debug_archive_expired
            and result.source_comparison_available
        )
    return (
        result.status == "succeeded"
        and result.docx_openable is True
        and result.qa_available
        and result.ai_call_count > 0
        and result.translation_batch_diagnostics_available
        and int(result.translation_batch_summary.get("total") or 0) > 0
        and result.term_hit_rate >= 1.0
        and debug_ok
    )


def build_preflight_report(config: P1RegressionConfig) -> dict[str, Any]:
    checks = [
        build_manifest_preflight_check(config),
        build_auth_preflight_check(config),
        build_runtime_preflight_check(config),
    ]
    blockers = list(dict.fromkeys(blocker for check in checks for blocker in check["blockers"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": config.base_url,
        "manifest_path": str(config.manifest_path),
        "ok": all(check["ok"] for check in checks),
        "blockers": blockers,
        "checks": checks,
    }


def build_manifest_preflight_check(config: P1RegressionConfig) -> dict[str, Any]:
    try:
        manifest = load_manifest(config.manifest_path)
        sample_root = resolve_sample_root(config.manifest_path, manifest)
        available = [sample for sample in manifest["samples"] if sample.get("source_status") == "available"]
        missing = [sample["filename"] for sample in available if not (sample_root / sample["filename"]).exists()]
        required = int(manifest.get("target_sample_count") or 3) if config.formal else 1
    except Exception as exc:  # noqa: BLE001 - preflight reports all blockers together.
        return {"name": "manifest", "ok": False, "blockers": ["p1_manifest_unreadable"], "details": {"error": str(exc)}}
    blockers: list[str] = []
    if missing:
        blockers.append("p1_available_pdf_missing")
    if len(available) < required:
        blockers.append("p1_available_sample_count_below_required")
    return {
        "name": "manifest",
        "ok": not blockers,
        "blockers": blockers,
        "details": {
            "sample_root": str(sample_root),
            "available_samples": len(available),
            "required_samples": required,
            "missing_pdf_files": missing,
        },
    }


def build_auth_preflight_check(config: P1RegressionConfig) -> dict[str, Any]:
    if not config.bearer_token.strip() and not config.password.strip() and not config.admin_token.strip():
        return {"name": "auth", "ok": False, "blockers": ["p1_auth_missing"], "details": {"username": config.username}}
    try:
        user = authenticate_for_preflight(config)
    except Exception as exc:  # noqa: BLE001
        return {"name": "auth", "ok": False, "blockers": ["p1_auth_unavailable"], "details": {"error": str(exc)}}
    role_ok = user.get("role") == "admin"
    return {
        "name": "auth",
        "ok": role_ok,
        "blockers": [] if role_ok else ["p1_auth_role_not_admin"],
        "details": {"username": user.get("username"), "role": user.get("role")},
    }


def authenticate_for_preflight(config: P1RegressionConfig) -> dict[str, Any]:
    """Validate P1 preflight admin access without creating translation jobs."""

    if config.admin_token.strip() and not config.bearer_token.strip() and not config.password.strip():
        session = build_readonly_preflight_session(config)
        response = session.get(api_url(config, "/api/v1/health/ops-alerts"), timeout=config.request_timeout_seconds)
        response.raise_for_status()
        return {"username": "admin", "role": "admin", "source": "admin_token"}
    session = build_authenticated_session(config)
    response = session.get(api_url(config, "/api/v1/auth/me"), timeout=config.request_timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    return {"username": payload.get("username"), "role": payload.get("role"), "source": "bearer_or_password"}


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def build_runtime_preflight_blockers(
    *,
    ready_status_code: int,
    checks: dict[str, Any],
    readiness: dict[str, Any],
    debug_full_text: bool,
) -> list[str]:
    """Return P1 runtime blockers from health/config-summary payloads."""

    blockers: list[str] = []
    blockers.extend(string_list(checks.get("p0_document_jobs_blockers")))
    if ready_status_code != 200:
        blockers.append("p1_health_not_ready")
    if checks.get("effective_repository_backend") != "mysql":
        blockers.append("document_jobs_metadata_store_not_mysql")
    if checks.get("document_jobs_worker_backend") != "celery":
        blockers.append("document_jobs_worker_backend_not_celery")
    if not str(checks.get("document_jobs_translation_batch_celery_queue") or "").strip():
        blockers.append("document_jobs_translation_batch_celery_queue_missing")
    if checks.get("translation_provider_backend") != "openai_compatible":
        blockers.append("translation_provider_backend_not_openai_compatible")
    if checks.get("translation_available") is not True:
        blockers.append("translation_not_available")
    if debug_full_text and checks.get("translation_debug_archive_enabled") is not True:
        blockers.append("translation_debug_archive_not_enabled")
    if readiness.get("en2zh_available") is not True:
        blockers.append("en2zh_not_available")
    return list(dict.fromkeys(blockers))


def build_runtime_preflight_check(config: P1RegressionConfig) -> dict[str, Any]:
    try:
        session = build_readonly_preflight_session(config)
        ready = session.get(api_url(config, "/api/v1/health/ready"), timeout=config.request_timeout_seconds)
        config_summary = session.get(
            api_url(config, "/api/v1/document-jobs/config-summary"),
            timeout=config.request_timeout_seconds,
        )
        ready_payload = ready.json()
        config_payload = config_summary.json()
    except Exception as exc:  # noqa: BLE001
        return {"name": "runtime", "ok": False, "blockers": ["p1_runtime_unreachable"], "details": {"error": str(exc)}}
    checks = ready_payload.get("dependency_checks") or {}
    readiness = config_payload.get("readiness") or {}
    blockers = build_runtime_preflight_blockers(
        ready_status_code=ready.status_code,
        checks=checks,
        readiness=readiness,
        debug_full_text=config.debug_full_text,
    )
    return {
        "name": "runtime",
        "ok": not blockers,
        "blockers": blockers,
        "details": {
            "health_status_code": ready.status_code,
            "config_summary_status_code": config_summary.status_code,
            "effective_repository_backend": checks.get("effective_repository_backend"),
            "document_jobs_worker_backend": checks.get("document_jobs_worker_backend"),
            "document_jobs_celery_queue": checks.get("document_jobs_celery_queue"),
            "document_jobs_translation_batch_celery_queue": checks.get("document_jobs_translation_batch_celery_queue"),
            "p0_document_jobs_ready": checks.get("p0_document_jobs_ready"),
            "p0_document_jobs_blockers": string_list(checks.get("p0_document_jobs_blockers")),
            "translation_provider_backend": checks.get("translation_provider_backend"),
            "translation_available": checks.get("translation_available"),
            "translation_debug_archive_enabled": checks.get("translation_debug_archive_enabled"),
            "en2zh_available": readiness.get("en2zh_available"),
        },
    }


def build_readonly_preflight_session(config: P1RegressionConfig) -> requests.Session:
    """Build a session for P1 read-only preflight checks without creating jobs."""

    if config.admin_token.strip() and not config.bearer_token.strip() and not config.password.strip():
        session = requests.Session()
        session.headers.update({"X-Admin-Token": config.admin_token.strip()})
        return session
    return build_authenticated_session(config)


def load_manual_signoff(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"P1 manual signoff 不存在: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("schema_version") != 1:
        raise ValueError("P1 manual signoff schema_version 必须为 1。")
    return payload


def evaluate_manual_signoff(result_payloads: list[dict[str, Any]], manual_signoff: dict[str, Any] | None) -> dict[str, Any]:
    expected_ids = [str(item.get("sample_id")) for item in result_payloads]
    base = {
        "present": manual_signoff is not None,
        "valid": False,
        "reviewer_role": None,
        "reviewer": None,
        "signed_at": None,
        "expected_sample_ids": expected_ids,
        "passed_sample_ids": [],
        "missing_sample_ids": expected_ids,
        "failed_sample_ids": [],
        "blockers": ["admin_manual_translation_quality_signoff_required"],
    }
    if manual_signoff is None:
        return base
    reviewer_role = str(manual_signoff.get("reviewer_role") or "").strip()
    reviewer = str(manual_signoff.get("reviewer") or "").strip()
    signed_at = str(manual_signoff.get("signed_at") or "").strip()
    entries = {
        str(item.get("sample_id")): item
        for item in manual_signoff.get("samples") or []
        if isinstance(item, dict) and item.get("sample_id")
    }
    passed = [
        sample_id
        for sample_id in expected_ids
        if str((entries.get(sample_id) or {}).get("verdict") or "").strip().lower() == "pass"
    ]
    missing = [sample_id for sample_id in expected_ids if sample_id not in entries]
    failed = [sample_id for sample_id in expected_ids if sample_id in entries and sample_id not in passed]
    blockers: list[str] = []
    if reviewer_role != "admin" or not reviewer:
        blockers.append("admin_manual_reviewer_required")
    if not signed_at:
        blockers.append("admin_manual_signed_at_required")
    if manual_signoff.get("final_signoff") is not True:
        blockers.append("admin_final_signoff_required")
    if missing or failed:
        blockers.append("admin_manual_translation_quality_signoff_incomplete")
    return {
        **base,
        "valid": not blockers and passed == expected_ids,
        "reviewer_role": reviewer_role or None,
        "reviewer": reviewer or None,
        "signed_at": signed_at or None,
        "passed_sample_ids": passed,
        "missing_sample_ids": missing,
        "failed_sample_ids": failed,
        "blockers": list(dict.fromkeys(blockers)),
    }


def apply_manual_signoff(run_dir: Path, signoff_path: Path) -> dict[str, Any]:
    report_path = run_dir / "report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"P1 report 不存在: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manual_quality = evaluate_manual_signoff(report.get("results") or [], load_manual_signoff(signoff_path))
    automated_chain_met_target = bool(report["summary"].get("automated_chain_met_target"))
    formal = bool(report["summary"].get("formal"))
    report["summary"]["manual_translation_quality"] = manual_quality
    report["summary"]["p1_beta_ready"] = bool(formal and automated_chain_met_target and manual_quality["valid"])
    report["summary"]["p1_beta_blocker"] = p1_beta_blocker_for_summary(formal, automated_chain_met_target, manual_quality)
    report.setdefault("config", {})["manual_signoff_path"] = str(signoff_path)
    write_report_files(run_dir, report)
    return report


def p1_beta_blocker_for(config: P1RegressionConfig, automated_chain_met_target: bool, manual_quality: dict[str, Any]) -> str | None:
    return p1_beta_blocker_for_summary(config.formal, automated_chain_met_target, manual_quality)


def p1_beta_blocker_for_summary(formal: bool, automated_chain_met_target: bool, manual_quality: dict[str, Any]) -> str | None:
    if not formal:
        return "p1_formal_mode_required_for_beta_ready"
    if not automated_chain_met_target:
        return "p1_automated_chain_target_not_met"
    if not manual_quality["valid"]:
        blockers = manual_quality.get("blockers") or []
        return str(blockers[0]) if blockers else "admin_manual_translation_quality_signoff_required"
    return None


def write_report_files(run_dir: Path, report: dict[str, Any]) -> None:
    write_json(run_dir / "report.json", report)
    (run_dir / "report.md").write_text(format_markdown_report(report), encoding="utf-8")
    (run_dir / "manual-signoff-template.yaml").write_text(format_manual_signoff_template(report), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def format_manual_signoff_template(report: dict[str, Any]) -> str:
    payload = {
        "schema_version": 1,
        "regression_run_dir": report["run_dir"],
        "reviewer_role": "admin",
        "reviewer": "",
        "signed_at": "",
        "final_signoff": False,
        "samples": [
            {
                "sample_id": item["sample_id"],
                "filename": item["filename"],
                "job_id": item.get("job_id") or "",
                "docx_sha256": item.get("docx_sha256") or "",
                "term_hit_rate": item.get("term_hit_rate"),
                "missing_terms": item.get("missing_terms") or [],
                "verdict": "",
                "notes": "",
            }
            for item in report.get("results") or []
        ],
    }
    header = (
        "# Fill after admin reviews generated Chinese DOCX and QA evidence.\n"
        "# Copy to manual-signoff.yaml, set every verdict to pass, then run:\n"
        "# python scripts/ops/run_p1_translation_regression.py --apply-manual-signoff <run_dir>\n"
    )
    return header + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def format_console_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    return (
        "P1 translation regression\n"
        f"run_dir: {report['run_dir']}\n"
        f"available: {summary['available_samples']}, pending: {summary['pending_samples']}, "
        f"required: {summary['required_sample_count']}, formal: {summary['formal']}\n"
        f"succeeded: {summary['succeeded']}, failed: {summary['failed']}\n"
        f"automated_chain_met_target: {summary['automated_chain_met_target']}\n"
        f"p1_beta_ready: {summary['p1_beta_ready']} ({summary['p1_beta_blocker'] or 'none'})"
    )


def format_preflight_report(report: dict[str, Any]) -> str:
    lines = [
        "P1 translation preflight",
        f"ok: {report['ok']}",
        f"base_url: {report['base_url']}",
        f"manifest: {report['manifest_path']}",
        f"blockers: {', '.join(report['blockers']) or 'none'}",
    ]
    for check in report["checks"]:
        lines.extend(["", f"[{check['name']}] ok: {check['ok']}", f"blockers: {', '.join(check['blockers']) or 'none'}"])
        lines.append(json.dumps(check["details"], ensure_ascii=False, indent=2))
    return "\n".join(lines)


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    manual = summary.get("manual_translation_quality") or {}
    lines = [
        "# P1 翻译回归报告",
        "",
        f"- 执行时间: `{report['generated_at']}`",
        f"- 结果目录: `{report['run_dir']}`",
        f"- Available samples: `{summary['available_samples']}`",
        f"- Pending samples: `{summary['pending_samples']}`",
        f"- Required samples: `{summary['required_sample_count']}`",
        f"- Formal: `{summary['formal']}`",
        f"- 成功: `{summary['succeeded']}`",
        f"- 失败: `{summary['failed']}`",
        f"- 自动链路是否达标: `{summary['automated_chain_met_target']}`",
        f"- P1 beta ready: `{summary['p1_beta_ready']}`",
        f"- P1 beta blocker: `{summary['p1_beta_blocker'] or 'none'}`",
        f"- Admin signoff valid: `{manual.get('valid', False)}`",
        "",
        "## Samples",
        "",
    ]
    for item in report.get("results") or []:
        lines.extend(
            [
                f"### {item['sample_id']} - {item['filename']}",
                "",
                f"- status: `{item['status']}`",
                f"- job_id: `{item.get('job_id') or '-'}`",
                f"- docx_openable: `{item.get('docx_openable')}`",
                f"- qa_available: `{item.get('qa_available')}`",
                f"- ai_call_count: `{item.get('ai_call_count')}`",
                f"- term_hit_rate: `{item.get('term_hit_rate')}`",
                f"- missing_terms: `{', '.join(item.get('missing_terms') or []) or 'none'}`",
                f"- source_comparison_available: `{item.get('source_comparison_available')}`",
                f"- debug_archive_expires_at: `{item.get('debug_archive_expires_at') or '-'}`",
                format_translation_batch_markdown(item),
                "",
            ]
        )
    return "\n".join(lines)


def format_translation_batch_markdown(item: dict[str, Any]) -> str:
    if not item.get("translation_batch_diagnostics_available"):
        error = item.get("translation_batch_diagnostics_error") or "unavailable"
        return f"- translation_batches: `unavailable` ({error})"
    summary = item.get("translation_batch_summary") or {}
    batches = item.get("translation_batches") or []
    lines = [
        (
            "- translation_batches: "
            f"`total={summary.get('total', 0)}, leaf={summary.get('leaf_succeeded', 0)}/{summary.get('leaf_total', 0)}, "
            f"failed={summary.get('failed', 0)}, split={summary.get('split', 0)}, "
            f"active={summary.get('active', 0)}, truncation_observed={summary.get('truncation_observed', False)}`"
        ),
        (
            "- translation_batch_budget: "
            f"`generation={item.get('translation_batch_generation')}, "
            f"provider_call_budget={summary.get('provider_call_budget') or '-'}, "
            f"deterministic_batch_count={summary.get('deterministic_batch_count') or '-'}`"
        ),
    ]
    if item.get("translation_batch_warnings"):
        lines.append(f"- translation_batch_warnings: `{', '.join(item.get('translation_batch_warnings') or [])}`")
    for batch in batches:
        error = ""
        if batch.get("error_code") or batch.get("error_message"):
            error = f", error={batch.get('error_code') or '-'}:{batch.get('error_message') or '-'}"
        lines.append(
            "  - "
            f"`{batch.get('batch_id')}` "
            f"status=`{batch.get('status')}` "
            f"pages=`{batch.get('page_start') or '-'}-{batch.get('page_end') or '-'}` "
            f"attempts=`{batch.get('attempt_count')}/{batch.get('max_attempts')}` "
            f"finish_reason=`{batch.get('finish_reason') or '-'}` "
            f"ai_logs=`{batch.get('ai_call_log_file_count', 0)}`"
            f"{error}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
