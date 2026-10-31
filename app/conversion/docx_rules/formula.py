"""共享数学边界、有限 TeX 解析和写入前输出投影。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.conversion.docx_rules.text_semantics import (
    GREEK_AND_TEXT_COMMANDS,
    STRUCTURAL_TEX_COMMANDS,
    collapse_double_escaped_tex_commands,
    compact_math_token_runs,
)

FORMULA_REPORT_VERSION = "formula-render/v1"
FORMULA_OUTPUT_VERSION = "formula-output/v1"
FORMULA_FALLBACK_NOTICE = "【公式降级，需复核】"
FORMULA_REASONS = frozenset({"unsupported_command", "invalid_syntax", "unsupported_structure", "unsafe_normalization"})
EQ_MATH_OPEN_RE = re.compile(r"<eq(?:\s[^>]*)?>", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class MathSpan:
    start: int
    end: int
    source: str = field(repr=False)
    expression: str = field(repr=False)
    boundary: str


class FormulaParseError(ValueError):
    """只表达可预期的数学语法失败，不隐藏程序或 XML 错误。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("公式无法按当前数学子集保真解析")


@dataclass(frozen=True, slots=True)
class FormulaRenderResult:
    mode: str
    elements: tuple[Any, ...] = field(repr=False)
    reason: str | None = None

    @property
    def expected_output_sha256(self) -> str:
        return output_sha256(self.elements)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _escaped(text: str, index: int) -> bool:
    count = 0
    while index > 0 and text[index - 1] == "\\":
        count += 1
        index -= 1
    return count % 2 == 1


def _command_end(text: str, start: int) -> int:
    """裸命令仅消费自己的参数与脚本，不吞并相邻自然语言。"""
    match = re.match(r"\\+[A-Za-z]+", text[start:])
    if match is None:
        return start
    end = start + match.end()
    while end < len(text):
        cursor = end
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor < len(text) and text[cursor] in "_^":
            cursor += 1
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
        elif cursor >= len(text) or text[cursor] not in "{[":
            break
        if cursor >= len(text):
            return cursor
        if text[cursor] in "{[":
            opening = text[cursor]
            closing = "}" if opening == "{" else "]"
            depth = 1
            cursor += 1
            while cursor < len(text) and depth:
                if not _escaped(text, cursor):
                    depth += text[cursor] == opening
                    depth -= text[cursor] == closing
                cursor += 1
            end = cursor
            if depth:
                return end
        elif text[cursor] == "\\":
            end = _command_end(text, cursor)
        else:
            end = cursor + 1
    return end


def _scan_delimited_math_spans(text: str) -> tuple[MathSpan, ...]:
    """按原字符串位置识别数学边界；span 包含分隔符并保留原式。"""
    spans: list[MathSpan] = []
    index = 0
    while index < len(text):
        boundary = None
        opening = closing = ""
        eq = EQ_MATH_OPEN_RE.match(text, index)
        if eq:
            opening, closing, boundary = eq.group(0), "</eq>", "eq"
        elif text.startswith(r"\(", index):
            opening, closing, boundary = r"\(", r"\)", "paren"
        elif text.startswith(r"\[", index):
            opening, closing, boundary = r"\[", r"\]", "bracket"
        elif text[index] == "$" and not _escaped(text, index):
            opening = "$$" if text.startswith("$$", index) else "$"
            closing = opening
            boundary = "display_dollar" if opening == "$$" else "dollar"
        if boundary:
            search = index + len(opening)
            end = text.lower().find(closing.lower(), search)
            while end >= 0 and closing.startswith("$") and _escaped(text, end):
                end = text.find(closing, end + 1)
            if end >= 0:
                expression = text[search:end]
                # 相邻金额的 dollar 不能误配为数学；闭合的纯数字仍是明确公式。
                currency = opening == "$" and expression[:1].isdigit() and end + 1 < len(text) and text[end + 1].isdigit()
                if not currency:
                    stop = end + len(closing)
                    spans.append(MathSpan(index, stop, text[index:stop], expression, boundary))
                    index = stop
                    continue
            elif boundary not in {"dollar", "display_dollar"} or (search < len(text) and (text[search].isalpha() or text[search] in "\\_^{")):
                spans.append(MathSpan(index, len(text), text[index:], text[search:], boundary))
                break
        if text[index] == "\\" and (index == 0 or text[index - 1] != "\\"):
            command = re.match(r"\\+([A-Za-z]+)", text[index:])
            if command and command.group(1) in STRUCTURAL_TEX_COMMANDS | GREEK_AND_TEXT_COMMANDS.keys():
                stop = _command_end(text, index)
                next_command = re.match(r"\\([A-Za-z]+)", text[stop:])
                if (index >= 2 and text[index - 1] == ":" and text[index - 2].isalpha()) or (next_command and next_command.group(1) not in STRUCTURAL_TEX_COMMANDS | GREEK_AND_TEXT_COMMANDS.keys()):
                    index = stop
                    continue
                spans.append(MathSpan(index, stop, text[index:stop], text[index:stop], "bare_command"))
                index = stop
                continue
        index += 1
    return tuple(spans)


