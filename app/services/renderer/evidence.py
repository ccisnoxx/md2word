"""构建本地与线上正式渲染共同使用的完整性证据。"""

from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Any

from bs4 import BeautifulSoup

from app.conversion.docx_rules.text_semantics import (
    is_list_item_text,
    normalize_list_item,
    prepare_text_for_rendering,
    split_document_identity,
)
from app.conversion.docx_rules.terminology import TerminologyReplacer
from app.conversion.runtime.table_html_parser import parse_html_table
from app.services.document_ir.integrity import (
    build_source_integrity,
    drawingml_crop_offsets,
    ensure_integrity,
    expected_image_shape_count,
    is_visible_body_block,
    visual_crop_rects,
)
from app.services.document_ir.models import DocumentIR, DocumentIRBlock
from app.services.renderer.docx_quality import analyze_docx_evidence_bytes, build_docx_quality_flags
from app.services.renderer.layout_plan import LayoutPlan, build_layout_plan
from app.services.renderer.semantic_text import parse_toc_entry_text
from app.services.renderer.template_config import TemplateConfigPackage
from app.services.renderer.text_renderer import _OmmlParser, _parse_mixed_math_segments


COLUMN_DOWNGRADE_REASONS = {
    "missing_page_width",
    "short_text_prelude_before_wide_visual",
    "table_container_degraded",
    "unpaired_column_membership",
}


def build_renderer_metadata(document_ir: DocumentIR, layout_plan: LayoutPlan | None = None) -> dict[str, Any]:
    """返回写入产物和事件的稳定 renderer metadata。"""

    resolved_layout_plan = layout_plan or build_layout_plan(document_ir)
    body_blocks = [block for block in document_ir.blocks if is_visible_body_block(block)]
    layout_block_ids = [
        block.id for page in resolved_layout_plan.pages for region in page.regions for block in region.blocks
    ]
    expected_block_ids = [block.id for block in body_blocks]
    table_fit_decisions = [
        resolved_layout_plan.table_fit_decisions[block_id].as_dict()
        for block_id in sorted(resolved_layout_plan.table_fit_decisions)
    ]
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
        "soft_page_groups": [
            {
                "page_index": page.index,
                "source_page_indices": list(page.source_page_indices),
                "break_before_block_id": page.break_before_block_id,
                "break_reason": page.break_reason,
                "continuation_reasons": list(page.continuation_reasons),
            }
            for page in resolved_layout_plan.pages
        ],
        "column_downgrades": [
            {
                "page_index": page.index,
                "region_kind": region.kind,
                "reason": region.reason,
                "block_ids": [block.id for block in region.blocks],
            }
            for page in resolved_layout_plan.pages
            for region in page.regions
            if region.reason in COLUMN_DOWNGRADE_REASONS or region.kind == "landscape_table"
        ],
        "table_fit_decisions": table_fit_decisions,
        "table_fit_quality_flags": list(
            dict.fromkeys(
                flag
                for decision in resolved_layout_plan.table_fit_decisions.values()
                for flag in decision.quality_flags
            )
        ),
        "visual_overlap_normalizations": [
            block.metadata["visual_overlap_normalization"]
            for block in body_blocks
            if block.type == "image" and isinstance(block.metadata.get("visual_overlap_normalization"), dict)
        ],
        "source_integrity": build_source_integrity(document_ir),
    }


