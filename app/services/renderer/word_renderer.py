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
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Twips

from app.conversion.docx_rules.terminology import TerminologyReplacer
from app.conversion.docx_rules.text_semantics import split_document_identity
from app.services.document_ir.models import DocumentIR, DocumentIRAsset, DocumentIRBlock
from app.services.document_ir.table_annotations import is_table_context_annotation
from app.services.renderer.image_renderer import WordImageRendererMixin
from app.services.renderer.layout_plan import LayoutPage, LayoutPlan, LayoutRegion, build_layout_plan
from app.services.renderer.semantic_text import parse_toc_entry_text
from app.services.renderer.table_renderer import WordTableRendererMixin
from app.services.renderer.table_layout import TableFitDecision
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


def resolve_template_config(
    document_ir: DocumentIR,
    config_path: Path | None,
    options: DocumentIRRenderOptions | None,
    *,
    template_path: Path | None = None,
) -> TemplateConfigPackage:
    """解析一次最终模板配置，供 LayoutPlan、renderer 和 evidence 共同消费。"""

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
    return _apply_template_page_size_defaults(template_config, template_path)


def _apply_template_page_size_defaults(
    template_config: TemplateConfigPackage,
    template_path: Path | None,
) -> TemplateConfigPackage:
    """配置未声明纸张尺寸时，从清空正文后仍保留的模板末节补齐。"""

    setup = template_config.page_setup
    has_explicit_page_size = setup.page_width_cm is not None and setup.page_height_cm is not None
    if has_explicit_page_size or template_path is None or not template_path.is_file():
        return template_config
    template_document = Document(str(template_path))
    if not template_document.sections:
        return template_config
    section = template_document.sections[-1]
    page_width = section.page_width
    page_height = section.page_height
    if page_width is None or page_width <= 0 or page_height is None or page_height <= 0:
        return template_config
    short_side, long_side = sorted((page_width.cm, page_height.cm))
    page_setup = setup.model_copy(
        update={
            "page_width_cm": setup.page_width_cm if setup.page_width_cm is not None else short_side,
            "page_height_cm": setup.page_height_cm if setup.page_height_cm is not None else long_side,
        }
    )
    return template_config.model_copy(update={"page_setup": page_setup})


