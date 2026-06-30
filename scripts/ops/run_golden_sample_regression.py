from __future__ import annotations

# scripts/ops/run_golden_sample_regression.py: 批量执行 P0 Golden Sample PDF 到 Word 回归。

import argparse
import hashlib
import json
import os
import sys
import time
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.renderer.docx_quality import analyze_docx_quality_file, build_docx_quality_flags

DEFAULT_MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "golden_samples" / "manifest.yaml"
DEFAULT_RUNS_DIR = REPO_ROOT / "tests" / "tmp" / "golden_sample_runs"
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
DEFAULT_REQUIRED_ROLE = "admin"


@dataclass(frozen=True, slots=True)
class RegressionConfig:
    """Golden Sample 回归运行配置；默认可直接在 PyCharm 中编辑后运行。"""

    base_url: str = os.environ.get("GOLDEN_SAMPLE_BASE_URL", "http://127.0.0.1:8000")
    username: str = os.environ.get("GOLDEN_SAMPLE_USERNAME", "admin")
    password: str = os.environ.get("GOLDEN_SAMPLE_PASSWORD", "")
    bearer_token: str = os.environ.get("GOLDEN_SAMPLE_BEARER_TOKEN", "")
    admin_token: str = os.environ.get("GOLDEN_SAMPLE_ADMIN_TOKEN", os.environ.get("ADMIN_TOKEN", ""))
    required_role: str = os.environ.get("GOLDEN_SAMPLE_REQUIRED_ROLE", DEFAULT_REQUIRED_ROLE)
    manifest_path: Path = Path(os.environ.get("GOLDEN_SAMPLE_MANIFEST", str(DEFAULT_MANIFEST_PATH)))
    runs_dir: Path = Path(os.environ.get("GOLDEN_SAMPLE_RUNS_DIR", str(DEFAULT_RUNS_DIR)))
    request_timeout_seconds: int = int(os.environ.get("GOLDEN_SAMPLE_REQUEST_TIMEOUT_SECONDS", "30"))
    poll_interval_seconds: float = float(os.environ.get("GOLDEN_SAMPLE_POLL_INTERVAL_SECONDS", "5"))
    job_timeout_seconds: int = int(os.environ.get("GOLDEN_SAMPLE_JOB_TIMEOUT_SECONDS", "1800"))
    download_outputs: bool = os.environ.get("GOLDEN_SAMPLE_DOWNLOAD_OUTPUTS", "1") != "0"
    fail_on_missing_samples: bool = os.environ.get("GOLDEN_SAMPLE_FAIL_ON_MISSING_SAMPLES", "1") != "0"
    manual_signoff_path: str = os.environ.get("GOLDEN_SAMPLE_MANUAL_SIGNOFF", "")


@dataclass(slots=True)
class SampleResult:
    sample_id: str
    filename: str
    title: str
    tags: list[str]
    status: str
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
    acceptance_focus: list[str] = field(default_factory=list)
    docx_quality: dict[str, Any] = field(default_factory=dict)
    docx_quality_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SampleInventory:
    """Golden Sample 文件盘点结果；orphan PDF 只报告，不参与正式通过率。"""

    manifest_samples: int
    manifest_matched_pdf_files: list[str]
    missing_pdf_files: list[str]
    orphan_pdf_files: list[str]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or update P0 Golden Sample regression reports.")
    parser.add_argument("--preflight", action="store_true", help="Check Golden Sample release prerequisites without running samples.")
    parser.add_argument("--preflight-output", metavar="PATH", help="Write --preflight JSON evidence to this path.")
    parser.add_argument("--apply-manual-signoff", metavar="RUN_DIR", help="Update an existing run_dir report with admin manual sign-off YAML.")
    parser.add_argument("--manual-signoff", metavar="PATH", help="Path to admin manual sign-off YAML.")
    args = parser.parse_args()
    if args.preflight:
        config = RegressionConfig()
        report = build_preflight_report(config)
        if args.preflight_output:
            write_preflight_report(Path(args.preflight_output), report)
        print(format_preflight_report(report))
        if not report["ok"]:
            raise SystemExit(1)
        return
    if args.apply_manual_signoff:
        run_dir = Path(args.apply_manual_signoff)
        signoff_path = Path(args.manual_signoff) if args.manual_signoff else run_dir / "manual-signoff.yaml"
        report = apply_manual_signoff(run_dir, signoff_path)
        print(format_console_report(report))
        if not report["summary"]["p0_release_ready"]:
            raise SystemExit(1)
        return

    config = RegressionConfig()
    report = run_regression(config)
    print(format_console_report(report))
    if not report["summary"]["met_target"]:
        raise SystemExit(1)


