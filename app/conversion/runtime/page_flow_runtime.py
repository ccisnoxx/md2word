from __future__ import annotations

# app/conversion/runtime/page_flow_runtime.py: Estimate DOCX page budgets before rendering MinerU blocks.

from dataclasses import dataclass, field
from math import ceil
import re
from typing import Any

from app.conversion.runtime.table_html_parser import HtmlTable, parse_html_table
from app.conversion.runtime.table_long_renderer import estimate_paragraph_height, estimate_row_height
from app.conversion.runtime.table_render_runtime import resolve_caption_style_name
from app.conversion.runtime.text_rendering import infer_heading_level


VISUAL_BLOCK_TYPES = {"image", "table", "chart", "equation_interline", "seal"}
TOP_LEVEL_SECTION_TITLE_RE = re.compile(r"^\s*\d{1,2}\s+\S")
A4_BODY_HEIGHT_PT = 697.0
MIN_TABLE_ROWS_VISIBLE = 2
LARGE_BLANK_RATIO = 0.35


@dataclass(slots=True)
class PageFlowPlan:
    break_before_region_ids: set[int] = field(default_factory=set)
    break_before_block_ids: set[int] = field(default_factory=set)
    break_after_block_ids: set[int] = field(default_factory=set)

    def should_break_before_region(self, region: Any) -> bool:
        return id(region) in self.break_before_region_ids

    def should_break_before_block(self, block: Any) -> bool:
        return id(block) in self.break_before_block_ids

    def should_break_after_block(self, block: Any) -> bool:
        return id(block) in self.break_after_block_ids


@dataclass(slots=True)
class FlowUnit:
    blocks: list[Any]
    height_pt: float
    anchor_height_pt: float
    region: Any | None = None
    break_after: bool = False

    @property
    def first_block(self) -> Any | None:
        return self.blocks[0] if self.blocks else None


def build_page_flow_plan(
    regions: list[Any],
    render_config: Any,
    page_width: float,
    usable_width: int,
) -> PageFlowPlan:
    source_page_height = max((block.y2 for region in regions for block in region.blocks), default=792.0)
    page_body_height = estimate_page_body_height_pt(render_config)
    units = build_flow_units(regions, render_config, page_width, usable_width, source_page_height)
    return plan_page_breaks(units, page_body_height)


def build_flow_units(
    regions: list[Any],
    render_config: Any,
    page_width: float,
    usable_width: int,
    source_page_height: float,
) -> list[FlowUnit]:
    units: list[FlowUnit] = []
    for region in regions:
        if region.kind == "two_col":
            units.append(estimate_two_col_region_unit(region, render_config, page_width, usable_width, source_page_height))
            continue
        for idx, block in enumerate(region.blocks):
            next_block = region.blocks[idx + 1] if idx + 1 < len(region.blocks) else None
            units.append(estimate_block_unit(block, render_config, page_width, usable_width, source_page_height, next_block))
    return units


def plan_page_breaks(units: list[FlowUnit], page_body_height: float) -> PageFlowPlan:
    plan = PageFlowPlan()
    if not units:
        return plan

    capacity = max(page_body_height, 1.0)
    used = 0.0
    for idx, unit in enumerate(units):
        remaining = capacity - used
        should_break = False
        if used > 0.0:
            if unit.anchor_height_pt > remaining:
                should_break = True
            elif used + unit.height_pt > capacity and remaining <= capacity * LARGE_BLANK_RATIO:
                should_break = True

        if should_break:
            mark_break_before(plan, unit)
            used = 0.0

        used = advance_used_height(used, unit.height_pt, capacity)
        if unit.break_after and idx + 1 < len(units):
            mark_break_after(plan, unit)
            used = 0.0

    return plan


def mark_break_before(plan: PageFlowPlan, unit: FlowUnit) -> None:
    if unit.region is not None:
        plan.break_before_region_ids.add(id(unit.region))
        return
    block = unit.first_block
    if block is not None:
        plan.break_before_block_ids.add(id(block))


def mark_break_after(plan: PageFlowPlan, unit: FlowUnit) -> None:
    block = unit.first_block
    if block is not None:
        plan.break_after_block_ids.add(id(block))


