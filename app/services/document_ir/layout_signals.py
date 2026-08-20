from __future__ import annotations

# app/services/document_ir/layout_signals.py: 从 MinerU 原始块和 layout/middle JSON 中提取 DocumentIR v2 布局事实。

import json
from pathlib import Path
from typing import Any

from app.conversion.docx_rules.mineru_content import (
    collect_text_from_fields,
    extract_first_asset_path,
    extract_first_html,
    is_empty_table_placeholder,
)
from app.services.document_ir.models import (
    DocumentIRBlockLayout,
    DocumentIRBlockRole,
    DocumentIRColumnHint,
    DocumentIRPage,
)


ROLE_BY_SOURCE_TYPE: dict[str, DocumentIRBlockRole] = {
    "header": "page_header",
    "page_header": "page_header",
    "footer": "page_footer",
    "page_footer": "page_footer",
    "page_number": "page_number",
}


def build_pages(
    raw_blocks: list[dict[str, Any]],
    package_root: Path,
    quality_flags: list[str],
    *,
    excluded_page_indices: set[int] | None = None,
) -> list[DocumentIRPage]:
    """构造 v2 页记录；优先读取 layout/middle 页尺寸，再对齐 content bbox 坐标空间。"""

    page_sizes, source_name = _load_page_sizes(package_root)
    if source_name is None:
        quality_flags.append("middle_json_missing")

    page_indices = set(page_sizes)
    page_indices.update(page_index for block in raw_blocks if (page_index := parse_page_index(block)) is not None)
    if not page_indices and not excluded_page_indices:
        page_indices.add(0)
    page_indices.difference_update(excluded_page_indices or set())

    bbox_extents = _bbox_extents_by_page(raw_blocks)
    pages: list[DocumentIRPage] = []
    for page_index in sorted(page_indices):
        raw_size = page_sizes.get(page_index)
        max_width, max_height = bbox_extents.get(page_index, (None, None))
        if raw_size is not None and raw_size[0] > 0 and raw_size[1] > 0:
            scale = max(
                1.0,
                max_width / raw_size[0] if max_width is not None else 1.0,
                max_height / raw_size[1] if max_height is not None else 1.0,
            )
            width = raw_size[0] * scale
            height = raw_size[1] * scale
        else:
            width = max_width
            height = max_height
        metadata: dict[str, Any] = {}
        if raw_size is not None:
            metadata["pdf_page_size"] = [raw_size[0], raw_size[1]]
            metadata["page_size_source"] = source_name
        if max_width is not None and max_height is not None:
            metadata["bbox_extent"] = [max_width, max_height]
        if width is not None and height is not None:
            metadata["orientation"] = "landscape" if width > height else "portrait"
        pages.append(DocumentIRPage(index=page_index, width=width, height=height, metadata=metadata))
    return pages


def find_final_source_page_index(
    raw_blocks: list[dict[str, Any]],
    package_root: Path,
) -> int | None:
    """优先按 MinerU 物理页元数据确定最后源页，缺失时回退到内容块页号。"""

    pdf_info, _source_name = _load_pdf_info(package_root)
    if pdf_info:
        page_indices = [
            _coerce_int(page_info.get("page_idx"), fallback=fallback_index)
            for fallback_index, page_info in enumerate(pdf_info)
            if isinstance(page_info, dict)
        ]
        if page_indices:
            return max(page_indices)
    return max(
        (page_index for block in raw_blocks if (page_index := parse_page_index(block)) is not None),
        default=None,
    )


