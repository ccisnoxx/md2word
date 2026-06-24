from __future__ import annotations

# app/services/renderer/text_renderer.py: 提供 DocumentIR Word 渲染器的段落与 run 样式 helper。

from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.conversion.docx_rules.terminology import TerminologyReplacer
from app.services.renderer.semantic_text import (
    infer_heading_level,
    infer_list_item_level,
    is_toc_title_text,
    is_list_item_text,
    looks_like_heading_text,
    normalize_formula_text,
    normalize_list_item,
    parse_toc_entry_text,
)
from app.services.renderer.template_config import TemplateConfigPackage, TemplateParagraphStyleConfig


MD2WORD_RENDERER_BULLET_NUM_ID_ATTR = "_md2word_renderer_bullet_num_id"


class WordTextRendererMixin:
    """封装段落、run 和基础样式写入逻辑，供 Word renderer 门面复用。"""

    def _fill_paragraph(
        self,
        paragraph: Any,
        text: str,
        style: TemplateParagraphStyleConfig,
        *,
        prefix: str = "",
        word_style_name: str | None = None,
        terminology: TerminologyReplacer | None = None,
    ) -> None:
        """写入段落文本；支持 MinerU 常见的内联 HTML 标记。"""

        self._apply_named_style(paragraph, word_style_name or style.word_style_name)
        self._apply_paragraph_style(paragraph, style)
        normalized_text = self._prepare_text_for_rendering(text, terminology)
        if self._looks_like_inline_markup(normalized_text):
            if prefix:
                self._add_text_run(paragraph, prefix, style)
            self._render_inline_html(paragraph, normalized_text, style)
            return

        run = paragraph.add_run(f"{prefix}{normalized_text}")
        self._apply_run_style(run, style)

    def _fill_heading_paragraph(
        self,
        paragraph: Any,
        text: str,
        level: int | None,
        template_config: TemplateConfigPackage,
    ) -> None:
        style = template_config.heading_style_for_level(level)
        self._fill_paragraph(
            paragraph,
            normalize_formula_text(text),
            style,
            word_style_name=template_config.heading_word_style_name_for_level(level),
            terminology=template_config.terminology,
        )

    def _fill_list_paragraph(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
    ) -> None:
        level = infer_list_item_level(text)
        self._fill_paragraph(
            paragraph,
            normalize_list_item(text),
            template_config.normal,
            terminology=template_config.terminology,
        )
        self._apply_bullet_numbering(paragraph, level=level)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph_format = paragraph.paragraph_format
        paragraph_format.space_before = Pt(0)
        paragraph_format.space_after = Pt(0)
        paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        paragraph_format.line_spacing = 1.0
        paragraph_format.left_indent = Pt(12 + min(max(level, 0), 1) * 12)
        paragraph_format.first_line_indent = Pt(-9)

    def _fill_auto_list_or_paragraph(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
    ) -> None:
        if is_toc_title_text(text):
            self._fill_paragraph(
                paragraph,
                text,
                template_config.toc_title,
                terminology=template_config.terminology,
            )
            return
        if self._fill_toc_entry_if_needed(paragraph, text, template_config):
            return
        if is_list_item_text(text):
            self._fill_list_paragraph(paragraph, text, template_config)
            return
        if looks_like_heading_text(text):
            self._fill_heading_paragraph(paragraph, text, infer_heading_level(text), template_config)
            return
        self._fill_paragraph(paragraph, text, template_config.normal, terminology=template_config.terminology)

    def _fill_auto_list_item_paragraph(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
    ) -> None:
        if is_toc_title_text(text):
            self._fill_paragraph(
                paragraph,
                text,
                template_config.toc_title,
                terminology=template_config.terminology,
            )
            return
        if self._fill_toc_entry_if_needed(paragraph, text, template_config):
            return
        self._fill_list_paragraph(paragraph, text, template_config)

    def _fill_toc_entry_if_needed(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
    ) -> bool:
        parsed = parse_toc_entry_text(text)
        if parsed is None:
            return False

        title, page_number = parsed
        toc_style = template_config.toc_style_for_level(infer_heading_level(title))
        self._apply_named_style(paragraph, toc_style.word_style_name)
        self._apply_paragraph_style(paragraph, toc_style)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Pt(0)
        paragraph.paragraph_format.tab_stops.add_tab_stop(Cm(15), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        self._render_inline_html(paragraph, self._prepare_text_for_rendering(title, template_config.terminology), toc_style)
        paragraph.add_run("\t")
        page_run = paragraph.add_run(page_number)
        self._apply_run_style(page_run, toc_style)
        return True

    def _fill_formula_paragraph(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
    ) -> None:
        self._fill_paragraph(paragraph, text, template_config.normal, terminology=template_config.terminology)

    def _prepare_text_for_rendering(self, text: str, terminology: TerminologyReplacer | None) -> str:
        """Normalize formula fragments and apply per-render terminology markup."""

        normalized_text = normalize_formula_text(text)
        if terminology is None:
            return normalized_text
        if self._looks_like_inline_markup(normalized_text):
            return terminology.replace_html(normalized_text) or normalized_text
        return terminology.replace_text(normalized_text)

    def _looks_like_inline_markup(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            token in lowered
            for token in ("<sub", "<sup", "<br", "<b", "<strong", "<i", "<em", "<td", "<th", "<span", "<p")
        )

    def _render_inline_html(
        self,
        paragraph: Any,
        text_or_html: str,
        style: TemplateParagraphStyleConfig,
    ) -> None:
        """将安全的内联 HTML 转为多个 Word run，保留下标、上标、粗斜体和换行。"""

        soup = BeautifulSoup(f"<root>{text_or_html}</root>", "html.parser")
        root = soup.find("root")
        if root is None:
            self._add_text_run(paragraph, text_or_html, style)
            return
        self._render_inline_children(root, paragraph, style)

    def _render_inline_children(
        self,
        parent: Tag,
        paragraph: Any,
        style: TemplateParagraphStyleConfig,
        *,
        bold: bool = False,
        italic: bool = False,
        subscript: bool = False,
        superscript: bool = False,
    ) -> None:
        for child in parent.children:
            if isinstance(child, NavigableString):
                self._add_text_run(
                    paragraph,
                    str(child),
                    style,
                    bold=bold,
                    italic=italic,
                    subscript=subscript,
                    superscript=superscript,
                )
                continue
            if not isinstance(child, Tag):
                continue

            tag_name = child.name.lower()
            if tag_name == "br":
                paragraph.add_run().add_break()
                continue
            self._render_inline_children(
                child,
                paragraph,
                style,
                bold=bold or tag_name in {"b", "strong", "th"},
                italic=italic or tag_name in {"i", "em"},
                subscript=subscript or tag_name == "sub",
                superscript=superscript or tag_name == "sup",
            )

    def _add_text_run(
        self,
        paragraph: Any,
        text: str,
        style: TemplateParagraphStyleConfig,
        *,
        bold: bool = False,
        italic: bool = False,
        subscript: bool = False,
        superscript: bool = False,
    ) -> None:
        if not text:
            return
        run = paragraph.add_run(text)
        self._apply_run_style(run, style)
        if bold:
            run.bold = True
        if italic:
            run.italic = True
        if subscript:
            run.font.subscript = True
        if superscript:
            run.font.superscript = True

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

    def _apply_named_style(self, paragraph: Any, style_name: str | None) -> None:
        if not style_name:
            return
        try:
            paragraph.style = style_name
        except (KeyError, ValueError):
            return

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

    def _apply_bullet_numbering(self, paragraph: Any, *, level: int = 0) -> None:
        normalized_level = min(max(level, 0), 1)
        num_id = self._ensure_bullet_numbering(paragraph)
        paragraph_properties = paragraph._p.get_or_add_pPr()
        num_properties = paragraph_properties.find(qn("w:numPr"))
        if num_properties is None:
            num_properties = OxmlElement("w:numPr")
            paragraph_properties.append(num_properties)

        self._set_numbering_child_value(num_properties, "w:ilvl", str(normalized_level))
        self._set_numbering_child_value(num_properties, "w:numId", str(num_id))

    def _ensure_bullet_numbering(self, paragraph: Any) -> str:
        part = paragraph.part
        cached_num_id = getattr(part, MD2WORD_RENDERER_BULLET_NUM_ID_ATTR, None)
        if cached_num_id is not None:
            return str(cached_num_id)

        numbering = part.numbering_part.element
        abstract_num_id = str(self._next_numbering_id(numbering, "w:abstractNum", "w:abstractNumId"))
        num_id = str(self._next_numbering_id(numbering, "w:num", "w:numId"))

        abstract_num = OxmlElement("w:abstractNum")
        abstract_num.set(qn("w:abstractNumId"), abstract_num_id)
        multi_level_type = OxmlElement("w:multiLevelType")
        multi_level_type.set(qn("w:val"), "hybridMultilevel")
        abstract_num.append(multi_level_type)

        for ilvl, marker, left in ((0, "•", "240"), (1, "–", "480")):
            level = OxmlElement("w:lvl")
            level.set(qn("w:ilvl"), str(ilvl))
            for tag, value in (
                ("w:start", "1"),
                ("w:numFmt", "bullet"),
                ("w:lvlText", marker),
                ("w:lvlJc", "left"),
            ):
                child = OxmlElement(tag)
                child.set(qn("w:val"), value)
                level.append(child)
            paragraph_properties = OxmlElement("w:pPr")
            indent = OxmlElement("w:ind")
            indent.set(qn("w:left"), left)
            indent.set(qn("w:hanging"), "180")
            paragraph_properties.append(indent)
            level.append(paragraph_properties)
            abstract_num.append(level)

        num = OxmlElement("w:num")
        num.set(qn("w:numId"), num_id)
        abstract_num_id_element = OxmlElement("w:abstractNumId")
        abstract_num_id_element.set(qn("w:val"), abstract_num_id)
        num.append(abstract_num_id_element)

        numbering.append(abstract_num)
        numbering.append(num)
        setattr(part, MD2WORD_RENDERER_BULLET_NUM_ID_ATTR, num_id)
        return num_id

    def _next_numbering_id(self, numbering: Any, element_tag: str, attr_name: str) -> int:
        values: list[int] = []
        for element in numbering.findall(qn(element_tag)):
            raw_value = element.get(qn(attr_name))
            if raw_value is not None and raw_value.isdigit():
                values.append(int(raw_value))
        return max(values, default=0) + 1

    def _set_numbering_child_value(self, parent: Any, tag: str, value: str) -> None:
        child = parent.find(qn(tag))
        if child is None:
            child = OxmlElement(tag)
            parent.append(child)
        child.set(qn("w:val"), value)
