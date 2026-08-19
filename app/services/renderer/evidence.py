"""Build renderer diagnostics shared by online jobs and local conversion tools."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.document_ir.integrity import build_source_integrity, ensure_integrity, is_visible_body_block
from app.services.document_ir.models import DocumentIR
from app.services.renderer.docx_quality import analyze_docx_quality_bytes, build_docx_quality_flags
from app.services.renderer.layout_plan import LayoutPlan, build_layout_plan


def build_renderer_metadata(document_ir: DocumentIR, layout_plan: LayoutPlan | None = None) -> dict[str, Any]:
    """Return the stable renderer metadata stored on artifacts and events."""

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
) -> dict[str, Any]:
    """Return renderer metadata plus DOCX quality evidence for the generated Word file."""

    evidence = build_renderer_metadata(document_ir, layout_plan)
    docx_quality = analyze_docx_quality_bytes(word_content)
    evidence["docx_quality"] = docx_quality
    evidence["quality_flags"] = build_docx_quality_flags(docx_quality)
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


def ensure_renderer_integrity(evidence: dict[str, Any]) -> None:
    """阻止包含确定性 IR→DOCX 内容丢失的产物进入发布边界。"""

    ensure_integrity("DocumentIR→DOCX", evidence)