def build_block_layout(
    raw_block: dict[str, Any],
    *,
    source_type: str,
    source_index: int,
    quality_flags: list[str],
    block_id: str,
    page_width: float | None = None,
) -> DocumentIRBlockLayout:
    """把 MinerU 块级 page/bbox/role 信息收口为 DocumentIRBlockLayout。"""

    bbox = parse_bbox(raw_block.get("bbox"))
    if bbox is None:
        quality_flags.append(f"layout_bbox_missing:{block_id}")
    continuation_heights = _parse_float_list(
        raw_block.get("continuation_heights", raw_block.get("table_continuation_heights"))
    )
    if continuation_heights:
        quality_flags.append(f"table_continuation:{block_id}")
    column_hint = _parse_column_hint(raw_block.get("column_hint")) or _classify_column_hint(bbox, page_width)
    if column_hint in {"left", "right"}:
        quality_flags.append(f"layout_two_column_candidate:{block_id}:{column_hint}")
    if source_type == "table" and column_hint == "wide":
        quality_flags.append(f"layout_wide_table:{block_id}")
    return DocumentIRBlockLayout(
        page_index=parse_page_index(raw_block),
        bbox=bbox,
        role=role_for_source_type(source_type),
        source_index=source_index,
        continuation_heights=continuation_heights,
        column_hint=column_hint,
    )


def build_block_layout_metadata(
    layout: DocumentIRBlockLayout,
    *,
    page_width: float | None,
) -> dict[str, Any]:
    """生成只用于排障的块级布局诊断 metadata。"""

    if layout.column_hint is None:
        return {}
    if layout.bbox is None or page_width is None or page_width <= 0:
        return {"layout_role_reason": f"column_hint={layout.column_hint}"}
    bbox_width = layout.bbox[2] - layout.bbox[0]
    return {
        "layout_role_reason": (
            f"column_hint={layout.column_hint};bbox_width={bbox_width:.2f};page_width={page_width:.2f}"
        )
    }


