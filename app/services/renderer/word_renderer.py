from __future__ import annotations

# app/services/renderer/word_renderer.py: 将 DocumentIR v1/v2 按模板配置渲染为可编辑 DOCX。

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

from docx import Document
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.shared import Cm

from app.services.document_ir.models import DocumentIR, DocumentIRAsset, DocumentIRBlock
from app.services.renderer.image_renderer import WordImageRendererMixin
from app.services.renderer.layout_plan import LayoutPage, LayoutRegion, build_layout_plan
from app.services.renderer.table_renderer import WordTableRendererMixin
from app.services.renderer.template_config import TemplateConfigPackage, TemplateParagraphStyleConfig
from app.services.renderer.text_renderer import WordTextRendererMixin


ImageContentLoader = Callable[[DocumentIRAsset], bytes | None]


class DocumentIRWordRenderer(WordTextRendererMixin, WordTableRendererMixin, WordImageRendererMixin):
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
        layout_plan = build_layout_plan(document_ir)
        if layout_plan.mode == "legacy_v1_fallback":
            for block in layout_plan.pages[0].regions[0].blocks:
                self._render_block(document, block, assets_by_id, template_config, image_loader)
        else:
            for page_index, page in enumerate(layout_plan.pages):
                if page_index > 0:
                    document.add_page_break()
                self._render_layout_page(document, page, assets_by_id, template_config, image_loader)

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
        *,
        page_width: float | None = None,
    ) -> None:
        if block.type == "heading":
            paragraph = document.add_paragraph()
            self._fill_heading_paragraph(paragraph, block.text or "", block.level, template_config)
            return
        if block.type == "paragraph":
            paragraph = document.add_paragraph()
            self._fill_paragraph(paragraph, block.text or "", template_config.normal)
            return
        if block.type == "list":
            for item in block.list_items or []:
                paragraph = document.add_paragraph()
                self._fill_list_paragraph(paragraph, item, template_config)
            return
        if block.type == "formula":
            paragraph = document.add_paragraph()
            self._fill_formula_paragraph(paragraph, block.latex or block.text or "", template_config)
            return
        if block.type == "table":
            self._render_table(document, block, template_config)
            return
        if block.type == "image":
            self._render_image(document, block, assets_by_id, template_config, image_loader, page_width=page_width)

    def _render_layout_page(
        self,
        document: Any,
        page: LayoutPage,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
    ) -> None:
        self._render_page_decorations(document, page, template_config)
        for region in page.regions:
            self._render_layout_region(document, region, assets_by_id, template_config, image_loader, page_width=page.width)

    def _render_page_decorations(
        self,
        document: Any,
        page: LayoutPage,
        template_config: TemplateConfigPackage,
    ) -> None:
        if not document.sections:
            return
        section = document.sections[-1]
        if template_config.header.enabled and page.header_blocks:
            paragraph = section.header.paragraphs[0] if section.header.paragraphs else section.header.add_paragraph()
            paragraph.text = ""
            self._fill_paragraph(paragraph, " ".join(block.text or "" for block in page.header_blocks).strip(), template_config.normal)
        footer_blocks = page.footer_blocks + page.page_number_blocks
        if template_config.footer.enabled and footer_blocks:
            paragraph = section.footer.paragraphs[0] if section.footer.paragraphs else section.footer.add_paragraph()
            paragraph.text = ""
            self._fill_paragraph(paragraph, " ".join(block.text or "" for block in footer_blocks).strip(), template_config.normal)

    def _render_layout_region(
        self,
        document: Any,
        region: LayoutRegion,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        *,
        page_width: float | None = None,
    ) -> None:
        if region.kind != "two_col":
            for block in region.blocks:
                self._render_block(document, block, assets_by_id, template_config, image_loader, page_width=page_width)
            return

        table = document.add_table(rows=1, cols=2)
        table.autofit = True
        left_blocks, right_blocks = self._split_two_col_blocks(region.blocks)
        for cell, blocks in zip(table.rows[0].cells, (left_blocks, right_blocks), strict=True):
            cell.text = ""
            for block in blocks:
                self._render_block(cell, block, assets_by_id, template_config, image_loader, page_width=page_width)

    def _split_two_col_blocks(
        self,
        blocks: list[DocumentIRBlock],
    ) -> tuple[list[DocumentIRBlock], list[DocumentIRBlock]]:
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
