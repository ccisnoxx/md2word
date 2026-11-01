from __future__ import annotations

# app/services/renderer/layout_plan.py: 将 DocumentIR v2 布局事实规划为 Word renderer 内部页面/区域计划。

from dataclasses import dataclass, field
from collections import Counter
import hashlib
import json
import math

from app.services.document_ir.models import DocumentIR, DocumentIRBlock, DocumentIRPage


IMAGE_GROUP_VERSION = "image-group/v1"
IMAGE_GROUP_THRESHOLDS = {"common_overlap": 0.80, "height_ratio": 0.80,
                          "center_offset": 0.10, "top_offset": 0.015, "gap": 0.08}


@dataclass(frozen=True, slots=True)
class ImageSpan:
    """源序连续图片的一次决定；旧页面区域的统计和排序不因此改变。"""

    block_ids: tuple[str, ...]
    page_index: int | None
    mode: str
    reasons: tuple[str, ...] = ()
    metrics: tuple[tuple[str, float], ...] = ()

    @property
    def id(self) -> str:
        value = json.dumps([IMAGE_GROUP_VERSION, self.page_index, self.block_ids], separators=(",", ":"))
        return "ig_" + hashlib.sha256(value.encode()).hexdigest()[:24]


def image_annotations(block: DocumentIRBlock) -> tuple[tuple[str, str], ...]:
    """沿用图片注释合并去重合同，同时保留首个原始字段来源。"""

    values = [(f"captions/{i}", text) for i, text in enumerate(block.captions)]
    if isinstance(block.metadata.get("caption"), str):
        values.append(("metadata/caption", block.metadata["caption"]))
    values.extend((f"footnotes/{i}", text) for i, text in enumerate(block.footnotes))
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for field_name, value in values:
        text = value.strip()
        if text and text not in seen:
            result.append((field_name, text))
            seen.add(text)
    return tuple(result)


def image_row_metrics(blocks: list[DocumentIRBlock], height: float) -> dict[str, float]:
    boxes = [block.layout.bbox for block in blocks]
    heights = [box[3] - box[1] for box in boxes]
    centers = [(box[1] + box[3]) / 2 for box in boxes]
    return {"common_overlap": (min(box[3] for box in boxes) - max(box[1] for box in boxes)) / max(heights),
            "height_ratio": min(heights) / max(heights),
            "center_offset": (max(centers) - min(centers)) / min(heights),
            "top_offset": (max(box[1] for box in boxes) - min(box[1] for box in boxes)) / height}


def _aligned(metrics: dict[str, float]) -> bool:
    return (metrics["common_overlap"] >= IMAGE_GROUP_THRESHOLDS["common_overlap"]
            and metrics["height_ratio"] >= IMAGE_GROUP_THRESHOLDS["height_ratio"]
            and metrics["center_offset"] <= IMAGE_GROUP_THRESHOLDS["center_offset"]
            and metrics["top_offset"] <= IMAGE_GROUP_THRESHOLDS["top_offset"])


