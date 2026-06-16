from __future__ import annotations

# app/conversion/runtime_rendering_api.py: 汇总运行时渲染 API，连接表格、图片和文本渲染实现。

from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Mm

from app.conversion.runtime_models import Block, RenderConfig
from app.conversion.runtime.page_layout_runtime import render_visual_block
from app.conversion.runtime.render_config_runtime import TerminologyReplacer
from app.conversion.runtime.table_html_parser import HtmlCell, HtmlTable, parse_html_table
from app.conversion.runtime.table_long_renderer import is_long_simple_table, render_long_simple_table
from app.conversion.runtime.table_render_runtime import (
    fill_table_cell_impl,
    render_block_annotations_impl,
    render_block_captions_impl,
    render_block_footnotes_impl,
    render_large_table_fallback_impl,
    render_large_table_if_needed_impl,
    render_standard_html_table_impl,
)
from app.conversion.runtime.text_rendering import (
    apply_named_style_config,
    fill_rich_text,
    get_style_config,
    prepare_text,
    render_inline_html_into_paragraph,
)
from loguru import logger


MIN_VISUAL_WIDTH = Mm(45)
MAX_COMPLEX_TABLE_ROWS = 400
MAX_COMPLEX_TABLE_HTML_LEN = 30000
TABLE_BORDER_COLOR = "C7CDD4"
TABLE_HEADER_FILL = ""
TABLE_OUTER_BORDER_SZ = "8"
TABLE_INNER_BORDER_SZ = "4"


def create_document(template_document: Any | None) -> Document:
    return template_document if template_document is not None else Document()


def clear_document_body(document: Document) -> None:
    body = document._body._element
    sect_pr = body.sectPr
    for child in list(body):
        if child is sect_pr:
            continue
        body.remove(child)


def clone_first_section_layout(document: Document) -> None:
    if len(document.sections) <= 1:
        return
    base_section = document.sections[0]
    for section in document.sections[1:]:
        section.page_width = base_section.page_width
        section.page_height = base_section.page_height
        section.orientation = base_section.orientation
        section.left_margin = base_section.left_margin
        section.right_margin = base_section.right_margin
        section.top_margin = base_section.top_margin
        section.bottom_margin = base_section.bottom_margin
        section.header_distance = base_section.header_distance
        section.footer_distance = base_section.footer_distance
        section.header.is_linked_to_previous = True
        section.footer.is_linked_to_previous = True


def render_block_annotations(container: Any, block: Block, render_config: RenderConfig) -> None:
    render_block_annotations_impl(
        container,
        block,
        render_config,
        apply_named_style_config_fn=apply_named_style_config,
        fill_rich_text_fn=fill_rich_text,
        prepare_text_fn=prepare_text,
    )


def render_block_captions(
    container: Any,
    block: Block,
    render_config: RenderConfig,
    *,
    keep_with_next: bool = False,
) -> None:
    render_block_captions_impl(
        container,
        block,
        render_config,
        apply_named_style_config_fn=apply_named_style_config,
        fill_rich_text_fn=fill_rich_text,
        prepare_text_fn=prepare_text,
        keep_with_next=keep_with_next,
    )


def render_block_footnotes(container: Any, block: Block, render_config: RenderConfig) -> None:
    render_block_footnotes_impl(
        container,
        block,
        render_config,
        apply_named_style_config_fn=apply_named_style_config,
        fill_rich_text_fn=fill_rich_text,
        prepare_text_fn=prepare_text,
    )


def render_table_from_html(
    container: Any,
    block: Block,
    usable_width: int,
    render_config: RenderConfig,
) -> bool:
    logger.debug(
        "render html table page={} block={} bbox={} caption={} raw_html_len={}",
        block.page_idx,
        block.block_idx,
        block.bbox,
        block.captions[0] if block.captions else "N/A",
        len(block.html or ""),
    )
    prepared_table = prepare_html_table_model(block, render_config)
    if prepared_table is None:
        return False

    html, table_model, max_cols = prepared_table

    logger.debug(
        "parsed html table page={} block={} rows={} max_cols={}",
        block.page_idx,
        block.block_idx,
        len(table_model.rows),
        max_cols,
    )

    if render_large_table_if_needed(container, block, table_model, max_cols, len(html or ""), render_config, usable_width):
        return True

    render_block_captions(container, block, render_config, keep_with_next=True)
    merge_failures = render_standard_html_table(container, table_model, max_cols, usable_width, render_config)
    render_block_footnotes(container, block, render_config)

    if merge_failures > 0:
        logger.warning(
            "table merge fallback page={} block={} bbox={} count={} caption={}",
            block.page_idx,
            block.block_idx,
            block.bbox,
            merge_failures,
            block.captions[0] if block.captions else "N/A",
        )

    logger.debug(
        "rendered html table page={} block={} rows={} max_cols={} merge_failures={}",
        block.page_idx,
        block.block_idx,
        len(table_model.rows),
        max_cols,
        merge_failures,
    )

    return True


