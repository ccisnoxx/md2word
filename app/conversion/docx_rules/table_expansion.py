"""正式大表展开的内容投影，同时保留每次显示对应的源单元格。"""

from __future__ import annotations

from dataclasses import dataclass

from app.conversion.runtime.table_html_parser import HtmlCell, HtmlTable


MAX_COMPLEX_TABLE_ROWS = 400
MAX_COMPLEX_TABLE_HTML_LEN = 30000


@dataclass(frozen=True, slots=True)
class TableCellOccurrence:
    source_row: int
    source_column: int
    cell: HtmlCell


def requires_table_expansion(table: HtmlTable, html: str | None) -> bool:
    return len(table.rows) > MAX_COMPLEX_TABLE_ROWS or len(html or "") > MAX_COMPLEX_TABLE_HTML_LEN


def expanded_table_rows(table: HtmlTable) -> list[list[TableCellOccurrence | None]]:
    """沿用跨行内容重复、跨列尾格留空的几何规则，保留 HTML 及源坐标。"""
    row_spans: dict[int, tuple[int, TableCellOccurrence | None]] = {}
    rows: list[list[TableCellOccurrence | None]] = []
    max_cols = table.max_columns
    for source_row, table_row in enumerate(table.rows):
        pending_cells = list(enumerate(table_row))
        row_values: list[TableCellOccurrence | None] = []
        col_index = 0
        while col_index < max_cols:
            active_span = row_spans.get(col_index)
            if active_span is not None and active_span[0] > 0:
                row_values.append(active_span[1])
                row_spans[col_index] = (active_span[0] - 1, active_span[1])
                col_index += 1
                continue
            if active_span is not None:
                row_spans.pop(col_index, None)
            if not pending_cells:
                row_values.append(None)
                col_index += 1
                continue
            source_column, cell = pending_cells.pop(0)
            occurrence = TableCellOccurrence(source_row, source_column, cell)
            for offset in range(cell.colspan):
                value = occurrence if offset == 0 else None
                row_values.append(value)
                if cell.rowspan > 1:
                    row_spans[col_index + offset] = (cell.rowspan - 1, value)
            col_index += cell.colspan
        rows.append(row_values[:max_cols])
    return rows
