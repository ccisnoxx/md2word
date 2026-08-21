from __future__ import annotations

# app/services/renderer/layout_plan.py: 将 DocumentIR v2 布局事实规划为 Word renderer 内部页面组和区域计划。

from dataclasses import dataclass, field, replace

from docx.shared import Cm, Twips

from app.conversion.runtime.table_html_parser import HtmlTable, parse_html_table
from app.services.document_ir.integrity import visual_overlap_mask
from app.services.document_ir.models import DocumentIR, DocumentIRBlock
from app.services.renderer.table_layout import TableFitDecision, choose_table_fit_decision
from app.services.renderer.template_config import TemplateConfigPackage


SAME_COLUMN_CONTINUATION_GAP = 24.0
PAGE_EDGE_CONTINUATION_RATIO = 0.2
DEFAULT_WORD_MARGIN_CM = 3.175


@dataclass(frozen=True, slots=True)
class LayoutRegion:
    """页面正文中的连续渲染区域；双栏块已按左栏、右栏的最终顺序排列。"""

    kind: str
    blocks: list[DocumentIRBlock]
    column_break_index: int | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class LayoutPage:
    """Word 页面组计划；一个组可以包含连续的多个 PDF 源页。"""

    index: int
    width: float | None
    height: float | None
    header_blocks: list[DocumentIRBlock] = field(default_factory=list)
    footer_blocks: list[DocumentIRBlock] = field(default_factory=list)
    page_number_blocks: list[DocumentIRBlock] = field(default_factory=list)
    regions: list[LayoutRegion] = field(default_factory=list)
    source_page_indices: tuple[int, ...] = ()
    break_before_block_id: str | None = None
    break_reason: str | None = None
    continuation_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    """DocumentIRWordRenderer 的运行时布局计划；不持久化。"""

    mode: str
    pages: list[LayoutPage]
    table_fit_decisions: dict[str, TableFitDecision] = field(default_factory=dict)


def build_layout_plan(
    document_ir: DocumentIR,
    template_config: TemplateConfigPackage | None = None,
) -> LayoutPlan:
    """构造最终 Word 布局计划；v1 或缺布局字段时回退到顺序渲染。"""

    if document_ir.schema_version != "document-ir/v2" or not document_ir.pages:
        return _build_legacy_plan(document_ir)
    if not any(block.layout is not None for block in document_ir.blocks):
        return _build_legacy_plan(document_ir)

    page_sizes = {page.index: (page.width, page.height) for page in document_ir.pages}
    page_indices = set(page_sizes)
    page_indices.update(_block_page_index(block) for block in document_ir.blocks)
    source_pages: list[LayoutPage] = []
    for page_index in sorted(index for index in page_indices if index is not None):
        page_blocks = [block for block in document_ir.blocks if _block_page_index(block) == page_index]
        header_blocks = _sort_blocks([block for block in page_blocks if _block_role(block) == "page_header"])
        footer_blocks = _sort_blocks([block for block in page_blocks if _block_role(block) == "page_footer"])
        page_number_blocks = _sort_blocks([block for block in page_blocks if _block_role(block) == "page_number"])
        body_blocks = _sort_blocks([block for block in page_blocks if _block_role(block) == "body"])
        width, height = page_sizes.get(page_index, (None, None))
        source_pages.append(
            LayoutPage(
                index=page_index,
                width=width,
                height=height,
                header_blocks=header_blocks,
                footer_blocks=footer_blocks,
                page_number_blocks=page_number_blocks,
                regions=_build_regions(body_blocks, width, height),
                source_page_indices=(page_index,),
            )
        )
    pages = _build_soft_page_groups(source_pages)
    if template_config is None:
        return LayoutPlan(mode="layout_v2", pages=pages)
    planned_pages: list[LayoutPage] = []
    decisions: dict[str, TableFitDecision] = {}
    for page in pages:
        planned_page, page_decisions = _plan_page_tables(page, template_config)
        planned_pages.append(planned_page)
        decisions.update(page_decisions)
    return LayoutPlan(mode="layout_v2", pages=planned_pages, table_fit_decisions=decisions)


