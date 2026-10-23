"""正式任务与本地转换共用的渲染完整性证据。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.conversion.docx_rules.formula import content_math_spans, formula_block_span, sha256_text
from app.conversion.docx_rules.table_expansion import expanded_table_rows, requires_table_expansion
from app.conversion.runtime.table_html_parser import parse_html_table
from app.services.document_ir.integrity import build_source_integrity, ensure_integrity, is_visible_body_block
from app.services.document_ir.models import DocumentIR
from app.services.renderer.docx_quality import (
    analyze_docx_quality_bytes,
    build_docx_quality_flags,
    validate_formula_report,
    verify_docx_formula_report,
)
from app.services.renderer.layout_plan import LayoutPlan, build_layout_plan


def build_renderer_metadata(document_ir: DocumentIR, layout_plan: LayoutPlan | None = None) -> dict[str, Any]:
    """生成产物与事件已有的稳定渲染元数据。"""

    resolved_layout_plan = layout_plan or build_layout_plan(document_ir)
    body_blocks = [block for block in document_ir.blocks if is_visible_body_block(block)]
    layout_block_ids = [
        block.id for page in resolved_layout_plan.pages for region in page.regions for block in region.blocks
    ]
    expected_block_ids = [block.id for block in body_blocks]
    return {
        "schema_version": document_ir.schema_version,
        "renderer_mode": resolved_layout_plan.mode,
        "layout_page_count": len(resolved_layout_plan.pages),
        "layout_region_count": sum(len(page.regions) for page in resolved_layout_plan.pages),
        "layout_block_count": sum(
            len(region.blocks) for page in resolved_layout_plan.pages for region in page.regions
        ),
        "expected_layout_block_count": len(expected_block_ids),
        "layout_block_count_delta": len(layout_block_ids) - len(expected_block_ids),
        "layout_missing_block_ids": sorted(set(expected_block_ids) - set(layout_block_ids)),
        "layout_duplicate_block_ids": sorted(
            block_id for block_id, count in Counter(layout_block_ids).items() if count > 1
        ),
        "layout_quality_flags": document_ir.quality_flags,
        "source_integrity": build_source_integrity(document_ir),
    }


def build_renderer_evidence(
    document_ir: DocumentIR,
    word_content: bytes,
    layout_plan: LayoutPlan | None = None,
    *,
    formula_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成 DOCX 证据；新报告严格核验，历史无报告保持原字段。"""

    evidence = build_renderer_metadata(document_ir, layout_plan)
    if formula_report is not None:
        summary = validate_formula_report(formula_report)
        expected_sources = formula_source_inventory(document_ir)
        recorded_sources = [entry["source"] for entry in formula_report["entries"]]
        if Counter(_binding_key(value) for value in expected_sources) != Counter(_binding_key(value) for value in recorded_sources):
            raise ValueError("公式报告与源 DocumentIR 不匹配")
        verify_docx_formula_report(word_content, formula_report)
        evidence["formula_report"] = formula_report
        evidence["formula_summary"] = summary
    docx_quality = analyze_docx_quality_bytes(word_content, formula_report=formula_report)
    evidence["docx_quality"] = docx_quality
    evidence["quality_flags"] = build_docx_quality_flags(docx_quality)
    if formula_report is not None and evidence["formula_summary"]["fallback_count"]:
        evidence["quality_flags"].append("formula_text_fallback")
    body_blocks = [block for block in document_ir.blocks if is_visible_body_block(block)]
    expected_inline_shapes = sum(1 for block in body_blocks if block.type == "image")
    expected_tables = sum(1 for block in body_blocks if block.type == "table")
    expected_headings = sum(1 for block in body_blocks if block.type == "heading")
    actual_inline_shapes = int(docx_quality.get("inline_shape_count") or 0)
    actual_tables = int(docx_quality.get("table_count") or 0)
    actual_headings = int(docx_quality.get("heading_paragraphs") or 0)
    evidence.update(
        {
            "expected_inline_shape_count": expected_inline_shapes,
            "inline_shape_count": actual_inline_shapes,
            "inline_shape_count_delta": actual_inline_shapes - expected_inline_shapes,
            "expected_table_count": expected_tables,
            "table_count": actual_tables,
            "table_count_delta": actual_tables - expected_tables,
            "expected_heading_count": expected_headings,
            "heading_count": actual_headings,
            "heading_count_delta": actual_headings - expected_headings,
        }
    )
    flags = list(evidence["source_integrity"]["blocking_quality_flags"])
    if evidence["layout_missing_block_ids"]:
        flags.append("ir_layout_integrity:missing_blocks")
    if evidence["layout_duplicate_block_ids"]:
        flags.append("ir_layout_integrity:duplicate_blocks")
    asset_ids = {asset.id for asset in document_ir.assets}
    if any(block.type == "image" and (not block.asset_ref or block.asset_ref not in asset_ids) for block in body_blocks):
        flags.append("ir_docx_integrity:image_asset_missing")
    if actual_inline_shapes != expected_inline_shapes:
        flags.append("ir_docx_integrity:inline_shape_count_mismatch")
    if actual_tables != expected_tables:
        flags.append("ir_docx_integrity:table_count_mismatch")
    if document_ir.schema_version == "document-ir/v2" and actual_headings != expected_headings:
        flags.append("ir_docx_integrity:heading_count_mismatch")
    evidence["blocking_quality_flags"] = list(dict.fromkeys(flags))
    return evidence


