from __future__ import annotations

# app/services/renderer/text_renderer.py: 提供 DocumentIR Word 渲染器的段落与 run 样式 helper。

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from app.conversion.docx_rules.run_fonts import apply_run_fonts
from app.conversion.docx_rules.text_semantics import (
    GREEK_AND_TEXT_COMMANDS,
    collapse_double_escaped_tex_commands,
    compact_math_token_runs,
    contains_inline_markup,
    prepare_text_for_rendering,
)
from app.conversion.docx_rules.terminology import TerminologyReplacer
from app.services.renderer.semantic_text import (
    infer_heading_level,
    infer_list_item_level,
    is_toc_title_text,
    is_list_item_text,
    looks_like_heading_text,
    normalize_formula_text,
    normalize_list_item,
    parse_decimal_list_marker,
    parse_toc_entry_text,
)
from app.services.renderer.template_config import TemplateConfigPackage, TemplateParagraphStyleConfig


MD2WORD_RENDERER_BULLET_NUM_ID_ATTR = "_md2word_renderer_bullet_num_id"
MD2WORD_RENDERER_DECIMAL_NUM_ID_ATTR = "_md2word_renderer_decimal_num_id"
MD2WORD_RENDERER_DECIMAL_NUMBER_ATTR = "_md2word_renderer_decimal_number"
MD2WORD_RENDERER_ROMAN_MATH_FONT_ATTR = "_md2word_renderer_roman_math_font_name"
DEFAULT_MATH_FONT_NAME = "Cambria Math"
CAPTION_NUMBER_PATTERN = r"(?P<number>\d+)(?![A-Za-z0-9]|[.．]\d|[-–—][A-Za-z0-9])"
CAPTION_RE = re.compile(
    r"^(?P<prefix>\s*)(?P<label>图|表|Figure|Table)(?P<spacing>\s*)"
    + CAPTION_NUMBER_PATTERN
    + r"(?P<tail>.*)$",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(
    r"(?P<label>图|表|Figure|Table)(?P<spacing>\s*)" + CAPTION_NUMBER_PATTERN,
    re.IGNORECASE,
)
INLINE_MATH_RE = re.compile(r"\$(?P<dollar>[^$\n]+)\$|\\\((?P<paren>.*?)\\\)")
TRAILING_MATH_BASE_RE = re.compile(
    r"(?is)(?P<prefix>.*?)(?P<base>(?:[A-Za-z0-9]+|<(?:sub|sup)>[A-Za-z0-9]+</(?:sub|sup)>)+)\s*$"
)
SPACED_FORMULA_ALNUM_RE = re.compile(r"\b(?:[A-Za-z0-9]\s+){1,}[A-Za-z0-9]\b")
CaptionBookmarks = Mapping[tuple[str, int], tuple[str, int]]


class _OmmlParser:
    """把当前合同允许的 TeX 子集直接构造成可编辑 OMML。"""

    def __init__(self, source: str, *, roman_font_name: str | None = None) -> None:
        cleaned = collapse_double_escaped_tex_commands(source.strip())
        cleaned = re.sub(r"^<eq>\s*|\s*</eq>$", "", cleaned, flags=re.IGNORECASE)
        if cleaned.startswith(r"\(") and cleaned.endswith(r"\)"):
            cleaned = cleaned[2:-2]
        compacted = SPACED_FORMULA_ALNUM_RE.sub(lambda match: "".join(match.group(0).split()), cleaned.replace("$", ""))
        self.source = compact_math_token_runs(compacted)
        self.position = 0
        self.roman_font_name = roman_font_name

    def parse(self) -> Any | None:
        try:
            children = self._parse_sequence()
            if self.position != len(self.source) or not children:
                return None
        except ValueError:
            return None
        math = OxmlElement("m:oMath")
        for child in children:
            math.append(child)
        return math

    def _parse_sequence(self, *, stop_at_brace: bool = False) -> list[Any]:
        children: list[Any] = []
        text: list[str] = []

        def flush_text() -> None:
            if text:
                children.extend(self._plain_math_runs("".join(text)))
                text.clear()

        while self.position < len(self.source):
            char = self.source[self.position]
            if char.isspace():
                next_position = self.position
                while next_position < len(self.source) and self.source[next_position].isspace():
                    next_position += 1
                if next_position < len(self.source) and self.source[next_position] in {"^", "_"}:
                    self.position = next_position
                    continue
            if char == "}":
                if not stop_at_brace:
                    raise ValueError("出现意外的右花括号")
                flush_text()
                self.position += 1
                return children
            if char == "{":
                flush_text()
                self.position += 1
                children.extend(self._parse_sequence(stop_at_brace=True))
                continue
            if char == "\\":
                flush_text()
                command_children = self._parse_command()
                children.extend(command_children if isinstance(command_children, list) else [command_children])
                continue
            if char in {"^", "_"}:
                flush_text()
                if not children:
                    raise ValueError("上下标缺少基底")
                self.position += 1
                argument = self._parse_argument()
                children.append(self._script(char, children.pop(), argument))
                continue
            text.append(char)
            self.position += 1

        if stop_at_brace:
            raise ValueError("花括号未闭合")
        flush_text()
        return children

    def _parse_command(self) -> Any:
        self.position += 1
        if self.position < len(self.source) and self.source[self.position] == ",":
            self.position += 1
            return self._math_run("\u2009")
        start = self.position
        while self.position < len(self.source) and self.source[self.position].isalpha():
            self.position += 1
        command = self.source[start : self.position]
        if not command:
            raise ValueError("TeX 命令为空")
        self._skip_spaces()
        if command in {"frac", "dfrac", "tfrac"}:
            numerator = self._parse_required_group()
            self._skip_spaces()
            denominator = self._parse_required_group()
            fraction = OxmlElement("m:f")
            num = OxmlElement("m:num")
            den = OxmlElement("m:den")
            for child in numerator:
                num.append(child)
            for child in denominator:
                den.append(child)
            fraction.extend((num, den))
            return fraction
        if command in {"mathrm", "mathsf", "text"}:
            group = self._parse_required_group()
            value = "".join(node.find(qn("m:t")).text or "" for node in group if node.tag == qn("m:r"))
            if len(group) != 1 or not value:
                self._apply_roman_style(group)
                wrapper = OxmlElement("m:box")
                element = OxmlElement("m:e")
                for child in group:
                    element.append(child)
                wrapper.append(element)
                return wrapper
            run = self._math_run(value)
            self._apply_roman_style([run])
            return run
        if command == "sqrt":
            degree_children = self._parse_optional_bracket_group()
            group = self._parse_required_group()
            radical = OxmlElement("m:rad")
            if not degree_children:
                properties = OxmlElement("m:radPr")
                degree_hidden = OxmlElement("m:degHide")
                degree_hidden.set(qn("m:val"), "1")
                properties.append(degree_hidden)
                radical.append(properties)
            degree = OxmlElement("m:deg")
            for child in degree_children:
                degree.append(child)
            element = OxmlElement("m:e")
            for child in group:
                element.append(child)
            radical.extend((degree, element))
            return radical
        if command == "overline":
            group = self._parse_required_group()
            bar = OxmlElement("m:bar")
            properties = OxmlElement("m:barPr")
            position = OxmlElement("m:pos")
            position.set(qn("m:val"), "top")
            properties.append(position)
            element = OxmlElement("m:e")
            for child in group:
                element.append(child)
            bar.extend((properties, element))
            return bar
        if command in {"mathbf", "boldsymbol", "mathit"}:
            group = self._parse_required_group()
            self._apply_math_style(group, "i" if command == "mathit" else "b")
            if len(group) == 1:
                return group[0]
            wrapper = OxmlElement("m:box")
            element = OxmlElement("m:e")
            for child in group:
                element.append(child)
            wrapper.append(element)
            return wrapper
        if command == "boxed":
            group = self._parse_required_group()
            border_box = OxmlElement("m:borderBox")
            element = OxmlElement("m:e")
            for child in group:
                element.append(child)
            border_box.append(element)
            return border_box
        if command in {"left", "right"}:
            return self._math_run("")
        if command == "tag":
            group = self._parse_required_group()
            if not any((node.text or "").strip() for child in group for node in child.iter(qn("m:t"))):
                raise ValueError("公式编号不能为空")
            # OMML 没有 TeX tag 的等价布局；直接追加可见序列，保留参数内已解析的复杂数学节点。
            return [self._upright_math_run("("), *group, self._upright_math_run(")")]
        symbol = GREEK_AND_TEXT_COMMANDS.get(command)
        if symbol is None:
            raise ValueError(f"不支持的 TeX 命令: {command}")
        run = self._math_run(symbol)
        if all(self._is_upright_math_character(char) for char in symbol):
            self._apply_roman_style([run])
        return run

    def _parse_required_group(self) -> list[Any]:
        self._skip_spaces()
        if self.position >= len(self.source) or self.source[self.position] != "{":
            raise ValueError("缺少必需的 TeX 参数组")
        self.position += 1
        return self._parse_sequence(stop_at_brace=True)

    def _parse_optional_bracket_group(self) -> list[Any]:
        self._skip_spaces()
        if self.position >= len(self.source) or self.source[self.position] != "[":
            return []
        end = self.source.find("]", self.position + 1)
        if end < 0:
            raise ValueError("根指数方括号未闭合")
        parser = _OmmlParser(
            self.source[self.position + 1 : end],
            roman_font_name=self.roman_font_name,
        )
        children = parser._parse_sequence()
        if parser.position != len(parser.source) or not children:
            raise ValueError("根指数无效")
        self.position = end + 1
        self._skip_spaces()
        return children

    def _parse_argument(self) -> list[Any]:
        self._skip_spaces()
        if self.position >= len(self.source):
            raise ValueError("缺少上下标参数")
        if self.source[self.position] == "{":
            self.position += 1
            return self._compact_plain_script_argument(self._parse_sequence(stop_at_brace=True))
        if self.source[self.position] == "\\":
            command_children = self._parse_command()
            return command_children if isinstance(command_children, list) else [command_children]

        value = self.source[self.position]
        self.position += 1
        return self._plain_math_runs(value)

    def _compact_plain_script_argument(self, argument: list[Any]) -> list[Any]:
        values: list[str] = []
        for node in argument:
            if node.tag != qn("m:r"):
                return argument
            value = node.find(qn("m:t"))
            if value is None:
                return argument
            values.append(value.text or "")
        combined = "".join(values)
        if not re.fullmatch(r"[A-Za-z0-9\s]+", combined):
            return argument
        return self._plain_math_runs("".join(combined.split()))

    def _skip_spaces(self) -> None:
        while self.position < len(self.source) and self.source[self.position].isspace():
            self.position += 1

    def _script(self, marker: str, base: Any, argument: list[Any]) -> Any:
        script = OxmlElement("m:sSup" if marker == "^" else "m:sSub")
        base_element = OxmlElement("m:e")
        base_element.append(base)
        argument_element = OxmlElement("m:sup" if marker == "^" else "m:sub")
        for child in argument:
            argument_element.append(child)
        script.extend((base_element, argument_element))
        return script

    @staticmethod
    def _apply_math_style(group: list[Any], value: str) -> None:
        for child in group:
            for run in child.iter(qn("m:r")):
                properties = run.find(qn("m:rPr"))
                if properties is None:
                    properties = OxmlElement("m:rPr")
                    run.insert(0, properties)
                style = properties.find(qn("m:sty"))
                if style is None:
                    style = OxmlElement("m:sty")
                    properties.append(style)
                style.set(qn("m:val"), value)
                word_properties = run.find(qn("w:rPr"))
                fonts = word_properties.find(qn("w:rFonts")) if word_properties is not None else None
                if fonts is not None:
                    word_properties.remove(fonts)
                if word_properties is not None and len(word_properties) == 0 and not word_properties.attrib:
                    run.remove(word_properties)

    def _apply_roman_style(self, group: list[Any]) -> None:
        """按当前输出 settings 的数学字体，为显式直立命令补齐 WPS 所需属性。"""

        if not self.roman_font_name:
            return
        for child in group:
            for run in child.iter(qn("m:r")):
                math_properties = run.find(qn("m:rPr"))
                style = math_properties.find(qn("m:sty")) if math_properties is not None else None
                if style is not None and style.get(qn("m:val")) in {"b", "i"}:
                    continue
                if math_properties is None:
                    math_properties = OxmlElement("m:rPr")
                    run.insert(0, math_properties)
                if style is None:
                    style = OxmlElement("m:sty")
                    math_properties.append(style)
                style.set(qn("m:val"), "p")
                properties = run.find(qn("w:rPr"))
                if properties is None:
                    properties = OxmlElement("w:rPr")
                    run.insert(run.index(math_properties) + 1, properties)
                fonts = properties.find(qn("w:rFonts"))
                if fonts is None:
                    fonts = OxmlElement("w:rFonts")
                    properties.insert(0, fonts)
                fonts.set(qn("w:ascii"), self.roman_font_name)
                fonts.set(qn("w:hAnsi"), self.roman_font_name)

    def _plain_math_runs(self, text: str) -> list[Any]:
        """按数学语义拆分变量与直立字符，避免 WPS 隐藏数字和运算符。"""

        if not text:
            return [self._math_run("")]
        runs: list[Any] = []
        start = 0
        upright = self._is_upright_math_character(text[0])
        for index, char in enumerate(text[1:], start=1):
            next_upright = self._is_upright_math_character(char)
            if next_upright == upright:
                continue
            token = text[start:index]
            runs.append(self._upright_math_run(token) if upright else self._math_run(token))
            start = index
            upright = next_upright
        token = text[start:]
        runs.append(self._upright_math_run(token) if upright else self._math_run(token))
        return runs

    def _upright_math_run(self, text: str) -> Any:
        run = self._math_run(text)
        self._apply_roman_style([run])
        return run

    @staticmethod
    def _is_upright_math_character(char: str) -> bool:
        """数字、运算符和标点使用直立数学样式，字母变量保留客户端数学斜体。"""

        return not char.isalpha() and not unicodedata.category(char).startswith("M")

    @staticmethod
    def _math_run(text: str) -> Any:
        # 基础数学 run 继承当前输出 mathFont 和客户端默认数学样式；
        # WPS 会隐藏仅强制 m:sty=p 的无字体 run。
        run = OxmlElement("m:r")
        value = OxmlElement("m:t")
        value.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        value.text = text
        run.append(value)
        return run


def _parse_mixed_math_segments(
    text: str,
    *,
    roman_font_name: str | None = None,
) -> list[tuple[str, Any]] | None:
    """按 renderer 实际规则拆分普通文本与可渲染 OMML，供写入和证据共用。"""

    source = re.sub(r"^\s*<(?:td|th)\b[^>]*>", "", text, flags=re.IGNORECASE)
    source = re.sub(r"</(?:td|th)>\s*$", "", source, flags=re.IGNORECASE)
    if any(command in source for command in (r"\frac", r"\dfrac", r"\tfrac")):
        math = _OmmlParser(source, roman_font_name=roman_font_name).parse()
        return [("math", math)] if math is not None else None

    matches = list(INLINE_MATH_RE.finditer(source))
    if not matches:
        return None
    segments: list[tuple[str, Any]] = []
    position = 0
    for match in matches:
        plain_text = source[position : match.start()]
        expression = match.group("dollar") if match.group("dollar") is not None else match.group("paren")
        stripped_expression = (expression or "").lstrip()
        if stripped_expression.startswith(("_", "^")):
            base_match = TRAILING_MATH_BASE_RE.search(plain_text)
            if base_match is not None:
                base = BeautifulSoup(base_match.group("base"), "html.parser").get_text()
                plain_text = base_match.group("prefix")
                expression = f"{base}{stripped_expression}"
        if plain_text:
            segments.append(("text", plain_text))
        math = _OmmlParser(expression or "", roman_font_name=roman_font_name).parse()
        segments.append(("math", math) if math is not None else ("text", match.group(0)))
        position = match.end()
    if source[position:]:
        segments.append(("text", source[position:]))
    return segments


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
        reference_bookmarks: CaptionBookmarks | None = None,
    ) -> None:
        """写入段落文本；支持 MinerU 常见的内联 HTML 标记。"""

        self._apply_named_style(paragraph, word_style_name or style.word_style_name)
        self._apply_paragraph_style(paragraph, style)
        if self._render_mixed_math(paragraph, text, style, terminology, reference_bookmarks):
            return
        normalized_text = self._prepare_text_for_rendering(text, terminology)
        if self._looks_like_inline_markup(normalized_text):
            if prefix:
                self._add_text_run(paragraph, prefix, style)
            self._render_inline_html(paragraph, normalized_text, style, reference_bookmarks=reference_bookmarks)
            return

        self._add_text_run(paragraph, f"{prefix}{normalized_text}", style, reference_bookmarks=reference_bookmarks)

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
            text,
            style,
            word_style_name=template_config.heading_word_style_name_for_level(level),
            terminology=template_config.terminology,
        )

    def _fill_list_paragraph(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
        *,
        reference_bookmarks: CaptionBookmarks | None = None,
    ) -> None:
        decimal_item = parse_decimal_list_marker(text)
        level = infer_list_item_level(text)
        self._fill_paragraph(
            paragraph,
            normalize_list_item(text),
            template_config.normal,
            terminology=template_config.terminology,
            reference_bookmarks=reference_bookmarks,
        )
        if decimal_item is None:
            self._apply_bullet_numbering(paragraph, level=level)
        else:
            self._apply_decimal_numbering(paragraph, source_number=decimal_item[0])
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
        *,
        reference_bookmarks: CaptionBookmarks | None = None,
        allow_heading_inference: bool = True,
        allow_toc_inference: bool = True,
    ) -> None:
        if allow_toc_inference and is_toc_title_text(text):
            self._fill_paragraph(
                paragraph,
                text,
                template_config.toc_title,
                terminology=template_config.terminology,
                reference_bookmarks=reference_bookmarks,
            )
            return
        if allow_toc_inference and self._fill_toc_entry_if_needed(paragraph, text, template_config):
            return
        if is_list_item_text(text):
            self._fill_list_paragraph(
                paragraph,
                text,
                template_config,
                reference_bookmarks=reference_bookmarks,
            )
            return
        if allow_heading_inference and looks_like_heading_text(text):
            self._fill_heading_paragraph(paragraph, text, infer_heading_level(text), template_config)
            return
        self._fill_paragraph(
            paragraph,
            text,
            template_config.normal,
            terminology=template_config.terminology,
            reference_bookmarks=reference_bookmarks,
        )

    def _fill_auto_list_item_paragraph(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
        *,
        reference_bookmarks: CaptionBookmarks | None = None,
        allow_toc_inference: bool = True,
    ) -> None:
        if allow_toc_inference and is_toc_title_text(text):
            self._fill_paragraph(
                paragraph,
                text,
                template_config.toc_title,
                terminology=template_config.terminology,
                reference_bookmarks=reference_bookmarks,
            )
            return
        if allow_toc_inference and self._fill_toc_entry_if_needed(paragraph, text, template_config):
            return
        self._fill_list_paragraph(
            paragraph,
            text,
            template_config,
            reference_bookmarks=reference_bookmarks,
        )

    def _fill_toc_entry_if_needed(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
    ) -> bool:
        parsed = parse_toc_entry_text(text)
        if parsed is None:
            return False

        title, _page_number = parsed
        toc_style = template_config.toc_style_for_level(infer_heading_level(title))
        self._configure_toc_styles(paragraph.part.styles, template_config)
        self._apply_named_style(paragraph, toc_style.word_style_name)
        self._apply_paragraph_style(paragraph, toc_style)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Pt(0)
        self._add_complex_field(paragraph, r' TOC \o "1-3" \h \z \u ', "更新目录", toc_style)
        return True

    def _fill_toc_anchor(
        self,
        paragraph: Any,
        headings: tuple[tuple[int, str], ...],
        template_config: TemplateConfigPackage,
    ) -> None:
        """写入一个原生 TOC 字段，并用最终 IR 标题提供无源页码的可见缓存。"""

        toc_style = template_config.toc_style_for_level(1)
        self._configure_toc_styles(paragraph.part.styles, template_config)
        self._apply_named_style(paragraph, toc_style.word_style_name)
        self._apply_paragraph_style(paragraph, toc_style)
        cache_lines = ["更新目录（在 Word/WPS 中更新字段以生成页码）"]
        cache_lines.extend(f"{'    ' * max(level - 1, 0)}{text}" for level, text in headings if text.strip())
        self._add_complex_field(paragraph, r' TOC \o "1-3" \h \z \u ', "\n".join(cache_lines), toc_style)

    def _fill_formula_paragraph(
        self,
        paragraph: Any,
        text: str,
        template_config: TemplateConfigPackage,
    ) -> None:
        self._apply_named_style(paragraph, template_config.normal.word_style_name)
        self._apply_paragraph_style(paragraph, template_config.normal)
        math = _OmmlParser(text, roman_font_name=self._roman_math_font_name(paragraph)).parse()
        if math is not None:
            paragraph._p.append(math)
            return
        self._fill_paragraph(paragraph, text, template_config.normal, terminology=template_config.terminology)

    def _parse_caption_text(self, text: str) -> tuple[str, str, str, int, str] | None:
        match = CAPTION_RE.match(text or "")
        if match is None:
            return None
        return (
            match.group("prefix"),
            match.group("label"),
            match.group("spacing"),
            int(match.group("number")),
            match.group("tail"),
        )

    def _fill_caption_paragraph(
        self,
        paragraph: Any,
        text: str,
        style: TemplateParagraphStyleConfig,
        *,
        terminology: TerminologyReplacer | None = None,
        caption_bookmarks: CaptionBookmarks | None = None,
    ) -> bool:
        parsed = self._parse_caption_text(text)
        tail_is_prepared = False
        if parsed is None:
            parsed = self._parse_caption_text(self._prepare_text_for_rendering(text, terminology))
            tail_is_prepared = parsed is not None
        if parsed is None:
            return False

        prefix, label, spacing, source_number, tail = parsed
        kind = "figure" if label.lower() == "figure" or label == "图" else "table"
        self._apply_named_style(paragraph, style.word_style_name)
        self._apply_paragraph_style(paragraph, style)
        caption_label = (
            f"{prefix}{label}{spacing}"
            if tail_is_prepared
            else f"{self._prepare_text_for_rendering(prefix + label, terminology)}{spacing}"
        )
        self._add_text_run(paragraph, caption_label, style)
        bookmark = caption_bookmarks.get((kind, source_number)) if caption_bookmarks else None
        if bookmark is not None:
            bookmark_start = OxmlElement("w:bookmarkStart")
            bookmark_start.set(qn("w:id"), str(bookmark[1]))
            bookmark_start.set(qn("w:name"), bookmark[0])
            paragraph._p.append(bookmark_start)
        sequence_name = label if label in {"图", "表"} else ("Figure" if kind == "figure" else "Table")
        # 每个简单整数题注都从源编号重置，避免客户端更新字段时按出现顺序重排跳号或重复编号。
        self._add_complex_field(
            paragraph,
            f" SEQ {sequence_name} \\r {source_number} \\* ARABIC ",
            str(source_number),
            style,
        )
        if bookmark is not None:
            bookmark_end = OxmlElement("w:bookmarkEnd")
            bookmark_end.set(qn("w:id"), str(bookmark[1]))
            paragraph._p.append(bookmark_end)
        if not tail_is_prepared:
            if self._render_mixed_math(paragraph, tail, style, terminology, None):
                return True
            self._add_prepared_text(paragraph, tail, style, terminology, None)
            return True
        prepared_tail = tail
        if self._looks_like_inline_markup(prepared_tail):
            self._render_inline_html(paragraph, prepared_tail, style)
        else:
            self._add_text_run(paragraph, prepared_tail, style)
        return True

    def _render_mixed_math(
        self,
        paragraph: Any,
        text: str,
        style: TemplateParagraphStyleConfig,
        terminology: TerminologyReplacer | None,
        reference_bookmarks: CaptionBookmarks | None,
    ) -> bool:
        segments = _parse_mixed_math_segments(
            text,
            roman_font_name=self._roman_math_font_name(paragraph),
        )
        if segments is None:
            return False
        for kind, value in segments:
            if kind == "math":
                paragraph._p.append(value)
                continue
            self._add_prepared_text(paragraph, value, style, terminology, reference_bookmarks)
        return True

    def _add_prepared_text(
        self,
        paragraph: Any,
        text: str,
        style: TemplateParagraphStyleConfig,
        terminology: TerminologyReplacer | None,
        reference_bookmarks: CaptionBookmarks | None,
    ) -> None:
        if not text:
            return
        leading_space = " " if text[0].isspace() else ""
        trailing_space = " " if text[-1].isspace() else ""
        prepared = self._prepare_text_for_rendering(text, terminology)
        prepared = f"{leading_space}{prepared}{trailing_space}"
        if self._looks_like_inline_markup(prepared):
            self._render_inline_html(paragraph, prepared, style, reference_bookmarks=reference_bookmarks)
            return
        self._add_text_run(paragraph, prepared, style, reference_bookmarks=reference_bookmarks)

    def _add_complex_field(
        self,
        paragraph: Any,
        instruction: str,
        result: str,
        style: TemplateParagraphStyleConfig,
    ) -> Any:
        begin_run = paragraph.add_run()
        begin = OxmlElement("w:fldChar")
        begin.set(qn("w:fldCharType"), "begin")
        begin_run._r.append(begin)

        instruction_run = paragraph.add_run()
        instruction_text = OxmlElement("w:instrText")
        instruction_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        instruction_text.text = instruction
        instruction_run._r.append(instruction_text)

        separate_run = paragraph.add_run()
        separate = OxmlElement("w:fldChar")
        separate.set(qn("w:fldCharType"), "separate")
        separate_run._r.append(separate)

        result_run = paragraph.add_run(result)
        self._apply_run_style(result_run, style)

        end_run = paragraph.add_run()
        end = OxmlElement("w:fldChar")
        end.set(qn("w:fldCharType"), "end")
        end_run._r.append(end)
        return result_run

    def _prepare_text_for_rendering(self, text: str, terminology: TerminologyReplacer | None) -> str:
        """归一化公式片段，并应用本次渲染的术语标记。"""

        return prepare_text_for_rendering(text, terminology)

    def _looks_like_inline_markup(self, text: str) -> bool:
        return contains_inline_markup(text)

    def _render_inline_html(
        self,
        paragraph: Any,
        text_or_html: str,
        style: TemplateParagraphStyleConfig,
        *,
        reference_bookmarks: CaptionBookmarks | None = None,
    ) -> None:
        """将安全的内联 HTML 转为多个 Word run，保留下标、上标、粗斜体和换行。"""

        soup = BeautifulSoup(f"<root>{text_or_html}</root>", "html.parser")
        root = soup.find("root")
        if root is None:
            self._add_text_run(paragraph, text_or_html, style)
            return
        self._render_inline_children(root, paragraph, style, reference_bookmarks=reference_bookmarks)

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
        reference_bookmarks: CaptionBookmarks | None = None,
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
                    reference_bookmarks=reference_bookmarks,
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
                reference_bookmarks=reference_bookmarks,
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
        reference_bookmarks: CaptionBookmarks | None = None,
    ) -> None:
        if not text:
            return
        if reference_bookmarks:
            position = 0
            for match in REFERENCE_RE.finditer(text):
                label = match.group("label")
                kind = "figure" if label.lower() == "figure" or label == "图" else "table"
                bookmark = reference_bookmarks.get((kind, int(match.group("number"))))
                if bookmark is None:
                    continue
                self._add_text_run(
                    paragraph,
                    text[position : match.start()] + label + match.group("spacing"),
                    style,
                    bold=bold,
                    italic=italic,
                    subscript=subscript,
                    superscript=superscript,
                )
                field_run = self._add_complex_field(paragraph, f" REF {bookmark[0]} \\h ", match.group("number"), style)
                field_run.bold = bold or None
                field_run.italic = italic or None
                field_run.font.subscript = subscript or None
                field_run.font.superscript = superscript or None
                position = match.end()
            if position:
                self._add_text_run(
                    paragraph,
                    text[position:],
                    style,
                    bold=bold,
                    italic=italic,
                    subscript=subscript,
                    superscript=superscript,
                )
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

    def _configure_toc_styles(self, styles: Any, template_config: TemplateConfigPackage) -> None:
        for level in range(1, 4):
            style_id = f"TOC{level}"
            word_style = next((style for style in styles if style.style_id == style_id), None)
            if word_style is None:
                word_style = styles.add_style(f"TOC {level}", WD_STYLE_TYPE.PARAGRAPH, builtin=True)

            config = template_config.toc_style_for_level(level)
            if config.word_style_name and config.word_style_name != word_style.name:
                try:
                    word_style.base_style = styles[config.word_style_name]
                except KeyError:
                    pass
            apply_run_fonts(
                word_style,
                font_name=config.font_name,
                western_font_name=config.western_font_name,
                complex_script_font_name=config.complex_script_font_name,
            )
            if config.font_size is not None:
                word_style.font.size = Pt(config.font_size)
            if config.bold is not None:
                word_style.font.bold = config.bold
            if config.italic is not None:
                word_style.font.italic = config.italic
            if config.color:
                word_style.font.color.rgb = self._parse_color(config.color)

            paragraph_format = word_style.paragraph_format
            if config.alignment:
                paragraph_format.alignment = self._parse_alignment(config.alignment)
            if config.space_before is not None:
                paragraph_format.space_before = Pt(config.space_before)
            if config.space_after is not None:
                paragraph_format.space_after = Pt(config.space_after)
            if config.line_spacing is not None:
                paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
                paragraph_format.line_spacing = config.line_spacing
            if config.first_line_indent_pt is not None:
                paragraph_format.first_line_indent = Pt(config.first_line_indent_pt)
            if config.left_indent_pt is not None:
                paragraph_format.left_indent = Pt(config.left_indent_pt)
            if config.right_indent_pt is not None:
                paragraph_format.right_indent = Pt(config.right_indent_pt)

    def _apply_run_style(self, run: Any, style: TemplateParagraphStyleConfig) -> None:
        apply_run_fonts(
            run,
            font_name=style.font_name,
            western_font_name=style.western_font_name,
            complex_script_font_name=style.complex_script_font_name,
        )
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

    def _apply_decimal_numbering(self, paragraph: Any, *, source_number: int) -> None:
        num_id = self._ensure_decimal_numbering(paragraph, source_number=source_number)
        paragraph_properties = paragraph._p.get_or_add_pPr()
        num_properties = paragraph_properties.find(qn("w:numPr"))
        if num_properties is None:
            num_properties = OxmlElement("w:numPr")
            paragraph_properties.append(num_properties)

        self._set_numbering_child_value(num_properties, "w:ilvl", "0")
        self._set_numbering_child_value(num_properties, "w:numId", str(num_id))

    def _ensure_decimal_numbering(self, paragraph: Any, *, source_number: int) -> str:
        """连续序号复用 numId；重启、跳号或中断时按源序号创建新编号。"""

        part = paragraph.part
        cached_num_id = getattr(part, MD2WORD_RENDERER_DECIMAL_NUM_ID_ATTR, None)
        previous_number = getattr(part, MD2WORD_RENDERER_DECIMAL_NUMBER_ATTR, None)
        if (
            cached_num_id is not None
            and previous_number is not None
            and source_number == previous_number + 1
            and self._previous_paragraph_uses_num_id(paragraph, str(cached_num_id))
        ):
            setattr(part, MD2WORD_RENDERER_DECIMAL_NUMBER_ATTR, source_number)
            return str(cached_num_id)

        numbering = part.numbering_part.element
        abstract_num_id = str(self._next_numbering_id(numbering, "w:abstractNum", "w:abstractNumId"))
        num_id = str(self._next_numbering_id(numbering, "w:num", "w:numId"))
        abstract_num = OxmlElement("w:abstractNum")
        abstract_num.set(qn("w:abstractNumId"), abstract_num_id)
        multi_level_type = OxmlElement("w:multiLevelType")
        multi_level_type.set(qn("w:val"), "singleLevel")
        abstract_num.append(multi_level_type)

        level = OxmlElement("w:lvl")
        level.set(qn("w:ilvl"), "0")
        for tag, value in (
            ("w:start", str(source_number)),
            ("w:numFmt", "decimal"),
            ("w:suff", "space"),
            ("w:lvlText", "%1."),
            ("w:lvlJc", "left"),
        ):
            child = OxmlElement(tag)
            child.set(qn("w:val"), value)
            level.append(child)
        paragraph_properties = OxmlElement("w:pPr")
        indent = OxmlElement("w:ind")
        indent.set(qn("w:left"), "240")
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
        setattr(part, MD2WORD_RENDERER_DECIMAL_NUM_ID_ATTR, num_id)
        setattr(part, MD2WORD_RENDERER_DECIMAL_NUMBER_ATTR, source_number)
        return num_id

    def _previous_paragraph_uses_num_id(self, paragraph: Any, num_id: str) -> bool:
        previous = paragraph._p.getprevious()
        if previous is None or previous.tag != qn("w:p"):
            return False
        paragraph_properties = previous.find(qn("w:pPr"))
        if paragraph_properties is None:
            return False
        num_properties = paragraph_properties.find(qn("w:numPr"))
        if num_properties is None:
            return False
        previous_num_id = num_properties.find(qn("w:numId"))
        return previous_num_id is not None and previous_num_id.get(qn("w:val")) == num_id

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

    def _bind_math_font_context(self, document: Any) -> None:
        """保留模板数学字体；缺失时只补当前输出默认值并绑定到文档 part。"""

        math_properties = document.settings.element.find(qn("m:mathPr"))
        if math_properties is None:
            math_properties = OxmlElement("m:mathPr")
            document.settings.element.append(math_properties)
        math_font = math_properties.find(qn("m:mathFont"))
        if math_font is None:
            math_font = OxmlElement("m:mathFont")
            math_properties.insert(0, math_font)
        value = (math_font.get(qn("m:val")) or "").strip() if math_font is not None else ""
        if not value:
            value = DEFAULT_MATH_FONT_NAME
            math_font.set(qn("m:val"), value)
        setattr(document.part, MD2WORD_RENDERER_ROMAN_MATH_FONT_ATTR, value)

    @staticmethod
    def _roman_math_font_name(paragraph: Any) -> str | None:
        return getattr(paragraph.part, MD2WORD_RENDERER_ROMAN_MATH_FONT_ATTR, None)