def _build_legacy_plan(document_ir: DocumentIR) -> LayoutPlan:
    return LayoutPlan(
        mode="legacy_v1_fallback",
        pages=[
            LayoutPage(
                index=0,
                width=None,
                height=None,
                regions=[LayoutRegion(kind="one_col", blocks=sorted(document_ir.blocks, key=lambda item: item.order))],
                source_page_indices=(0,),
                break_reason="document_start",
            )
        ],
    )


def _build_soft_page_groups(source_pages: list[LayoutPage]) -> list[LayoutPage]:
    """把有明确续接证据的相邻源页合并，其他边界锚定到最终阅读顺序的首块。"""

    groups: list[LayoutPage] = []
    for source_page in source_pages:
        if not groups:
            groups.append(replace(source_page, break_reason="document_start"))
            continue

        previous = groups[-1]
        same_orientation = _is_landscape(previous) == _is_landscape(source_page)
        continuation_reason = _continuation_reason(previous, source_page) if same_orientation else None
        if continuation_reason is not None:
            groups[-1] = _merge_page_group(previous, source_page, continuation_reason)
            continue

        break_reason = "source_page_boundary" if same_orientation else "orientation_change"
        break_anchor = _first_rendered_block_id(source_page)
        groups.append(
            replace(
                source_page,
                break_before_block_id=break_anchor if same_orientation else None,
                break_reason=break_reason,
            )
        )
    return groups


def _merge_page_group(previous: LayoutPage, current: LayoutPage, reason: str) -> LayoutPage:
    previous_has_body = any(region.blocks for region in previous.regions)
    width = previous.width if previous_has_body else current.width
    height = previous.height if previous_has_body else current.height
    return replace(
        previous,
        width=width,
        height=height,
        header_blocks=[*previous.header_blocks, *current.header_blocks],
        footer_blocks=[*previous.footer_blocks, *current.footer_blocks],
        page_number_blocks=[*previous.page_number_blocks, *current.page_number_blocks],
        regions=[*previous.regions, *current.regions],
        source_page_indices=(*previous.source_page_indices, *current.source_page_indices),
        continuation_reasons=(*previous.continuation_reasons, reason),
    )


def _continuation_reason(previous: LayoutPage, current: LayoutPage) -> str | None:
    previous_blocks = [block for region in previous.regions for block in region.blocks]
    current_blocks = [block for region in current.regions for block in region.blocks]
    if not current_blocks and (current.header_blocks or current.footer_blocks or current.page_number_blocks):
        return f"decoration_only_source_page:{current.index}"
    if not previous_blocks and (previous.header_blocks or previous.footer_blocks or previous.page_number_blocks):
        return f"body_after_decoration_only_page:{current.index}"
    if not previous_blocks or not current_blocks:
        return None

    previous_last = previous_blocks[-1]
    current_first = current_blocks[0]
    if _is_promoted_page_edge_decoration(previous_last, previous):
        return f"promoted_page_edge_decoration:{previous_last.id}"

    table_page_index = _block_page_index(previous_last)
    if (
        previous_last.type == "table"
        and previous_last.layout is not None
        and table_page_index is not None
        and current.index - table_page_index <= len(previous_last.layout.continuation_heights)
    ):
        return f"table_continuation:{previous_last.id}"

    previous_group = previous_last.metadata.get("content_group_id")
    current_group = current_first.metadata.get("content_group_id")
    if isinstance(previous_group, str) and previous_group and previous_group == current_group:
        return f"content_group:{previous_group}"

    if previous_last.type == current_first.type == "list" and _touches_source_page_edge(previous_last, current_first, previous, current):
        return f"list_continuation:{previous_last.id}"
    return None


def _is_promoted_page_edge_decoration(block: DocumentIRBlock, page: LayoutPage) -> bool:
    """识别因保全内容而进入正文、但仍位于源页底边的页脚块。"""

    bbox = _bbox(block)
    return bool(
        block.metadata.get("semantic_decision_reason") == "decoration_candidate_promoted_to_body"
        and block.metadata.get("source_type") in {"footer", "page_footer"}
        and bbox is not None
        and page.height
        and bbox[3] >= page.height * (1 - PAGE_EDGE_CONTINUATION_RATIO)
    )