def _binding_key(binding: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(binding[key] for key in ("block_id", "field", "start", "end", "boundary", "source_sha256"))


def formula_source_inventory(document_ir: DocumentIR) -> list[dict[str, Any]]:
    """从权威 IR 重建每次公式出现的源绑定，不依赖渲染报告自证。"""
    sources: list[dict[str, Any]] = []

    def add(block_id: str, field: str, text: str, *, formula: bool = False) -> None:
        spans = (formula_block_span(text),) if formula else content_math_spans(text)
        sources.extend({"block_id": block_id, "field": field, "start": span.start, "end": span.end, "boundary": span.boundary, "source_sha256": sha256_text(span.source)} for span in spans)

    for block in document_ir.blocks:
        if not is_visible_body_block(block):
            continue
        if block.type == "formula":
            add(block.id, "latex" if block.latex else "text", block.latex or block.text or "", formula=True)
        elif block.type == "table":
            table = parse_html_table(block.html)
            if table:
                if requires_table_expansion(table, block.html):
                    for row in expanded_table_rows(table):
                        for occurrence in row:
                            if occurrence is not None:
                                add(block.id, f"html/{occurrence.source_row}/{occurrence.source_column}", occurrence.cell.html or occurrence.cell.text)
                else:
                    for row_index, row in enumerate(table.rows):
                        for col_index, cell in enumerate(row):
                            add(block.id, f"html/{row_index}/{col_index}", cell.html or cell.text)
            else:
                add(block.id, "text", block.text or "")
        elif block.type == "list":
            for index, text in enumerate(block.list_items or []):
                add(block.id, f"list_items/{index}", text)
        elif block.type != "image":
            add(block.id, "text", block.text or "")
        if block.type in {"table", "image"}:
            seen: set[tuple[str, str]] = set()
            values = [(f"captions/{index}", text) for index, text in enumerate(block.captions)]
            if block.type == "image" and isinstance(block.metadata.get("caption"), str):
                values.append(("metadata/caption", block.metadata["caption"]))
            values.extend((f"footnotes/{index}", text) for index, text in enumerate(block.footnotes))
            for field, text in values:
                # 表题与表注分别去重；图片沿用所有 annotation 合并去重的既有规则。
                key = (field.split("/")[0] if block.type == "table" else "", text.strip())
                if text.strip() and key not in seen:
                    seen.add(key)
                    add(block.id, field, text.strip())
            if block.type == "image" and not seen:
                add(block.id, "text", block.text or "")
    return sources


def ensure_renderer_integrity(evidence: dict[str, Any]) -> None:
    """阻止包含确定性 IR→DOCX 内容丢失的产物进入发布边界。"""

    ensure_integrity("DocumentIR→DOCX", evidence)
