"""集中生成 DocumentIR 内容完整性证据并执行失败关闭。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from app.conversion.runtime.table_html_parser import parse_html_table
from app.services.document_ir.models import DocumentIR, DocumentIRBlock


VISUAL_SOURCE_TYPES = {"chart", "image", "figure"}
FORMULA_SOURCE_TYPES = {
    "equation",
    "formula",
    "interline_equation",
    "inline_equation",
    "equation_interline",
}


class DocumentIntegrityError(RuntimeError):
    """确定性内容丢失；调用方必须停止发布当前产物。"""

    def __init__(self, boundary: str, evidence: Mapping[str, Any]) -> None:
        self.boundary = boundary
        self.evidence = dict(evidence)
        flags = [str(flag) for flag in evidence.get("blocking_quality_flags", [])]
        summary = ", ".join(flags) if flags else "unknown_integrity_failure"
        count_keys = (
            "expected_source_block_count",
            "ir_main_block_count",
            "expected_layout_block_count",
            "layout_block_count",
            "expected_inline_shape_count",
            "inline_shape_count",
            "expected_table_count",
            "table_count",
            "expected_heading_count",
            "heading_count",
        )
        counts = ", ".join(
            f"{key}={evidence[key]}"
            for key in count_keys
            if evidence.get(key) is not None
        )
        details = f"（{counts}）" if counts else ""
        super().__init__(f"{boundary} 内容完整性校验失败：{summary}{details}")


def build_source_integrity(document_ir: DocumentIR) -> dict[str, Any]:
    """使用 metadata inventory 与主 IR block 建立 source→IR 对账证据。"""

    expected_total = document_ir.metadata.source_block_count
    expected_types = dict(document_ir.metadata.source_type_counts)
    main_blocks = [block for block in document_ir.blocks if not block.metadata.get("source_block_id")]
    actual_types = Counter(str(block.metadata.get("source_type") or "text") for block in main_blocks)
    flags: list[str] = []

    # 旧 IR 没有 inventory，无法可靠重建 source 合同；仅正式 converter 产物执行对账。
    if expected_total is None and not expected_types:
        return {
            "expected_source_block_count": None,
            "ir_main_block_count": len(main_blocks),
            "source_block_count_delta": None,
            "expected_source_type_counts": {},
            "ir_source_type_counts": dict(sorted(actual_types.items())),
            "blocking_quality_flags": [],
        }

    if expected_total is not None and expected_total != len(main_blocks):
        flags.append("source_ir_integrity:block_count_mismatch")
    if expected_types and expected_types != dict(actual_types):
        flags.append("source_ir_integrity:type_count_mismatch")

    assets_by_id = {asset.id for asset in document_ir.assets}
    requires_semantic_decisions = any("semantic_decision_reason" in block.metadata for block in main_blocks)
    for block in main_blocks:
        source_type = str(block.metadata.get("source_type") or "text")
        role = block.layout.role if block.layout is not None else "body"
        if requires_semantic_decisions and not str(block.metadata.get("semantic_decision_reason") or "").strip():
            flags.append(f"source_ir_integrity:semantic_decision_missing:{source_type}")
        if block.metadata.get("caption_owner_unresolved"):
            flags.append(f"source_ir_integrity:caption_subject_unresolved:{block.id}")
        if block.metadata.get("visual_overlap_unresolved"):
            flags.append(f"source_ir_integrity:visual_overlap_unresolved:{block.id}")
        normalization = block.metadata.get("visual_overlap_normalization")
        group_id = block.metadata.get("visual_overlap_group_id")
        has_group_id = isinstance(group_id, str) and bool(group_id.strip())
        has_normalization = "visual_overlap_normalization" in block.metadata
        if has_group_id != has_normalization or (
            "visual_overlap_group_id" in block.metadata and not has_group_id
        ):
            flags.append(f"source_ir_integrity:visual_overlap_group_invalid:{block.id}")
        if normalization is not None and block.type == "image":
            rects = visual_crop_rects(block)
            mask = visual_overlap_mask(block)
            if not rects or mask is None:
                flags.append(f"source_ir_integrity:visual_crop_rects_invalid:{block.id}")
            elif not _same_rects(rects, complement_crop_rects(mask)):
                flags.append(f"source_ir_integrity:visual_crop_coverage_mismatch:{block.id}")
            elif normalization.get("crop_fragment_count") != len(rects):
                flags.append(f"source_ir_integrity:visual_crop_fragment_count_mismatch:{block.id}")
        elif block.metadata.get("visual_crop_rects") is not None:
            flags.append(f"source_ir_integrity:visual_crop_rects_invalid:{block.id}")
        if role in {"toc_source", "filtered", "page_header", "page_footer", "page_number"}:
            continue
        if source_type in VISUAL_SOURCE_TYPES:
            if block.type != "image":
                flags.append(f"source_ir_integrity:type_mismatch:{source_type}")
            elif not block.asset_ref or block.asset_ref not in assets_by_id:
                flags.append(f"source_ir_integrity:payload_missing:{source_type}")
        elif (source_type == "table" or block.type == "table") and (
            block.type != "table" or parse_html_table(block.html) is None
        ):
            flags.append("source_ir_integrity:payload_missing:table")
        elif source_type in FORMULA_SOURCE_TYPES and (
            block.type != "formula" or not ((block.latex or block.text or "").strip())
        ):
            flags.append(f"source_ir_integrity:payload_missing:{source_type}")
        elif block.type in {"heading", "paragraph"} and not (block.text or "").strip():
            flags.append(f"source_ir_integrity:payload_missing:{source_type}")
        elif source_type in {"list", "index"} and (
            block.type != "list" or not block.list_items
        ):
            flags.append(f"source_ir_integrity:payload_missing:{source_type}")

    normalized_groups: dict[str, list[DocumentIRBlock]] = {}
    for block in main_blocks:
        group_id = block.metadata.get("visual_overlap_group_id")
        if isinstance(group_id, str) and group_id:
            normalized_groups.setdefault(group_id, []).append(block)
    for group_id, group in normalized_groups.items():
        if sorted(block.type for block in group) != ["image", "table"]:
            flags.append(f"source_ir_integrity:visual_overlap_group_invalid:{group_id}")
            continue
        image = next(block for block in group if block.type == "image")
        table = next(block for block in group if block.type == "table")
        normalization = image.metadata.get("visual_overlap_normalization")
        if (
            not isinstance(normalization, dict)
            or table.metadata.get("visual_overlap_normalization") != normalization
            or normalization.get("image_block_id") != image.id
            or normalization.get("table_block_id") != table.id
        ):
            flags.append(f"source_ir_integrity:visual_overlap_group_invalid:{group_id}")

    unique_flags = list(dict.fromkeys(flags))
    return {
        "expected_source_block_count": expected_total,
        "ir_main_block_count": len(main_blocks),
        "source_block_count_delta": None if expected_total is None else len(main_blocks) - expected_total,
        "expected_source_type_counts": expected_types,
        "ir_source_type_counts": dict(sorted(actual_types.items())),
        "blocking_quality_flags": unique_flags,
    }


def ensure_integrity(boundary: str, evidence: Mapping[str, Any]) -> None:
    """存在确定性阻断标记时抛错，禁止调用方继续发布。"""

    if evidence.get("blocking_quality_flags"):
        raise DocumentIntegrityError(boundary, evidence)


def is_visible_body_block(block: DocumentIRBlock) -> bool:
    """判断 block 是否应进入正文布局和最终 DOCX。"""

    role = block.layout.role if block.layout is not None else "body"
    if role != "body":
        return False
    if block.metadata.get("annotation_role") == "toc_anchor":
        return True
    if block.type in {"heading", "paragraph"}:
        return bool((block.text or "").strip())
    if block.type == "table":
        return bool((block.html or block.text or "").strip() or block.captions or block.footnotes)
    if block.type == "image":
        return bool(block.asset_ref or block.captions or block.footnotes or (block.text or "").strip())
    if block.type == "list":
        return bool(block.list_items or (block.text or "").strip())
    if block.type == "formula":
        return bool((block.latex or block.text or "").strip())
    return False


def visual_crop_rects(block: DocumentIRBlock) -> list[tuple[float, float, float, float]]:
    """读取 converter 已裁决的图片保留区域；非法数据由完整性门禁阻断。"""

    raw_rects = block.metadata.get("visual_crop_rects")
    if raw_rects is None:
        return []
    if not isinstance(raw_rects, list):
        return []
    rects: list[tuple[float, float, float, float]] = []
    for raw_rect in raw_rects:
        rect = _normalized_rect(raw_rect)
        if rect is None:
            return []
        rects.append(rect)
    return rects


def visual_overlap_mask(block: DocumentIRBlock) -> tuple[float, float, float, float] | None:
    """读取表图复合关系中的归一化表区遮罩。"""

    normalization = block.metadata.get("visual_overlap_normalization")
    if not isinstance(normalization, dict):
        return None
    return _normalized_rect(normalization.get("masked_rect"))


def complement_crop_rects(
    mask: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    """返回矩形遮罩之外互不重叠的 DrawingML 保留区域。"""

    left, top, right, bottom = mask
    candidates = [
        (0.0, 0.0, left, 1.0),
        (left, 0.0, right, top),
        (right, 0.0, 1.0, 1.0),
        (left, bottom, right, 1.0),
    ]
    return [rect for rect in candidates if rect[2] > rect[0] and rect[3] > rect[1]]


def drawingml_crop_offsets(
    rect: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    """把归一化保留区域转换为 DrawingML `srcRect` 四侧裁剪量。"""

    left, top, right, bottom = rect
    return (
        round(left * 100000),
        round(top * 100000),
        round((1 - right) * 100000),
        round((1 - bottom) * 100000),
    )


def expected_image_shape_count(block: DocumentIRBlock) -> int:
    """返回一个 IR image block 预期写入的 Word drawing 数。"""

    rects = visual_crop_rects(block)
    return len(rects) if rects else 1


def _normalized_rect(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        left, top, right, bottom = (float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        return None
    return left, top, right, bottom


def _same_rects(
    actual: list[tuple[float, float, float, float]],
    expected: list[tuple[float, float, float, float]],
) -> bool:
    return len(actual) == len(expected) and all(
        all(
            abs(actual_value - expected_value) <= 1e-9
            for actual_value, expected_value in zip(left, right, strict=True)
        )
        for left, right in zip(actual, expected, strict=True)
    )
