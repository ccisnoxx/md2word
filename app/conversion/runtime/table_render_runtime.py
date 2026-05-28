from __future__ import annotations

from typing import Any

from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Emu, Mm, Pt


def render_block_annotations_impl(
    container: Any,
    block: Any,
    render_config: Any,
    *,
    apply_named_style_config_fn: Any,
    fill_rich_text_fn: Any,
    prepare_text_fn: Any,
) -> None:
    for caption in block.captions:
        caption_paragraph = container.add_paragraph()
        apply_named_style_config_fn(caption_paragraph, render_config, "Caption")
        fill_rich_text_fn(
            caption_paragraph,
            prepare_text_fn(caption, render_config),
            render_config=render_config,
            style_name="Caption",
        )

    for footnote in block.footnotes:
        note_paragraph = container.add_paragraph()
        apply_named_style_config_fn(note_paragraph, render_config, "TableNote")
        fill_rich_text_fn(
            note_paragraph,
            prepare_text_fn(footnote, render_config),
            render_config=render_config,
            style_name="TableNote",
        )


def render_large_table_if_needed_impl(
    container: Any,
    block: Any,
    table_model: Any,
    max_cols: int,
    html_len: int,
    render_config: Any,
    usable_width: int,
    *,
    max_complex_rows: int,
    max_complex_html_len: int,
    is_long_simple_table_fn: Any,
    render_long_simple_table_fn: Any,
    render_large_table_fallback_fn: Any,
    logger: Any,
) -> bool:
    if len(table_model.rows) <= max_complex_rows and html_len <= max_complex_html_len:
        return False

    logger.warning(
        "large table fallback page={} block={} rows={} max_cols={} html_len={} caption={}",
        block.page_idx,
        block.block_idx,
        len(table_model.rows),
        max_cols,
        html_len,
        block.captions[0] if block.captions else "N/A",
    )
    if is_long_simple_table_fn(table_model, max_complex_rows):
        logger.info(
            "long simple table chunk rendering page={} block={} rows={} max_cols={} caption={}",
            block.page_idx,
            block.block_idx,
            len(table_model.rows),
            max_cols,
            block.captions[0] if block.captions else "N/A",
        )
        render_long_simple_table_fn(container, block, table_model, render_config, usable_width)
        return True

    render_large_table_fallback_fn(container, block, table_model, render_config, usable_width)
    return True


def render_standard_html_table_impl(
    container: Any,
    table_model: Any,
    max_cols: int,
    usable_width: int,
    render_config: Any,
    *,
    remove_table_borders_fn: Any,
    fill_table_cell_fn: Any,
) -> int:
    table = container.add_table(rows=len(table_model.rows), cols=max_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    remove_table_borders_fn(table)

    column_width = max(int(usable_width // max_cols), int(Emu(Mm(16))))
    for col in table.columns:
        col.width = column_width

    occupied: dict[tuple[int, int], bool] = {}
    merge_failures = 0
    for row_idx, row in enumerate(table_model.rows):
        col_idx = 0
        for cell_model in row:
            while occupied.get((row_idx, col_idx)):
                col_idx += 1
            if col_idx >= max_cols:
                break

            base_cell = table.cell(row_idx, col_idx)
            end_row = min(row_idx + cell_model.rowspan - 1, len(table_model.rows) - 1)
            end_col = min(col_idx + cell_model.colspan - 1, max_cols - 1)
            merged_cell = base_cell
            if end_row != row_idx or end_col != col_idx:
                try:
                    target_cell = table.cell(end_row, end_col)
                    merged_cell = base_cell.merge(target_cell)
                except ValueError:
                    merge_failures += 1

            fill_table_cell_fn(merged_cell, cell_model, row_idx == 0, render_config)
            merged_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

            for r in range(row_idx, end_row + 1):
                for c in range(col_idx, end_col + 1):
                    occupied[(r, c)] = True

            col_idx = end_col + 1

    return merge_failures


def expand_table_rows(table_model: Any) -> list[list[str]]:
    expanded: list[list[str]] = []
    spans: dict[int, tuple[int, str]] = {}
    max_cols = table_model.max_columns

    for row in table_model.rows:
        pending_cells = list(row)
        row_values: list[str] = []
        col_idx = 0

        while col_idx < max_cols:
            active = spans.get(col_idx)
            if active and active[0] > 0:
                row_values.append(active[1])
                spans[col_idx] = (active[0] - 1, active[1])
                col_idx += 1
                continue

            if active and active[0] <= 0:
                spans.pop(col_idx, None)

            if not pending_cells:
                row_values.append("")
                col_idx += 1
                continue

            cell = pending_cells.pop(0)
            cell_text = cell.text
            for offset in range(cell.colspan):
                row_values.append(cell_text if offset == 0 else "")
                if cell.rowspan > 1:
                    spans[col_idx + offset] = (cell.rowspan - 2, cell_text if offset == 0 else "")
            col_idx += cell.colspan

        expanded.append(row_values[:max_cols])

    return expanded


def render_large_table_fallback_impl(
    container: Any,
    block: Any,
    table_model: Any,
    render_config: Any,
    usable_width: int,
    *,
    compute_visual_width_fn: Any,
    remove_table_borders_fn: Any,
    fill_table_cell_fn: Any,
    render_block_annotations_fn: Any,
    html_cell_cls: Any,
) -> None:
    if block.image_path and block.image_path.exists():
        picture_paragraph = container.add_paragraph()
        picture_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        picture_paragraph.paragraph_format.space_before = Pt(2)
        picture_paragraph.paragraph_format.space_after = Pt(2)
        picture_paragraph.add_run().add_picture(str(block.image_path), width=Emu(min(int(usable_width), compute_visual_width_fn(block, 1000.0, usable_width))))
    else:
        expanded_rows = expand_table_rows(table_model)
        if not expanded_rows:
            return

        max_cols = max((len(row) for row in expanded_rows), default=0)
        if max_cols <= 0:
            return

        table = container.add_table(rows=len(expanded_rows), cols=max_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        remove_table_borders_fn(table)

        for row_idx, row_values in enumerate(expanded_rows):
            for col_idx in range(max_cols):
                cell = table.cell(row_idx, col_idx)
                text = row_values[col_idx] if col_idx < len(row_values) else ""
                fill_table_cell_fn(
                    cell,
                    html_cell_cls(text=text, rowspan=1, colspan=1, html=text),
                    row_idx == 0,
                    render_config,
                )
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    render_block_annotations_fn(container, block, render_config)


def fill_table_cell_impl(
    cell: Any,
    cell_model: Any,
    is_header: bool,
    render_config: Any,
    *,
    apply_named_style_config_fn: Any,
    render_inline_html_into_paragraph_fn: Any,
    prepare_text_fn: Any,
) -> None:
    paragraph = cell.paragraphs[0]
    paragraph.text = ""
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if is_header else WD_ALIGN_PARAGRAPH.LEFT
    apply_named_style_config_fn(paragraph, render_config, "TableContent")
    render_inline_html_into_paragraph_fn(
        paragraph,
        cell_model.html or prepare_text_fn(cell_model.text, None),
        render_config=render_config,
        style_name="TableContent",
        bold=is_header,
    )