def _touches_source_page_edge(
    previous_block: DocumentIRBlock,
    current_block: DocumentIRBlock,
    previous_page: LayoutPage,
    current_page: LayoutPage,
) -> bool:
    previous_bbox = _bbox(previous_block)
    current_bbox = _bbox(current_block)
    if previous_bbox is None or current_bbox is None or not previous_page.height or not current_page.height:
        return False
    return (
        previous_bbox[3] >= previous_page.height * (1 - PAGE_EDGE_CONTINUATION_RATIO)
        and current_bbox[1] <= current_page.height * PAGE_EDGE_CONTINUATION_RATIO
    )


def _first_rendered_block_id(page: LayoutPage) -> str | None:
    return next((block.id for region in page.regions for block in region.blocks), None)


def _is_landscape(page: LayoutPage) -> bool:
    return bool(page.width and page.height and page.width > page.height)


def _build_regions(
    body_blocks: list[DocumentIRBlock],
    page_width: float | None,
    page_height: float | None,
) -> list[LayoutRegion]:
    if not body_blocks:
        return []
    if page_width is None or page_width <= 0:
        return [LayoutRegion(kind="one_col", blocks=body_blocks, reason="missing_page_width")]

    two_col_bands = _detect_two_col_bands(body_blocks, page_width)
    membership = {block.id: _is_two_col_member(block, page_width, two_col_bands) for block in body_blocks}
    _extend_same_column_membership(body_blocks, page_width, membership)

    regions: list[LayoutRegion] = []
    for block in body_blocks:
        kind = "two_col" if membership[block.id] else "one_col"
        same_visual_flow = not (
            kind == "two_col"
            and regions
            and regions[-1].kind == kind
            and (regions[-1].blocks[-1].type == "image") != (block.type == "image")
        )
        if regions and regions[-1].kind == kind and same_visual_flow:
            regions[-1].blocks.append(block)
        else:
            reason = "trusted_column_band" if kind == "two_col" else "single_column_or_wide"
            regions.append(LayoutRegion(kind=kind, blocks=[block], reason=reason))

    finalized = [_finalize_region(region, page_width) for region in regions]
    composites = _extract_visual_table_composites(finalized, page_width)
    paired_rows = _extract_paired_visual_rows(composites)
    return _extract_short_visual_preludes(paired_rows, page_width, page_height)


def _is_two_col_member(
    block: DocumentIRBlock,
    page_width: float,
    bands: list[tuple[float, float]],
) -> bool:
    bbox = _bbox(block)
    return (
        _classify_body_block(block, page_width) in {"left", "right"}
        and bbox is not None
        and any(bbox[1] < bottom and bbox[3] > top for top, bottom in bands)
    )


def _extend_same_column_membership(
    blocks: list[DocumentIRBlock],
    page_width: float,
    membership: dict[str, bool],
) -> None:
    """只吸收与可信双栏带短距离相接的同侧尾块，不跨越 wide barrier。"""

    changed = True
    while changed:
        changed = False
        for candidate in blocks:
            if membership[candidate.id] or _classify_body_block(candidate, page_width) not in {"left", "right"}:
                continue
            candidate_bbox = _bbox(candidate)
            if candidate_bbox is None:
                continue
            candidate_side = _classify_body_block(candidate, page_width)
            for member in blocks:
                member_bbox = _bbox(member)
                if (
                    not membership[member.id]
                    or member_bbox is None
                    or _classify_body_block(member, page_width) != candidate_side
                ):
                    continue
                gap = max(candidate_bbox[1] - member_bbox[3], member_bbox[1] - candidate_bbox[3], 0.0)
                if gap <= SAME_COLUMN_CONTINUATION_GAP and not _has_wide_barrier(blocks, page_width, candidate_bbox, member_bbox):
                    membership[candidate.id] = True
                    changed = True
                    break


def _has_wide_barrier(
    blocks: list[DocumentIRBlock],
    page_width: float,
    first_bbox: tuple[float, float, float, float],
    second_bbox: tuple[float, float, float, float],
) -> bool:
    top = min(first_bbox[3], second_bbox[3])
    bottom = max(first_bbox[1], second_bbox[1])
    return any(
        _classify_body_block(block, page_width) == "wide"
        and (bbox := _bbox(block)) is not None
        and bbox[1] < bottom
        and bbox[3] > top
        for block in blocks
    )