def build_renderer_evidence(
    document_ir: DocumentIR,
    word_content: bytes,
    layout_plan: LayoutPlan | None = None,
    template_config: TemplateConfigPackage | None = None,
) -> dict[str, Any]:
    """返回 renderer metadata、DOCX 证据和确定性阻断项。"""

    resolved_layout_plan = layout_plan or build_layout_plan(document_ir, template_config)
    evidence = build_renderer_metadata(document_ir, resolved_layout_plan)
    docx_quality, content_evidence = analyze_docx_evidence_bytes(word_content)
    evidence["docx_quality"] = docx_quality
    evidence["quality_flags"] = build_docx_quality_flags(docx_quality)
    body_blocks = [block for block in document_ir.blocks if is_visible_body_block(block)]
    expected_inline_shapes = sum(
        expected_image_shape_count(block) for block in body_blocks if block.type == "image"
    )
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

    visible_evidence = _build_visible_payload_evidence(
        body_blocks,
        content_evidence,
        terminology=template_config.terminology if template_config is not None else None,
        allow_legacy_toc_inference=document_ir.schema_version == "document-ir/v1",
    )
    evidence["visible_payload_evidence"] = visible_evidence
    if visible_evidence["missing_payload_ids"]:
        flags.append("ir_docx_integrity:visible_payload_missing")

    toc_evidence = _build_toc_evidence(document_ir, content_evidence)
    evidence["toc_evidence"] = toc_evidence
    if toc_evidence["disposition_violations"]:
        flags.append("ir_docx_integrity:toc_disposition_mismatch")

    image_evidence = _build_image_evidence(document_ir, body_blocks, content_evidence)
    evidence["image_evidence"] = image_evidence
    if image_evidence["missing_asset_ids"] or image_evidence["unexpected_asset_ids"]:
        flags.append("ir_docx_integrity:image_asset_identity_mismatch")
    if image_evidence["unresolved_asset_ids"]:
        flags.append("ir_docx_integrity:image_asset_unresolved")
    if image_evidence["checksum_mismatch_asset_ids"]:
        flags.append("ir_docx_integrity:image_asset_checksum_mismatch")
    if image_evidence["invalid_crop_block_ids"]:
        flags.append("ir_docx_integrity:image_fragment_contract_invalid")
    if (
        image_evidence["missing_fragments"]
        or image_evidence["unexpected_fragments"]
        or image_evidence["order_mismatch_asset_ids"]
    ):
        flags.append("ir_docx_integrity:image_fragment_identity_mismatch")

    composite_evidence = _build_visual_table_composite_evidence(body_blocks, content_evidence)
    evidence["visual_table_composite_evidence"] = composite_evidence
    if composite_evidence["missing_group_ids"] or composite_evidence["unexpected_group_ids"]:
        flags.append("ir_docx_integrity:visual_table_composite_identity_mismatch")

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