def prepare_html_table_model(
    block: Block,
    render_config: RenderConfig,
) -> tuple[str | None, "HtmlTable", int] | None:
    html = block.html
    if render_config.terminology:
        html = render_config.terminology.replace_html(html)

    table_model = parse_html_table(html)
    if not table_model or not table_model.rows:
        logger.warning(
            "skip html table page={} block={} because parsed rows are empty caption={}",
            block.page_idx,
            block.block_idx,
            block.captions[0] if block.captions else "N/A",
        )
        return None

    max_cols = table_model.max_columns
    if max_cols <= 0:
        logger.warning(
            "skip html table page={} block={} because max_cols<=0 caption={}",
            block.page_idx,
            block.block_idx,
            block.captions[0] if block.captions else "N/A",
        )
        return None

    return html, table_model, max_cols


def render_large_table_if_needed(
    container: Any,
    block: Block,
    table_model: "HtmlTable",
    max_cols: int,
    html_len: int,
    render_config: RenderConfig,
    usable_width: int,
) -> bool:
    def render_long_simple_table_adapter(
        target_container: Any,
        target_block: Block,
        target_table_model: HtmlTable,
        target_render_config: RenderConfig,
        target_usable_width: int,
    ) -> None:
        render_long_simple_table(
            target_container,
            target_block,
            target_table_model,
            target_render_config,
            target_usable_width,
            apply_named_style_config_fn=apply_named_style_config,
            fill_rich_text_fn=fill_rich_text,
            prepare_text_fn=prepare_text,
            fill_table_cell_fn=fill_table_cell,
            remove_table_borders_fn=remove_table_borders,
            get_style_config_fn=get_style_config,
        )

    return render_large_table_if_needed_impl(
        container,
        block,
        table_model,
        max_cols,
        html_len,
        render_config,
        usable_width,
        max_complex_rows=MAX_COMPLEX_TABLE_ROWS,
        max_complex_html_len=MAX_COMPLEX_TABLE_HTML_LEN,
        is_long_simple_table_fn=is_long_simple_table,
        render_long_simple_table_fn=render_long_simple_table_adapter,
        render_large_table_fallback_fn=render_large_table_fallback,
        logger=logger,
    )


def render_standard_html_table(
    container: Any,
    table_model: "HtmlTable",
    max_cols: int,
    usable_width: int,
    render_config: RenderConfig,
) -> int:
    return render_standard_html_table_impl(
        container,
        table_model,
        max_cols,
        usable_width,
        render_config,
        remove_table_borders_fn=remove_table_borders,
        fill_table_cell_fn=fill_table_cell,
    )


def render_large_table_fallback(
    container: Any,
    block: Block,
    table_model: "HtmlTable",
    render_config: RenderConfig,
    usable_width: int,
) -> None:
    render_large_table_fallback_impl(
        container,
        block,
        table_model,
        render_config,
        usable_width,
        compute_visual_width_fn=compute_visual_width,
        remove_table_borders_fn=remove_table_borders,
        fill_table_cell_fn=fill_table_cell,
        render_block_captions_fn=render_block_captions,
        render_block_footnotes_fn=render_block_footnotes,
        html_cell_cls=HtmlCell,
    )


def fill_table_cell(
    cell: Any,
    cell_model: "HtmlCell",
    is_header: bool,
    render_config: RenderConfig,
    *,
    compact: bool = False,
) -> None:
    fill_table_cell_impl(
        cell,
        cell_model,
        is_header,
        render_config,
        apply_named_style_config_fn=apply_named_style_config,
        render_inline_html_into_paragraph_fn=render_inline_html_into_paragraph,
        prepare_text_fn=prepare_text,
        compact=compact,
    )
    if is_header:
        apply_table_header_cell_style(cell)


def compute_visual_width(block: Block, page_width: float, usable_width: int) -> int:
    ratio = min(max(block.width / max(page_width, 1.0), 0.45), 1.0)
    width_by_ratio = int(usable_width * ratio)
    min_width = int(Emu(MIN_VISUAL_WIDTH))
    return min(max(width_by_ratio, min_width), int(usable_width))


def remove_table_borders(table: Any) -> None:
    table_element = table._tbl
    table_properties = table_element.tblPr
    borders = table_properties.find(qn("w:tblBorders"))
    if borders is not None:
        table_properties.remove(borders)

    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), TABLE_OUTER_BORDER_SZ)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), TABLE_BORDER_COLOR)
        borders.append(element)
    for edge in ("insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), TABLE_INNER_BORDER_SZ)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), TABLE_BORDER_COLOR)
        borders.append(element)
    table_properties.append(borders)


def apply_table_header_cell_style(cell: Any) -> None:
    """Keep header cells visually plain; bold text is handled during cell fill."""
    return