def run_regression(config: RegressionConfig) -> dict[str, Any]:
    manifest = load_manifest(config.manifest_path)
    run_dir = create_run_dir(config.runs_dir)
    sample_root = resolve_sample_root(config.manifest_path, manifest)
    all_samples = manifest.get("samples", [])
    samples = [item for item in all_samples if item.get("enabled", True)]
    inventory = build_sample_inventory(sample_root, samples, all_samples)
    matched_filenames = set(inventory.manifest_matched_pdf_files)
    runnable_samples = [item for item in samples if item["filename"] in matched_filenames]

    results: list[SampleResult] = []
    for sample in samples:
        sample_path = sample_root / sample["filename"]
        if sample_path.exists():
            continue
        results.append(
            SampleResult(
                sample_id=sample["id"],
                filename=sample["filename"],
                title=sample.get("title", ""),
                tags=list(sample.get("tags", [])),
                status="missing_pdf",
                error_message=f"样本 PDF 不存在: {sample_path}",
                acceptance_focus=list(sample.get("acceptance_focus", [])),
            )
        )

    if runnable_samples:
        session = build_authenticated_session(config)
        for sample in runnable_samples:
            results.append(run_one_sample(config, session, sample_root, run_dir, manifest, sample))

    manual_signoff = load_manual_signoff(Path(config.manual_signoff_path)) if config.manual_signoff_path.strip() else None
    report = build_report(config, manifest, run_dir, results, inventory, manual_signoff=manual_signoff)
    write_report_files(run_dir, report)
    if config.fail_on_missing_samples and not runnable_samples:
        report["summary"]["met_target"] = False
    return report


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Golden Sample manifest 不存在: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if data.get("schema_version") != 1:
        raise ValueError("Golden Sample manifest schema_version 必须为 1。")
    if not isinstance(data.get("samples"), list) or not data["samples"]:
        raise ValueError("Golden Sample manifest 必须包含非空 samples。")
    return data


