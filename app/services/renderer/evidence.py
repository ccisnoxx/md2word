"""Build renderer diagnostics shared by online jobs and local conversion tools."""

from __future__ import annotations

from typing import Any

from app.services.document_ir.models import DocumentIR
from app.services.renderer.docx_quality import analyze_docx_quality_bytes, build_docx_quality_flags
from app.services.renderer.layout_plan import LayoutPlan, build_layout_plan


def build_renderer_metadata(document_ir: DocumentIR, layout_plan: LayoutPlan | None = None) -> dict[str, Any]:
    """Return the stable renderer metadata stored on artifacts and events."""

    resolved_layout_plan = layout_plan or build_layout_plan(document_ir)
    return {
        "schema_version": document_ir.schema_version,
        "renderer_mode": resolved_layout_plan.mode,
        "layout_page_count": len(resolved_layout_plan.pages),
        "layout_region_count": sum(len(page.regions) for page in resolved_layout_plan.pages),
        "layout_block_count": sum(
            len(region.blocks) for page in resolved_layout_plan.pages for region in page.regions
        ),
        "layout_quality_flags": document_ir.quality_flags,
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
    return evidence
