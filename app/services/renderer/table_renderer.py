from __future__ import annotations

# app/services/renderer/table_renderer.py: 提供 DocumentIR Word 渲染器的 HTML 表格与表注 helper。

import re
from typing import Any

from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Emu, Mm, Pt

from app.conversion.runtime.table_html_parser import HtmlCell, HtmlTable, parse_html_table
from app.services.document_ir.models import DocumentIRBlock
from app.services.renderer.template_config import TemplateConfigPackage


MAX_COMPLEX_TABLE_ROWS = 400
MAX_COMPLEX_TABLE_HTML_LEN = 30000
MIN_TABLE_COLUMN_WIDTH = Mm(16)
LONG_TABLE_CAPTION_RE = re.compile(r"^(?:续表|continued\s+table|[A-Z]\.\d+(?:\.\d+)?)\b", re.IGNORECASE)
TH_TAG_RE = re.compile(r"</?th\b[^>]*>", re.IGNORECASE)


class WordTableRendererMixin:
    """封装可编辑 HTML 表格、合并单元格和表注渲染逻辑。"""

    def _configure_layout_table(self, table: Any) -> None:
        """把仅用于版面承载的 Word 表格配置为无边框容器。"""

        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        self._clear_table_borders(table)
        for row in table.rows:
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    def _render_table(self, document: Any, block: DocumentIRBlock, template_config: TemplateConfigPackage) -> None:
        table_html = self._prepare_table_html(block.html, template_config)
        table_model = parse_html_table(table_html)
        self._render_table_captions(document, block, template_config)
        if table_model is None or not table_model.rows or table_model.max_columns <= 0:
            paragraph = document.add_paragraph()
            self._fill_paragraph(
                paragraph,
                block.text or "",
                template_config.normal,
                terminology=template_config.terminology,
            )
            self._render_table_notes(document, block, template_config)
            return

        max_cols = table_model.max_columns
        usable_width = self._available_table_width(document)
        if self._is_large_table(block, table_model):
            self._render_expanded_table(document, table_model, max_cols, usable_width, template_config)
        else:
            self._render_standard_html_table(document, table_model, max_cols, usable_width, template_config)
        self._render_table_notes(document, block, template_config)

    def _render_standard_html_table(
        self,
        document: Any,
        table_model: HtmlTable,
        max_cols: int,
        usable_width: int,
        template_config: TemplateConfigPackage,
    ) -> None:
        """渲染常规 HTML table，保留 rowspan/colspan 合并结构。"""

        table = self._add_configured_table(document, len(table_model.rows), max_cols, usable_width, template_config)
        column_widths = self._table_column_widths(max_cols, usable_width)
        occupied: dict[tuple[int, int], bool] = {}
        for row_index, row in enumerate(table_model.rows):
            col_index = 0
            for cell_model in row:
                while occupied.get((row_index, col_index)):
                    col_index += 1
                if col_index >= max_cols:
                    break

                base_cell = table.cell(row_index, col_index)
                end_row = min(row_index + cell_model.rowspan - 1, len(table_model.rows) - 1)
                end_col = min(col_index + cell_model.colspan - 1, max_cols - 1)
                merged_cell = base_cell
                if end_row != row_index or end_col != col_index:
                    merged_cell = base_cell.merge(table.cell(end_row, end_col))
                merged_cell.width = sum(column_widths[col_index : end_col + 1])
                self._fill_table_cell(merged_cell, cell_model, row_index == 0 or cell_model.is_header, template_config)

                for occupied_row in range(row_index, end_row + 1):
                    for occupied_col in range(col_index, end_col + 1):
                        occupied[(occupied_row, occupied_col)] = True
                col_index = end_col + 1

    def _render_expanded_table(
        self,
        document: Any,
        table_model: HtmlTable,
        max_cols: int,
        usable_width: int,
        template_config: TemplateConfigPackage,
    ) -> None:
        """大表 fallback：展开跨行跨列，避免巨大复杂表合并导致渲染失败。"""

        rows = self._expand_table_rows(table_model, max_cols)
        table = self._add_configured_table(document, len(rows), max_cols, usable_width, template_config)
        column_widths = self._table_column_widths(max_cols, usable_width)
        for row_index, row in enumerate(rows):
            for col_index in range(max_cols):
                text = row[col_index] if col_index < len(row) else ""
                table.cell(row_index, col_index).width = column_widths[col_index]
                self._fill_table_cell(
                    table.cell(row_index, col_index),
                    HtmlCell(text=text, html=text),
                    row_index == 0,
                    template_config,
                )

    def _add_configured_table(
        self,
        document: Any,
        rows: int,
        cols: int,
        usable_width: int,
        template_config: TemplateConfigPackage,
    ) -> Any:
        table = document.add_table(rows=rows, cols=cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        try:
            table.style = template_config.table_style.style_name
        except (KeyError, ValueError):
            table.style = "Table Grid"

        for column, column_width in zip(table.columns, self._table_column_widths(cols, usable_width), strict=True):
            column.width = column_width
        if template_config.table_style.border_color:
            self._set_table_borders(table, template_config.table_style.border_color)
        self._configure_data_table_rows(table)
        return table

    def _table_column_widths(self, cols: int, usable_width: int) -> list[int]:
        if cols <= 0:
            return []
        if cols == 5:
            weights = [0.11, 0.37, 0.21, 0.21, 0.10]
            widths = [int(usable_width * weight) for weight in weights]
            widths[1] += int(usable_width) - sum(widths)
            return widths

        column_width = max(int(usable_width // cols), int(Emu(MIN_TABLE_COLUMN_WIDTH)))
        return [column_width for _ in range(cols)]

    def _fill_table_cell(
        self,
        cell: Any,
        cell_model: HtmlCell,
        is_header: bool,
        template_config: TemplateConfigPackage,
    ) -> None:
        cell.text = ""
        paragraph = cell.paragraphs[0]
        cell_content = self._table_cell_content(cell_model, is_header, template_config)
        self._fill_paragraph(
            paragraph,
            cell_content,
            template_config.table_content,
            terminology=template_config.terminology,
        )
        self._apply_table_header_run_style(paragraph, is_header, template_config)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if is_header else WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        if is_header and template_config.table_style.header_fill:
            self._set_cell_fill(cell, template_config.table_style.header_fill)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def _expand_table_rows(self, table_model: HtmlTable, max_cols: int) -> list[list[str]]:
        row_spans: dict[int, tuple[int, str]] = {}
        rows: list[list[str]] = []
        for table_row in table_model.rows:
            pending_cells = list(table_row)
            row_values: list[str] = []
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
                    row_values.append("")
                    col_index += 1
                    continue

                cell_model = pending_cells.pop(0)
                for offset in range(cell_model.colspan):
                    row_values.append(cell_model.text if offset == 0 else "")
                    if cell_model.rowspan > 1:
                        row_spans[col_index + offset] = (
                            cell_model.rowspan - 1,
                            cell_model.text if offset == 0 else "",
                        )
                col_index += cell_model.colspan
            rows.append(row_values[:max_cols])
        return rows

    def _render_block_annotations(
        self,
        document: Any,
        block: DocumentIRBlock,
        template_config: TemplateConfigPackage,
    ) -> None:
        self._render_table_captions(document, block, template_config)
        self._render_table_notes(document, block, template_config)

    def _render_table_captions(
        self,
        document: Any,
        block: DocumentIRBlock,
        template_config: TemplateConfigPackage,
    ) -> None:
        for text in self._unique_annotation_texts(block.captions):
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.keep_with_next = True
            self._fill_paragraph(
                paragraph,
                text,
                self._caption_style_for_text(text, template_config),
                terminology=template_config.terminology,
            )

    def _render_table_notes(
        self,
        document: Any,
        block: DocumentIRBlock,
        template_config: TemplateConfigPackage,
    ) -> None:
        for text in self._unique_annotation_texts(block.footnotes):
            paragraph = document.add_paragraph()
            self._fill_paragraph(
                paragraph,
                text,
                template_config.table_note,
                terminology=template_config.terminology,
            )

    def _unique_annotation_texts(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        texts: list[str] = []
        for value in values:
            text = value.strip()
            if text and text not in seen:
                texts.append(text)
                seen.add(text)
        return texts

    def _is_large_table(self, block: DocumentIRBlock, table_model: HtmlTable) -> bool:
        return len(table_model.rows) > MAX_COMPLEX_TABLE_ROWS or len(block.html or "") > MAX_COMPLEX_TABLE_HTML_LEN

    def _prepare_table_html(self, html: str | None, template_config: TemplateConfigPackage) -> str | None:
        terminology = template_config.terminology
        if terminology is None:
            return html
        return terminology.replace_html(html) or html

    def _apply_table_header_run_style(
        self,
        paragraph: Any,
        is_header: bool,
        template_config: TemplateConfigPackage,
    ) -> None:
        if not is_header or not template_config.table_style.header_bold:
            return
        for run in paragraph.runs:
            run.bold = True

    def _table_cell_content(
        self,
        cell_model: HtmlCell,
        is_header: bool,
        template_config: TemplateConfigPackage,
    ) -> str:
        content = cell_model.html or cell_model.text
        if is_header and not template_config.table_style.header_bold:
            return TH_TAG_RE.sub("", content)
        return content

    def _available_table_width(self, document: Any) -> int:
        sections = getattr(document, "sections", None)
        if not sections:
            return int(Cm(14))
        section = sections[-1]
        width = section.page_width - section.left_margin - section.right_margin
        return int(width if width > 0 else Cm(14))

    def _set_cell_fill(self, cell: Any, fill: str) -> None:
        tc_pr = cell._tc.get_or_add_tcPr()
        shading = tc_pr.find(qn("w:shd"))
        if shading is None:
            shading = OxmlElement("w:shd")
            tc_pr.append(shading)
        shading.set(qn("w:fill"), fill.strip().lstrip("#").upper())

    def _caption_style_for_text(self, text: str, template_config: TemplateConfigPackage) -> Any:
        if LONG_TABLE_CAPTION_RE.match((text or "").strip()):
            return template_config.long_table_caption
        return template_config.caption

    def _set_table_borders(self, table: Any, color: str) -> None:
        table_properties = table._tbl.tblPr
        borders = table_properties.find(qn("w:tblBorders"))
        if borders is None:
            borders = OxmlElement("w:tblBorders")
            table_properties.append(borders)
        normalized_color = color.strip().lstrip("#").upper()
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            element = borders.find(qn(f"w:{edge}"))
            if element is None:
                element = OxmlElement(f"w:{edge}")
                borders.append(element)
            element.set(qn("w:val"), "single")
            element.set(qn("w:sz"), "4")
            element.set(qn("w:space"), "0")
            element.set(qn("w:color"), normalized_color)

    def _clear_table_borders(self, table: Any) -> None:
        table_properties = table._tbl.tblPr
        borders = table_properties.find(qn("w:tblBorders"))
        if borders is None:
            borders = OxmlElement("w:tblBorders")
            table_properties.append(borders)
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            element = borders.find(qn(f"w:{edge}"))
            if element is None:
                element = OxmlElement(f"w:{edge}")
                borders.append(element)
            element.set(qn("w:val"), "none")
            element.set(qn("w:sz"), "0")
            element.set(qn("w:space"), "0")
            element.set(qn("w:color"), "auto")

    def _configure_data_table_rows(self, table: Any) -> None:
        for row_index, row in enumerate(table.rows):
            row_properties = row._tr.get_or_add_trPr()
            self._ensure_row_flag(row_properties, "w:cantSplit")
            if row_index == 0:
                self._ensure_row_flag(row_properties, "w:tblHeader", value="true")

    def _ensure_row_flag(self, row_properties: Any, tag: str, *, value: str | None = None) -> None:
        element = row_properties.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            row_properties.append(element)
        if value is not None:
            element.set(qn("w:val"), value)