def build_image_plan(document_ir: DocumentIR) -> tuple[ImageSpan, ...]:
    """仅用最终 IR 判定图片组，不重排源块，也不读取资产或运行时配置。"""

    pages = {page.index: page for page in document_ir.pages}
    source = sorted(document_ir.blocks, key=lambda block: block.order)
    duplicate_orders = {order for order, count in Counter(b.order for b in source).items() if count > 1}
    localized = any(isinstance(b.metadata.get("caption_reconciliation"), dict)
                    and b.metadata["caption_reconciliation"].get("status") == "uncertain" for b in source)
    global_uncertain = "caption_binding_uncertain" in document_ir.quality_flags and not localized
    spans: list[ImageSpan] = []
    run: list[DocumentIRBlock] = []

    def flush() -> None:
        if not run:
            return
        page_index = _block_page_index(run[0])
        if len(run) == 1:
            spans.append(ImageSpan((run[0].id,), page_index, "single"))
            run.clear()
            return
        page = pages.get(page_index)
        reason = None
        if document_ir.schema_version != "document-ir/v2" or page is None or page.width is None or page.height is None:
            reason = "geometry_unavailable"
        elif not all(math.isfinite(v) and v > 0 for v in (page.width, page.height)):
            reason = "geometry_invalid"
        else:
            for block in run:
                box = _bbox(block)
                if box is None:
                    reason = "geometry_unavailable"
                    break
                if not all(math.isfinite(v) for v in box) or not (0 <= box[0] < box[2] <= page.width and 0 <= box[1] < box[3] <= page.height):
                    reason = "geometry_invalid"
                    break
                if block.page_index is not None and block.layout.page_index is not None and block.page_index != block.layout.page_index:
                    reason = "page_or_section_boundary"
                    break
        if any(block.order in duplicate_orders for block in run):
            reason = "source_order_conflict"
        if reason:
            spans.append(ImageSpan(tuple(b.id for b in run), page_index, "single_sequence", (reason,)))
            run.clear()
            return
        # 连通只用于发现竞争分量；最终必须重新证明整个分量的共同阈值。
        remaining = set(range(len(run)))
        components: list[list[int]] = []
        while remaining:
            component = {min(remaining)}
            frontier = list(component)
            remaining -= component
            while frontier:
                index = frontier.pop()
                neighbors = {other for other in remaining if _aligned(image_row_metrics([run[index], run[other]], page.height))}
                remaining -= neighbors
                component |= neighbors
                frontier.extend(neighbors)
            components.append(sorted(component))
        decisions: dict[int, ImageSpan] = {}
        for indices in components:
            members = [run[i] for i in indices]
            metrics = image_row_metrics(members, page.height)
            reasons: list[str] = []
            if indices != list(range(indices[0], indices[-1] + 1)) or not _aligned(metrics):
                reasons.append("competing_row_membership")
            if len(indices) == 1:
                box = _bbox(members[0])
                if any(min(box[3], _bbox(other)[3]) > max(box[1], _bbox(other)[1]) for other in run if other is not members[0]):
                    reasons.append("row_alignment_insufficient")
            if len(indices) > 1:
                boxes = [_bbox(member) for member in members]
                if any(right[0] <= left[0] for left, right in zip(boxes, boxes[1:])):
                    reasons.append("source_order_conflict")
                elif any(right[0] < left[2] for left, right in zip(boxes, boxes[1:])):
                    reasons.append("horizontal_overlap")
                if any((right[0] - left[2]) / page.width > IMAGE_GROUP_THRESHOLDS["gap"] for left, right in zip(boxes, boxes[1:])):
                    reasons.append("gap_too_large")
                if global_uncertain or any((receipt := member.metadata.get("caption_reconciliation", {})).get("status") == "uncertain" or receipt.get("candidates") for member in members):
                    reasons.append("caption_binding_uncertain")
                if any(receipt.get("evidence_only") for member in members for receipt in member.metadata.get("caption_reconciliation", {}).get("bindings", [])):
                    reasons.append("external_caption_binding")
            # 非连续竞争分量不能作为原子单元移动；逐块展开，保留每个源位置。
            if indices != list(range(indices[0], indices[-1] + 1)):
                for index in indices:
                    decisions[index] = ImageSpan((run[index].id,), page_index, "single_sequence", tuple(dict.fromkeys(reasons)))
            else:
                mode = "group" if len(indices) > 1 and not reasons else ("single_sequence" if reasons else "single")
                decisions[indices[0]] = ImageSpan(tuple(b.id for b in members), page_index, mode, tuple(dict.fromkeys(reasons)), tuple(metrics.items()))
        spans.extend(decisions[index] for index in sorted(decisions))
        run.clear()

    for block in source:
        if block.type != "image" or _block_role(block) != "body":
            flush()
            continue
        if run and _block_page_index(run[-1]) != _block_page_index(block):
            flush()
        run.append(block)
    flush()
    return tuple(spans)


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
    # 归一化坐标页面宽高相等，方向取 IR 页 metadata（源自 PDF 页尺寸），不能用宽 > 高推断。
    landscape: bool = False


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

    from app.services.document_ir.table_placeholder import decode_placeholders
    unknown_owners = {item.owner_block_id for item in decode_placeholders(document_ir) if item.page_index is None}
    page_sizes = {page.index: (page.width, page.height) for page in document_ir.pages}
    landscape_pages = {page.index for page in document_ir.pages if _page_is_landscape(page)}
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
                landscape=page_index in landscape_pages,
            )
        )
    _place_unlocated_placeholders(pages, [block for block in document_ir.blocks
        if (block.id in unknown_owners or (
            block.type == "paragraph" and block.metadata.get("annotation_role") == "table_context"
            and block.metadata.get("source_block_id") in unknown_owners))
        and _block_page_index(block) is None and _block_role(block) == "body"])
    return LayoutPlan(mode="layout_v2", pages=pages)


