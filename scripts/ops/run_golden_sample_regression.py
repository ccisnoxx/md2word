from __future__ import annotations

# scripts/ops/run_golden_sample_regression.py: 批量执行 P0 Golden Sample PDF 到 Word 回归。

import hashlib
import json
import os
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "golden_samples" / "manifest.yaml"
DEFAULT_RUNS_DIR = REPO_ROOT / "tests" / "tmp" / "golden_sample_runs"
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}


@dataclass(frozen=True, slots=True)
class RegressionConfig:
    """Golden Sample 回归运行配置；默认可直接在 PyCharm 中编辑后运行。"""

    base_url: str = os.environ.get("GOLDEN_SAMPLE_BASE_URL", "http://127.0.0.1:8000")
    username: str = os.environ.get("GOLDEN_SAMPLE_USERNAME", "operator")
    password: str = os.environ.get("GOLDEN_SAMPLE_PASSWORD", "")
    bearer_token: str = os.environ.get("GOLDEN_SAMPLE_BEARER_TOKEN", "")
    manifest_path: Path = Path(os.environ.get("GOLDEN_SAMPLE_MANIFEST", str(DEFAULT_MANIFEST_PATH)))
    runs_dir: Path = Path(os.environ.get("GOLDEN_SAMPLE_RUNS_DIR", str(DEFAULT_RUNS_DIR)))
    request_timeout_seconds: int = int(os.environ.get("GOLDEN_SAMPLE_REQUEST_TIMEOUT_SECONDS", "30"))
    poll_interval_seconds: float = float(os.environ.get("GOLDEN_SAMPLE_POLL_INTERVAL_SECONDS", "5"))
    job_timeout_seconds: int = int(os.environ.get("GOLDEN_SAMPLE_JOB_TIMEOUT_SECONDS", "1800"))
    download_outputs: bool = os.environ.get("GOLDEN_SAMPLE_DOWNLOAD_OUTPUTS", "1") != "0"
    fail_on_missing_samples: bool = os.environ.get("GOLDEN_SAMPLE_FAIL_ON_MISSING_SAMPLES", "1") != "0"


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
    docx_openable: bool | None = None


@dataclass(frozen=True, slots=True)
class SampleInventory:
    """Golden Sample 文件盘点结果；orphan PDF 只报告，不参与正式通过率。"""

    manifest_samples: int
    manifest_matched_pdf_files: list[str]
    missing_pdf_files: list[str]
    orphan_pdf_files: list[str]


def main() -> None:
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
            )
        )

    if runnable_samples:
        session = build_authenticated_session(config)
        for sample in runnable_samples:
            results.append(run_one_sample(config, session, sample_root, run_dir, manifest, sample))

    report = build_report(config, manifest, run_dir, results, inventory)
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
            result.docx_openable = is_docx_openable(docx_path)
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
    while time.monotonic() < deadline:
        response = session.get(
            api_url(config, f"/api/v1/document-jobs/{job_id}"),
            timeout=config.request_timeout_seconds,
        )
        response.raise_for_status()
        job = response.json()
        if job.get("status") in TERMINAL_STATUSES:
            return job
        time.sleep(config.poll_interval_seconds)
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


def build_report(
    config: RegressionConfig,
    manifest: dict[str, Any],
    run_dir: Path,
    results: list[SampleResult],
    inventory: SampleInventory,
) -> dict[str, Any]:
    runnable = [item for item in results if item.status != "missing_pdf"]
    succeeded = [item for item in runnable if item.status == "succeeded" and item.docx_openable is not False]
    failed = [item for item in runnable if item.status != "succeeded" or item.docx_openable is False]
    missing = [item for item in results if item.status == "missing_pdf"]
    pass_rate = len(succeeded) / len(runnable) if runnable else 0.0
    target = float(manifest.get("target_success_rate") or 0.9)
    return {
        "run_dir": str(run_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            **asdict(config),
            "manifest_path": str(config.manifest_path),
            "runs_dir": str(config.runs_dir),
            "password": "***" if config.password else "",
            "bearer_token": "***" if config.bearer_token else "",
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
            "met_target": bool(runnable and pass_rate >= target),
        },
        "results": [asdict(item) for item in results],
    }


def write_report_files(run_dir: Path, report: dict[str, Any]) -> None:
    json_path = run_dir / "report.json"
    markdown_path = run_dir / "report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(format_markdown_report(report), encoding="utf-8")


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
        f"met_target: {summary['met_target']}"
    )


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
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
        f"- 是否达标: `{summary['met_target']}`",
        "",
        "| 样本 ID | 文件名 | 状态 | job_id | 失败阶段 | 错误码 | Word 可打开 | 耗时秒 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in report["results"]:
        lines.append(
            "| {sample_id} | {filename} | {status} | {job_id} | {failure_stage} | "
            "{error_code} | {docx_openable} | {elapsed_seconds} |".format(
                sample_id=item["sample_id"],
                filename=item["filename"],
                status=item["status"],
                job_id=item.get("job_id") or "",
                failure_stage=item.get("failure_stage") or "",
                error_code=item.get("error_code") or "",
                docx_openable=item.get("docx_openable"),
                elapsed_seconds=item.get("elapsed_seconds"),
            )
        )
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