def _build_visible_payload_evidence(
    blocks: list[DocumentIRBlock],
    content_evidence: dict[str, Any],
    *,
    terminology: TerminologyReplacer | None,
    allow_legacy_toc_inference: bool,
) -> dict[str, Any]:
    expected: dict[str, list[tuple[str, str]]] = {
        "heading": [],
        "paragraph": [],
        "list_item": [],
        "table_cell": [],
        "annotation": [],
        "formula": [],
    }
    for block in blocks:
        if block.metadata.get("annotation_role") == "toc_anchor":
            continue
        if block.metadata.get("annotation_role") == "document_identity" and block.text:
            identity = split_document_identity(block.text)
            if identity is None:
                raise ValueError(f"文档身份文本无法拆分: {block.id}")
            expected["paragraph"].extend(
                (f"{block.id}:{role}", _prepared_visible_text(text, terminology))
                for role, text in zip(("part_number", "category"), identity, strict=True)
            )
        elif block.metadata.get("annotation_role") == "standalone_caption" and block.text:
            expected["annotation"].append((block.id, _prepared_visible_text(block.text, terminology)))
        elif block.type == "heading" and block.text:
            expected["heading"].append((block.id, _prepared_visible_text(block.text, terminology)))
        elif (
            block.type == "paragraph"
            and block.text
            and not (allow_legacy_toc_inference and parse_toc_entry_text(block.text) is not None)
        ):
            text = normalize_list_item(block.text) if is_list_item_text(block.text) else block.text
            expected["paragraph"].append((block.id, _prepared_visible_text(text, terminology)))
        elif block.type == "list":
            for index, item in enumerate(block.list_items or []):
                if allow_legacy_toc_inference and parse_toc_entry_text(item) is not None:
                    continue
                expected["list_item"].append(
                    (f"{block.id}:item:{index}", _prepared_visible_text(normalize_list_item(item), terminology))
                )
        elif block.type == "table":
            table_html = block.html
            if terminology is not None:
                table_html = terminology.replace_html(table_html) or table_html
            table = parse_html_table(table_html)
            if table is not None:
                for row_index, row in enumerate(table.rows):
                    for cell_index, cell in enumerate(row):
                        expected["table_cell"].append(
                            (
                                f"{block.id}:cell:{row_index}:{cell_index}",
                                _prepared_visible_text(cell.html or cell.text, terminology),
                            )
                        )
        elif block.type == "formula":
            formula = block.latex or block.text or ""
            expected["formula"].append((block.id, _canonical_formula_text(formula, terminology)))

        if block.type == "table":
            annotations = _unique_texts([*block.captions, *block.footnotes])
        elif block.type == "image":
            metadata_caption = block.metadata.get("caption")
            annotations = _unique_texts(
                [
                    *block.captions,
                    *((metadata_caption,) if isinstance(metadata_caption, str) else ()),
                    *block.footnotes,
                ]
            )
        else:
            annotations = []
        for index, annotation in enumerate(annotations):
            expected["annotation"].append(
                (f"{block.id}:annotation:{index}", _prepared_visible_text(annotation, terminology))
            )

    actual_by_kind = {
        "heading": content_evidence.get("heading_paragraph_texts", []),
        "paragraph": content_evidence.get("non_toc_body_paragraph_texts", []),
        "list_item": content_evidence.get("numbering_paragraph_texts", []),
        "table_cell": content_evidence.get("semantic_table_cell_texts", []),
        "annotation": content_evidence.get("non_toc_paragraph_texts", []),
        "formula": content_evidence.get("non_toc_paragraph_texts", []),
    }
    missing: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    for kind, expected_items in expected.items():
        actual = [_canonical_text(str(value)) for value in actual_by_kind[kind] if _canonical_text(str(value))]
        covered = _match_distinct_payloads(expected_items, actual)
        missing.extend(item_id for item_id, _text in expected_items if item_id not in covered)
        counts[kind] = {"expected": len(expected_items), "covered": len(covered)}
    return {"counts": counts, "missing_payload_ids": missing}


def _build_toc_evidence(
    document_ir: DocumentIR,
    content_evidence: dict[str, Any],
) -> dict[str, Any]:
    cache_texts = [str(value) for value in content_evidence.get("toc_cache_texts", [])]
    if document_ir.schema_version != "document-ir/v2":
        return {
            "source_block_ids": [],
            "anchor_block_ids": [],
            "expected_field_count": None,
            "field_count": len(cache_texts),
            "cache_missing_heading_ids": [],
            "disposition_violations": [],
        }
    toc_source_ids = [
        block.id for block in document_ir.blocks if block.layout is not None and block.layout.role == "toc_source"
    ]
    toc_anchor_ids = [
        block.id for block in document_ir.blocks if block.metadata.get("annotation_role") == "toc_anchor"
    ]
    expected_field_count = 1 if toc_anchor_ids else 0
    cache = _canonical_text("".join(cache_texts))
    missing_heading_ids = [
        block.id
        for block in document_ir.blocks
        if block.type == "heading"
        and (block.layout is None or block.layout.role == "body")
        and _canonical_text(block.text or "") not in cache
        and toc_anchor_ids
    ]
    actual_field_count = len(cache_texts)
    violations: list[str] = []
    if toc_source_ids and not toc_anchor_ids:
        violations.append("toc_source_without_anchor")
    if actual_field_count != expected_field_count:
        violations.append("toc_field_count_mismatch")
    if missing_heading_ids:
        violations.append("toc_cache_heading_missing")
    return {
        "source_block_ids": toc_source_ids,
        "anchor_block_ids": toc_anchor_ids,
        "expected_field_count": expected_field_count,
        "field_count": actual_field_count,
        "cache_missing_heading_ids": missing_heading_ids,
        "disposition_violations": violations,
    }


