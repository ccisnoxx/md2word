from __future__ import annotations

# app/services/renderer/word_renderer.py: 将 DocumentIR v1 按模板配置渲染为可编辑 DOCX。

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.services.document_ir.models import DocumentIR, DocumentIRAsset, DocumentIRBlock
from app.services.renderer.template_config import TemplateConfigPackage, TemplateParagraphStyleConfig


ImageContentLoader = Callable[[DocumentIRAsset], bytes | None]


class DocumentIRWordRenderer:
    """P0 Word 渲染器：覆盖标题、段落、基础表格和图片。"""

    def render_to_bytes(
        self,
        document_ir: DocumentIR,
        *,
        template_path: Path | None,
        config_path: Path | None,
        image_loader: ImageContentLoader,
    ) -> bytes:
        """按模板 DOCX 与配置包生成 Word 二进制。"""

        template_config = TemplateConfigPackage.load(config_path)
        document = self._create_document(template_path)
        self._clear_body(document)
        self._apply_page_setup(document, template_config)
        self._apply_header_footer(document, template_config, config_path=config_path)

        assets_by_id = {asset.id: asset for asset in document_ir.assets}
        for block in sorted(document_ir.blocks, key=lambda item: item.order):
            self._render_block(document, block, assets_by_id, template_config, image_loader)

        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def _create_document(self, template_path: Path | None) -> Any:
        if template_path is not None and template_path.exists():
            return Document(str(template_path))
        return Document()

    def _clear_body(self, document: Any) -> None:
        body = document._body._element
        sect_pr = body.sectPr
        for child in list(body):
            if child is sect_pr:
                continue
            body.remove(child)

    def _apply_page_setup(self, document: Any, template_config: TemplateConfigPackage) -> None:
        setup = template_config.page_setup
        for section in document.sections:
            if setup.top_margin is not None:
                section.top_margin = Cm(setup.top_margin)
            if setup.bottom_margin is not None:
                section.bottom_margin = Cm(setup.bottom_margin)
            if setup.left_margin is not None:
                section.left_margin = Cm(setup.left_margin)
            if setup.right_margin is not None:
                section.right_margin = Cm(setup.right_margin)
            if setup.header_distance is not None:
                section.header_distance = Cm(setup.header_distance)
            if setup.footer_distance is not None:
                section.footer_distance = Cm(setup.footer_distance)

    def _apply_header_footer(
        self,
        document: Any,
        template_config: TemplateConfigPackage,
        *,
        config_path: Path | None,
    ) -> None:
        if not document.sections:
            return
        section = document.sections[0]
        if template_config.header.enabled:
            paragraph = section.header.paragraphs[0] if section.header.paragraphs else section.header.add_paragraph()
            paragraph.text = ""
            header_style = TemplateParagraphStyleConfig(
                font_name=template_config.header.title_font_name,
                font_size=template_config.header.title_font_size,
                color=template_config.header.title_color,
                alignment="left",
            )
            logo_path = self._resolve_asset_path(template_config.header.logo_path, config_path)
            if logo_path is not None and logo_path.exists():
                run = paragraph.add_run()
                try:
                    run.add_picture(str(logo_path), height=Cm(template_config.header.logo_height_cm or 1.0))
                    paragraph.add_run("  ")
                except (InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError):
                    paragraph.text = ""
            if template_config.header.title_text:
                run = paragraph.add_run(template_config.header.title_text)
                self._apply_run_style(run, header_style)

        if template_config.footer.enabled and template_config.footer.show_page_number:
            paragraph = section.footer.paragraphs[0] if section.footer.paragraphs else section.footer.add_paragraph()
            if not paragraph.text.strip():
                paragraph.text = "第  页"
            paragraph.alignment = self._parse_alignment(template_config.footer.alignment or "center")

    def _resolve_asset_path(self, raw_path: str | None, config_path: Path | None) -> Path | None:
        if not raw_path:
            return None
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        if config_path is not None:
            return (config_path.parent / candidate).resolve()
        return candidate.resolve()

    def _render_block(
        self,
        document: Any,
        block: DocumentIRBlock,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
    ) -> None:
        if block.type == "heading":
            paragraph = document.add_paragraph()
            style = template_config.heading_style_for_level(block.level)
            self._fill_paragraph(paragraph, block.text or "", style)
            return
        if block.type == "paragraph":
            paragraph = document.add_paragraph()
            self._fill_paragraph(paragraph, block.text or "", template_config.normal)
            return
        if block.type == "list":
            for item in block.list_items or []:
                paragraph = document.add_paragraph()
                self._fill_paragraph(paragraph, item, template_config.normal, prefix="• ")
            return
        if block.type == "formula":
            paragraph = document.add_paragraph()
            self._fill_paragraph(paragraph, block.latex or block.text or "", template_config.normal)
            return
        if block.type == "table":
            self._render_table(document, block, template_config)
            return
        if block.type == "image":
            self._render_image(document, block, assets_by_id, template_config, image_loader)

    def _fill_paragraph(
        self,
        paragraph: Any,
        text: str,
        style: TemplateParagraphStyleConfig,
        *,
        prefix: str = "",
    ) -> None:
        self._apply_paragraph_style(paragraph, style)
        run = paragraph.add_run(f"{prefix}{text}")
        self._apply_run_style(run, style)

    def _render_table(self, document: Any, block: DocumentIRBlock, template_config: TemplateConfigPackage) -> None:
        rows = self._extract_table_rows(block.html)
        if not rows:
            paragraph = document.add_paragraph()
            self._fill_paragraph(paragraph, block.text or "", template_config.normal)
            return

        max_cols = max(len(row) for row in rows)
        table = document.add_table(rows=len(rows), cols=max_cols)
        try:
            table.style = template_config.table_style.style_name
        except (KeyError, ValueError):
            table.style = "Table Grid"
        table.autofit = True

        for row_index, row in enumerate(rows):
            for col_index in range(max_cols):
                cell = table.cell(row_index, col_index)
                text = row[col_index] if col_index < len(row) else ""
                cell.text = ""
                paragraph = cell.paragraphs[0]
                self._fill_paragraph(paragraph, text, template_config.table_content)
                if row_index == 0 and template_config.table_style.header_fill:
                    self._set_cell_fill(cell, template_config.table_style.header_fill)

    def _extract_table_rows(self, html: str | None) -> list[list[str]]:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        rows: list[list[str]] = []
        for tr in soup.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"], recursive=False)]
            if cells:
                rows.append(cells)
        return rows

    def _set_cell_fill(self, cell: Any, fill: str) -> None:
        tc_pr = cell._tc.get_or_add_tcPr()
        shading = tc_pr.find(qn("w:shd"))
        if shading is None:
            shading = OxmlElement("w:shd")
            tc_pr.append(shading)
        shading.set(qn("w:fill"), fill.strip().lstrip("#").upper())

    def _render_image(
        self,
        document: Any,
        block: DocumentIRBlock,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
    ) -> None:
        asset = assets_by_id.get(block.asset_ref or "")
        image_content = image_loader(asset) if asset is not None else None
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if not image_content:
            self._fill_paragraph(paragraph, block.text or "", template_config.caption)
            return

        try:
            available_width = self._available_width(document)
            run = paragraph.add_run()
            run.add_picture(io.BytesIO(image_content), width=available_width)
        except (InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError):
            paragraph.text = ""
            self._fill_paragraph(paragraph, block.text or "", template_config.caption)

        caption = block.text or block.metadata.get("caption")
        if isinstance(caption, str) and caption.strip():
            caption_paragraph = document.add_paragraph()
            self._fill_paragraph(caption_paragraph, caption.strip(), template_config.caption)

    def _available_width(self, document: Any) -> Any:
        if not document.sections:
            return Cm(14)
        section = document.sections[0]
        width = section.page_width - section.left_margin - section.right_margin
        return width if width > 0 else Cm(14)

    def _apply_paragraph_style(self, paragraph: Any, style: TemplateParagraphStyleConfig) -> None:
        if style.alignment:
            paragraph.alignment = self._parse_alignment(style.alignment)
        paragraph_format = paragraph.paragraph_format
        if style.space_before is not None:
            paragraph_format.space_before = Pt(style.space_before)
        if style.space_after is not None:
            paragraph_format.space_after = Pt(style.space_after)
        if style.line_spacing is not None:
            paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            paragraph_format.line_spacing = style.line_spacing
        if style.first_line_indent_pt is not None:
            paragraph_format.first_line_indent = Pt(style.first_line_indent_pt)
        if style.left_indent_pt is not None:
            paragraph_format.left_indent = Pt(style.left_indent_pt)
        if style.right_indent_pt is not None:
            paragraph_format.right_indent = Pt(style.right_indent_pt)

    def _apply_run_style(self, run: Any, style: TemplateParagraphStyleConfig) -> None:
        if style.font_name:
            run.font.name = style.font_name
            r_fonts = run._element.rPr.rFonts if run._element.rPr is not None else None
            if r_fonts is not None:
                r_fonts.set(qn("w:eastAsia"), style.font_name)
                r_fonts.set(qn("w:ascii"), style.font_name)
                r_fonts.set(qn("w:hAnsi"), style.font_name)
        if style.font_size is not None:
            run.font.size = Pt(style.font_size)
        if style.bold is not None:
            run.bold = style.bold
        if style.italic is not None:
            run.italic = style.italic
        if style.color:
            run.font.color.rgb = self._parse_color(style.color)

    def _parse_alignment(self, value: str) -> WD_ALIGN_PARAGRAPH:
        normalized = value.strip().lower()
        if normalized == "center":
            return WD_ALIGN_PARAGRAPH.CENTER
        if normalized == "right":
            return WD_ALIGN_PARAGRAPH.RIGHT
        if normalized == "justify":
            return WD_ALIGN_PARAGRAPH.JUSTIFY
        return WD_ALIGN_PARAGRAPH.LEFT

    def _parse_color(self, value: str) -> RGBColor:
        raw = value.strip().lstrip("#")
        if len(raw) != 6:
            return RGBColor(0, 0, 0)
        try:
            return RGBColor.from_string(raw.upper())
        except ValueError:
            return RGBColor(0, 0, 0)
