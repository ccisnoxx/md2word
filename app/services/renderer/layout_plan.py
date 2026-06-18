from __future__ import annotations

# app/services/renderer/layout_plan.py: 将 DocumentIR v2 布局事实规划为 Word renderer 内部页面/区域计划。

from dataclasses import dataclass, field

from app.services.document_ir.models import DocumentIR, DocumentIRBlock


@dataclass(frozen=True, slots=True)
class LayoutRegion:
    """页面正文中的连续渲染区域。"""

    kind: str
    blocks: list[DocumentIRBlock]


@dataclass(frozen=True, slots=True)
class LayoutPage:
    """renderer 内部页计划，区分页眉页脚和正文区域。"""

    index: int
    width: float | None
    height: float | None
    header_blocks: list[DocumentIRBlock] = field(default_factory=list)
    footer_blocks: list[DocumentIRBlock] = field(default_factory=list)
    page_number_blocks: list[DocumentIRBlock] = field(default_factory=list)
    regions: list[LayoutRegion] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    """DocumentIRWordRenderer 的运行时布局计划；不持久化。"""

    mode: str
    pages: list[LayoutPage]


def build_layout_plan(document_ir: DocumentIR) -> LayoutPlan:
    """从 DocumentIR 构造布局计划；v1 或缺布局字段时回退到顺序渲染。"""

    if document_ir.schema_version != "document-ir/v2" or not document_ir.pages:
        return _build_legacy_plan(document_ir)
    if not any(block.layout is not None for block in document_ir.blocks):
        return _build_legacy_plan(document_ir)

    page_sizes = {page.index: (page.width, page.height) for page in document_ir.pages}
    page_indices = set(page_sizes)
    page_indices.update(_block_page_index(block) for block in document_ir.blocks)
    pages: list[LayoutPage] = []
    for page_index in sorted(index for index in page_indices if index is not None):
        page_blocks = [block for block in document_ir.blocks if _block_page_index(block) == page_index]
        header_blocks = _sort_blocks([block for block in page_blocks if _block_role(block) == "page_header"])
        footer_blocks = _sort_blocks([block for block in page_blocks if _block_role(block) == "page_footer"])
        page_number_blocks = _sort_blocks([block for block in page_blocks if _block_role(block) == "page_number"])
        body_blocks = _sort_blocks([block for block in page_blocks if _block_role(block) == "body"])
        width, height = page_sizes.get(page_index, (None, None))
        pages.append(
            LayoutPage(
                index=page_index,
                width=width,
                height=height,
                header_blocks=header_blocks,
                footer_blocks=footer_blocks,
                page_number_blocks=page_number_blocks,
                regions=_build_regions(body_blocks, width),
            )
        )
    return LayoutPlan(mode="layout_v2", pages=pages)


def _build_legacy_plan(document_ir: DocumentIR) -> LayoutPlan:
    return LayoutPlan(
        mode="legacy_v1_fallback",
        pages=[
            LayoutPage(
                index=0,
                width=None,
                height=None,
                regions=[LayoutRegion(kind="one_col", blocks=sorted(document_ir.blocks, key=lambda item: item.order))],
            )
        ],
    )


def _build_regions(body_blocks: list[DocumentIRBlock], page_width: float | None) -> list[LayoutRegion]:
    if not body_blocks:
        return []
    if page_width is None or page_width <= 0:
        return [LayoutRegion(kind="one_col", blocks=body_blocks)]

    two_col_bands = _detect_two_col_bands(body_blocks, page_width)
    regions: list[LayoutRegion] = []
    for block in body_blocks:
        bbox = _bbox(block)
        mid_y = ((bbox[1] + bbox[3]) / 2) if bbox is not None else None
        block_class = _classify_body_block(block, page_width)
        kind = (
            "two_col"
            if block_class != "wide" and mid_y is not None and any(start <= mid_y <= end for start, end in two_col_bands)
            else "one_col"
        )
        if regions and regions[-1].kind == kind:
            regions[-1].blocks.append(block)
        else:
            regions.append(LayoutRegion(kind=kind, blocks=[block]))
    return regions


