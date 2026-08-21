#!/usr/bin/env python3
"""运行受治理电子元器件样本的本地 DOCX 回归与人工视觉签字。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml


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
TARGET_WORD_CLIENTS = {"word", "wps"}
VISUAL_CHECKS = (
    "unexpected_blank_pages",
    "key_content_group_placement",
    "table_squeeze",
    "column_balance",
    "image_clarity",
    "font_substitution",
)


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
    input_sha256: str = ""
    docx_sha256: str = ""
    docx_openable: bool = False
    acceptance_focus: list[str] = field(default_factory=list)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行电子元器件 MinerU-to-DOCX 本地回归。")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="样本 manifest 路径。")
    parser.add_argument("--output-dir", default=str(DEFAULT_RUNS_DIR), help="报告和 DOCX 输出目录。")
    parser.add_argument("--sample-id", action="append", default=[], help="要运行的样本 ID，可重复指定。")
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="直接写入 --output-dir，不创建时间戳子目录。",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告，不输出控制台摘要。")
    parser.add_argument("--apply-manual-signoff", metavar="RUN_DIR", help="校验并应用指定批次的人工视觉签字。")
    parser.add_argument("--manual-signoff", help="人工签字 YAML；默认使用 RUN_DIR/manual-signoff.yaml。")
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
            input_sha256=_sha256_tree(input_path),
            docx_sha256=_sha256(output_path),
            docx_openable=_is_docx_openable(output_path),
            acceptance_focus=list(sample.get("acceptance_focus", [])),
        )
    except Exception as exc:  # noqa: BLE001 - 回归报告需要逐样本记录失败。
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
            input_sha256=_sha256_tree(input_path),
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
        "source_revision": _source_revision(),
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
        "manual_visual_acceptance": {
            "present": False,
            "valid": False,
            "accepted": False,
            "blockers": ["manual_visual_signoff_required"],
        },
        "results": [asdict(result) for result in results],
    }


def write_report_files(run_dir: Path, report: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(format_markdown_report(report), encoding="utf-8")
    (run_dir / "manual-signoff-template.yaml").write_text(format_manual_signoff_template(report), encoding="utf-8")


def apply_manual_signoff(run_dir: Path, signoff_path: Path) -> dict[str, Any]:
    """把与当前产物和源码版本匹配的 Word/WPS 签字写回回归报告。"""

    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    signoff = yaml.safe_load(signoff_path.read_text(encoding="utf-8"))
    report["manual_visual_acceptance"] = evaluate_manual_signoff(report, signoff)
    write_report_files(run_dir, report)
    return report


def evaluate_manual_signoff(report: dict[str, Any], signoff: Any) -> dict[str, Any]:
    """校验签字完整性；视觉结论只记录，不伪装成确定性 OOXML blocker。"""

    blockers: list[str] = []
    mismatch_sample_ids: list[str] = []
    incomplete_sample_ids: list[str] = []
    conditional_sample_ids: list[str] = []
    failed_sample_ids: list[str] = []
    if not isinstance(signoff, dict):
        return {
            "present": signoff is not None,
            "valid": False,
            "accepted": False,
            "blockers": ["manual_visual_signoff_invalid"],
        }
    if (
        signoff.get("schema_version") != 1
        or signoff.get("final_signoff") is not True
        or not str(signoff.get("reviewer") or "").strip()
        or not str(signoff.get("signed_at") or "").strip()
    ):
        blockers.append("manual_visual_signoff_incomplete")
    if signoff.get("source_revision") != report.get("source_revision"):
        blockers.append("manual_visual_signoff_revision_mismatch")

    entries = signoff.get("samples") if isinstance(signoff.get("samples"), list) else []
    by_id = {str(entry.get("sample_id")): entry for entry in entries if isinstance(entry, dict)}
    expected_results = [
        result
        for result in report.get("results") or []
        if result.get("status") == "succeeded" and result.get("docx_openable") is True
    ]
    for result in expected_results:
        sample_id = str(result.get("sample_id") or "")
        entry = by_id.get(sample_id)
        if (
            entry is None
            or entry.get("input_sha256") != result.get("input_sha256")
            or entry.get("docx_sha256") != result.get("docx_sha256")
        ):
            mismatch_sample_ids.append(sample_id)
            continue
        checks = entry.get("checks") if isinstance(entry.get("checks"), dict) else {}
        page_count = entry.get("actual_page_count")
        verdict = str(entry.get("verdict") or "").strip().lower()
        check_values = [str(checks.get(name) or "").strip().lower() for name in VISUAL_CHECKS]
        complete = (
            str(entry.get("client") or "").strip().lower() in TARGET_WORD_CLIENTS
            and bool(str(entry.get("client_version") or "").strip())
            and isinstance(page_count, int)
            and not isinstance(page_count, bool)
            and page_count > 0
            and verdict in {"pass", "conditional", "fail"}
            and all(value in {"pass", "fail", "n/a"} for value in check_values)
        )
        needs_notes = verdict != "pass" or any(value != "pass" for value in check_values)
        contradictory_pass = verdict == "pass" and "fail" in check_values
        if not complete or contradictory_pass or (needs_notes and not str(entry.get("notes") or "").strip()):
            incomplete_sample_ids.append(sample_id)
        if verdict == "conditional":
            conditional_sample_ids.append(sample_id)
        if verdict == "fail":
            failed_sample_ids.append(sample_id)

    if mismatch_sample_ids:
        blockers.append("manual_visual_signoff_artifact_mismatch")
    if incomplete_sample_ids or len(by_id) != len(expected_results) or len(entries) != len(by_id):
        blockers.append("manual_visual_signoff_sample_incomplete")
    valid = not blockers
    return {
        "present": True,
        "valid": valid,
        "accepted": valid and not failed_sample_ids,
        "reviewer": str(signoff.get("reviewer") or ""),
        "signed_at": str(signoff.get("signed_at") or ""),
        "blockers": blockers,
        "mismatch_sample_ids": mismatch_sample_ids,
        "incomplete_sample_ids": incomplete_sample_ids,
        "conditional_sample_ids": conditional_sample_ids,
        "failed_sample_ids": failed_sample_ids,
    }


def format_manual_signoff_template(report: dict[str, Any]) -> str:
    """生成绑定源码版本和 DOCX 哈希的 Word/WPS 人工验收模板。"""

    payload = {
        "schema_version": 1,
        "regression_run_dir": report["run_dir"],
        "source_revision": report["source_revision"],
        "reviewer": "",
        "signed_at": "",
        "final_signoff": False,
        "samples": [
            {
                "sample_id": item["sample_id"],
                "input_sha256": item.get("input_sha256") or "",
                "docx_sha256": item.get("docx_sha256") or "",
                "client": "",
                "client_version": "",
                "actual_page_count": None,
                "checks": {name: "" for name in VISUAL_CHECKS},
                "verdict": "",
                "notes": "",
            }
            for item in report.get("results") or []
            if item.get("status") == "succeeded" and item.get("docx_openable") is True
        ],
    }
    header = (
        "# 复制为 manual-signoff.yaml，并用 Word 或 WPS 完成整文档检查。\n"
        "# client 只接受 word/wps；检查值为 pass/fail/n/a，非全 pass 时必须说明 notes。\n"
    )
    return header + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def format_console_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "电子元器件 PDF 回归报告",
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
        "# 电子元器件 PDF 回归报告",
        "",
        f"- 生成时间: `{report['generated_at']}`",
        f"- Manifest: `{report['manifest_path']}`",
        f"- 运行目录: `{report['run_dir']}`",
        f"- 样本数: {summary['sample_count']}",
        f"- 成功: {summary['succeeded']}",
        f"- 失败: {summary['failed']}",
        f"- OK: `{summary['ok']}`",
        f"- 人工视觉记录有效: `{report.get('manual_visual_acceptance', {}).get('valid', False)}`",
        f"- 人工视觉结论可接受（含 conditional）: `{report.get('manual_visual_acceptance', {}).get('accepted', False)}`",
        "",
        "## 结果",
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
    lines.append("## 人工验收重点")
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


def _sha256_tree(root: Path) -> str:
    """把相对路径和文件内容一起纳入 MinerU 包哈希，避免同内容异资产被混用。"""

    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
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


def _source_revision() -> dict[str, Any]:
    """记录当前 commit 和 dirty 状态，防止旧视觉签字跨版本复用。"""

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"git_commit": commit, "worktree_dirty": dirty}


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.apply_manual_signoff:
        run_dir = Path(args.apply_manual_signoff).expanduser().resolve()
        signoff_path = (
            Path(args.manual_signoff).expanduser().resolve()
            if args.manual_signoff
            else run_dir / "manual-signoff.yaml"
        )
        report = apply_manual_signoff(run_dir, signoff_path)
        print(format_console_report(report))
        if not report["manual_visual_acceptance"]["valid"]:
            raise SystemExit(1)
        return
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