def _finalize_region(region: LayoutRegion, page_width: float) -> LayoutRegion:
    if region.kind != "two_col":
        return region
    left = _sort_blocks([block for block in region.blocks if _classify_body_block(block, page_width) == "left"])
    right = _sort_blocks([block for block in region.blocks if _classify_body_block(block, page_width) == "right"])
    if not left or not right:
        return LayoutRegion(kind="one_col", blocks=_sort_blocks(region.blocks), reason="unpaired_column_membership")
    return LayoutRegion(
        kind="two_col",
        blocks=[*left, *right],
        column_break_index=len(left),
        reason=region.reason,
    )


def _extract_paired_visual_rows(regions: list[LayoutRegion]) -> list[LayoutRegion]:
    planned: list[LayoutRegion] = []
    for region in regions:
        rows = _paired_visual_rows(region)
        if rows is None:
            planned.append(region)
            continue
        planned.extend(
            LayoutRegion(kind="paired_visual_row", blocks=[left, right], reason="strict_paired_images")
            for left, right in rows
        )
    return planned


def _extract_short_visual_preludes(
    regions: list[LayoutRegion],
    page_width: float,
    page_height: float | None,
) -> list[LayoutRegion]:
    """把紧邻宽图的短双栏标签降为单栏连续流，避免连续分节拆散视觉主题。"""

    planned: list[LayoutRegion] = []
    index = 0
    while index < len(regions):
        region = regions[index]
        next_region = regions[index + 1] if index + 1 < len(regions) else None
        if not _is_short_visual_prelude(region, next_region, page_width, page_height):
            planned.append(region)
            index += 1
            continue

        assert next_region is not None
        subject = next_region.blocks[0]
        planned.append(
            LayoutRegion(
                kind="visual_prelude",
                blocks=[*_sort_blocks(region.blocks), subject],
                reason="short_text_prelude_before_wide_visual",
            )
        )
        if len(next_region.blocks) > 1:
            planned.append(replace(next_region, blocks=next_region.blocks[1:]))
        index += 2
    return planned


def _is_short_visual_prelude(
    region: LayoutRegion,
    next_region: LayoutRegion | None,
    page_width: float,
    page_height: float | None,
) -> bool:
    if (
        region.kind != "two_col"
        or next_region is None
        or next_region.kind != "one_col"
        or not region.blocks
        or not next_region.blocks
        or page_height is None
        or page_height <= 0
        or any(block.type != "paragraph" or block.metadata.get("annotation_role") for block in region.blocks)
    ):
        return False
    subject = next_region.blocks[0]
    subject_bbox = _bbox(subject)
    prelude_boxes = [_bbox(block) for block in region.blocks]
    if (
        subject.type != "image"
        or _classify_body_block(subject, page_width) != "wide"
        or subject_bbox is None
        or any(bbox is None for bbox in prelude_boxes)
    ):
        return False
    boxes = [bbox for bbox in prelude_boxes if bbox is not None]
    prelude_top = min(bbox[1] for bbox in boxes)
    prelude_bottom = max(bbox[3] for bbox in boxes)
    return (
        prelude_bottom - prelude_top < page_height * PAGE_EDGE_CONTINUATION_RATIO
        and 0 <= subject_bbox[1] - prelude_bottom <= SAME_COLUMN_CONTINUATION_GAP
    )