def resolve_sample_root(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    raw_root = str(manifest.get("sample_root") or "tests/fixtures/golden_samples/pdfs")
    candidate = Path(raw_root)
    if candidate.is_absolute():
        return candidate
    return (REPO_ROOT / candidate).resolve() if manifest_path == DEFAULT_MANIFEST_PATH else (manifest_path.parent / candidate).resolve()


def create_run_dir(runs_dir: Path) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def build_sample_inventory(
    sample_root: Path,
    enabled_samples: list[dict[str, Any]],
    all_samples: list[dict[str, Any]],
) -> SampleInventory:
    manifest_filenames = {str(item["filename"]) for item in all_samples}
    enabled_filenames = {str(item["filename"]) for item in enabled_samples}
    pdf_filenames = list_sample_pdf_filenames(sample_root)
    matched = sorted(filename for filename in enabled_filenames if (sample_root / filename).exists())
    missing = sorted(filename for filename in enabled_filenames if not (sample_root / filename).exists())
    orphan = sorted(filename for filename in pdf_filenames if filename not in manifest_filenames)
    return SampleInventory(
        manifest_samples=len(enabled_samples),
        manifest_matched_pdf_files=matched,
        missing_pdf_files=missing,
        orphan_pdf_files=orphan,
    )


def build_preflight_report(config: RegressionConfig) -> dict[str, Any]:
    """Check Golden Sample release prerequisites before running slow sample jobs."""

    checks = [
        _build_manifest_preflight_check(config),
        _build_auth_preflight_check(config),
        _build_runtime_preflight_check(config),
    ]
    blockers = list(dict.fromkeys(blocker for check in checks for blocker in check["blockers"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": config.base_url,
        "manifest_path": str(config.manifest_path),
        "ok": all(bool(check["ok"]) for check in checks),
        "blockers": blockers,
        "checks": checks,
    }


def _build_manifest_preflight_check(config: RegressionConfig) -> dict[str, Any]:
    try:
        manifest = load_manifest(config.manifest_path)
        sample_root = resolve_sample_root(config.manifest_path, manifest)
        all_samples = manifest.get("samples", [])
        enabled_samples = [item for item in all_samples if item.get("enabled", True)]
        inventory = build_sample_inventory(sample_root, enabled_samples, all_samples)
    except Exception as exc:  # noqa: BLE001 - preflight reports config problems instead of raising.
        return {
            "name": "manifest",
            "ok": False,
            "blockers": ["golden_sample_manifest_unreadable"],
            "details": {"error": str(exc)},
        }

    blockers: list[str] = []
    if inventory.missing_pdf_files:
        blockers.append("golden_sample_pdf_missing")
    if not inventory.manifest_matched_pdf_files:
        blockers.append("golden_sample_no_runnable_pdf")
    return {
        "name": "manifest",
        "ok": not blockers,
        "blockers": blockers,
        "details": {
            "sample_root": str(sample_root),
            "manifest_samples": inventory.manifest_samples,
            "manifest_matched_pdf_files": inventory.manifest_matched_pdf_files,
            "missing_pdf_files": inventory.missing_pdf_files,
            "orphan_pdf_files": inventory.orphan_pdf_files,
        },
    }


def _build_auth_preflight_check(config: RegressionConfig) -> dict[str, Any]:
    credential_available = bool(config.bearer_token.strip() or config.password.strip() or config.admin_token.strip())
    details: dict[str, Any] = {
        "username": config.username,
        "required_role": config.required_role,
        "password_configured": bool(config.password.strip()),
        "bearer_token_configured": bool(config.bearer_token.strip()),
        "admin_token_configured": bool(config.admin_token.strip()),
    }
    if not credential_available:
        return {
            "name": "auth",
            "ok": False,
            "blockers": ["golden_sample_auth_missing"],
            "details": details,
        }

    try:
        auth_details = _authenticate_for_preflight(config)
    except Exception as exc:  # noqa: BLE001 - preflight reports auth problems without hiding manifest checks.
        details["error"] = str(exc)
        return {
            "name": "auth",
            "ok": False,
            "blockers": ["golden_sample_auth_unavailable"],
            "details": details,
        }

    details.update(auth_details)
    authenticated_role = str(auth_details.get("role") or "").strip()
    required_role = config.required_role.strip()
    role_ok = not required_role or authenticated_role == required_role
    return {
        "name": "auth",
        "ok": role_ok,
        "blockers": [] if role_ok else ["golden_sample_auth_role_not_admin"],
        "details": details,
    }


def _authenticate_for_preflight(config: RegressionConfig) -> dict[str, Any]:
    session = requests.Session()
    if config.bearer_token.strip():
        session.headers.update({"Authorization": f"Bearer {config.bearer_token.strip()}"})
        response = session.get(api_url(config, "/api/v1/auth/me"), timeout=config.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        return {
            "username": payload.get("username"),
            "role": payload.get("role"),
            "source": "bearer_token",
        }
    if config.admin_token.strip():
        session.headers.update({"X-Admin-Token": config.admin_token.strip()})
        response = session.get(api_url(config, "/api/v1/health/ops-alerts"), timeout=config.request_timeout_seconds)
        response.raise_for_status()
        return {
            "username": "admin",
            "role": "admin",
            "source": "admin_token",
        }

    response = session.post(
        api_url(config, "/api/v1/auth/login"),
        json={"username": config.username, "password": config.password},
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "username": payload.get("username"),
        "role": payload.get("role"),
        "source": "password_login",
    }


def _build_runtime_preflight_check(config: RegressionConfig) -> dict[str, Any]:
    ready_url = api_url(config, "/api/v1/health/ready")
    try:
        response = requests.get(ready_url, timeout=config.request_timeout_seconds)
    except requests.RequestException as exc:
        return {
            "name": "runtime-readiness",
            "ok": False,
            "blockers": ["golden_sample_api_unreachable"],
            "details": {"url": ready_url, "error": str(exc)},
        }

    try:
        payload = response.json()
    except ValueError as exc:
        return {
            "name": "runtime-readiness",
            "ok": False,
            "blockers": ["golden_sample_health_invalid_json"],
            "details": {"url": ready_url, "status_code": response.status_code, "error": str(exc)},
        }

    checks = payload.get("dependency_checks")
    if not isinstance(checks, dict):
        return {
            "name": "runtime-readiness",
            "ok": False,
            "blockers": ["golden_sample_health_dependency_checks_missing"],
            "details": {"url": ready_url, "status_code": response.status_code},
        }

    blockers = _string_list(checks.get("readiness_blockers")) + _string_list(checks.get("p0_document_jobs_blockers"))
    if checks.get("deployment_init_ready") is not True:
        blockers.append("deployment_init_not_ready")
    if checks.get("p0_document_jobs_ready") is not True:
        blockers.append("p0_document_jobs_not_ready")
    if checks.get("effective_repository_backend") != "mysql":
        blockers.append("document_jobs_metadata_store_not_mysql")
    if checks.get("document_jobs_worker_backend") != "celery":
        blockers.append("document_jobs_worker_backend_not_celery")
    if not str(checks.get("document_jobs_translation_batch_celery_queue") or "").strip():
        blockers.append("document_jobs_translation_batch_celery_queue_missing")
    if response.status_code != 200:
        blockers.append("golden_sample_health_http_status_not_ok")
    blockers = list(dict.fromkeys(blockers))
    return {
        "name": "runtime-readiness",
        "ok": response.status_code == 200 and not blockers,
        "blockers": blockers,
        "details": {
            "url": ready_url,
            "status_code": response.status_code,
            "deployment_init_ready": checks.get("deployment_init_ready"),
            "p0_document_jobs_ready": checks.get("p0_document_jobs_ready"),
            "effective_repository_backend": checks.get("effective_repository_backend"),
            "document_jobs_worker_backend": checks.get("document_jobs_worker_backend"),
            "document_jobs_celery_queue": checks.get("document_jobs_celery_queue"),
            "document_jobs_translation_batch_celery_queue": checks.get("document_jobs_translation_batch_celery_queue"),
            "readiness_blockers": _string_list(checks.get("readiness_blockers")),
            "p0_document_jobs_blockers": _string_list(checks.get("p0_document_jobs_blockers")),
        },
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def list_sample_pdf_filenames(sample_root: Path) -> list[str]:
    if not sample_root.exists():
        return []
    return sorted(
        path.name
        for path in sample_root.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def build_authenticated_session(config: RegressionConfig) -> requests.Session:
    session = requests.Session()
    token = config.bearer_token.strip() or login_for_token(config, session)
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def login_for_token(config: RegressionConfig, session: requests.Session) -> str:
    if not config.password:
        raise RuntimeError("请设置 GOLDEN_SAMPLE_PASSWORD，或设置 GOLDEN_SAMPLE_BEARER_TOKEN。")
    response = session.post(
        api_url(config, "/api/v1/auth/login"),
        json={"username": config.username, "password": config.password},
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("登录响应缺少 access_token。")
    return token


def run_one_sample(
    config: RegressionConfig,
    session: requests.Session,
    sample_root: Path,
    run_dir: Path,
    manifest: dict[str, Any],
    sample: dict[str, Any],
) -> SampleResult:
    started = time.monotonic()
    sample_path = sample_root / sample["filename"]
    result = SampleResult(
        sample_id=sample["id"],
        filename=sample["filename"],
        title=sample.get("title", ""),
        tags=list(sample.get("tags", [])),
        status="running",
        acceptance_focus=list(sample.get("acceptance_focus", [])),
    )
    try:
        file_id = upload_source_pdf(config, session, sample_path)
        result.file_id = file_id
        job = create_document_job(config, session, manifest, sample, file_id)
        result.job_id = job["id"]
        final_job = wait_for_terminal_job(config, session, job["id"])
        result.status = final_job.get("status", "unknown")
        result.failure_stage = final_job.get("failed_stage")
        result.error_code = final_job.get("error_code")
        result.error_message = final_job.get("error_message")
        result.result_file_id = final_job.get("result_file_id")
        if result.status == "succeeded":
            docx_path = download_result_docx(config, session, run_dir, sample, final_job["id"])
            result.docx_path = str(docx_path) if docx_path is not None else None
            result.docx_sha256 = sha256_file(docx_path) if docx_path is not None else None
            result.docx_openable = is_docx_openable(docx_path)
            result.docx_quality = analyze_docx_quality(docx_path) if result.docx_openable else {}
            result.docx_quality_flags = build_docx_quality_flags(result.docx_quality) if result.docx_openable else ["docx_not_openable"]
            if not result.docx_openable:
                result.status = "failed"
                result.error_code = "docx_not_openable"
                result.error_message = "生成 Word 不是可打开的 docx 包。"
    except Exception as exc:  # noqa: BLE001 - 回归脚本需要把单样本异常归入报告。
        result.status = "failed"
        result.error_code = exc.__class__.__name__
        result.error_message = str(exc)
    finally:
        result.elapsed_seconds = round(time.monotonic() - started, 3)
    return result


def upload_source_pdf(config: RegressionConfig, session: requests.Session, sample_path: Path) -> str:
    content = sample_path.read_bytes()
    checksum = "sha256:" + hashlib.sha256(content).hexdigest()
    response = session.post(
        api_url(config, "/api/v1/files/upload-url"),
        json={
            "filename": sample_path.name,
            "mime_type": "application/pdf",
            "size_bytes": len(content),
            "file_type": "source_pdf",
            "checksum_sha256": checksum,
        },
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    authorization = response.json()
    upload_url = absolute_url(config, authorization["upload_url"])
    headers = dict(authorization.get("headers") or {})
    if is_same_origin(upload_url, config.base_url):
        headers["Authorization"] = session.headers["Authorization"]
    upload_response = requests.put(
        upload_url,
        data=content,
        headers=headers,
        timeout=config.request_timeout_seconds,
    )
    upload_response.raise_for_status()
    return str(authorization["file_id"])


def create_document_job(
    config: RegressionConfig,
    session: requests.Session,
    manifest: dict[str, Any],
    sample: dict[str, Any],
    file_id: str,
) -> dict[str, Any]:
    response = session.post(
        api_url(config, "/api/v1/document-jobs"),
        json={
            "source_file_id": file_id,
            "mode": sample.get("mode") or manifest.get("default_mode") or "direct_pdf_to_word",
            "document_language": sample.get("document_language")
            or manifest.get("default_document_language")
            or "zh",
            "template_version_id": sample.get("template_version_id")
            if "template_version_id" in sample
            else manifest.get("default_template_version_id"),
            "term_version_id": sample.get("term_version_id"),
        },
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["job"]


def wait_for_terminal_job(config: RegressionConfig, session: requests.Session, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + config.job_timeout_seconds
    last_request_error: requests.RequestException | None = None
    while time.monotonic() < deadline:
        try:
            response = session.get(
                api_url(config, f"/api/v1/document-jobs/{job_id}"),
                timeout=config.request_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            last_request_error = exc
            time.sleep(config.poll_interval_seconds)
            continue
        job = response.json()
        if job.get("status") in TERMINAL_STATUSES:
            return job
        time.sleep(config.poll_interval_seconds)
    if last_request_error is not None:
        raise TimeoutError(f"等待任务完成超时，最近一次轮询失败: {job_id}: {last_request_error}") from last_request_error
    raise TimeoutError(f"等待任务完成超时: {job_id}")


def download_result_docx(
    config: RegressionConfig,
    session: requests.Session,
    run_dir: Path,
    sample: dict[str, Any],
    job_id: str,
) -> Path | None:
    if not config.download_outputs:
        return None
    response = session.get(
        api_url(config, f"/api/v1/document-jobs/{job_id}/download-url"),
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    download_response = requests.get(
        absolute_url(config, payload["download_url"]),
        timeout=config.request_timeout_seconds,
    )
    download_response.raise_for_status()
    output_path = run_dir / f"{sample['id']}-{job_id}.docx"
    output_path.write_bytes(download_response.content)
    return output_path


def is_docx_openable(path: Path | None) -> bool | None:
    if path is None:
        return None
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and "word/document.xml" in names


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def analyze_docx_quality(path: Path | None) -> dict[str, Any]:
    """Extract lightweight DOCX structure evidence for admin Golden Sample review."""

    return analyze_docx_quality_file(path)


def build_report(
    config: RegressionConfig,
    manifest: dict[str, Any],
    run_dir: Path,
    results: list[SampleResult],
    inventory: SampleInventory,
    manual_signoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runnable = [item for item in results if item.status != "missing_pdf"]
    succeeded = [item for item in runnable if item.status == "succeeded" and item.docx_openable is not False]
    failed = [item for item in runnable if item.status != "succeeded" or item.docx_openable is False]
    missing = [item for item in results if item.status == "missing_pdf"]
    pass_rate = len(succeeded) / len(runnable) if runnable else 0.0
    target = float(manifest.get("target_success_rate") or 0.9)
    automated_chain_met_target = bool(runnable and pass_rate >= target)
    quality_items = [item.docx_quality for item in succeeded if item.docx_quality]
    result_payloads = [asdict(item) for item in results]
    manual_quality = evaluate_manual_quality_signoff(result_payloads, manual_signoff)
    p0_release_ready = bool(automated_chain_met_target and manual_quality["valid"])
    p0_release_blocker = p0_release_blocker_for(
        automated_chain_met_target=automated_chain_met_target,
        manual_quality=manual_quality,
    )
    quality_flags = sorted(
        {
            str(flag)
            for item in succeeded
            for flag in item.docx_quality_flags
            if str(flag).strip()
        }
    )
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
            "configured_samples": len(results),
            "manifest_samples": inventory.manifest_samples,
            "manifest_matched_pdfs": len(inventory.manifest_matched_pdf_files),
            "runnable_samples": len(runnable),
            "missing_pdf_samples": len(missing),
            "orphan_pdf_count": len(inventory.orphan_pdf_files),
            "orphan_pdf_files": inventory.orphan_pdf_files,
            "succeeded": len(succeeded),
            "failed": len(failed),
            "pass_rate": round(pass_rate, 4),
            "target_success_rate": target,
            "met_target": automated_chain_met_target,
            "automated_chain_met_target": automated_chain_met_target,
            "manual_quality_required": True,
            "manual_quality": manual_quality,
            "p0_release_ready": p0_release_ready,
            "p0_release_blocker": p0_release_blocker,
            "quality_evidence_available": bool(quality_items),
            "docx_quality_flagged_samples": sum(1 for item in succeeded if item.docx_quality_flags),
            "docx_quality_flags": quality_flags,
            "editable_content_available_samples": sum(
                1 for item in quality_items if item.get("editable_content_available") is True
            ),
            "image_only_suspected_samples": sum(1 for item in quality_items if item.get("image_only_suspected") is True),
            "heading_paragraphs_total": sum(int(item.get("heading_paragraphs") or 0) for item in quality_items),
            "heading_like_unstyled_paragraphs_total": sum(
                int(item.get("heading_like_unstyled_paragraphs") or 0) for item in quality_items
            ),
            "numbering_paragraphs_total": sum(int(item.get("numbering_paragraphs") or 0) for item in quality_items),
            "manual_list_marker_paragraphs_total": sum(
                int(item.get("manual_list_marker_paragraphs") or 0) for item in quality_items
            ),
            "toc_tab_leader_paragraphs_total": sum(int(item.get("toc_tab_leader_paragraphs") or 0) for item in quality_items),
            "plain_toc_entry_paragraphs_total": sum(
                int(item.get("plain_toc_entry_paragraphs") or 0) for item in quality_items
            ),
            "wide_table_count_total": sum(int(item.get("wide_table_count") or 0) for item in quality_items),
            "keep_next_paragraphs_total": sum(int(item.get("keep_next_paragraphs") or 0) for item in quality_items),
            "table_header_rows_total": sum(int(item.get("table_header_rows") or 0) for item in quality_items),
            "table_no_split_rows_total": sum(int(item.get("table_no_split_rows") or 0) for item in quality_items),
            "shaded_table_cells_total": sum(int(item.get("shaded_table_cells") or 0) for item in quality_items),
            "table_cell_zero_spacing_paragraphs_total": sum(
                int(item.get("table_cell_zero_spacing_paragraphs") or 0) for item in quality_items
            ),
            "landscape_sections_total": sum(int(item.get("landscape_sections") or 0) for item in quality_items),
            "latex_residue_total": sum(int(item.get("latex_residue_count") or 0) for item in quality_items),
        },
        "results": result_payloads,
    }


def load_manual_signoff(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Golden Sample manual sign-off 不存在: {path}")
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    if payload.get("schema_version") != 1:
        raise ValueError("Golden Sample manual sign-off schema_version 必须为 1。")
    return payload


def apply_manual_signoff(run_dir: Path, signoff_path: Path) -> dict[str, Any]:
    report_path = run_dir / "report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Golden Sample report 不存在: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manual_signoff = load_manual_signoff(signoff_path)
    apply_manual_signoff_to_report(report, manual_signoff, signoff_path=signoff_path)
    write_report_files(run_dir, report)
    return report


def apply_manual_signoff_to_report(
    report: dict[str, Any],
    manual_signoff: dict[str, Any] | None,
    *,
    signoff_path: Path | None = None,
) -> None:
    summary = report["summary"]
    manual_quality = evaluate_manual_quality_signoff(report.get("results") or [], manual_signoff)
    automated_chain_met_target = bool(summary.get("automated_chain_met_target"))
    summary["manual_quality_required"] = True
    summary["manual_quality"] = manual_quality
    summary["p0_release_ready"] = bool(automated_chain_met_target and manual_quality["valid"])
    summary["p0_release_blocker"] = p0_release_blocker_for(
        automated_chain_met_target=automated_chain_met_target,
        manual_quality=manual_quality,
    )
    if signoff_path is not None:
        report.setdefault("config", {})["manual_signoff_path"] = str(signoff_path)


def evaluate_manual_quality_signoff(
    result_payloads: list[dict[str, Any]],
    manual_signoff: dict[str, Any] | None,
) -> dict[str, Any]:
    expected_results = [item for item in result_payloads if item.get("status") != "missing_pdf"]
    expected_sample_ids = [str(item.get("sample_id")) for item in expected_results]
    base: dict[str, Any] = {
        "present": manual_signoff is not None,
        "valid": False,
        "reviewer_role": None,
        "reviewer": None,
        "signed_at": None,
        "expected_sample_ids": expected_sample_ids,
        "passed_sample_ids": [],
        "missing_sample_ids": [],
        "failed_sample_ids": [],
        "mismatch_sample_ids": [],
        "flagged_without_notes_sample_ids": [],
        "blockers": [],
    }
    if manual_signoff is None:
        base["missing_sample_ids"] = expected_sample_ids
        base["blockers"] = ["admin_manual_word_quality_signoff_required"]
        return base

    reviewer_role = str(manual_signoff.get("reviewer_role") or "").strip()
    reviewer = str(manual_signoff.get("reviewer") or "").strip()
    signed_at = str(manual_signoff.get("signed_at") or "").strip()
    base["reviewer_role"] = reviewer_role or None
    base["reviewer"] = reviewer or None
    base["signed_at"] = signed_at or None

    blockers: list[str] = []
    if reviewer_role != "admin" or not reviewer:
        blockers.append("admin_manual_reviewer_required")
    if not signed_at:
        blockers.append("admin_manual_signed_at_required")
    if manual_signoff.get("final_signoff") is not True:
        blockers.append("admin_final_signoff_required")

    sample_entries = {
        str(item.get("sample_id")): item
        for item in manual_signoff.get("samples") or []
        if isinstance(item, dict) and item.get("sample_id")
    }
    results_by_id = {str(item.get("sample_id")): item for item in expected_results}
    passed_sample_ids: list[str] = []
    missing_sample_ids: list[str] = []
    failed_sample_ids: list[str] = []
    mismatch_sample_ids: list[str] = []
    flagged_without_notes_sample_ids: list[str] = []
    for sample_id in expected_sample_ids:
        result = results_by_id[sample_id]
        entry = sample_entries.get(sample_id)
        if entry is None:
            missing_sample_ids.append(sample_id)
            continue
        if str(entry.get("verdict") or "").strip().lower() != "pass":
            failed_sample_ids.append(sample_id)
            continue
        if not _manual_signoff_entry_matches_result(entry, result):
            mismatch_sample_ids.append(sample_id)
            continue
        if result.get("docx_quality_flags") and not str(entry.get("notes") or "").strip():
            flagged_without_notes_sample_ids.append(sample_id)
        passed_sample_ids.append(sample_id)

    if missing_sample_ids or failed_sample_ids or mismatch_sample_ids:
        blockers.append("admin_manual_word_quality_signoff_incomplete")
    if flagged_without_notes_sample_ids:
        blockers.append("admin_manual_quality_flag_notes_required")

    base["passed_sample_ids"] = passed_sample_ids
    base["missing_sample_ids"] = missing_sample_ids
    base["failed_sample_ids"] = failed_sample_ids
    base["mismatch_sample_ids"] = mismatch_sample_ids
    base["flagged_without_notes_sample_ids"] = flagged_without_notes_sample_ids
    base["blockers"] = list(dict.fromkeys(blockers))
    base["valid"] = not base["blockers"] and passed_sample_ids == expected_sample_ids
    return base


def _manual_signoff_entry_matches_result(entry: dict[str, Any], result: dict[str, Any]) -> bool:
    expected_job_id = str(result.get("job_id") or "").strip()
    signed_job_id = str(entry.get("job_id") or "").strip()
    if expected_job_id and signed_job_id != expected_job_id:
        return False
    expected_sha256 = str(result.get("docx_sha256") or "").strip()
    signed_sha256 = str(entry.get("docx_sha256") or "").strip()
    if expected_sha256 and signed_sha256 != expected_sha256:
        return False
    expected_filename = str(result.get("filename") or "").strip()
    signed_filename = str(entry.get("filename") or "").strip()
    return not expected_filename or signed_filename == expected_filename


def p0_release_blocker_for(
    *,
    automated_chain_met_target: bool,
    manual_quality: dict[str, Any],
) -> str | None:
    if not automated_chain_met_target:
        return "automated_chain_target_not_met"
    if not manual_quality["valid"]:
        blockers = manual_quality.get("blockers") or []
        return str(blockers[0]) if blockers else "admin_manual_word_quality_signoff_required"
    return None


def write_report_files(run_dir: Path, report: dict[str, Any]) -> None:
    json_path = run_dir / "report.json"
    markdown_path = run_dir / "report.md"
    signoff_template_path = run_dir / "manual-signoff-template.yaml"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(format_markdown_report(report), encoding="utf-8")
    signoff_template_path.write_text(format_manual_signoff_template(report), encoding="utf-8")


def write_preflight_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
                "docx_quality_flags": item.get("docx_quality_flags") or [],
                "machine_evidence": {
                    "editable_content_available": (item.get("docx_quality") or {}).get("editable_content_available"),
                    "image_only_suspected": (item.get("docx_quality") or {}).get("image_only_suspected"),
                    "heading_like_unstyled_paragraphs": (item.get("docx_quality") or {}).get(
                        "heading_like_unstyled_paragraphs"
                    ),
                    "manual_list_marker_paragraphs": (item.get("docx_quality") or {}).get("manual_list_marker_paragraphs"),
                    "plain_toc_entry_paragraphs": (item.get("docx_quality") or {}).get("plain_toc_entry_paragraphs"),
                    "wide_table_count": (item.get("docx_quality") or {}).get("wide_table_count"),
                    "landscape_sections": (item.get("docx_quality") or {}).get("landscape_sections"),
                    "latex_residue_count": (item.get("docx_quality") or {}).get("latex_residue_count"),
                },
                "verdict": "",
                "notes": "",
            }
            for item in report.get("results") or []
            if item.get("status") != "missing_pdf"
        ],
    }
    header = (
        "# Fill this file after admin opens each generated DOCX.\n"
        "# If docx_quality_flags is not empty and the verdict is pass, notes must explain the admin override.\n"
        "# Copy to manual-signoff.yaml, set every verdict to pass, then run:\n"
        "# python scripts/ops/run_golden_sample_regression.py --apply-manual-signoff <run_dir>\n"
    )
    return header + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def format_console_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    orphan_files = ", ".join(summary["orphan_pdf_files"]) or "none"
    return (
        "Golden Sample regression\n"
        f"run_dir: {report['run_dir']}\n"
        f"manifest: {summary['manifest_samples']}, manifest_matched: {summary['manifest_matched_pdfs']}, "
        f"runnable: {summary['runnable_samples']}, missing_pdf: {summary['missing_pdf_samples']}\n"
        f"orphan_pdf: {summary['orphan_pdf_count']} ({orphan_files})\n"
        f"succeeded: {summary['succeeded']}, failed: {summary['failed']}, "
        f"pass_rate: {summary['pass_rate']:.2%}, target: {summary['target_success_rate']:.0%}\n"
        f"automated_chain_met_target: {summary['automated_chain_met_target']}\n"
        f"p0_release_ready: {summary['p0_release_ready']} ({summary['p0_release_blocker'] or 'none'})"
    )


def format_preflight_report(report: dict[str, Any]) -> str:
    lines = [
        "Golden Sample preflight",
        f"ok: {report['ok']}",
        f"base_url: {report['base_url']}",
        f"manifest: {report['manifest_path']}",
        f"blockers: {', '.join(report['blockers']) or 'none'}",
    ]
    for check in report["checks"]:
        lines.extend(
            [
                "",
                f"[{check['name']}] ok: {check['ok']}",
                f"blockers: {', '.join(check['blockers']) or 'none'}",
                json.dumps(check["details"], ensure_ascii=False, indent=2),
            ]
        )
    return "\n".join(lines)


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    manual_quality = summary.get("manual_quality") or {}
    lines = [
        "# Golden Sample 回归报告",
        "",
        f"- 执行时间: `{report['generated_at']}`",
        f"- 结果目录: `{report['run_dir']}`",
        f"- Manifest 样本数: `{summary['manifest_samples']}`",
        f"- 正式匹配 PDF 数: `{summary['manifest_matched_pdfs']}`",
        f"- 实际执行: `{summary['runnable_samples']}`",
        f"- 缺少 PDF: `{summary['missing_pdf_samples']}`",
        f"- Manifest 外 PDF 数: `{summary['orphan_pdf_count']}`",
        f"- Manifest 外 PDF: `{', '.join(summary['orphan_pdf_files']) or 'none'}`",
        f"- 成功: `{summary['succeeded']}`",
        f"- 失败: `{summary['failed']}`",
        f"- 成功率: `{summary['pass_rate']:.2%}`",
        f"- 目标: `{summary['target_success_rate']:.0%}`",
        f"- 自动链路是否达标: `{summary['automated_chain_met_target']}`",
        f"- P0 是否可发布: `{summary['p0_release_ready']}`",
        f"- P0 发布阻断: `{summary['p0_release_blocker'] or 'none'}`",
        f"- Admin 人工签字有效: `{manual_quality.get('valid', False)}`",
        f"- Admin reviewer: `{manual_quality.get('reviewer') or '-'}`",
        f"- Admin signed_at: `{manual_quality.get('signed_at') or '-'}`",
        f"- Admin 签字 blockers: `{', '.join(manual_quality.get('blockers') or []) or 'none'}`",
        f"- DOCX 质量证据可用: `{summary.get('quality_evidence_available', False)}`",
        f"- DOCX 质量标记样本数: `{summary.get('docx_quality_flagged_samples', 0)}`",
        f"- DOCX 质量标记: `{', '.join(summary.get('docx_quality_flags') or []) or 'none'}`",
        f"- 可编辑内容证据样本数: `{summary.get('editable_content_available_samples', 0)}`",
        f"- 疑似整页截图样本数: `{summary.get('image_only_suspected_samples', 0)}`",
        f"- Heading 段落总数: `{summary.get('heading_paragraphs_total', 0)}`",
        f"- 疑似标题未样式化段落总数: `{summary.get('heading_like_unstyled_paragraphs_total', 0)}`",
        f"- Word numbering 段落总数: `{summary.get('numbering_paragraphs_total', 0)}`",
        f"- 手写列表符号段落总数: `{summary.get('manual_list_marker_paragraphs_total', 0)}`",
        f"- TOC 点线制表位段落总数: `{summary.get('toc_tab_leader_paragraphs_total', 0)}`",
        f"- 纯文本目录项段落总数: `{summary.get('plain_toc_entry_paragraphs_total', 0)}`",
        f"- 宽表总数: `{summary.get('wide_table_count_total', 0)}`",
        f"- 表头重复行总数: `{summary.get('table_header_rows_total', 0)}`",
        f"- 表格防跨页断行总数: `{summary.get('table_no_split_rows_total', 0)}`",
        f"- 表格零段前后距段落总数: `{summary.get('table_cell_zero_spacing_paragraphs_total', 0)}`",
        f"- 表头底纹单元格总数: `{summary.get('shaded_table_cells_total', 0)}`",
        f"- Landscape section 总数: `{summary.get('landscape_sections_total', 0)}`",
        f"- LaTeX 残留总数: `{summary.get('latex_residue_total', 0)}`",
        "",
        "| 样本 ID | 文件名 | 状态 | job_id | 失败阶段 | 错误码 | Word 可打开 | DOCX flags | 可编辑证据 | 疑似截图 | Heading | 疑似标题 | Numbering | 手写列表 | TOC Tabs | 纯文本 TOC | 宽表 | Landscape | TblHeader | NoSplit | CellSpacing0 | LaTeX 残留 | 表格 | 耗时秒 |",
        "|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for item in report["results"]:
        quality = item.get("docx_quality") or {}
        lines.append(
            "| {sample_id} | {filename} | {status} | {job_id} | {failure_stage} | {error_code} | "
            "{docx_openable} | {docx_quality_flags} | {editable_content_available} | {image_only_suspected} | "
            "{heading_paragraphs} | {heading_like_unstyled_paragraphs} | {numbering_paragraphs} | "
            "{manual_list_marker_paragraphs} | {toc_tab_leader_paragraphs} | {plain_toc_entry_paragraphs} | "
            "{wide_table_count} | {landscape_sections} | {table_header_rows} | {table_no_split_rows} | "
            "{table_cell_zero_spacing_paragraphs} | "
            "{latex_residue_count} | "
            "{table_shapes} | {elapsed_seconds} |".format(
                sample_id=item["sample_id"],
                filename=item["filename"],
                status=item["status"],
                job_id=item.get("job_id") or "",
                failure_stage=item.get("failure_stage") or "",
                error_code=item.get("error_code") or "",
                docx_openable=item.get("docx_openable"),
                docx_quality_flags=", ".join(item.get("docx_quality_flags") or []),
                editable_content_available=quality.get("editable_content_available", ""),
                image_only_suspected=quality.get("image_only_suspected", ""),
                heading_paragraphs=quality.get("heading_paragraphs", ""),
                heading_like_unstyled_paragraphs=quality.get("heading_like_unstyled_paragraphs", ""),
                numbering_paragraphs=quality.get("numbering_paragraphs", ""),
                manual_list_marker_paragraphs=quality.get("manual_list_marker_paragraphs", ""),
                toc_tab_leader_paragraphs=quality.get("toc_tab_leader_paragraphs", ""),
                plain_toc_entry_paragraphs=quality.get("plain_toc_entry_paragraphs", ""),
                wide_table_count=quality.get("wide_table_count", ""),
                landscape_sections=quality.get("landscape_sections", ""),
                table_header_rows=quality.get("table_header_rows", ""),
                table_no_split_rows=quality.get("table_no_split_rows", ""),
                table_cell_zero_spacing_paragraphs=quality.get("table_cell_zero_spacing_paragraphs", ""),
                latex_residue_count=quality.get("latex_residue_count", ""),
                table_shapes=", ".join(quality.get("table_shapes") or []),
                elapsed_seconds=item.get("elapsed_seconds"),
            )
        )
    lines.extend(["", "## Admin 人工验收关注点", ""])
    for item in report["results"]:
        lines.append(f"### {item['sample_id']} / {item['filename']}")
        focus_items = item.get("acceptance_focus") or []
        if focus_items:
            lines.extend(f"- {focus}" for focus in focus_items)
        else:
            lines.append("- 未在 manifest 中配置 acceptance_focus。")
        lines.append("")
    return "\n".join(lines) + "\n"


def api_url(config: RegressionConfig, path: str) -> str:
    return urljoin(config.base_url.rstrip("/") + "/", path.lstrip("/"))


def absolute_url(config: RegressionConfig, raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme and parsed.netloc:
        return raw_url
    return urljoin(config.base_url.rstrip("/") + "/", raw_url.lstrip("/"))


def is_same_origin(url: str, base_url: str) -> bool:
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    return (parsed_url.scheme, parsed_url.netloc) == (parsed_base.scheme, parsed_base.netloc)


if __name__ == "__main__":
    main()
