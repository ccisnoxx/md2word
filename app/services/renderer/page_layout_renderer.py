from __future__ import annotations

# app/services/renderer/page_layout_renderer.py: 页面设置、页眉页脚、分节分栏与页面装饰的 Word 写入 helper。

import io
from typing import Any

from docx.enum.section import WD_ORIENTATION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm

from app.services.renderer.template_config import TemplateConfigPackage, TemplateParagraphStyleConfig


A4_PORTRAIT_WIDTH = Mm(210)
A4_PORTRAIT_HEIGHT = Mm(297)


class WordPageLayoutMixin:
    """页面与节级写入；段落填充、run 样式和页码域由其他 Mixin 提供。"""

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

    def _apply_header_footer(
        self,
        document: Any,
        template_config: TemplateConfigPackage,
        *,
        logo_bytes: bytes | None,
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
            if logo_bytes is not None:
                run = paragraph.add_run()
                try:
                    run.add_picture(io.BytesIO(logo_bytes), height=Cm(template_config.header.logo_height_cm or 1.0))
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

    def _render_page_decoration(self, document, operation, blocks, template_config, collector):
        ids = operation.block_ids
        if operation.decoration_policy != "replace":
            for block_id in ids:
                record = collector.records[block_id]
                record.disposition = "suppressed"
                record.reason_code = "custom_footer" if operation.decoration_policy == "custom" else "decoration_disabled"
            return
        section = document.sections[-1]
        header = operation.decoration_kind == "header"
        decoration = section.header if header else section.footer
        paragraph = decoration.paragraphs[0] if decoration.paragraphs else decoration.add_paragraph()
        # 同一物理段落被复用时先撤销旧贡献，即使跨 section 链接也不能保留旧 owner。
        collector.replace_decoration(ids, paragraph, operation.decoration_kind)
        paragraph.text = ""
        settings = template_config.header if header else template_config.footer
        font_name = settings.title_font_name if header else settings.font_name
        western = settings.title_western_font_name if header else settings.western_font_name
        complex_font = settings.title_complex_script_font_name if header else settings.complex_script_font_name
        style = template_config.normal.model_copy(update={
            "font_name": template_config.normal.font_name if font_name is None else font_name,
            "western_font_name": self._resolve_decoration_font(western, font_name, template_config.normal.western_font_name),
            "complex_script_font_name": self._resolve_decoration_font(complex_font, font_name, template_config.normal.complex_script_font_name),
        })
        self._fill_paragraph(paragraph, " ".join(blocks[key].text or "" for key in ids).strip(), style,
            terminology=template_config.terminology)

    @staticmethod
    def _resolve_decoration_font(configured: str | None, legacy: str | None, inherited: str | None) -> str | None:
        """字体字段缺失时依次沿用旧单字体和正文；显式空字符串不回退。"""

        if configured is not None:
            return configured
        if legacy is not None:
            return legacy
        return inherited

    def _set_section_columns(self, section: Any, count: int) -> None:
        columns = section._sectPr.find(qn("w:cols"))
        if columns is None:
            columns = OxmlElement("w:cols")
            section._sectPr.append(columns)
        columns.set(qn("w:num"), str(count))
        if count > 1 and columns.get(qn("w:space")) in (None, "0"):
            # 单栏模板的零栏间距不能继承到新创建的双栏节。
            columns.set(qn("w:space"), "720")