SEMANTIC_SCRIPT_TAG_RE = re.compile(r"</?(sub|sup)\b[^>]*>", re.IGNORECASE)


def _semantic_script_ranges(text: str) -> tuple[tuple[int, int, bool], ...]:
    """按原字符范围配对脚本标签；内部样式不切断数学，畸形 HTML 仍可见降级。"""
    ranges: list[tuple[int, int, bool]] = []
    stack: list[str] = []
    start = 0
    for match in SEMANTIC_SCRIPT_TAG_RE.finditer(text):
        name = match.group(1).lower()
        if not match.group(0).startswith("</"):
            if not stack:
                start = match.start()
            stack.append(name)
            if match.group(0).endswith("/>"):
                stack.pop()
                if not stack:
                    ranges.append((start, match.end(), True))
        elif stack:
            if stack.pop() != name:
                stack.clear()
                ranges.append((start, match.end(), False))
            elif not stack:
                ranges.append((start, match.end(), True))
    if stack:
        ranges.append((start, len(text), False))
    combined: list[tuple[int, int, bool]] = []
    for start, end, closed in ranges:
        if combined and combined[-1][1] == start:
            previous = combined.pop()
            combined.append((previous[0], end, previous[2] and closed))
        else:
            combined.append((start, end, closed))
    return tuple(combined)


def _bare_script_spans(text: str) -> tuple[MathSpan, ...]:
    """从脚本标记定位变量，完整认领嵌套参数，避免逐字符回溯长正文。"""
    spans: list[MathSpan] = []
    for marker in re.finditer(r"\^|_(?=\{)", text):
        if spans and marker.start() < spans[-1].end:
            continue
        start = marker.start()
        while start > 0 and text[start - 1].isascii() and text[start - 1].isalnum():
            start -= 1
        if start == marker.start() or not text[start].isalpha():
            continue
        end = marker.start()
        while end < len(text) and text[end] in "_^":
            if text[end] == "_" and not text.startswith("{", end + 1):
                break
            end += 1
            if end < len(text) and text[end] == "{":
                depth = 1
                end += 1
                while end < len(text) and depth:
                    if not _escaped(text, end):
                        depth += text[end] == "{"
                        depth -= text[end] == "}"
                    end += 1
            elif end < len(text) and text[end] == "\\":
                end = _command_end(text, end)
            elif end < len(text) and text[end].isalnum():
                end += 1
            else:
                break
        source = text[start:end]
        expression = source
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:_\{[A-Za-z0-9]+\}|\^(?:\{[A-Za-z0-9]+\}|[A-Za-z0-9]))+", source):
            expression = re.sub(r"_\{([^{}]+)\}", r"<sub>\1</sub>", expression)
            expression = re.sub(r"\^(?:\{([^{}]+)\}|([A-Za-z0-9]))", lambda value: f"<sup>{value.group(1) or value.group(2)}</sup>", expression)
        spans.append(MathSpan(start, end, source, expression, "semantic_script"))
    return tuple(spans)