def advance_used_height(current: float, height: float, capacity: float) -> float:
    if height >= capacity:
        overflow = height % capacity
        return overflow if overflow > 0.0 else capacity
    next_height = current + height
    if next_height <= capacity:
        return next_height
    overflow = next_height - capacity
    return overflow if overflow > 0.0 else capacity


def estimate_two_col_region_unit(
    region: Any,
    render_config: Any,
    page_width: float,
    usable_width: int,
    source_page_height: float,
) -> FlowUnit:
    left_blocks: list[Any] = []
    right_blocks: list[Any] = []
    for block in sorted(region.blocks, key=lambda current: (current.y1, current.x1)):
        if classify_block_column(block, page_width) == "right":
            right_blocks.append(block)
        else:
            left_blocks.append(block)

    column_width = max(int(usable_width / 2), 1)
    left_height = sum(
        estimate_block_height_pt(block, render_config, page_width / 2, column_width, source_page_height)
        for block in left_blocks
    )
    right_height = sum(
        estimate_block_height_pt(block, render_config, page_width / 2, column_width, source_page_height)
        for block in right_blocks
    )
    height = max(left_height, right_height) + 4.0
    return FlowUnit(blocks=region.blocks, height_pt=height, anchor_height_pt=height, region=region)


def estimate_block_unit(
    block: Any,
    render_config: Any,
    page_width: float,
    usable_width: int,
    source_page_height: float,
    next_block: Any | None,
) -> FlowUnit:
    height = estimate_block_height_pt(block, render_config, page_width, usable_width, source_page_height)
    anchor = estimate_anchor_height_pt(block, render_config, page_width, usable_width, source_page_height, next_block, height)
    return FlowUnit(
        blocks=[block],
        height_pt=height,
        anchor_height_pt=anchor,
        break_after=is_estimated_long_table_block(block, render_config, usable_width),
    )


def estimate_anchor_height_pt(
    block: Any,
    render_config: Any,
    page_width: float,
    usable_width: int,
    source_page_height: float,
    next_block: Any | None,
    full_height: float,
) -> float:
    if block.type == "title":
        return full_height + estimate_min_body_lines_height(render_config, usable_width, lines=2)
    if block.type == "table" and block.html:
        table_model = parse_html_table(block.html)
        if table_model is not None:
            return estimate_table_anchor_height_pt(block, table_model, render_config, usable_width)
    if block.type in VISUAL_BLOCK_TYPES and block.type != "table":
        return full_height
    if next_block is not None and next_block.type in VISUAL_BLOCK_TYPES:
        return min(full_height, estimate_min_body_lines_height(render_config, usable_width, lines=1))
    return min(full_height, estimate_min_body_lines_height(render_config, usable_width, lines=2))


def estimate_block_height_pt(
    block: Any,
    render_config: Any,
    page_width: float,
    usable_width: int,
    source_page_height: float,
) -> float:
    if block.type == "table" and block.html:
        table_model = parse_html_table(block.html)
        if table_model is not None:
            return estimate_table_group_height_pt(block, table_model, render_config, usable_width)
    if block.type in VISUAL_BLOCK_TYPES:
        return estimate_visual_group_height_pt(block, render_config, usable_width, source_page_height)
    if block.type == "list":
        items = [item for item in block.items if item]
        return sum(estimate_text_height_pt(item, render_config, usable_width, "Normal") for item in items) or 0.0
    if block.type == "title":
        style_name = f"Heading {infer_heading_level(block.text or '')}"
        return estimate_text_height_pt(block.text or "", render_config, usable_width, style_name)
    return estimate_text_height_pt(block.text or "", render_config, usable_width, "Normal")


def estimate_visual_group_height_pt(
    block: Any,
    render_config: Any,
    usable_width: int,
    source_page_height: float,
) -> float:
    page_body_height = estimate_page_body_height_pt(render_config)
    bbox_height = max(block.height, 1.0)
    visual_height = min(max((bbox_height / max(source_page_height, 1.0)) * page_body_height, 18.0), page_body_height * 0.82)
    captions = sum(
        estimate_text_height_pt(text, render_config, usable_width, resolve_caption_style_name(text))
        for text in block.captions
    )
    notes = sum(estimate_text_height_pt(text, render_config, usable_width, "TableNote") for text in block.footnotes)
    return visual_height + captions + notes + 4.0


