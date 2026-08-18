from __future__ import annotations

# app/services/renderer/word_renderer.py: 将 DocumentIR v1/v2 按模板配置渲染为可编辑 DOCX。

import io
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_ORIENTATION, WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Twips

from app.conversion.docx_rules.terminology import TerminologyReplacer
from app.services.document_ir.models import DocumentIR, DocumentIRAsset, DocumentIRBlock
from app.services.renderer.image_renderer import WordImageRendererMixin
from app.services.renderer.layout_plan import LayoutPage, LayoutRegion, build_layout_plan
from app.services.renderer.semantic_text import parse_toc_entry_text
from app.services.renderer.table_renderer import WordTableRendererMixin
from app.services.renderer.template_config import TemplateConfigPackage, TemplateParagraphStyleConfig
from app.services.renderer.text_renderer import WordTextRendererMixin


ImageContentLoader = Callable[[DocumentIRAsset], bytes | None]
A4_PORTRAIT_WIDTH = Mm(210)
A4_PORTRAIT_HEIGHT = Mm(297)


@dataclass(frozen=True, slots=True)
class DocumentIRRenderOptions:
    """document_jobs 正式管线为单次渲染提供的选项。"""

    subscript_config_path: Path | None = None
    document_language: str | None = None


@dataclass(slots=True)
class _RenderContext:
    """单次渲染的字段目标；不得存到可并发复用的 renderer 实例。"""

    caption_bookmarks: dict[tuple[str, int], tuple[str, int]]
    toc_written: bool = False