def content_math_spans(text: str) -> tuple[MathSpan, ...]:
    """在共享数学边界外登记已有的原生上下标 HTML 语义。"""
    spans = list(_scan_delimited_math_spans(text))
    for index, span in enumerate(spans):
        if span.expression.lstrip().startswith(("_", "^")):
            base = re.search(r"(?:[A-Za-z0-9]+|<(?:sub|sup)>[A-Za-z0-9]+</(?:sub|sup)>)+\s*$", text[:span.start])
            if base:
                value = BeautifulSoup(base.group(0), "html.parser").get_text().strip()
                spans[index] = MathSpan(base.start(), span.end, text[base.start():span.end], value + span.expression.lstrip(), span.boundary)
    for start, end, _closed in _semantic_script_ranges(text):
        while start > 0 and ((text[start - 1].isascii() and text[start - 1].isalnum())
                             or "Α" <= text[start - 1] <= "Ω" or "α" <= text[start - 1] <= "ω"):
            start -= 1
        overlaps = [span for span in spans if start < span.end and span.start < end]
        if any(span.start <= start and span.end >= end for span in overlaps):
            continue
        if overlaps:
            start = min(start, *(span.start for span in overlaps))
            end = max(end, *(span.end for span in overlaps))
            spans = [span for span in spans if span not in overlaps]
        source = text[start:end]
        spans.append(MathSpan(start, end, source, source, "semantic"))
    for script in _bare_script_spans(text):
        overlaps = [span for span in spans if script.start < span.end and span.start < script.end]
        if any(span.boundary != "bare_command" or span.start < script.start or span.end > script.end for span in overlaps):
            continue
        # 脚本包含的命令属于完整表达式，不能先把其中 theta/text 等拆成另一公式。
        spans = [span for span in spans if span not in overlaps]
        spans.append(script)
    return tuple(sorted(spans, key=lambda span: span.start))


def scan_math_spans(text: str) -> tuple[MathSpan, ...]:
    """翻译与渲染唯一共用的全部可识别数学边界。"""
    return content_math_spans(text)


def formula_block_span(text: str) -> MathSpan:
    if not text.strip() or not text.replace("$", "").strip():
        raise ValueError("公式源内容为空")
    expression = text
    # 公式 block 是强数学输入；历史 IR 允许在同一式中混用 dollar 边界。
    for span in reversed(scan_math_spans(text)):
        if span.boundary in {"dollar", "display_dollar", "paren", "bracket", "eq"}:
            expression = expression[:span.start] + span.expression + expression[span.end:]
    return MathSpan(0, len(text), text, expression, "block")


def _word_run(text: str, *, subscript: bool = False, superscript: bool = False, bold: bool = False, italic: bool = False) -> Any:
    run = OxmlElement("w:r")
    if subscript or superscript or bold or italic:
        properties = OxmlElement("w:rPr")
        for enabled, name in ((bold, "b"), (italic, "i")):
            if enabled:
                properties.append(OxmlElement(f"w:{name}"))
        if subscript or superscript:
            align = OxmlElement("w:vertAlign")
            align.set(qn("w:val"), "subscript" if subscript else "superscript")
            properties.append(align)
        run.append(properties)
    for line in re.split(r"(\n|\t)", text):
        if line in {"\n", "\t"}:
            run.append(OxmlElement("w:br" if line == "\n" else "w:tab"))
        elif line:
            value = OxmlElement("w:t")
            value.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            value.text = line
            run.append(value)
    return run