def estimate_table_group_height_pt(
    block: Any,
    table_model: HtmlTable,
    render_config: Any,
    usable_width: int,
) -> float:
    caption_height = sum(
        estimate_text_height_pt(text, render_config, usable_width, resolve_caption_style_name(text))
        for text in block.captions
    )
    note_height = sum(estimate_text_height_pt(text, render_config, usable_width, "TableNote") for text in block.footnotes)
    row_height = sum(estimate_table_row_height_pt(row, table_model, render_config, usable_width) for row in table_model.rows)
    return caption_height + row_height + note_height + 4.0


def estimate_table_anchor_height_pt(
    block: Any,
    table_model: HtmlTable,
    render_config: Any,
    usable_width: int,
) -> float:
    caption_height = sum(
        estimate_text_height_pt(text, render_config, usable_width, resolve_caption_style_name(text))
        for text in block.captions
    )
    visible_rows = table_model.rows[:MIN_TABLE_ROWS_VISIBLE]
    rows_height = sum(estimate_table_row_height_pt(row, table_model, render_config, usable_width) for row in visible_rows)
    return caption_height + rows_height + 2.0


def estimate_table_row_height_pt(
    row: list[Any],
    table_model: HtmlTable,
    render_config: Any,
    usable_width: int,
) -> float:
    base = estimate_row_height(row, render_config, usable_width, get_style_config_fn=get_style_config)
    density_factor = 1.14 if table_model.max_columns >= 6 else 1.06
    return base * density_factor


def estimate_table_page_count(
    block: Any,
    table_model: HtmlTable,
    render_config: Any,
    usable_width: int,
) -> int:
    height = estimate_table_group_height_pt(block, table_model, render_config, usable_width)
    return max(ceil(height / max(estimate_page_body_height_pt(render_config), 1.0)), 1)


def is_estimated_long_table_block(block: Any, render_config: Any, usable_width: int) -> bool:
    if block.type != "table" or not block.html:
        return False
    table_model = parse_html_table(block.html)
    if table_model is None:
        return False
    return estimate_table_page_count(block, table_model, render_config, usable_width) > 2


def estimate_text_height_pt(text: str, render_config: Any, usable_width: int, style_name: str) -> float:
    if not (text or "").strip():
        return 0.0
    return estimate_paragraph_height(
        text,
        render_config,
        usable_width,
        style_name=style_name,
        get_style_config_fn=get_style_config,
    )


def estimate_min_body_lines_height(render_config: Any, usable_width: int, *, lines: int) -> float:
    style = get_style_config(render_config, "Normal")
    font_size = style.font_size if style and style.font_size else 10.5
    line_spacing = style.line_spacing if style and style.line_spacing else 1.0
    return max(lines, 1) * (font_size * line_spacing + 0.2)


def estimate_page_body_height_pt(render_config: Any) -> float:
    layout = getattr(render_config, "section_layout", None)
    if layout is None:
        return A4_BODY_HEIGHT_PT
    page_height = length_to_pt(getattr(layout, "page_height", None))
    top_margin = length_to_pt(getattr(layout, "top_margin", None))
    bottom_margin = length_to_pt(getattr(layout, "bottom_margin", None))
    if page_height <= 0.0:
        return A4_BODY_HEIGHT_PT
    return max(page_height - top_margin - bottom_margin, 1.0)


def length_to_pt(value: Any) -> float:
    if value is None:
        return 0.0
    pt_value = getattr(value, "pt", None)
    if pt_value is not None:
        return float(pt_value)
    try:
        return float(value) / 12700.0
    except (TypeError, ValueError):
        return 0.0


def get_style_config(render_config: Any | None, style_name: str | None) -> Any | None:
    if not render_config or not style_name:
        return None
    return getattr(render_config, "paragraph_styles", {}).get(style_name)


def classify_block_column(block: Any, page_width: float) -> str:
    if block.width >= page_width * 0.6:
        return "wide"
    return "left" if block.center_x < page_width / 2 else "right"


def is_top_level_section_title(block: Any) -> bool:
    return block.type == "title" and bool(TOP_LEVEL_SECTION_TITLE_RE.match((block.text or "").strip()))