def merge_table_placeholder_continuations(raw_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把显式或 MinerU 空表续页高度并入前一张真实表。"""

    merged: list[dict[str, Any]] = []
    pending_table: dict[str, Any] | None = None
    for raw_block in raw_blocks:
        source_type = _source_type(raw_block)
        is_placeholder = source_type == "table_placeholder" or _is_mineru_empty_table_placeholder(raw_block)
        if is_placeholder and pending_table is not None:
            placeholder_height = _placeholder_height(raw_block)
            if placeholder_height is not None:
                continuation_heights = _parse_float_list(
                    pending_table.get("continuation_heights", pending_table.get("table_continuation_heights"))
                )
                pending_table["continuation_heights"] = [*continuation_heights, placeholder_height]
            continue

        copied = dict(raw_block)
        merged.append(copied)
        if _is_table_block(copied):
            pending_table = copied
        elif source_type not in {"header", "footer", "page_header", "page_footer", "page_number"}:
            pending_table = None
    return merged


def role_for_source_type(source_type: str) -> DocumentIRBlockRole:
    return ROLE_BY_SOURCE_TYPE.get(source_type, "body")


def parse_page_index(raw_block: dict[str, Any]) -> int | None:
    raw_page = raw_block.get("page_idx", raw_block.get("page_index"))
    if isinstance(raw_page, int):
        return raw_page
    try:
        return int(raw_page)
    except (TypeError, ValueError):
        return None


def parse_bbox(raw_bbox: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return None
    try:
        return tuple(float(value) for value in raw_bbox)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _load_page_sizes(package_root: Path) -> tuple[dict[int, tuple[float, float]], str | None]:
    for path in _layout_info_candidates(package_root):
        payload = json.loads(path.read_text(encoding="utf-8"))
        pdf_info = payload.get("pdf_info", []) if isinstance(payload, dict) else []
        page_sizes: dict[int, tuple[float, float]] = {}
        for fallback_index, page_info in enumerate(pdf_info):
            if not isinstance(page_info, dict):
                continue
            page_index = _coerce_int(page_info.get("page_idx"), fallback=fallback_index)
            page_size = _parse_page_size(page_info.get("page_size"))
            if page_size is not None:
                page_sizes[page_index] = page_size
        if page_sizes:
            return page_sizes, path.name
    return {}, None


def _load_pdf_info(package_root: Path) -> tuple[list[Any], str | None]:
    for path in _layout_info_candidates(package_root):
        payload = json.loads(path.read_text(encoding="utf-8"))
        pdf_info = payload.get("pdf_info", []) if isinstance(payload, dict) else []
        if isinstance(pdf_info, list) and pdf_info:
            return pdf_info, path.name
    return [], None


def _layout_info_candidates(package_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in package_root.rglob("*.json"):
        name = path.name
        if name in {"middle.json", "layout.json"} or name.endswith("_middle.json") or name.endswith("_layout.json"):
            candidates.append(path)
    return sorted(candidates, key=lambda item: (0 if item.name in {"middle.json", "layout.json"} else 1, len(item.parts), item.as_posix()))


def _parse_page_size(raw_value: Any) -> tuple[float, float] | None:
    if not isinstance(raw_value, (list, tuple)) or len(raw_value) != 2:
        return None
    try:
        width = float(raw_value[0])
        height = float(raw_value[1])
    except (TypeError, ValueError):
        return None
    return width, height


def _parse_float_list(raw_value: Any) -> list[float]:
    if not isinstance(raw_value, list):
        return []
    values: list[float] = []
    for item in raw_value:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            continue
    return values


def _parse_column_hint(raw_value: Any) -> DocumentIRColumnHint | None:
    if raw_value in {"left", "right", "wide"}:
        return raw_value
    return None


def _classify_column_hint(
    bbox: tuple[float, float, float, float] | None,
    page_width: float | None,
) -> DocumentIRColumnHint | None:
    if bbox is None or page_width is None or page_width <= 0:
        return None
    bbox_width = bbox[2] - bbox[0]
    if bbox_width >= page_width * 0.6:
        return "wide"
    center_x = (bbox[0] + bbox[2]) / 2
    return "left" if center_x < page_width / 2 else "right"


def _placeholder_height(raw_block: dict[str, Any]) -> float | None:
    raw_height = raw_block.get("height")
    try:
        height = float(raw_height)
    except (TypeError, ValueError):
        bbox = parse_bbox(raw_block.get("bbox"))
        height = bbox[3] - bbox[1] if bbox is not None else None
    if height is None or height <= 0:
        return None
    return height


def _source_type(raw_block: dict[str, Any]) -> str:
    return str(raw_block.get("type") or raw_block.get("block_type") or "").strip().lower()


def _is_table_block(raw_block: dict[str, Any]) -> bool:
    source_type = _source_type(raw_block)
    return source_type == "table" or bool(raw_block.get("table_body") or raw_block.get("table_html"))


def _is_mineru_empty_table_placeholder(raw_block: dict[str, Any]) -> bool:
    bbox = parse_bbox(raw_block.get("bbox")) or (0.0, 0.0, 0.0, 0.0)
    direct_asset_path = raw_block.get("img_path", raw_block.get("image_path"))
    raw_asset_path = direct_asset_path if isinstance(direct_asset_path, str) else extract_first_asset_path(raw_block)
    return is_empty_table_placeholder(
        block_type=_source_type(raw_block),
        raw_asset_path=raw_asset_path,
        image_path=None,
        captions=collect_text_from_fields(
            raw_block,
            ("table_caption", "caption", "captions", "table_footnote", "footnote", "footnotes"),
        ),
        html=extract_first_html(raw_block),
        text_candidates=collect_text_from_fields(
            raw_block,
            ("text", "equation_content", "math_content", "latex", "alt", "description"),
        ),
        bbox=bbox,
    )


def _bbox_extents_by_page(raw_blocks: list[dict[str, Any]]) -> dict[int, tuple[float, float]]:
    extents: dict[int, tuple[float, float]] = {}
    for block in raw_blocks:
        page_index = parse_page_index(block)
        bbox = parse_bbox(block.get("bbox"))
        if page_index is None or bbox is None:
            continue
        current_width, current_height = extents.get(page_index, (0.0, 0.0))
        extents[page_index] = (max(current_width, bbox[2]), max(current_height, bbox[3]))
    return extents


def _coerce_int(value: Any, *, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