def _semantic_elements(source: str) -> tuple[Any, ...]:
    if any(not closed for _start, _end, closed in _semantic_script_ranges(source)):
        raise FormulaParseError("invalid_syntax")
    if _scan_delimited_math_spans(source):
        raise FormulaParseError("unsupported_structure")
    soup = BeautifulSoup(source, "html.parser")
    if _bare_script_spans(soup.get_text()):
        raise FormulaParseError("unsupported_structure")
    result: list[Any] = []

    def visit(parent: Any, *, sub: bool = False, sup: bool = False, bold: bool = False, italic: bool = False) -> None:
        for child in parent.children:
            if isinstance(child, NavigableString):
                result.append(_word_run(str(child), subscript=sub, superscript=sup, bold=bold, italic=italic))
            elif isinstance(child, Tag):
                if child.name in {"sub", "sup"} and (sub or sup):
                    raise FormulaParseError("unsupported_structure")
                if child.name == "br":
                    result.append(_word_run("\n", subscript=sub, superscript=sup, bold=bold, italic=italic))
                else:
                    visit(child, sub=sub or child.name == "sub", sup=sup or child.name == "sup", bold=bold or child.name in {"b", "strong"}, italic=italic or child.name in {"i", "em"})

    visit(soup)
    return tuple(result)


def render_formula(span: MathSpan) -> FormulaRenderResult:
    if not span.expression.strip():
        raise ValueError("公式源内容为空")
    try:
        if span.boundary == "semantic" or (span.boundary == "semantic_script" and span.expression != span.source):
            return FormulaRenderResult("semantic_runs", _semantic_elements(span.expression))
        closing = {"dollar": "$", "display_dollar": "$$", "paren": r"\)", "bracket": r"\]", "eq": "</eq>"}.get(span.boundary)
        if closing is not None and not span.source.lower().endswith(closing):
            raise FormulaParseError("invalid_syntax")
        if span.boundary == "block":
            for inner in _scan_delimited_math_spans(span.source):
                ending = {"dollar": "$", "display_dollar": "$$", "paren": r"\)", "bracket": r"\]", "eq": "</eq>"}.get(inner.boundary)
                if ending is not None and not inner.source.lower().endswith(ending):
                    raise FormulaParseError("invalid_syntax")
        if re.search(r"</?[A-Za-z][^>]*>", span.expression):
            raise FormulaParseError("unsafe_normalization")
        math = _OmmlParser(span.expression).parse()
        return FormulaRenderResult("omml", (math,))
    except FormulaParseError as error:
        return FormulaRenderResult("text_fallback", (_word_run(FORMULA_FALLBACK_NOTICE), _word_run(span.source)), error.reason)


def output_projection(elements: Any) -> list[Any]:
    """固定 v1 投影保留数学树、值、脚本及显式样式，排除易变排版属性。"""
    ignored_run_properties = {qn("w:rFonts"), qn("w:sz"), qn("w:szCs")}

    def attributes(node: Any) -> list[tuple[str, str]]:
        return sorted((key, value) for key, value in node.attrib.items() if not key.startswith(qn("w:rsid")))

    def children(node: Any) -> list[Any]:
        return [value for child in node if (value := project(child)) is not None]

    def project(node: Any) -> Any:
        tag = node.tag
        if tag in ignored_run_properties:
            return None
        if tag == qn("w:rPr"):
            semantic = children(node)
            return [tag, attributes(node), semantic] if semantic or attributes(node) else None
        if tag.startswith("{http://schemas.openxmlformats.org/officeDocument/2006/math}"):
            # XML 保存会把空字符串读回为 None；两者都不含字符，非空文字仍逐字绑定。
            return [tag, attributes(node), (node.text or None) if tag == qn("m:t") else None, children(node)]
        if tag == qn("w:r"):
            semantic = [value for props in node if props.tag == qn("w:rPr") and (value := project(props)) is not None]
            values = [
                [child.tag, child.text or "", [(key, value) for key, value in attributes(child) if key != "{http://www.w3.org/XML/1998/namespace}space"]]
                if child.tag in {qn("w:t"), qn("w:br"), qn("w:tab")} else project(child)
                for child in node if child.tag != qn("w:rPr")
            ]
            return [tag, attributes(node), semantic, values]
        return [tag, attributes(node), node.text, children(node)]

    return [FORMULA_OUTPUT_VERSION, [project(node) for node in elements]]