def _place_unlocated_placeholders(pages: list[LayoutPage], blocks: list[DocumentIRBlock]) -> None:
    """只给未知页占位安排输出锚点；不写源页号，不重排既有页、栏或装饰。

    单栏可在来源邻块处插入；双栏作为完整区域保留，避免切断左/右栏而改变正常阅读顺序。
    converter 派生 context 与 owner 同 order；稳定排序保留数组中的 context→owner 展开顺序。
    """
    if not blocks or not pages:
        return
    anchors = [(block.order, page_index, region_index, block_index)
               for page_index, page in enumerate(pages) for region_index, region in enumerate(page.regions)
               for block_index, block in enumerate(region.blocks)]
    insertions: dict[tuple[int, int, int], list[DocumentIRBlock]] = {}
    for block in sorted(blocks, key=lambda item: item.order):
        before = [anchor for anchor in anchors if anchor[0] < block.order]
        if before:
            _, pi, ri, bi = max(before)
            region = pages[pi].regions[ri]
            offset = len(region.blocks) if region.kind == "two_col" else bi + 1
        elif anchors:
            _, pi, ri, _ = min(anchors)
            offset = 0
        else:
            pi, ri, offset = 0, 0, 0
        insertions.setdefault((pi, ri, offset), []).append(block)
    for pi, page in enumerate(pages):
        output = []
        for ri, region in enumerate(page.regions or [LayoutRegion("one_col", [])]):
            start = 0
            for offset in range(len(region.blocks) + 1):
                additions = insertions.get((pi, ri, offset))
                if additions:
                    if offset > start:
                        output.append(LayoutRegion(region.kind, region.blocks[start:offset]))
                    output.append(LayoutRegion("unlocated", additions))
                    start = offset
            if start < len(region.blocks):
                output.append(LayoutRegion(region.kind, region.blocks[start:]))
        page.regions[:] = output


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
    return _merge_single_column_tails(regions, page_width)


def _merge_single_column_tails(regions: list[LayoutRegion], page_width: float) -> list[LayoutRegion]:
    """把有充分栏位证据的同侧正文尾部留在前一双栏流中。"""

    merged: list[LayoutRegion] = []
    index = 0
    while index < len(regions):
        region = regions[index]
        tail = regions[index + 1] if index + 1 < len(regions) else None
        later_regions = regions[index + 2 :]
        if (
            region.kind == "two_col"
            and not _is_image_only_region(region)
            and tail is not None
            and tail.kind == "one_col"
            and _is_single_side_text_tail(tail, page_width)
            and all(candidate.kind == "two_col" and _is_image_only_region(candidate) for candidate in later_regions)
        ):
            merged.append(LayoutRegion(kind="two_col", blocks=[*region.blocks, *tail.blocks]))
            index += 2
            continue
        merged.append(region)
        index += 1
    return merged


def _is_single_side_text_tail(region: LayoutRegion, page_width: float) -> bool:
    if not region.blocks or any(block.type == "image" or _bbox(block) is None for block in region.blocks):
        return False
    classes = {_classify_body_block(block, page_width) for block in region.blocks}
    return classes in ({"left"}, {"right"})


def _is_image_only_region(region: LayoutRegion) -> bool:
    return bool(region.blocks) and all(block.type == "image" for block in region.blocks)


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
    if interval_bands:
        return _merge_bands(interval_bands)
    return _merge_bands(_detect_stable_two_col_bands(body_blocks, page_width))


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
    top = max(
        min(_bbox(block)[1] for block in blocks if _bbox(block) is not None)
        for blocks in (left_blocks, right_blocks)
    )
    bottom = min(
        max(_bbox(block)[3] for block in blocks if _bbox(block) is not None)
        for blocks in (left_blocks, right_blocks)
    )
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


def _page_is_landscape(page: DocumentIRPage) -> bool:
    orientation = page.metadata.get("orientation")
    if orientation in {"landscape", "portrait"}:
        return orientation == "landscape"
    return bool(page.width and page.height and page.width > page.height)


def _block_role(block: DocumentIRBlock) -> str:
    return block.layout.role if block.layout is not None else "body"


def split_two_col_blocks(
    blocks: list[DocumentIRBlock],
) -> tuple[list[DocumentIRBlock], list[DocumentIRBlock]]:
    """双栏读取顺序的共享 owner；布局对账与实际输出使用相同分流规则。"""
    left_blocks: list[DocumentIRBlock] = []
    right_blocks: list[DocumentIRBlock] = []
    for block in blocks:
        column_hint = block.layout.column_hint if block.layout is not None else None
        if column_hint == "left":
            left_blocks.append(block)
            continue
        if column_hint == "right":
            right_blocks.append(block)
            continue
        if column_hint == "wide":
            left_blocks.append(block)
            continue
        bbox = block.layout.bbox if block.layout is not None else None
        if bbox is None:
            left_blocks.append(block)
            continue
        page_width = max((candidate.layout.bbox[2] for candidate in blocks if candidate.layout and candidate.layout.bbox), default=bbox[2])
        center_x = (bbox[0] + bbox[2]) / 2
        if center_x < page_width / 2:
            left_blocks.append(block)
        else:
            right_blocks.append(block)
    return left_blocks, right_blocks
