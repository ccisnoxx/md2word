#!/usr/bin/env python3
"""Run the phase-2 local MinerU quality matrix for datasheet DOCX hardening."""

from __future__ import annotations

# scripts/dev/run_local_mineru_quality_matrix.py: local-only phase-2 MinerU QA runner.

import argparse
import hashlib
import json
import os
import sys
import time
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.conversion import runtime_runner
from app.conversion.runtime import llm_client
from app.conversion.runtime_config import APP_CONFIG
from app.services.renderer.docx_quality import analyze_docx_quality_file, build_docx_quality_flags


DEFAULT_RUNS_DIR = ROOT / "tests" / "tmp" / "local_mineru_quality"
DEFAULT_TEMPLATE_PATH = ROOT / "resources" / "templates" / "default" / "datasheet_template.docx"
DEFAULT_LAYOUT_CONFIG_PATH = ROOT / "resources" / "template_configs" / "datasheet_template.yaml"
DEFAULT_SUBSCRIPT_CONFIG_PATH = ROOT / "resources" / "term_rules" / "subscripts_dictionary.yaml"
RENDER_DOCX_SCRIPT = (
    Path.home()
    / ".codex"
    / "plugins"
    / "cache"
    / "openai-primary-runtime"
    / "documents"
    / "26.622.11653"
    / "skills"
    / "documents"
    / "render_docx.py"
)
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
PHASE2_SAMPLE_SET = "phase2-core"
RU2ZH_ACCEPTANCE_SAMPLE_SET = "ru2zh-acceptance"
MODE_DIRECT = "direct"
MODE_EN2ZH = "en2zh"
MODE_RU2ZH = "ru2zh"
TRANSLATION_MODES = (MODE_EN2ZH, MODE_RU2ZH)
ALL_MODES = (MODE_DIRECT, *TRANSLATION_MODES)


P0_BLOCKING_DOCX_FLAGS = {
    "docx_quality_unavailable",
    "docx_analysis_error",
    "docx_no_editable_content",
    "docx_image_only_suspected",
}
P0_BLOCKING_DOCX_FLAG_PREFIXES = ("docx_latex_residue:",)


@dataclass(frozen=True, slots=True)
class Phase2Sample:
    sample_id: str
    title: str
    priority: str
    input_glob: str
    document_language: str
    tags: tuple[str, ...]
    acceptance_focus: tuple[str, ...]
    source_pdf_note: str = ""


@dataclass(frozen=True, slots=True)
class MatrixConfig:
    output_dir: Path = DEFAULT_RUNS_DIR
    sample_set: str = PHASE2_SAMPLE_SET
    sample_ids: tuple[str, ...] = ()
    modes: tuple[str, ...] = (MODE_DIRECT,)
    timestamped: bool = True
    template_path: Path = DEFAULT_TEMPLATE_PATH
    layout_config_path: Path = DEFAULT_LAYOUT_CONFIG_PATH
    subscript_config_path: Path = DEFAULT_SUBSCRIPT_CONFIG_PATH
    translation_response_dir: Path | None = None
    translation_model: str = APP_CONFIG.openai_model or llm_client.DEFAULT_MODEL
    translation_api_key: str | None = None
    translation_base_url: str | None = None
    translation_max_pages: int = APP_CONFIG.translation_max_pages
    translation_max_chars: int = APP_CONFIG.translation_max_chars
    dry_run: bool = False
    allow_blockers: bool = False


@dataclass(slots=True)
class MatrixResult:
    sample_id: str
    title: str
    priority: str
    mode: str
    status: str
    input_path: str = ""
    input_matches: list[str] = field(default_factory=list)
    output_path: str = ""
    source_pdf: str = ""
    elapsed_seconds: float = 0.0
    error_code: str = ""
    error_message: str = ""
    docx_sha256: str = ""
    docx_openable: bool = False
    docx_quality: dict[str, Any] = field(default_factory=dict)
    docx_quality_flags: list[str] = field(default_factory=list)
    mineru_stats: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    acceptance_focus: list[str] = field(default_factory=list)
    qa: dict[str, Any] = field(default_factory=dict)
    issues: list[dict[str, str]] = field(default_factory=list)