def _extract_visual_table_composites(
    regions: list[LayoutRegion],
    page_width: float,
) -> list[LayoutRegion]:
    """把同组 image/table 收拢成一个 Word 原生复合关系区域。"""

    groups: dict[str, list[DocumentIRBlock]] = {}
    for region in regions:
        for block in region.blocks:
            group_id = block.metadata.get("visual_overlap_group_id")
            if isinstance(group_id, str) and group_id:
                groups.setdefault(group_id, []).append(block)
    valid_groups = {
        group_id: blocks
        for group_id, blocks in groups.items()
        if sorted(block.type for block in blocks) == ["image", "table"]
    }
    if not valid_groups:
        return regions

    emitted: set[str] = set()
    planned: list[LayoutRegion] = []
    for region in regions:
        pending: list[DocumentIRBlock] = []

        def flush_pending() -> None:
            if not pending:
                return
            planned.append(_finalize_region(replace(region, blocks=list(pending)), page_width))
            pending.clear()

        for block in region.blocks:
            group_id = block.metadata.get("visual_overlap_group_id")
            if group_id not in valid_groups:
                pending.append(block)
                continue
            flush_pending()
            if group_id in emitted:
                continue
            planned.append(
                LayoutRegion(
                    kind="visual_table_composite",
                    blocks=sorted(valid_groups[group_id], key=lambda item: item.order),
                    reason="editable_table_extracted_from_containing_image",
                )
            )
            emitted.add(group_id)
        flush_pending()
    return planned


def _paired_visual_rows(region: LayoutRegion) -> list[tuple[DocumentIRBlock, DocumentIRBlock]] | None:
    if (
        region.kind != "two_col"
        or region.column_break_index is None
        or len(region.blocks) < 2
        or any(block.type != "image" for block in region.blocks)
        or any(_image_annotation_count(block) > 1 for block in region.blocks)
    ):
        return None
    left = region.blocks[: region.column_break_index]
    right = region.blocks[region.column_break_index :]
    if not left or len(left) != len(right):
        return None
    rows: list[tuple[DocumentIRBlock, DocumentIRBlock]] = []
    for left_block, right_block in zip(left, right, strict=True):
        left_bbox = _bbox(left_block)
        right_bbox = _bbox(right_block)
        if left_bbox is None or right_bbox is None:
            return None
        if min(left_bbox[3], right_bbox[3]) <= max(left_bbox[1], right_bbox[1]):
            return None
        rows.append((left_block, right_block))
    return rows


def _image_annotation_count(block: DocumentIRBlock) -> int:
    values = [*block.captions]
    metadata_caption = block.metadata.get("caption")
    if isinstance(metadata_caption, str):
        values.append(metadata_caption)
    values.extend(block.footnotes)
    return len({value.strip() for value in values if value.strip()})


def _plan_page_tables(
    page: LayoutPage,
    template_config: TemplateConfigPackage,
) -> tuple[LayoutPage, dict[str, TableFitDecision]]:
    widths = _word_table_container_widths(page, template_config)
    decisions: dict[str, TableFitDecision] = {}
    planned_regions: list[LayoutRegion] = []
    for region in page.regions:
        if region.kind == "two_col":
            regions, region_decisions = _plan_two_column_tables(region, page, template_config, widths)
        elif region.kind == "visual_table_composite":
            regions, region_decisions = _plan_visual_table_composite(region, page, template_config, widths)
        else:
            regions, region_decisions = _plan_single_column_tables(region, page, template_config, widths)
        for candidate in regions:
            _append_planned_region(planned_regions, candidate)
        decisions.update(region_decisions)
    return replace(page, regions=planned_regions), decisions


def _plan_visual_table_composite(
    region: LayoutRegion,
    page: LayoutPage,
    template_config: TemplateConfigPackage,
    widths: dict[str, int],
) -> tuple[list[LayoutRegion], dict[str, TableFitDecision]]:
    """按图片遮罩中的原生单元格宽度适配复合关系内的语义表格。"""

    table_block = next((block for block in region.blocks if block.type == "table"), None)
    image_block = next((block for block in region.blocks if block.type == "image"), None)
    if table_block is None or image_block is None:
        return [region], {}
    table = _final_table_model(table_block, template_config)
    mask = visual_overlap_mask(image_block)
    if table is None or mask is None:
        return [region], {}
    decision = choose_table_fit_decision(
        block_id=table_block.id,
        table=table,
        container="visual_table_composite",
        available_width=max(int(widths["full_width"] * (mask[2] - mask[0])), 1),
        preferred_font_size=template_config.table_content.font_size,
        minimum_font_size=template_config.table_content.min_font_size,
        source_width_ratio=_source_table_width_ratio(table_block, page, "full_width"),
    )
    return [region], {table_block.id: decision}