def _build_image_evidence(
    document_ir: DocumentIR,
    body_blocks: list[DocumentIRBlock],
    content_evidence: dict[str, Any],
) -> dict[str, Any]:
    expected_asset_ids = [
        block.asset_ref
        for block in body_blocks
        if block.type == "image" and block.asset_ref
        for _fragment in range(expected_image_shape_count(block))
    ]
    actual_items = [item for item in content_evidence.get("image_asset_evidence", []) if isinstance(item, dict)]
    actual_asset_ids = [str(item.get("asset_id") or "") for item in actual_items if item.get("asset_id")]
    expected_fragments = [
        {
            "asset_id": block.asset_ref,
            "crop_offsets": list(drawingml_crop_offsets(rect)),
        }
        for block in body_blocks
        if block.type == "image" and block.asset_ref
        for rect in visual_crop_rects(block)
    ]
    expected_fragments.extend(
        {"asset_id": block.asset_ref, "crop_offsets": None}
        for block in body_blocks
        if block.type == "image" and block.asset_ref and not visual_crop_rects(block)
    )
    actual_fragments = [
        {
            "asset_id": str(item.get("asset_id") or ""),
            "crop_offsets": item.get("crop_offsets"),
        }
        for item in actual_items
        if item.get("asset_id")
    ]
    expected_fragment_counts = Counter(_fragment_key(item) for item in expected_fragments)
    actual_fragment_counts = Counter(_fragment_key(item) for item in actual_fragments)
    expected_order = _fragment_order_by_asset(expected_fragments)
    actual_order = _fragment_order_by_asset(actual_fragments)
    order_mismatch_asset_ids = sorted(
        asset_id
        for asset_id in expected_order.keys() & actual_order.keys()
        if Counter(expected_order[asset_id]) == Counter(actual_order[asset_id])
        and expected_order[asset_id] != actual_order[asset_id]
    )
    invalid_crop_block_ids = [
        block.id
        for block in body_blocks
        if block.type == "image"
        and block.metadata.get("visual_crop_rects") is not None
        and not visual_crop_rects(block)
    ]
    expected_counts = Counter(expected_asset_ids)
    actual_counts = Counter(actual_asset_ids)
    assets_by_id = {asset.id: asset for asset in document_ir.assets}
    unresolved = sorted(
        {
            str(item.get("asset_id") or "")
            for item in actual_items
            if not item.get("relationship_id") or not item.get("checksum_sha256")
        }
        - {""}
    )
    checksum_mismatches = sorted(
        asset_id
        for asset_id in expected_counts
        if assets_by_id.get(asset_id) is not None
        and assets_by_id[asset_id].checksum_sha256
        and any(
            item.get("checksum_sha256") != assets_by_id[asset_id].checksum_sha256
            for item in actual_items
            if item.get("asset_id") == asset_id
        )
    )
    return {
        "expected_asset_ids": expected_asset_ids,
        "rendered_assets": actual_items,
        "expected_fragments": expected_fragments,
        "invalid_crop_block_ids": invalid_crop_block_ids,
        "missing_fragments": _fragment_items(expected_fragment_counts - actual_fragment_counts),
        "unexpected_fragments": _fragment_items(actual_fragment_counts - expected_fragment_counts),
        "order_mismatch_asset_ids": order_mismatch_asset_ids,
        "missing_asset_ids": sorted((expected_counts - actual_counts).elements()),
        "unexpected_asset_ids": sorted((actual_counts - expected_counts).elements()),
        "unresolved_asset_ids": unresolved,
        "checksum_mismatch_asset_ids": checksum_mismatches,
    }