@dataclass(slots=True)
class _RenderContext:
    """单次渲染的字段目标；不得存到可并发复用的 renderer 实例。"""

    caption_bookmarks: dict[tuple[str, int], tuple[str, int]]
    allow_heading_inference: bool
    toc_headings: tuple[tuple[int, str], ...]
    table_fit_decisions: dict[str, TableFitDecision]
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
        layout_plan: LayoutPlan | None = None,
        template_config: TemplateConfigPackage | None = None,
    ) -> bytes:
        """按模板 DOCX 与配置包生成 Word 二进制。"""

        template_config = template_config or resolve_template_config(
            document_ir,
            config_path,
            options,
            template_path=template_path,
        )
        document = self._create_document(template_path)
        self._bind_math_font_context(document)
        self._clear_body(document)
        self._apply_page_setup(document, template_config)
        self._apply_header_footer(document, template_config, config_path=config_path)
        self._apply_document_settings(document)

        assets_by_id = {asset.id: asset for asset in document_ir.assets}
        resolved_layout_plan = layout_plan or build_layout_plan(document_ir, template_config)
        render_context = self._build_render_context(
            document_ir,
            resolved_layout_plan.table_fit_decisions,
            template_config,
        )
        if resolved_layout_plan.mode == "legacy_v1_fallback":
            for block in resolved_layout_plan.pages[0].regions[0].blocks:
                self._render_block(document, block, assets_by_id, template_config, image_loader, render_context)
        else:
            # 只在真实内容即将使用时创建 section，避免横向表格降级前出现无内容的中间页。
            current_section_landscape: bool | None = None
            for page_index, page in enumerate(resolved_layout_plan.pages):
                page_landscape = self._layout_page_requires_landscape(page)
                starts_with_landscape_table = bool(page.regions and page.regions[0].kind == "landscape_table")
                if page_index == 0:
                    self._configure_layout_page_section(
                        document,
                        page,
                        template_config,
                        landscape=starts_with_landscape_table or page_landscape,
                    )
                elif not starts_with_landscape_table:
                    if page_landscape != current_section_landscape:
                        document.add_section(WD_SECTION_START.NEW_PAGE)
                    self._configure_layout_page_section(document, page, template_config, landscape=page_landscape)
                self._render_layout_page(
                    document,
                    page,
                    assets_by_id,
                    template_config,
                    image_loader,
                    render_context,
                    page_break_before_block_id=page.break_before_block_id,
                    use_current_section_for_first_landscape=page_index == 0 and starts_with_landscape_table,
                )
                if page.regions:
                    current_section_landscape = page.regions[-1].kind == "landscape_table" or page_landscape

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

    def _build_render_context(
        self,
        document_ir: DocumentIR,
        table_fit_decisions: dict[str, TableFitDecision],
        template_config: TemplateConfigPackage,
    ) -> _RenderContext:
        """只为本次实际生成的唯一题注字段建立 bookmark 与 REF 目标。"""

        caption_keys: list[tuple[str, int]] = []
        for block in document_ir.blocks:
            if block.type == "table":
                annotations = [
                    annotation
                    for annotation in self._unique_annotation_texts(block.captions)
                    if not is_table_context_annotation(annotation)
                ]
            elif block.type == "image":
                annotations = self._image_annotation_texts(block)
            elif block.type == "paragraph" and block.metadata.get("annotation_role") == "standalone_caption":
                annotations = [block.text or ""] if (block.text or "").strip() else []
            else:
                continue
            for annotation in annotations:
                parsed = self._parse_caption_text(annotation.strip())
                if parsed is None:
                    parsed = self._parse_caption_text(
                        self._prepare_text_for_rendering(annotation.strip(), template_config.terminology)
                    )
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
        return _RenderContext(
            caption_bookmarks=bookmarks,
            allow_heading_inference=document_ir.schema_version == "document-ir/v1",
            toc_headings=tuple(
                (block.level or 1, block.text or "")
                for block in sorted(document_ir.blocks, key=lambda item: item.order)
                if block.type == "heading"
                and (block.layout is None or block.layout.role == "body")
                and (block.text or "").strip()
            ),
            table_fit_decisions=table_fit_decisions,
        )

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
        logo_path = self._resolve_asset_path(template_config.header.logo_path, config_path)
        has_header_content = bool(template_config.header.title_text or (logo_path is not None and logo_path.exists()))
        if template_config.header.enabled and has_header_content:
            header = section.header
            for child in list(header._element):
                header._element.remove(child)
            paragraph = header.add_paragraph()
            header_style = TemplateParagraphStyleConfig(
                font_name=template_config.header.title_font_name,
                western_font_name=template_config.header.title_western_font_name,
                complex_script_font_name=template_config.header.title_complex_script_font_name,
                font_size=template_config.header.title_font_size,
                color=template_config.header.title_color,
                alignment="left",
            )
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

        has_footer_override = bool(
            template_config.footer.left_text
            or template_config.footer.right_text
            or template_config.footer.show_page_number
        )
        if template_config.footer.enabled and has_footer_override:
            footer_style = TemplateParagraphStyleConfig(
                font_name=template_config.footer.font_name,
                western_font_name=template_config.footer.western_font_name,
                complex_script_font_name=template_config.footer.complex_script_font_name,
            )
            footer = section.footer
            for child in list(footer._element):
                footer._element.remove(child)
            paragraph = footer.add_paragraph()
            if template_config.footer.left_text or template_config.footer.right_text:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                self._add_text_run(paragraph, template_config.footer.left_text, footer_style)
                self._add_positional_tab(paragraph, "center")
                if template_config.footer.show_page_number:
                    self._add_complex_field(paragraph, " PAGE ", "1", footer_style)
                self._add_positional_tab(paragraph, "right")
                self._add_text_run(paragraph, template_config.footer.right_text, footer_style)
                return

            paragraph.alignment = self._parse_alignment(template_config.footer.alignment or "center")
            if template_config.footer.show_page_number:
                self._add_complex_field(paragraph, " PAGE ", "1", footer_style)

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
        page_height: float | None = None,
        page_break_before: bool = False,
        column_break_before: bool = False,
        keep_with_next: bool = False,
    ) -> None:
        if block.type == "heading":
            paragraph = document.add_paragraph()
            self._apply_paragraph_breaks(
                paragraph,
                page_break_before=page_break_before,
                column_break_before=column_break_before,
            )
            self._fill_heading_paragraph(paragraph, block.text or "", block.level, template_config)
            paragraph.paragraph_format.keep_with_next = True
            return
        if block.type == "paragraph":
            text = block.text or ""
            annotation_role = block.metadata.get("annotation_role")
            if annotation_role == "document_identity":
                identity = split_document_identity(text)
                if identity is None:
                    raise ValueError(f"文档身份文本无法拆分: {block.id}")
                for index, (value, style) in enumerate(
                    zip(identity, (template_config.part_number, template_config.category), strict=True)
                ):
                    paragraph = document.add_paragraph()
                    self._apply_paragraph_breaks(
                        paragraph,
                        page_break_before=page_break_before and index == 0,
                        column_break_before=column_break_before and index == 0,
                    )
                    self._fill_paragraph(paragraph, value, style, terminology=template_config.terminology)
                    paragraph.paragraph_format.keep_with_next = index == 0
                return
            if annotation_role == "toc_anchor":
                if render_context.toc_written:
                    return
                render_context.toc_written = True
                paragraph = document.add_paragraph()
                self._apply_paragraph_breaks(
                    paragraph,
                    page_break_before=page_break_before,
                    column_break_before=column_break_before,
                )
                self._fill_toc_anchor(paragraph, render_context.toc_headings, template_config)
                return
            if annotation_role == "toc_title":
                paragraph = document.add_paragraph()
                self._apply_paragraph_breaks(
                    paragraph,
                    page_break_before=page_break_before,
                    column_break_before=column_break_before,
                )
                self._fill_paragraph(
                    paragraph,
                    text,
                    template_config.toc_title,
                    terminology=template_config.terminology,
                )
                paragraph.paragraph_format.keep_with_next = True
                return
            if annotation_role == "standalone_caption":
                paragraph = document.add_paragraph()
                self._apply_paragraph_breaks(
                    paragraph,
                    page_break_before=page_break_before,
                    column_break_before=column_break_before,
                )
                if not self._fill_caption_paragraph(
                    paragraph,
                    text,
                    template_config.caption,
                    terminology=template_config.terminology,
                    caption_bookmarks=render_context.caption_bookmarks,
                ):
                    self._fill_paragraph(paragraph, text, template_config.caption, terminology=template_config.terminology)
                return
            if annotation_role == "group_label":
                paragraph = document.add_paragraph()
                self._apply_paragraph_breaks(
                    paragraph,
                    page_break_before=page_break_before,
                    column_break_before=column_break_before,
                )
                self._fill_paragraph(paragraph, text, template_config.normal, terminology=template_config.terminology)
                for run in paragraph.runs:
                    run.bold = True
                paragraph.paragraph_format.keep_with_next = True
                return
            if annotation_role == "page_note":
                paragraph = document.add_paragraph()
                self._apply_paragraph_breaks(
                    paragraph,
                    page_break_before=page_break_before,
                    column_break_before=column_break_before,
                )
                self._fill_paragraph(paragraph, text, template_config.table_note, terminology=template_config.terminology)
                return
            if render_context.allow_heading_inference and parse_toc_entry_text(text) is not None:
                if render_context.toc_written:
                    return
                render_context.toc_written = True
            paragraph = document.add_paragraph()
            self._apply_paragraph_breaks(
                paragraph,
                page_break_before=page_break_before,
                column_break_before=column_break_before,
            )
            if block.metadata.get("annotation_role") == "table_context":
                paragraph.paragraph_format.keep_with_next = True
                self._fill_table_context_paragraph(paragraph, text, template_config)
                return
            self._fill_auto_list_or_paragraph(
                paragraph,
                text,
                template_config,
                reference_bookmarks=render_context.caption_bookmarks,
                allow_heading_inference=render_context.allow_heading_inference,
                allow_toc_inference=render_context.allow_heading_inference,
            )
            if keep_with_next:
                paragraph.paragraph_format.keep_with_next = True
            return
        if block.type == "list":
            for index, item in enumerate(block.list_items or []):
                if render_context.allow_heading_inference and parse_toc_entry_text(item) is not None:
                    if render_context.toc_written:
                        continue
                    render_context.toc_written = True
                paragraph = document.add_paragraph()
                self._apply_paragraph_breaks(
                    paragraph,
                    page_break_before=page_break_before and index == 0,
                    column_break_before=column_break_before and index == 0,
                )
                self._fill_auto_list_item_paragraph(
                    paragraph,
                    item,
                    template_config,
                    reference_bookmarks=render_context.caption_bookmarks,
                    allow_toc_inference=render_context.allow_heading_inference,
                )
            return
        if block.type == "formula":
            paragraph = document.add_paragraph()
            self._apply_paragraph_breaks(
                paragraph,
                page_break_before=page_break_before,
                column_break_before=column_break_before,
            )
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
                column_break_before=column_break_before,
                fit_decision=render_context.table_fit_decisions.get(block.id),
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
                page_height=page_height,
                caption_bookmarks=render_context.caption_bookmarks,
                page_break_before=page_break_before,
                column_break_before=column_break_before,
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
        use_current_section_for_first_landscape: bool = False,
    ) -> None:
        for region_index, region in enumerate(page.regions):
            self._render_layout_region(
                document,
                region,
                assets_by_id,
                template_config,
                image_loader,
                render_context,
                page_width=page.width,
                page_height=page.height,
                page_break_before_block_id=page_break_before_block_id,
                layout_page=page,
                restore_after_landscape=region_index < len(page.regions) - 1,
                use_current_section_for_landscape=use_current_section_for_first_landscape and region_index == 0,
            )

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
        page_height: float | None = None,
        page_break_before_block_id: str | None = None,
        layout_page: LayoutPage | None = None,
        restore_after_landscape: bool = False,
        use_current_section_for_landscape: bool = False,
    ) -> None:
        if region.kind == "landscape_table":
            if layout_page is None:
                raise ValueError("横向表格区域缺少页面计划")
            if not use_current_section_for_landscape:
                document.add_section(WD_SECTION_START.NEW_PAGE)
            self._configure_layout_page_section(document, layout_page, template_config, landscape=True)
            for block in region.blocks:
                self._render_block(
                    document,
                    block,
                    assets_by_id,
                    template_config,
                    image_loader,
                    render_context,
                    page_width=page_width,
                    page_height=page_height,
                )
            if restore_after_landscape:
                document.add_section(WD_SECTION_START.NEW_PAGE)
                self._configure_layout_page_section(
                    document,
                    layout_page,
                    template_config,
                    landscape=self._layout_page_requires_landscape(layout_page),
                )
            return

        if region.kind == "paired_visual_row":
            if len(region.blocks) != 2:
                raise ValueError("成对视觉行必须且只能包含左右两张图片")
            self._render_paired_visual_row(
                document,
                region.blocks[0],
                region.blocks[1],
                assets_by_id,
                template_config,
                image_loader,
                page_width=page_width,
                page_height=page_height,
                caption_bookmarks=render_context.caption_bookmarks,
                page_break_before=region.blocks[0].id == page_break_before_block_id,
            )
            return

        if region.kind == "visual_table_composite":
            image_block = next((block for block in region.blocks if block.type == "image"), None)
            table_block = next((block for block in region.blocks if block.type == "table"), None)
            if image_block is None or table_block is None or len(region.blocks) != 2:
                raise ValueError("表图复合区域必须且只能包含一张图片和一张表格")
            self._render_visual_table_composite(
                document,
                image_block,
                table_block,
                assets_by_id,
                template_config,
                image_loader,
                page_width=page_width,
                caption_bookmarks=render_context.caption_bookmarks,
                reference_bookmarks=render_context.caption_bookmarks,
                fit_decision=render_context.table_fit_decisions.get(table_block.id),
                page_break_before=any(block.id == page_break_before_block_id for block in region.blocks),
            )
            return

        if region.kind == "visual_prelude":
            for index, block in enumerate(region.blocks):
                self._render_block(
                    document,
                    block,
                    assets_by_id,
                    template_config,
                    image_loader,
                    render_context,
                    page_width=page_width,
                    page_height=page_height,
                    page_break_before=block.id == page_break_before_block_id,
                    keep_with_next=index < len(region.blocks) - 1,
                )
            return

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
                    page_height=page_height,
                    page_break_before=block.id == page_break_before_block_id,
                )
            return

        if region.column_break_index is None or not 0 < region.column_break_index < len(region.blocks):
            raise ValueError("双栏区域缺少有效的最终栏断点")
        left_blocks = region.blocks[: region.column_break_index]
        right_blocks = region.blocks[region.column_break_index :]
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
                page_height=page_height,
                page_break_before=block.id == page_break_before_block_id,
            )
        for index, block in enumerate(right_blocks):
            self._render_block(
                document,
                block,
                assets_by_id,
                template_config,
                image_loader,
                render_context,
                page_width=page_width,
                page_height=page_height,
                page_break_before=block.id == page_break_before_block_id,
                column_break_before=index == 0,
            )
        one_column_section = document.add_section(WD_SECTION_START.CONTINUOUS)
        self._set_section_columns(one_column_section, 1)

    def _set_section_columns(self, section: Any, count: int) -> None:
        columns = section._sectPr.find(qn("w:cols"))
        if columns is None:
            columns = OxmlElement("w:cols")
            section._sectPr.append(columns)
        columns.set(qn("w:num"), str(count))