def _plan_two_column_tables(
    region: LayoutRegion,
    page: LayoutPage,
    template_config: TemplateConfigPackage,
    widths: dict[str, int],
) -> tuple[list[LayoutRegion], dict[str, TableFitDecision]]:
    decisions: dict[str, TableFitDecision] = {}
    degraded: list[tuple[DocumentIRBlock, TableFitDecision, str]] = []
    for block in region.blocks:
        if block.type != "table":
            continue
        table = _final_table_model(block, template_config)
        if table is None:
            continue
        column_decision = _table_decision(block, table, "column", widths["column"], page, template_config)
        if column_decision.fits:
            decisions[block.id] = column_decision
            continue
        final_decision, region_kind = _wider_table_decision(block, table, page, template_config, widths)
        decisions[block.id] = final_decision
        degraded.append((block, final_decision, region_kind))

    if not degraded:
        return [region], decisions

    degraded_ids = {block.id for block, _decision, _kind in degraded}
    context_ids = {
        block.id
        for block in region.blocks
        if block.metadata.get("annotation_role") == "table_context"
        and block.metadata.get("source_block_id") in degraded_ids
    }
    assert region.column_break_index is not None
    left = [
        block
        for block in region.blocks[: region.column_break_index]
        if block.id not in degraded_ids and block.id not in context_ids
    ]
    right = [
        block
        for block in region.blocks[region.column_break_index :]
        if block.id not in degraded_ids and block.id not in context_ids
    ]
    planned: list[LayoutRegion] = []
    if left and right:
        planned.append(replace(region, blocks=[*left, *right], column_break_index=len(left)))
    elif left or right:
        planned.append(LayoutRegion(kind="one_col", blocks=[*left, *right], reason="table_container_degraded"))

    for table_block, decision, region_kind in degraded:
        group = [
            block
            for block in region.blocks
            if block.id == table_block.id
            or (
                block.metadata.get("annotation_role") == "table_context"
                and block.metadata.get("source_block_id") == table_block.id
            )
        ]
        planned.append(LayoutRegion(kind=region_kind, blocks=group, reason=decision.reason))
    return planned, decisions


def _plan_single_column_tables(
    region: LayoutRegion,
    page: LayoutPage,
    template_config: TemplateConfigPackage,
    widths: dict[str, int],
) -> tuple[list[LayoutRegion], dict[str, TableFitDecision]]:
    if region.kind not in {"one_col"}:
        return [region], {}
    planned: list[LayoutRegion] = []
    current_blocks: list[DocumentIRBlock] = []
    decisions: dict[str, TableFitDecision] = {}
    for block in region.blocks:
        if block.type != "table":
            current_blocks.append(block)
            continue
        table = _final_table_model(block, template_config)
        if table is None:
            current_blocks.append(block)
            continue
        decision = _table_decision(block, table, "full_width", widths["full_width"], page, template_config)
        region_kind = "one_col"
        if not decision.fits and not _is_landscape(page):
            decision = _degraded_decision(
                _table_decision(block, table, "landscape", widths["landscape"], page, template_config),
                from_container="full_width",
            )
            region_kind = "landscape_table"
        decisions[block.id] = decision
        if region_kind == "one_col":
            current_blocks.append(block)
            continue
        contexts = [
            candidate
            for candidate in current_blocks
            if candidate.metadata.get("annotation_role") == "table_context"
            and candidate.metadata.get("source_block_id") == block.id
        ]
        context_ids = {candidate.id for candidate in contexts}
        current_blocks = [candidate for candidate in current_blocks if candidate.id not in context_ids]
        if current_blocks:
            planned.append(LayoutRegion(kind="one_col", blocks=current_blocks, reason=region.reason))
            current_blocks = []
        planned.append(LayoutRegion(kind=region_kind, blocks=[*contexts, block], reason=decision.reason))
    if current_blocks:
        planned.append(LayoutRegion(kind="one_col", blocks=current_blocks, reason=region.reason))
    return planned, decisions


