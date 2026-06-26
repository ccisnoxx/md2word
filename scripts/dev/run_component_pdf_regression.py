#!/usr/bin/env python3
"""Run local DOCX regression for governed electronic component PDF samples."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import formal_mineru_conversion
from scripts.dev.manage_component_pdf_samples import (
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    resolve_sample_root,
    sample_package_path,
    validate_manifest,
)


DEFAULT_RUNS_DIR = ROOT / "tests" / "tmp" / "component_pdf_regression"


@dataclass(frozen=True, slots=True)
class ComponentRegressionConfig:
    manifest_path: Path = DEFAULT_MANIFEST_PATH
    output_dir: Path = DEFAULT_RUNS_DIR
    sample_ids: tuple[str, ...] = ()
    timestamped: bool = True


@dataclass(slots=True)
class ComponentRegressionResult:
    sample_id: str
    brand: str
    category: str
    product: str
    title: str
    status: str
    input_path: str
    output_path: str
    elapsed_seconds: float = 0.0
    error_message: str = ""
    docx_sha256: str = ""
    docx_openable: bool = False
    acceptance_focus: list[str] = field(default_factory=list)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local component PDF MinerU-to-DOCX regression.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Component sample manifest path.")
    parser.add_argument("--output-dir", default=str(DEFAULT_RUNS_DIR), help="Directory for report and DOCX outputs.")
    parser.add_argument("--sample-id", action="append", default=[], help="Sample id to run. May be repeated.")
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="Write directly into --output-dir instead of creating a timestamped child directory.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report instead of a console summary.")
    return parser.parse_args(argv)


def run_regression(config: ComponentRegressionConfig) -> dict[str, Any]:
    manifest_path = config.manifest_path.expanduser().resolve()
    manifest = load_manifest(manifest_path)
    inventory = validate_manifest(manifest_path)
    sample_root = resolve_sample_root(manifest_path, manifest)
    run_dir = _create_run_dir(config.output_dir.expanduser().resolve(), timestamped=config.timestamped)
    requested_ids = set(config.sample_ids)
    samples = [
        sample
        for sample in manifest["samples"]
        if _is_enabled(sample) and (not requested_ids or str(sample.get("id")) in requested_ids)
    ]
    results = [run_one_sample(sample_root, run_dir, manifest, sample) for sample in samples]
    report = build_report(manifest_path, sample_root, run_dir, inventory, results)
    write_report_files(run_dir, report)
    return report


def run_one_sample(
    sample_root: Path,
    run_dir: Path,
    manifest: dict[str, Any],
    sample: dict[str, Any],
) -> ComponentRegressionResult:
    sample_id = str(sample["id"])
    input_path = sample_package_path(sample_root, sample).resolve()
    output_path = run_dir / "docx" / f"{sample_id}.docx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        formal_mineru_conversion.run_conversion(
            input_path=str(input_path),
            output_path=str(output_path),
            template_path=None,
            subscript_config=None,
            no_template=False,
            use_mineru_header_footer=False,
            document_language=str(sample.get("document_language") or manifest.get("default_document_language") or "auto"),
            translation_mode=str(sample.get("translation_mode") or manifest.get("default_translation_mode") or "direct"),
        )
        elapsed = time.monotonic() - started
        return ComponentRegressionResult(
            sample_id=sample_id,
            brand=str(sample.get("brand") or ""),
            category=str(sample.get("category") or ""),
            product=str(sample.get("product") or ""),
            title=str(sample.get("title") or ""),
            status="succeeded",
            input_path=str(input_path),
            output_path=str(output_path),
            elapsed_seconds=elapsed,
            docx_sha256=_sha256(output_path),
            docx_openable=_is_docx_openable(output_path),
            acceptance_focus=list(sample.get("acceptance_focus", [])),
        )
    except Exception as exc:  # noqa: BLE001 - regression reports per-sample failures.
        elapsed = time.monotonic() - started
        return ComponentRegressionResult(
            sample_id=sample_id,
            brand=str(sample.get("brand") or ""),
            category=str(sample.get("category") or ""),
            product=str(sample.get("product") or ""),
            title=str(sample.get("title") or ""),
            status="failed",
            input_path=str(input_path),
            output_path=str(output_path),
            elapsed_seconds=elapsed,
            error_message=str(exc),
            acceptance_focus=list(sample.get("acceptance_focus", [])),
        )


def build_report(
    manifest_path: Path,
    sample_root: Path,
    run_dir: Path,
    inventory: Any,
    results: list[ComponentRegressionResult],
) -> dict[str, Any]:
    succeeded = [result for result in results if result.status == "succeeded" and result.docx_openable]
    failed = [result for result in results if not (result.status == "succeeded" and result.docx_openable)]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "sample_root": str(sample_root),
        "run_dir": str(run_dir),
        "summary": {
            "sample_count": len(results),
            "succeeded": len(succeeded),
            "failed": len(failed),
            "manifest_sample_count": inventory.sample_count,
            "manifest_enabled_count": inventory.enabled_count,
            "manifest_runnable_count": inventory.runnable_count,
            "ok": not failed and bool(results),
        },
        "results": [asdict(result) for result in results],
    }


def write_report_files(run_dir: Path, report: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(format_markdown_report(report), encoding="utf-8")


def format_console_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "Component PDF regression report",
        f"run_dir: {report['run_dir']}",
        f"sample_count: {summary['sample_count']}",
        f"succeeded: {summary['succeeded']}",
        f"failed: {summary['failed']}",
        f"ok: {summary['ok']}",
    ]
    for result in report["results"]:
        lines.append(f"- {result['sample_id']}: {result['status']} -> {result['output_path']}")
    return "\n".join(lines)


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Component PDF Regression Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Manifest: `{report['manifest_path']}`",
        f"- Run dir: `{report['run_dir']}`",
        f"- Samples: {summary['sample_count']}",
        f"- Succeeded: {summary['succeeded']}",
        f"- Failed: {summary['failed']}",
        f"- OK: `{summary['ok']}`",
        "",
        "## Results",
        "",
        "| Sample | Brand | Category | Status | DOCX |",
        "|---|---|---|---|---|",
    ]
    for result in report["results"]:
        lines.append(
            "| "
            f"`{result['sample_id']}` | "
            f"{result['brand']} | "
            f"{result['category']} | "
            f"`{result['status']}` | "
            f"`{result['output_path']}` |"
        )
    lines.append("")
    lines.append("## Manual Acceptance Focus")
    lines.append("")
    for result in report["results"]:
        lines.append(f"### {result['sample_id']}")
        for focus in result.get("acceptance_focus", []):
            lines.append(f"- {focus}")
        if result.get("error_message"):
            lines.append(f"- Error: `{result['error_message']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _create_run_dir(output_dir: Path, *, timestamped: bool) -> Path:
    if timestamped:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = output_dir / run_id
    else:
        run_dir = output_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _is_enabled(sample: dict[str, Any]) -> bool:
    regression = sample.get("regression") if isinstance(sample.get("regression"), dict) else {}
    return regression.get("enabled", True) is not False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_docx_openable(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return "[Content_Types].xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = ComponentRegressionConfig(
        manifest_path=Path(args.manifest),
        output_dir=Path(args.output_dir),
        sample_ids=tuple(args.sample_id),
        timestamped=not args.no_timestamp,
    )
    report = run_regression(config)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_console_report(report))
    if not report["summary"]["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