def _build_visual_table_composite_evidence(
    body_blocks: list[DocumentIRBlock],
    content_evidence: dict[str, Any],
) -> dict[str, Any]:
    """证明每个表图关系组只生成一个带身份标记的原生复合容器。"""

    expected = [
        str(block.metadata["visual_overlap_group_id"])
        for block in body_blocks
        if block.type == "image" and block.metadata.get("visual_overlap_group_id")
    ]
    actual = [str(value) for value in content_evidence.get("visual_table_composite_ids", []) if value]
    expected_counts = Counter(expected)
    actual_counts = Counter(actual)
    return {
        "expected_group_ids": expected,
        "rendered_group_ids": actual,
        "missing_group_ids": sorted((expected_counts - actual_counts).elements()),
        "unexpected_group_ids": sorted((actual_counts - expected_counts).elements()),
    }


def _fragment_key(item: dict[str, Any]) -> tuple[str, tuple[int, ...] | str | None]:
    crop_offsets = item.get("crop_offsets")
    if isinstance(crop_offsets, list):
        crop_key: tuple[int, ...] | str | None = tuple(int(value) for value in crop_offsets)
    elif isinstance(crop_offsets, str):
        crop_key = crop_offsets
    else:
        crop_key = None
    return str(item.get("asset_id") or ""), crop_key


def _fragment_items(
    counts: Counter[tuple[str, tuple[int, ...] | str | None]],
) -> list[dict[str, Any]]:
    return [
        {
            "asset_id": asset_id,
            "crop_offsets": list(crop_offsets) if isinstance(crop_offsets, tuple) else crop_offsets,
        }
        for (asset_id, crop_offsets), count in sorted(counts.items(), key=lambda item: repr(item[0]))
        for _ in range(count)
    ]


def _fragment_order_by_asset(
    fragments: list[dict[str, Any]],
) -> dict[str, list[tuple[int, ...] | str | None]]:
    order: dict[str, list[tuple[int, ...] | str | None]] = {}
    for item in fragments:
        asset_id, crop_offsets = _fragment_key(item)
        order.setdefault(asset_id, []).append(crop_offsets)
    return order


def _prepared_visible_text(text: str, terminology: TerminologyReplacer | None) -> str:
    segments = _parse_mixed_math_segments(text)
    if segments is not None:
        values = []
        for kind, value in segments:
            if kind == "math":
                values.append("".join(element.text or "" for element in value.iter() if element.tag.endswith("}t")))
            else:
                values.append(BeautifulSoup(prepare_text_for_rendering(value, terminology), "html.parser").get_text())
        return _canonical_text("".join(values))
    return _canonical_text(BeautifulSoup(prepare_text_for_rendering(text, terminology), "html.parser").get_text())


def _canonical_formula_text(text: str, terminology: TerminologyReplacer | None) -> str:
    math = _OmmlParser(text).parse()
    if math is None:
        return _prepared_visible_text(text, terminology)
    return _canonical_text("".join(element.text or "" for element in math.iter() if element.tag.endswith("}t")))


def _canonical_text(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split())


def _match_distinct_payloads(expected: list[tuple[str, str]], actual: list[str]) -> set[str]:
    remaining = list(actual)
    covered: set[str] = set()
    # 长文本和精确文本优先，避免短前缀消耗本应证明另一项的 DOCX 文本节点。
    for item_id, text in sorted(expected, key=lambda item: len(item[1]), reverse=True):
        if not text:
            covered.add(item_id)
            continue
        match_index = next((index for index, value in enumerate(remaining) if text == value), None)
        if match_index is None:
            match_index = next((index for index, value in enumerate(remaining) if text in value), None)
        if match_index is None:
            continue
        covered.add(item_id)
        remaining.pop(match_index)
    return covered


def _unique_texts(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))