def _wider_table_decision(
    block: DocumentIRBlock,
    table: HtmlTable,
    page: LayoutPage,
    template_config: TemplateConfigPackage,
    widths: dict[str, int],
) -> tuple[TableFitDecision, str]:
    full_width = _table_decision(block, table, "full_width", widths["full_width"], page, template_config)
    if full_width.fits or _is_landscape(page):
        return _degraded_decision(full_width, from_container="column"), "one_col"
    landscape = _table_decision(block, table, "landscape", widths["landscape"], page, template_config)
    landscape = _degraded_decision(landscape, from_container="full_width")
    return (
        replace(
            landscape,
            reason=f"column_and_full_width_unreadable_landscape_{'fits' if landscape.fits else 'unresolved'}",
            quality_flags=(
                f"table_container_degraded:{block.id}:column->full_width",
                *landscape.quality_flags,
            ),
        ),
        "landscape_table",
    )


def _degraded_decision(decision: TableFitDecision, *, from_container: str) -> TableFitDecision:
    degraded_flag = f"table_container_degraded:{decision.block_id}:{from_container}->{decision.container}"
    flags = tuple(flag for flag in decision.quality_flags if not flag.startswith("table_fit_unresolved:"))
    if not decision.fits:
        flags = (*flags, f"table_fit_unresolved:{decision.block_id}:{decision.container}")
    return replace(
        decision,
        reason=f"{from_container}_unreadable_{decision.container}_{'fits' if decision.fits else 'unresolved'}",
        quality_flags=(*flags, degraded_flag),
    )


def _table_decision(
    block: DocumentIRBlock,
    table: HtmlTable,
    container: str,
    available_width: int,
    page: LayoutPage,
    template_config: TemplateConfigPackage,
) -> TableFitDecision:
    return choose_table_fit_decision(
        block_id=block.id,
        table=table,
        container=container,
        available_width=available_width,
        preferred_font_size=template_config.table_content.font_size,
        minimum_font_size=template_config.table_content.min_font_size,
        source_width_ratio=_source_table_width_ratio(block, page, container),
    )


def _final_table_model(block: DocumentIRBlock, template_config: TemplateConfigPackage) -> HtmlTable | None:
    html = block.html
    if template_config.terminology is not None:
        html = template_config.terminology.replace_html(html) or html
    return parse_html_table(html)


def _word_table_container_widths(
    page: LayoutPage,
    template_config: TemplateConfigPackage,
) -> dict[str, int]:
    setup = template_config.page_setup
    portrait_width = setup.page_width_cm if setup.page_width_cm is not None else 21.0
    portrait_height = setup.page_height_cm if setup.page_height_cm is not None else 29.7
    left_margin = setup.left_margin if setup.left_margin is not None else DEFAULT_WORD_MARGIN_CM
    right_margin = setup.right_margin if setup.right_margin is not None else DEFAULT_WORD_MARGIN_CM
    current_page_width = portrait_height if _is_landscape(page) else portrait_width
    full_width = max(int(Cm(current_page_width - left_margin - right_margin)), 1)
    landscape_width = max(int(Cm(portrait_height - left_margin - right_margin)), 1)
    column_gap = int(Twips(720))
    column_width = max((full_width - column_gap) // 2, 1)
    return {
        "column": column_width,
        "full_width": full_width,
        "landscape": landscape_width,
    }


def _source_table_width_ratio(
    block: DocumentIRBlock,
    page: LayoutPage,
    container: str,
) -> float | None:
    """记录源表在所属源容器中的占比，仅用于 evidence，不反推 Word 列宽。"""

    bbox = _bbox(block)
    if bbox is None or page.width is None or page.width <= 0:
        return None
    source_container_width = page.width / 2 if container == "column" else page.width
    return round(min(max((bbox[2] - bbox[0]) / source_container_width, 0.0), 1.0), 4)


def _append_planned_region(regions: list[LayoutRegion], region: LayoutRegion) -> None:
    if not region.blocks:
        return
    if regions and region.kind in {"one_col", "landscape_table"} and regions[-1].kind == region.kind:
        previous = regions[-1]
        regions[-1] = replace(previous, blocks=[*previous.blocks, *region.blocks])
        return
    regions.append(region)


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


def _block_role(block: DocumentIRBlock) -> str:
    return block.layout.role if block.layout is not None else "body"