class DocumentIRWordRenderer(WordTextRendererMixin, WordTableRendererMixin, WordImageRendererMixin):
    """P0 Word 渲染器：覆盖标题、段落、基础表格和图片。"""

    def render_to_bytes(
        self,
        document_ir: DocumentIR,
        *,
        template_path: Path | None,
        config_path: Path | None,
        image_loader: ImageContentLoader,
        options: DocumentIRRenderOptions | None = None,
    ) -> bytes:
        """按模板 DOCX 与配置包生成 Word 二进制。"""

        template_config = self._load_template_config(document_ir, config_path, options)
        document = self._create_document(template_path)
        self._clear_body(document)
        self._apply_page_setup(document, template_config)
        self._apply_header_footer(document, template_config, config_path=config_path)
        self._apply_document_settings(document)

        assets_by_id = {asset.id: asset for asset in document_ir.assets}
        render_context = self._build_render_context(document_ir)
        layout_plan = build_layout_plan(document_ir)
        if layout_plan.mode == "legacy_v1_fallback":
            for block in layout_plan.pages[0].regions[0].blocks:
                self._render_block(document, block, assets_by_id, template_config, image_loader, render_context)
        else:
            previous_page_landscape = False
            for page_index, page in enumerate(layout_plan.pages):
                page_landscape = self._layout_page_requires_landscape(page)
                page_break_before_block_id = None
                if page_index > 0:
                    if page_landscape != previous_page_landscape:
                        document.add_section(WD_SECTION_START.NEW_PAGE)
                    else:
                        page_break_before_block_id = self._semantic_page_break_block_id(page)
                self._configure_layout_page_section(document, page, template_config, landscape=page_landscape)
                self._render_layout_page(
                    document,
                    page,
                    assets_by_id,
                    template_config,
                    image_loader,
                    render_context,
                    page_break_before_block_id=page_break_before_block_id,
                )
                previous_page_landscape = page_landscape

        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def _apply_document_settings(self, document: Any) -> None:
        settings = document.settings.element
        for tag in ("w:doNotAutoCompressPictures", "w:updateFields"):
            element = settings.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                settings.append(element)
            element.set(qn("w:val"), "true")

    def _content_width_and_columns(self, document: Any) -> tuple[int, int]:
        sections = getattr(document, "sections", None)
        if not sections:
            return int(Cm(14)), 1
        section = sections[-1]
        total_width = section.page_width - section.left_margin - section.right_margin
        if total_width <= 0:
            return int(Cm(14)), 1

        columns = section._sectPr.find(qn("w:cols"))
        raw_count = columns.get(qn("w:num")) if columns is not None else None
        column_count = max(int(raw_count), 1) if raw_count and raw_count.isdigit() else 1
        if column_count == 1:
            return int(total_width), 1
        raw_space = columns.get(qn("w:space")) if columns is not None else None
        column_space = int(raw_space) if raw_space and raw_space.isdigit() else 720
        available_width = total_width - Twips(column_space * (column_count - 1))
        return max(int(available_width / column_count), 1), column_count

    def _build_render_context(self, document_ir: DocumentIR) -> _RenderContext:
        caption_keys: list[tuple[str, int]] = []
        for block in document_ir.blocks:
            if block.type == "table":
                annotations = self._unique_annotation_texts(block.captions)
            elif block.type == "image":
                annotations = self._image_annotation_texts(block)
            else:
                continue
            for annotation in annotations:
                parsed = self._parse_caption_text(annotation.strip())
                if parsed is None:
                    continue
                _prefix, label, _spacing, source_number, _tail = parsed
                kind = "figure" if label.lower() == "figure" or label == "图" else "table"
                caption_keys.append((kind, source_number))

        counts = Counter(caption_keys)
        bookmarks: dict[tuple[str, int], tuple[str, int]] = {}
        for key in caption_keys:
            if counts[key] != 1 or key in bookmarks:
                continue
            kind, source_number = key
            bookmarks[key] = (f"_md2word_{kind}_{source_number}", len(bookmarks) + 1)
        return _RenderContext(caption_bookmarks=bookmarks)

    def _create_document(self, template_path: Path | None) -> Any:
        if template_path is not None and template_path.exists():
            return Document(str(template_path))
        return Document()

    def _load_template_config(
        self,
        document_ir: DocumentIR,
        config_path: Path | None,
        options: DocumentIRRenderOptions | None,
    ) -> TemplateConfigPackage:
        document_language = (
            options.document_language
            if options is not None and options.document_language
            else document_ir.metadata.document_language
        )
        template_config = TemplateConfigPackage.load(config_path).for_document_language(document_language)
        subscript_config_path = options.subscript_config_path if options is not None else None
        if subscript_config_path is not None:
            terminology = TerminologyReplacer(subscript_config_path)
            if terminology.rules:
                template_config.terminology = terminology
        return template_config

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
            self._apply_page_setup_to_section(section, setup)

    def _apply_page_setup_to_section(self, section: Any, setup: Any, *, apply_page_size: bool = True) -> None:
        if apply_page_size:
            if setup.page_width_cm is not None:
                section.page_width = Cm(setup.page_width_cm)
            if setup.page_height_cm is not None:
                section.page_height = Cm(setup.page_height_cm)
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

    def _configure_layout_page_section(
        self,
        document: Any,
        page: LayoutPage,
        template_config: TemplateConfigPackage,
        *,
        landscape: bool,
    ) -> None:
        if not document.sections:
            return
        section = document.sections[-1]
        section.orientation = WD_ORIENTATION.LANDSCAPE if landscape else WD_ORIENTATION.PORTRAIT
        portrait_width, portrait_height = self._portrait_page_dimensions(template_config)
        short_side = min(portrait_width, portrait_height)
        long_side = max(portrait_width, portrait_height)
        section.page_width = long_side if landscape else short_side
        section.page_height = short_side if landscape else long_side
        self._apply_page_setup_to_section(section, template_config.page_setup, apply_page_size=False)

    def _portrait_page_dimensions(self, template_config: TemplateConfigPackage) -> tuple[Any, Any]:
        setup = template_config.page_setup
        width = Cm(setup.page_width_cm) if setup.page_width_cm is not None else A4_PORTRAIT_WIDTH
        height = Cm(setup.page_height_cm) if setup.page_height_cm is not None else A4_PORTRAIT_HEIGHT
        return width, height

    def _layout_page_requires_landscape(self, page: LayoutPage) -> bool:
        return page.width is not None and page.height is not None and page.width > page.height

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
                western_font_name=template_config.header.title_western_font_name,
                complex_script_font_name=template_config.header.title_complex_script_font_name,
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

        if template_config.footer.enabled:
            footer_style = TemplateParagraphStyleConfig(
                font_name=template_config.footer.font_name,
                western_font_name=template_config.footer.western_font_name,
                complex_script_font_name=template_config.footer.complex_script_font_name,
            )
            if template_config.footer.left_text or template_config.footer.right_text:
                footer = section.footer
                for child in list(footer._element):
                    footer._element.remove(child)
                paragraph = footer.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                self._add_text_run(paragraph, template_config.footer.left_text, footer_style)
                self._add_positional_tab(paragraph, "center")
                if template_config.footer.show_page_number:
                    self._add_complex_field(paragraph, " PAGE ", "1", footer_style)
                self._add_positional_tab(paragraph, "right")
                self._add_text_run(paragraph, template_config.footer.right_text, footer_style)
                return

            paragraph = section.footer.paragraphs[0] if section.footer.paragraphs else section.footer.add_paragraph()
            if template_config.footer.show_page_number and not paragraph.text.strip() and not paragraph.runs:
                paragraph.text = "第  页"
            for footer_paragraph in section.footer.paragraphs:
                footer_paragraph.alignment = self._parse_alignment(template_config.footer.alignment or "center")
                for run in footer_paragraph.runs:
                    self._apply_run_style(run, footer_style)

    def _add_positional_tab(self, paragraph: Any, alignment: str) -> None:
        run = paragraph.add_run()
        tab = OxmlElement("w:ptab")
        tab.set(qn("w:alignment"), alignment)
        tab.set(qn("w:relativeTo"), "margin")
        tab.set(qn("w:leader"), "none")
        run._r.append(tab)

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
        render_context: _RenderContext,
        *,
        page_width: float | None = None,
        page_break_before: bool = False,
    ) -> None:
        if block.type == "heading":
            paragraph = document.add_paragraph()
            self._fill_heading_paragraph(paragraph, block.text or "", block.level, template_config)
            paragraph.paragraph_format.keep_with_next = True
            if page_break_before:
                paragraph.paragraph_format.page_break_before = True
            return
        if block.type == "paragraph":
            text = block.text or ""
            if parse_toc_entry_text(text) is not None:
                if render_context.toc_written:
                    return
                render_context.toc_written = True
            paragraph = document.add_paragraph()
            if block.metadata.get("annotation_role") == "table_context":
                paragraph.paragraph_format.keep_with_next = True
                if page_break_before:
                    paragraph.paragraph_format.page_break_before = True
                self._fill_table_context_paragraph(paragraph, text, template_config)
                return
            self._fill_auto_list_or_paragraph(
                paragraph,
                text,
                template_config,
                reference_bookmarks=render_context.caption_bookmarks,
            )
            return
        if block.type == "list":
            for item in block.list_items or []:
                if parse_toc_entry_text(item) is not None:
                    if render_context.toc_written:
                        continue
                    render_context.toc_written = True
                paragraph = document.add_paragraph()
                self._fill_auto_list_item_paragraph(
                    paragraph,
                    item,
                    template_config,
                    reference_bookmarks=render_context.caption_bookmarks,
                )
            return
        if block.type == "formula":
            paragraph = document.add_paragraph()
            self._fill_formula_paragraph(paragraph, block.latex or block.text or "", template_config)
            return
        if block.type == "table":
            self._render_table(
                document,
                block,
                template_config,
                caption_bookmarks=render_context.caption_bookmarks,
                reference_bookmarks=render_context.caption_bookmarks,
                page_break_before=page_break_before,
            )
            return
        if block.type == "image":
            self._render_image(
                document,
                block,
                assets_by_id,
                template_config,
                image_loader,
                page_width=page_width,
                caption_bookmarks=render_context.caption_bookmarks,
            )

    def _render_layout_page(
        self,
        document: Any,
        page: LayoutPage,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        render_context: _RenderContext,
        *,
        page_break_before_block_id: str | None = None,
    ) -> None:
        self._render_page_decorations(document, page, template_config)
        for region in page.regions:
            self._render_layout_region(
                document,
                region,
                assets_by_id,
                template_config,
                image_loader,
                render_context,
                page_width=page.width,
                page_break_before_block_id=page_break_before_block_id,
            )

    def _semantic_page_break_block_id(self, page: LayoutPage) -> str | None:
        first_block = next((block for region in page.regions for block in region.blocks), None)
        if first_block is None:
            return None
        if first_block.type == "heading":
            return first_block.id
        if first_block.type == "table" and first_block.captions:
            return first_block.id
        if first_block.type == "paragraph" and first_block.metadata.get("annotation_role") == "table_context":
            return first_block.id
        return None

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
            # 抽取装饰块历史上沿用正文排版，这里只用页眉/页脚配置覆盖字体。
            header_font_name = template_config.header.title_font_name
            header_style = template_config.normal.model_copy(
                update={
                    "font_name": template_config.normal.font_name if header_font_name is None else header_font_name,
                    "western_font_name": self._resolve_decoration_font(
                        template_config.header.title_western_font_name,
                        header_font_name,
                        template_config.normal.western_font_name,
                    ),
                    "complex_script_font_name": self._resolve_decoration_font(
                        template_config.header.title_complex_script_font_name,
                        header_font_name,
                        template_config.normal.complex_script_font_name,
                    ),
                }
            )
            self._fill_paragraph(
                paragraph,
                " ".join(block.text or "" for block in page.header_blocks).strip(),
                header_style,
                terminology=template_config.terminology,
            )
        footer_blocks = page.footer_blocks + page.page_number_blocks
        custom_footer = bool(template_config.footer.left_text or template_config.footer.right_text)
        if template_config.footer.enabled and footer_blocks and not custom_footer:
            paragraph = section.footer.paragraphs[0] if section.footer.paragraphs else section.footer.add_paragraph()
            paragraph.text = ""
            footer_font_name = template_config.footer.font_name
            footer_style = template_config.normal.model_copy(
                update={
                    "font_name": template_config.normal.font_name if footer_font_name is None else footer_font_name,
                    "western_font_name": self._resolve_decoration_font(
                        template_config.footer.western_font_name,
                        footer_font_name,
                        template_config.normal.western_font_name,
                    ),
                    "complex_script_font_name": self._resolve_decoration_font(
                        template_config.footer.complex_script_font_name,
                        footer_font_name,
                        template_config.normal.complex_script_font_name,
                    ),
                }
            )
            self._fill_paragraph(
                paragraph,
                " ".join(block.text or "" for block in footer_blocks).strip(),
                footer_style,
                terminology=template_config.terminology,
            )

    @staticmethod
    def _resolve_decoration_font(configured: str | None, legacy: str | None, inherited: str | None) -> str | None:
        """字体字段缺失时依次沿用旧单字体和正文；显式空字符串不回退。"""

        if configured is not None:
            return configured
        if legacy is not None:
            return legacy
        return inherited

    def _render_layout_region(
        self,
        document: Any,
        region: LayoutRegion,
        assets_by_id: dict[str, DocumentIRAsset],
        template_config: TemplateConfigPackage,
        image_loader: ImageContentLoader,
        render_context: _RenderContext,
        *,
        page_width: float | None = None,
        page_break_before_block_id: str | None = None,
    ) -> None:
        if region.kind != "two_col":
            for block in region.blocks:
                self._render_block(
                    document,
                    block,
                    assets_by_id,
                    template_config,
                    image_loader,
                    render_context,
                    page_width=page_width,
                    page_break_before=block.id == page_break_before_block_id,
                )
            return

        image_rows = self._split_two_column_image_rows(region.blocks)
        if image_rows is not None:
            for row_index, (left, right) in enumerate(image_rows):
                self._render_two_column_image_row(
                    document,
                    left,
                    right,
                    assets_by_id,
                    template_config,
                    image_loader,
                    page_width=page_width,
                    caption_bookmarks=render_context.caption_bookmarks,
                    keep_with_next=row_index < len(image_rows) - 1,
                )
            return

        left_blocks, right_blocks = self._split_two_col_blocks(region.blocks)
        two_column_section = document.add_section(WD_SECTION_START.CONTINUOUS)
        self._set_section_columns(two_column_section, 2)
        for block in left_blocks:
            self._render_block(
                document,
                block,
                assets_by_id,
                template_config,
                image_loader,
                render_context,
                page_width=page_width,
                page_break_before=block.id == page_break_before_block_id,
            )
        column_break = document.add_paragraph()
        column_break.add_run().add_break(WD_BREAK.COLUMN)
        for block in right_blocks:
            self._render_block(
                document,
                block,
                assets_by_id,
                template_config,
                image_loader,
                render_context,
                page_width=page_width,
                page_break_before=block.id == page_break_before_block_id,
            )
        one_column_section = document.add_section(WD_SECTION_START.CONTINUOUS)
        self._set_section_columns(one_column_section, 1)

    def _set_section_columns(self, section: Any, count: int) -> None:
        columns = section._sectPr.find(qn("w:cols"))
        if columns is None:
            columns = OxmlElement("w:cols")
            section._sectPr.append(columns)
        columns.set(qn("w:num"), str(count))

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

    def _split_two_column_image_rows(
        self,
        blocks: list[DocumentIRBlock],
    ) -> list[tuple[DocumentIRBlock, DocumentIRBlock]] | None:
        """把 bbox 明确成对的纯图片双栏区按行切分，保持题注字段的阅读顺序。"""

        if (
            len(blocks) < 2
            or any(block.type != "image" for block in blocks)
            or any(len(self._image_annotation_texts(block)) > 1 for block in blocks)
        ):
            return None
        left_blocks, right_blocks = self._split_two_col_blocks(blocks)
        if len(left_blocks) != len(right_blocks) or not left_blocks:
            return None
        left_blocks.sort(key=lambda block: block.layout.bbox[1] if block.layout and block.layout.bbox else float("inf"))
        right_blocks.sort(key=lambda block: block.layout.bbox[1] if block.layout and block.layout.bbox else float("inf"))
        rows: list[tuple[DocumentIRBlock, DocumentIRBlock]] = []
        for left, right in zip(left_blocks, right_blocks, strict=True):
            left_bbox = left.layout.bbox if left.layout is not None else None
            right_bbox = right.layout.bbox if right.layout is not None else None
            if left_bbox is None or right_bbox is None:
                return None
            if min(left_bbox[3], right_bbox[3]) <= max(left_bbox[1], right_bbox[1]):
                return None
            rows.append((left, right))
        return rows
