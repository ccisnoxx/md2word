from __future__ import annotations

# app/services/renderer/text_renderer.py: 提供 DocumentIR Word 渲染器的段落与 run 样式 helper。

from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from app.services.renderer.template_config import TemplateParagraphStyleConfig


class WordTextRendererMixin:
    """封装段落、run 和基础样式写入逻辑，供 Word renderer 门面复用。"""

    def _fill_paragraph(
        self,
        paragraph: Any,
        text: str,
        style: TemplateParagraphStyleConfig,
        *,
        prefix: str = "",
    ) -> None:
        """写入段落文本；支持 MinerU 常见的内联 HTML 标记。"""

        self._apply_paragraph_style(paragraph, style)
        if self._looks_like_inline_markup(text):
            if prefix:
                self._add_text_run(paragraph, prefix, style)
            self._render_inline_html(paragraph, text, style)
            return

        run = paragraph.add_run(f"{prefix}{text}")
        self._apply_run_style(run, style)

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