def output_sha256(elements: Any) -> str:
    return canonical_sha256(output_projection(elements))


class _OmmlParser:
    """把当前合同允许的 TeX 子集直接构造成可编辑 OMML。"""

    def __init__(self, source: str) -> None:
        self.source = collapse_double_escaped_tex_commands(source.strip())
        self.position = 0

    def parse(self) -> Any:
        children = self._parse_sequence()
        if self.position != len(self.source) or not children:
            raise FormulaParseError("invalid_syntax")
        math = OxmlElement("m:oMath")
        math.extend(children)
        return math

    def _parse_sequence(self, *, stop_at_brace: bool = False, preserve_spaces: bool = False) -> list[Any]:
        children: list[Any] = []
        text: list[str] = []

        def flush_text() -> None:
            if text:
                value = "".join(text)
                if not preserve_spaces:
                    value = re.sub(r"\b(?:[A-Za-z0-9]\s+){1,}[A-Za-z0-9]\b", lambda match: "".join(match.group(0).split()), value)
                    value = compact_math_token_runs(value)
                children.append(self._math_run(value))
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
                    raise FormulaParseError("invalid_syntax")
                flush_text()
                self.position += 1
                return children
            if char == "{":
                flush_text()
                self.position += 1
                group = self._parse_sequence(stop_at_brace=True, preserve_spaces=preserve_spaces)
                following = self.position
                while following < len(self.source) and self.source[following].isspace():
                    following += 1
                if following < len(self.source) and self.source[following] in "_^":
                    wrapper = OxmlElement("m:box")
                    element = OxmlElement("m:e")
                    element.extend(group)
                    wrapper.append(element)
                    children.append(wrapper)
                else:
                    children.extend(group)
                continue
            if char == "\\":
                flush_text()
                child = self._parse_command()
                following = self.position
                while following < len(self.source) and self.source[following].isspace():
                    following += 1
                # 命令结果是一个完整原子；脚本不能拆掉文本 wrapper 或重建其数学样式。
                if child.tag == qn("m:r") and following < len(self.source) and self.source[following] in "_^":
                    wrapper = OxmlElement("m:box")
                    element = OxmlElement("m:e")
                    element.append(child)
                    wrapper.append(element)
                    child = wrapper
                children.append(child)
                continue
            if char in {"^", "_"}:
                flush_text()
                if not children:
                    raise FormulaParseError("invalid_syntax")
                self.position += 1
                argument = self._parse_argument()
                base = children.pop()
                if base.tag == qn("m:r"):
                    raw = (base.find(qn("m:t")).text or "").rstrip()
                    if not raw:
                        raise FormulaParseError("invalid_syntax")
                    # 连续字母是数据手册变量名，运算符以前的部分不属于基底。
                    match = re.search(r"[A-Za-zΑ-Ωα-ω0-9]+$", raw)
                    offset = match.start() if match else len(raw) - 1
                    if offset:
                        children.append(self._math_run(raw[:offset]))
                    base = self._math_run(raw[offset:])
                children.append(self._script(char, base, argument))
                continue
            text.append(char)
            self.position += 1

        if stop_at_brace:
            raise FormulaParseError("invalid_syntax")
        flush_text()
        return children

    def _parse_command(self) -> Any:
        self.position += 1
        if self.position < len(self.source) and self.source[self.position] in {",", "_"}:
            literal = "\u2009" if self.source[self.position] == "," else "_"
            self.position += 1
            return self._math_run(literal)
        start = self.position
        while self.position < len(self.source) and self.source[self.position].isalpha():
            self.position += 1
        command = self.source[start : self.position]
        if not command:
            raise FormulaParseError("invalid_syntax")
        self._skip_spaces()
        if command in {"ln", "log", "exp", "sin", "cos", "tan"}:
            return self._math_run(command)
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
            group = self._parse_required_group(preserve_spaces=True)
            value = "".join(node.find(qn("m:t")).text or "" for node in group if node.tag == qn("m:r"))
            if len(group) != 1 or not value:
                wrapper = OxmlElement("m:box")
                element = OxmlElement("m:e")
                for child in group:
                    element.append(child)
                wrapper.append(element)
                return wrapper
            return self._math_run(value)
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
            if self.position < len(self.source) and self.source[self.position] == ".":
                raise FormulaParseError("unsupported_structure")
            return self._math_run("")
        if command in {"begin", "end"}:
            raise FormulaParseError("unsupported_structure")
        if command == "tag":
            if not self.source[:start - 1].strip():
                raise FormulaParseError("invalid_syntax")
            group = self._parse_required_group(preserve_spaces=True)
            self._skip_spaces()
            if self.position != len(self.source):
                raise FormulaParseError("unsupported_structure")
            if len(group) != 1 or group[0].tag != qn("m:r"):
                raise FormulaParseError("unsupported_structure")
            value = group[0].find(qn("m:t")).text or ""
            if not re.fullmatch(r"[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*", value):
                raise FormulaParseError("unsupported_structure")
            return self._math_run(f" ({value})")
        symbol = {"vee": "∨", "to": "→"}.get(command, GREEK_AND_TEXT_COMMANDS.get(command))
        if symbol is None:
            raise FormulaParseError("unsupported_command")
        return self._math_run(symbol)

    def _parse_required_group(self, *, preserve_spaces: bool = False) -> list[Any]:
        self._skip_spaces()
        if self.position >= len(self.source) or self.source[self.position] != "{":
            raise FormulaParseError("invalid_syntax")
        self.position += 1
        return self._parse_sequence(stop_at_brace=True, preserve_spaces=preserve_spaces)

    def _parse_optional_bracket_group(self) -> list[Any]:
        self._skip_spaces()
        if self.position >= len(self.source) or self.source[self.position] != "[":
            return []
        end = self.source.find("]", self.position + 1)
        if end < 0:
            raise FormulaParseError("invalid_syntax")
        parser = _OmmlParser(self.source[self.position + 1 : end])
        children = parser._parse_sequence()
        if parser.position != len(parser.source) or not children:
            raise FormulaParseError("invalid_syntax")
        self.position = end + 1
        self._skip_spaces()
        return children

    def _parse_argument(self) -> list[Any]:
        self._skip_spaces()
        if self.position >= len(self.source):
            raise FormulaParseError("invalid_syntax")
        if self.source[self.position] == "{":
            self.position += 1
            start = self.position
            argument = self._parse_sequence(stop_at_brace=True)
            # 显式文本 wrapper 的空白是公式内容，不能在外层脚本再次压缩。
            if re.search(r"\\(?:text|mathrm|mathsf)\b", self.source[start:self.position]):
                return argument
            return self._compact_plain_script_argument(argument)
        if self.source[self.position] == "\\":
            return [self._parse_command()]

        value = self.source[self.position]
        if value in "}_^":
            raise FormulaParseError("invalid_syntax")
        self.position += 1
        return [self._math_run(value)]

    def _compact_plain_script_argument(self, argument: list[Any]) -> list[Any]:
        values: list[str] = []
        for node in argument:
            if node.tag != qn("m:r"):
                return argument
            # 压缩只适用于默认纯文字 run；显式样式或其它语义属性必须保留原节点。
            if any(child.tag not in {qn("m:rPr"), qn("m:t")} for child in node) or any(
                property.tag != qn("m:sty") or property.attrib != {qn("m:val"): "p"}
                for properties in node.findall(qn("m:rPr")) for property in properties
            ):
                return argument
            value = node.find(qn("m:t"))
            if value is None:
                return argument
            values.append(value.text or "")
        combined = "".join(values)
        if not re.fullmatch(r"[A-Za-z0-9\s]+", combined):
            return argument
        return [self._math_run("".join(combined.split()))]

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

    @staticmethod
    def _math_run(text: str) -> Any:
        run = OxmlElement("m:r")
        value = OxmlElement("m:t")
        value.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        value.text = text
        run.append(value)
        _OmmlParser._apply_math_style([run], "p")
        return run