PHASE2_CORE_SAMPLES: tuple[Phase2Sample, ...] = (
    Phase2Sample(
        sample_id="OPA228_P1",
        title="OPA228 双栏 datasheet 首页",
        priority="P0",
        input_glob="mineru_result/OPA228_P1.pdf-*",
        document_language="en",
        tags=("en", "datasheet", "double_column", "cover", "figures", "table"),
        acceptance_focus=(
            "双栏阅读顺序正确，Features/Applications/Description 不左右栏交错。",
            "标题层级、噪声曲线图和 Device Information 表格相对位置可追溯。",
            "首页双栏在一页内闭合，不跨页，不压页尾。",
        ),
    ),
    Phase2Sample(
        sample_id="OPA228_P2",
        title="OPA228 目录与 Revision History",
        priority="P0",
        input_glob="mineru_result/OPA228_P2.pdf-*",
        document_language="en",
        tags=("en", "datasheet", "table_of_contents", "revision_history", "double_column", "lists"),
        acceptance_focus=(
            "双栏目录条目和页码顺序可追溯。",
            "Revision History 项目符号列表顺序保留。",
            "页眉、页脚和正文边界不互相覆盖。",
        ),
    ),
    Phase2Sample(
        sample_id="OPA228_P6",
        title="OPA228 Thermal Information 多表格页",
        priority="P0",
        input_glob="mineru_result/OPA228_P6.pdf-*",
        document_language="en",
        tags=("en", "datasheet", "thermal_table", "parameter_table", "symbols", "wide_table"),
        acceptance_focus=(
            "多张 Thermal Information 表行列稳定且可编辑。",
            "θ/ψ、°C/W、封装和 pin 数等符号可读。",
            "表格脚注靠近对应表格且正文顺序正确。",
        ),
    ),
    Phase2Sample(
        sample_id="OPA228_P7",
        title="OPA228 Electrical Characteristics 宽表页",
        priority="P0",
        input_glob="mineru_result/OPA228_P7.pdf-*",
        document_language="en",
        tags=("en", "datasheet", "wide_table", "electrical_characteristics", "parameter_table", "symbols"),
        acceptance_focus=(
            "Electrical Characteristics 宽表列名、单位和分组保留。",
            "VOS、PSRR、CMRR、nV/√Hz、µV/°C 等上下标和特殊符号可读。",
            "表格内容可编辑且不大面积挤压或错列。",
        ),
    ),
    Phase2Sample(
        sample_id="RS2G04",
        title="RS2G04 13 页技术手册观察样本",
        priority="P1",
        input_glob="mineru_result/RS2G04_(RevA.4).pdf-*",
        document_language="en",
        tags=("en", "technical_manual", "multi_page", "figures", "tables", "observer"),
        acceptance_focus=(
            "多页图文、表格、页眉页脚和页码均有可追溯证据。",
            "记录第一阶段规则在 13 页手册上的边界问题，不作为 P0 阻塞。",
            "把影响 OPA228 P0 的共性根因升级处理，其余进入 P1/P2 backlog。",
        ),
    ),
)
RU2ZH_ACCEPTANCE_SAMPLES: tuple[Phase2Sample, ...] = (
    Phase2Sample(
        sample_id="RU_DIODE_ANODE_TOP",
        title="俄文二极管样本",
        priority="P0",
        input_glob="mineru_result/диод анод сверху.pdf-5a23152f-e597-40a4-98e8-585b78811b63",
        document_language="ru",
        tags=("ru", "datasheet", "diode", "translation"),
        acceptance_focus=(
            "俄文西里尔文本进入 translation request。",
            "ru2zh 输出中文，trace 记录 request/response 对齐证据。",
            "翻译术语表按 ru2zh language_pair 绑定，不使用术语规则 YAML。",
        ),
    ),
)
SAMPLE_SETS: dict[str, tuple[Phase2Sample, ...]] = {
    PHASE2_SAMPLE_SET: PHASE2_CORE_SAMPLES,
    RU2ZH_ACCEPTANCE_SAMPLE_SET: RU2ZH_ACCEPTANCE_SAMPLES,
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local MinerU phase-2 DOCX quality matrix.")
    parser.add_argument("--sample-set", default=PHASE2_SAMPLE_SET, choices=sorted(SAMPLE_SETS))
    parser.add_argument("--sample-id", action="append", default=[], help="Sample id to run. May be repeated.")
    parser.add_argument("--mode", action="append", choices=ALL_MODES, default=[], help="Mode to run. Defaults to direct.")
    parser.add_argument("--output-dir", default=str(DEFAULT_RUNS_DIR), help="Directory for run outputs.")
    parser.add_argument("--no-timestamp", action="store_true", help="Write directly into --output-dir.")
    parser.add_argument("--template-path", default=str(DEFAULT_TEMPLATE_PATH))
    parser.add_argument("--layout-config-path", default=str(DEFAULT_LAYOUT_CONFIG_PATH))
    parser.add_argument("--subscript-config-path", default=str(DEFAULT_SUBSCRIPT_CONFIG_PATH))
    parser.add_argument("--translation-response-dir", help="Directory containing <sample_id>.translation-response.json files.")
    parser.add_argument("--translation-model", default=APP_CONFIG.openai_model or llm_client.DEFAULT_MODEL)
    parser.add_argument("--translation-api-key", default=None)
    parser.add_argument("--translation-base-url", default=None)
    parser.add_argument("--translation-max-pages", type=int, default=APP_CONFIG.translation_max_pages)
    parser.add_argument("--translation-max-chars", type=int, default=APP_CONFIG.translation_max_chars)
    parser.add_argument("--dry-run", action="store_true", help="Write matrix reports without running conversion.")
    parser.add_argument("--allow-blockers", action="store_true", help="Exit 0 when a run only has environment blockers.")
    parser.add_argument("--json", action="store_true", help="Print report JSON instead of a console summary.")
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> MatrixConfig:
    modes = tuple(dict.fromkeys(args.mode or [MODE_DIRECT]))
    return MatrixConfig(
        output_dir=Path(args.output_dir),
        sample_set=str(args.sample_set),
        sample_ids=tuple(args.sample_id),
        modes=modes,
        timestamped=not args.no_timestamp,
        template_path=Path(args.template_path),
        layout_config_path=Path(args.layout_config_path),
        subscript_config_path=Path(args.subscript_config_path),
        translation_response_dir=Path(args.translation_response_dir) if args.translation_response_dir else None,
        translation_model=str(args.translation_model),
        translation_api_key=args.translation_api_key,
        translation_base_url=args.translation_base_url,
        translation_max_pages=int(args.translation_max_pages),
        translation_max_chars=int(args.translation_max_chars),
        dry_run=bool(args.dry_run),
        allow_blockers=bool(args.allow_blockers),
    )


def run_matrix(config: MatrixConfig) -> dict[str, Any]:
    run_dir = _create_run_dir(config.output_dir.expanduser().resolve(), timestamped=config.timestamped)
    samples = select_samples(config.sample_set, config.sample_ids)
    results = [
        run_one_matrix_entry(sample, mode, run_dir, config)
        for sample in samples
        for mode in config.modes
    ]
    report = build_report(config, run_dir, samples, results)
    write_report_files(run_dir, report)
    return report


def select_samples(sample_set: str, sample_ids: Sequence[str]) -> list[Phase2Sample]:
    if sample_set not in SAMPLE_SETS:
        raise ValueError(f"unknown sample set: {sample_set}")
    samples = list(SAMPLE_SETS[sample_set])
    requested = set(sample_ids)
    if not requested:
        return samples
    selected = [sample for sample in samples if sample.sample_id in requested]
    missing = sorted(requested - {sample.sample_id for sample in selected})
    if missing:
        raise ValueError(f"unknown sample ids for {sample_set}: {', '.join(missing)}")
    return selected


def run_one_matrix_entry(sample: Phase2Sample, mode: str, run_dir: Path, config: MatrixConfig) -> MatrixResult:
    started = time.monotonic()
    matches = _find_sample_matches(sample)
    selected_input = matches[0] if matches else None
    is_translation_mode = mode in TRANSLATION_MODES
    output_path = run_dir / "docx" / mode / f"{sample.sample_id}{'.zh' if is_translation_mode else ''}.docx"
    qa_dir = run_dir / "visual_qa" / mode / sample.sample_id
    result = MatrixResult(
        sample_id=sample.sample_id,
        title=sample.title,
        priority=sample.priority,
        mode=mode,
        status="pending",
        input_path=str(selected_input) if selected_input else "",
        input_matches=[str(path) for path in matches],
        output_path=str(output_path),
        tags=list(sample.tags),
        acceptance_focus=list(sample.acceptance_focus),
        qa=build_visual_qa_evidence(output_path, qa_dir),
    )
    if selected_input is None:
        return _finish_blocked_result(
            result,
            started,
            "sample_input_missing",
            f"no local MinerU package matched {sample.input_glob}",
            sample,
        )
    result.mineru_stats = analyze_mineru_package(selected_input)
    result.source_pdf = str(_find_origin_pdf(selected_input) or sample.source_pdf_note)
    if config.dry_run:
        result.status = "dry_run"
        result.elapsed_seconds = round(time.monotonic() - started, 3)
        result.issues = classify_result_issues(result, sample)
        return result

    response_path = _translation_response_path(config.translation_response_dir, sample.sample_id) if is_translation_mode else None
    api_key = config.translation_api_key or os.environ.get(OPENAI_API_KEY_ENV)
    if is_translation_mode and response_path is None and not api_key:
        return _finish_blocked_result(
            result,
            started,
            "translation_api_key_missing",
            f"{mode} requires OPENAI_API_KEY or a local translation response file",
            sample,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    translation_request_output = None
    translation_trace_output = None
    if is_translation_mode:
        trace_dir = run_dir / "translation" / sample.sample_id
        translation_request_output = trace_dir / f"{sample.sample_id}.translation-request.json"
        translation_trace_output = trace_dir / f"{sample.sample_id}.translation-trace.json"
    try:
        runtime_runner.run_conversion(
            input_path=str(selected_input),
            output_path=str(output_path),
            template_path=str(config.template_path),
            layout_config_path=str(config.layout_config_path),
            subscript_config=str(config.subscript_config_path),
            no_template=False,
            use_mineru_header_footer=False,
            document_language=sample.document_language if mode == MODE_DIRECT else "auto",
            translation_mode=mode,
            translation_request_output=str(translation_request_output) if translation_request_output else None,
            translation_response=str(response_path) if response_path else None,
            translation_trace_output=str(translation_trace_output) if translation_trace_output else None,
            translation_model=config.translation_model,
            translation_api_key=api_key,
            translation_base_url=config.translation_base_url,
            translation_max_pages=config.translation_max_pages,
            translation_max_chars=config.translation_max_chars,
        )
    except Exception as exc:  # noqa: BLE001 - matrix report captures per-sample failures.
        result.status = "failed"
        result.error_code = exc.__class__.__name__
        result.error_message = str(exc)
        result.elapsed_seconds = round(time.monotonic() - started, 3)
        result.issues = classify_result_issues(result, sample)
        return result

    result.status = "succeeded"
    result.elapsed_seconds = round(time.monotonic() - started, 3)
    result.docx_sha256 = _sha256(output_path)
    result.docx_openable = _is_docx_openable(output_path)
    result.docx_quality = analyze_docx_quality_file(output_path) if result.docx_openable else {}
    result.docx_quality_flags = build_docx_quality_flags(result.docx_quality) if result.docx_openable else ["docx_not_openable"]
    result.issues = classify_result_issues(result, sample)
    return result


def _finish_blocked_result(
    result: MatrixResult,
    started: float,
    error_code: str,
    error_message: str,
    sample: Phase2Sample,
) -> MatrixResult:
    result.status = "blocked"
    result.error_code = error_code
    result.error_message = error_message
    result.elapsed_seconds = round(time.monotonic() - started, 3)
    result.issues = classify_result_issues(result, sample)
    return result


def build_report(
    config: MatrixConfig,
    run_dir: Path,
    samples: Sequence[Phase2Sample],
    results: Sequence[MatrixResult],
) -> dict[str, Any]:
    result_payloads = [asdict(result) for result in results]
    issue_payloads = [issue for result in result_payloads for issue in result.get("issues", [])]
    statuses = Counter(result.status for result in results)
    quality_flags = sorted({flag for result in results for flag in result.docx_quality_flags})
    p0_results = [result for result in results if result.priority == "P0"]
    p0_issues = [issue for issue in issue_payloads if issue.get("severity") == "P0"]
    summary = {
        "sample_set": config.sample_set,
        "sample_count": len(samples),
        "entry_count": len(results),
        "modes": list(config.modes),
        "succeeded": statuses.get("succeeded", 0),
        "failed": statuses.get("failed", 0),
        "blocked": statuses.get("blocked", 0),
        "dry_run": statuses.get("dry_run", 0),
        "p0_entries": len(p0_results),
        "p0_succeeded": sum(1 for result in p0_results if result.status == "succeeded"),
        "p0_issues": len(p0_issues),
        "docx_quality_flagged_entries": sum(1 for result in results if result.docx_quality_flags),
        "docx_quality_flags": quality_flags,
        "automated_matrix_ok": all(result.status in {"succeeded", "dry_run"} for result in results) and not p0_issues,
        "phase3_entry_ready": False,
        "phase3_entry_blocker": phase3_entry_blocker(results, issue_payloads),
    }
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "config": {
            "sample_set": config.sample_set,
            "modes": list(config.modes),
            "template_path": str(config.template_path),
            "layout_config_path": str(config.layout_config_path),
            "subscript_config_path": str(config.subscript_config_path),
            "translation_response_dir": str(config.translation_response_dir) if config.translation_response_dir else "",
            "translation_model": config.translation_model,
            "translation_api_key_present": bool(config.translation_api_key or os.environ.get(OPENAI_API_KEY_ENV)),
            "translation_base_url_present": bool(config.translation_base_url),
            "translation_max_pages": config.translation_max_pages,
            "translation_max_chars": config.translation_max_chars,
            "dry_run": config.dry_run,
        },
        "summary": summary,
        "samples": [asdict(sample) for sample in samples],
        "results": result_payloads,
        "issues": issue_payloads,
        "acceptance_layers": acceptance_layers(),
        "phase3_entry_criteria": phase3_entry_criteria(),
        "new_sample_selection_principles": new_sample_selection_principles(),
    }


def phase3_entry_blocker(results: Sequence[MatrixResult], issues: Sequence[Mapping[str, str]]) -> str:
    if any(issue.get("severity") == "P0" for issue in issues):
        return "p0_issues_must_be_resolved"
    if any(result.status == "failed" for result in results):
        return "matrix_failures_must_be_resolved"
    if any(result.status == "blocked" for result in results):
        return "environment_or_input_blockers_must_be_resolved"
    if any(result.status != "succeeded" for result in results if result.priority == "P0" and result.mode == MODE_DIRECT):
        return "p0_direct_matrix_must_succeed"
    if any(issue.get("severity") in {"P1", "P2"} for issue in issues):
        return "p1_p2_backlog_required"
    return "manual_visual_signoff_required"


def classify_result_issues(result: MatrixResult, sample: Phase2Sample) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if result.status == "blocked":
        severity = "P1" if result.error_code == "translation_api_key_missing" else sample.priority
        issues.append(
            {
                "severity": severity,
                "code": result.error_code,
                "sample_id": result.sample_id,
                "mode": result.mode,
                "message": result.error_message,
            }
        )
        return issues
    if result.status == "failed":
        issues.append(
            {
                "severity": sample.priority,
                "code": result.error_code or "conversion_failed",
                "sample_id": result.sample_id,
                "mode": result.mode,
                "message": result.error_message,
            }
        )
    if result.docx_openable is False and result.status == "succeeded":
        issues.append(
            {
                "severity": sample.priority,
                "code": "docx_not_openable",
                "sample_id": result.sample_id,
                "mode": result.mode,
                "message": "generated DOCX is not a valid zip package",
            }
        )
    for flag in result.docx_quality_flags:
        severity = "P2"
        if flag in P0_BLOCKING_DOCX_FLAGS or flag.startswith(P0_BLOCKING_DOCX_FLAG_PREFIXES):
            severity = "P0" if sample.priority == "P0" else "P1"
        elif sample.priority == "P0":
            severity = "P1"
        issues.append(
            {
                "severity": severity,
                "code": flag,
                "sample_id": result.sample_id,
                "mode": result.mode,
                "message": f"DOCX quality flag: {flag}",
            }
        )
    return issues


def analyze_mineru_package(package_path: Path) -> dict[str, Any]:
    content_list = _find_content_list(package_path)
    pages: list[Any] = []
    blocks: list[dict[str, Any]] = []
    if content_list is not None:
        payload = json.loads(content_list.read_text(encoding="utf-8"))
        pages = payload if isinstance(payload, list) and (not payload or isinstance(payload[0], list)) else [payload]
        for page in pages:
            if isinstance(page, list):
                blocks.extend(item for item in page if isinstance(item, dict))
    type_counts = Counter(str(block.get("type") or "<missing>") for block in blocks)
    image_dir = package_path / "images"
    return {
        "content_list": str(content_list) if content_list else "",
        "page_count": len(pages),
        "block_count": len(blocks),
        "block_type_counts": dict(sorted(type_counts.items())),
        "image_count": len([path for path in image_dir.glob("*") if path.is_file()]) if image_dir.exists() else 0,
        "origin_pdf": str(_find_origin_pdf(package_path) or ""),
    }


def build_visual_qa_evidence(output_path: Path, qa_dir: Path) -> dict[str, Any]:
    command = [
        "env",
        "TMPDIR=/private/tmp",
        ".venv/bin/python",
        str(RENDER_DOCX_SCRIPT),
        str(output_path),
        "--output_dir",
        str(qa_dir),
        "--emit_pdf",
    ]
    return {
        "standard_renderer": "LibreOffice + Poppler via render_docx.py",
        "manual_review_required": True,
        "output_dir": str(qa_dir),
        "render_command": command,
        "checks": [
            "page_size_margin_header_footer",
            "heading_body_table_caption_style_groups",
            "double_column_order_and_closure",
            "tables_editable_and_readable",
            "figures_caption_position",
            "pagination_not_tail_cramped",
            "symbols_units_subscripts",
            "direct_en2zh_structure_delta",
        ],
    }


def write_report_files(run_dir: Path, report: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(format_markdown_report(report), encoding="utf-8")
    (run_dir / "manual-signoff-template.yaml").write_text(format_manual_signoff_template(report), encoding="utf-8")


def format_markdown_report(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Local MinerU Phase-2 Quality Matrix",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Run dir: `{report['run_dir']}`",
        f"- Sample set: `{summary['sample_set']}`",
        f"- Modes: `{', '.join(summary['modes'])}`",
        f"- Entries: `{summary['entry_count']}`",
        f"- Succeeded: `{summary['succeeded']}`",
        f"- Failed: `{summary['failed']}`",
        f"- Blocked: `{summary['blocked']}`",
        f"- P0 issues: `{summary['p0_issues']}`",
        f"- Automated matrix OK: `{summary['automated_matrix_ok']}`",
        f"- Phase 3 entry ready: `{summary['phase3_entry_ready']}`",
        f"- Phase 3 blocker: `{summary['phase3_entry_blocker']}`",
        f"- DOCX quality flags: `{', '.join(summary.get('docx_quality_flags') or []) or 'none'}`",
        "",
        "## Results",
        "",
        "| Sample | Priority | Mode | Status | DOCX | Flags | Issues | Pages | Blocks | Images |",
        "|---|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for item in report.get("results") or []:
        stats = item.get("mineru_stats") or {}
        issue_codes = [issue["code"] for issue in item.get("issues") or []]
        lines.append(
            "| {sample_id} | {priority} | {mode} | `{status}` | `{docx}` | {flags} | {issues} | {pages} | {blocks} | {images} |".format(
                sample_id=item["sample_id"],
                priority=item["priority"],
                mode=item["mode"],
                status=item["status"],
                docx=item.get("output_path") or "",
                flags=", ".join(item.get("docx_quality_flags") or []) or "none",
                issues=", ".join(issue_codes) or "none",
                pages=stats.get("page_count", ""),
                blocks=stats.get("block_count", ""),
                images=stats.get("image_count", ""),
            )
        )
    lines.extend(["", "## Visual QA Commands", ""])
    for item in report.get("results") or []:
        qa = item.get("qa") or {}
        command = " ".join(str(part) for part in qa.get("render_command") or [])
        lines.extend(
            [
                f"### {item['sample_id']} / {item['mode']}",
                "",
                f"- Output dir: `{qa.get('output_dir') or '-'}`",
                "",
                "```bash",
                command,
                "```",
                "",
            ]
        )
    lines.extend(["## Acceptance Focus", ""])
    for item in report.get("results") or []:
        lines.append(f"### {item['sample_id']} / {item['mode']}")
        for focus in item.get("acceptance_focus") or []:
            lines.append(f"- {focus}")
        if item.get("error_message"):
            lines.append(f"- Error: `{item['error_code']}: {item['error_message']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_manual_signoff_template(report: Mapping[str, Any]) -> str:
    payload = {
        "schema_version": 1,
        "regression_run_dir": report["run_dir"],
        "reviewer": "",
        "signed_at": "",
        "final_signoff": False,
        "verdicts": [
            {
                "sample_id": item["sample_id"],
                "priority": item["priority"],
                "mode": item["mode"],
                "status": item["status"],
                "docx_sha256": item.get("docx_sha256") or "",
                "docx_quality_flags": item.get("docx_quality_flags") or [],
                "visual_qa_output_dir": (item.get("qa") or {}).get("output_dir") or "",
                "verdict": "",
                "issue_severity": "",
                "notes": "",
            }
            for item in report.get("results") or []
            if item.get("status") == "succeeded"
        ],
        "p1_p2_backlog": [],
    }
    header = (
        "# Copy to manual-signoff.yaml after reviewing DOCX and standard-render PNG/PDF evidence.\n"
        "# verdict must be pass, conditional, or fail. P0 final gate does not accept conditional.\n"
        "# issue_severity should be P0, P1, P2, or empty when the verdict is pass with no issue.\n"
    )
    return header + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def format_console_report(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    return (
        "Local MinerU phase-2 quality matrix\n"
        f"run_dir: {report['run_dir']}\n"
        f"sample_set: {summary['sample_set']}, modes: {', '.join(summary['modes'])}\n"
        f"entries: {summary['entry_count']}, succeeded: {summary['succeeded']}, "
        f"failed: {summary['failed']}, blocked: {summary['blocked']}\n"
        f"p0_issues: {summary['p0_issues']}, automated_matrix_ok: {summary['automated_matrix_ok']}\n"
        f"phase3_entry_ready: {summary['phase3_entry_ready']} ({summary['phase3_entry_blocker']})"
    )


def acceptance_layers() -> list[dict[str, str]]:
    return [
        {"layer": "L0", "name": "script_smoke", "requirement": "runner exits deliberately and writes report files"},
        {"layer": "L1", "name": "docx_structure", "requirement": "DOCX opens and quality flags are captured"},
        {"layer": "L2", "name": "standard_render", "requirement": "LibreOffice + Poppler PNG/PDF evidence exists"},
        {"layer": "L3", "name": "manual_visual_signoff", "requirement": "reviewer compares PDF, DOCX, and rendered pages"},
        {"layer": "L4", "name": "phase_summary", "requirement": "P1/P2 backlog and phase-3 blockers are recorded"},
    ]


def phase3_entry_criteria() -> list[str]:
    return [
        "OPA228_P1/P2/P6/P7 direct all succeed and have manual pass verdicts.",
        "en2zh P0 samples are verified with offline response or controlled model batch and preserve structure.",
        "RS2G04 direct observation report is complete and all findings are graded.",
        "Every P0 result has DOCX, quality report, standard-render evidence, and manual signoff.",
        "No committed mineru_result, tests/tmp outputs, real PDFs, real keys, or full translation traces.",
    ]


def new_sample_selection_principles() -> list[str]:
    return [
        "Pick public or minimized MinerU packages from mineru_result/; do not commit proprietary PDFs.",
        "Add one clear layout risk at a time, such as long tables, pinout diagrams, or mixed headers.",
        "Promote a local sample to component_pdf_samples only when it should prevent future regressions.",
        "Record sample id, source reference, page count, tags, modes, and manual acceptance focus.",
    ]


def _find_sample_matches(sample: Phase2Sample) -> list[Path]:
    matches = [path for path in ROOT.glob(sample.input_glob) if path.is_dir()]
    return sorted(matches, key=lambda path: (path.stat().st_mtime, path.name), reverse=True)


def _find_content_list(package_path: Path) -> Path | None:
    candidates = [
        *sorted(package_path.glob("*_content_list_v2.json")),
        package_path / "content_list_v2.json",
        *sorted(package_path.glob("*_content_list.json")),
        package_path / "content_list.json",
    ]
    return next((path for path in candidates if path.exists()), None)


def _find_origin_pdf(package_path: Path) -> Path | None:
    return next(iter(sorted(package_path.glob("*_origin.pdf"))), None)


def _translation_response_path(response_dir: Path | None, sample_id: str) -> Path | None:
    if response_dir is None:
        return None
    candidates = (
        response_dir / f"{sample_id}.translation-response.json",
        response_dir / f"{sample_id}.response.json",
        response_dir / f"{sample_id}.json",
    )
    return next((path.expanduser().resolve() for path in candidates if path.exists()), None)


def _create_run_dir(output_dir: Path, *, timestamped: bool) -> Path:
    run_dir = output_dir / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") if timestamped else output_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


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
    config = build_config(args)
    report = run_matrix(config)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_console_report(report))
    failed = bool(report["summary"]["failed"])
    blockers = bool(report["summary"]["blocked"])
    if failed or (blockers and not config.allow_blockers):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