def _detect_two_col_bands(body_blocks: list[DocumentIRBlock], page_width: float) -> list[tuple[float, float]]:
    y_points = sorted({value for block in body_blocks if (bbox := _bbox(block)) for value in (bbox[1], bbox[3])})
    intervals: list[tuple[float, float, str]] = []
    for top, bottom in zip(y_points, y_points[1:]):
        if bottom - top < 4:
            continue
        active = [block for block in body_blocks if (bbox := _bbox(block)) and bbox[1] < bottom and bbox[3] > top]
        if not active:
            continue
        roles = {_classify_body_block(block, page_width) for block in active}
        label = "two_col" if "left" in roles and "right" in roles and "wide" not in roles else "one_col"
        intervals.append((top, bottom, label))

    merged: list[tuple[float, float, str]] = []
    for top, bottom, label in intervals:
        if merged and merged[-1][2] == label and top - merged[-1][1] <= 12:
            merged[-1] = (merged[-1][0], bottom, label)
        else:
            merged.append((top, bottom, label))
    interval_bands = [(top, bottom) for top, bottom, label in merged if label == "two_col"]
    return _merge_bands([*interval_bands, *_detect_stable_two_col_bands(body_blocks, page_width)])


def _classify_body_block(block: DocumentIRBlock, page_width: float) -> str:
    if block.layout is not None and block.layout.column_hint in {"left", "right", "wide"}:
        return block.layout.column_hint
    bbox = _bbox(block)
    if bbox is None:
        return "wide"
    width = bbox[2] - bbox[0]
    if width >= page_width * 0.6:
        return "wide"
    center_x = (bbox[0] + bbox[2]) / 2
    return "left" if center_x < page_width / 2 else "right"


def _detect_stable_two_col_bands(
    body_blocks: list[DocumentIRBlock],
    page_width: float,
) -> list[tuple[float, float]]:
    left_blocks = [block for block in body_blocks if _classify_body_block(block, page_width) == "left" and _bbox(block)]
    right_blocks = [block for block in body_blocks if _classify_body_block(block, page_width) == "right" and _bbox(block)]
    if len(left_blocks) < 2 or len(right_blocks) < 2:
        return []
    top = min(_bbox(block)[1] for block in [*left_blocks, *right_blocks] if _bbox(block) is not None)
    bottom = max(_bbox(block)[3] for block in [*left_blocks, *right_blocks] if _bbox(block) is not None)
    return [(top, bottom)] if bottom - top >= 120 else []


def _merge_bands(bands: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not bands:
        return []
    sorted_bands = sorted(bands)
    merged: list[tuple[float, float]] = []
    for top, bottom in sorted_bands:
        if merged and top - merged[-1][1] <= 12:
            merged[-1] = (merged[-1][0], max(merged[-1][1], bottom))
        else:
            merged.append((top, bottom))
    return merged


def _sort_blocks(blocks: list[DocumentIRBlock]) -> list[DocumentIRBlock]:
    return sorted(blocks, key=lambda block: (_sort_y(block), _sort_x(block), block.order))


def _sort_x(block: DocumentIRBlock) -> float:
    bbox = _bbox(block)
    return bbox[0] if bbox is not None else float("inf")


def _sort_y(block: DocumentIRBlock) -> float:
    bbox = _bbox(block)
    return bbox[1] if bbox is not None else float("inf")


def _bbox(block: DocumentIRBlock) -> tuple[float, float, float, float] | None:
    return block.layout.bbox if block.layout is not None else None


def _block_page_index(block: DocumentIRBlock) -> int | None:
    if block.layout is not None and block.layout.page_index is not None:
        return block.layout.page_index
    return block.page_index


def _block_role(block: DocumentIRBlock) -> str:
    return block.layout.role if block.layout is not None else "body"
