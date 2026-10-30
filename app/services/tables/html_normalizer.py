"""将已验证的表格来源规范化为有序行与语义 runs，不改写原始 HTML。"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
import re
from typing import Literal, NoReturn

from app.services.tables.models import CellRun, TableSourceFragment, make_cell_id, make_run_id


NORMALIZER_VERSION = "table-html/v1"
MAX_RAW_HTML_BYTES = 8 * 1024 * 1024
MAX_HTML_DEPTH = 128
MAX_CELLS = 100_000
MAX_SPAN = 1_000_000
MAX_GRID_SLOTS = 1_000_000
MAX_OCCUPANCY_CHECKS = 1_000_000

DiagnosticCode = Literal[
    "table_html_missing", "table_html_empty", "table_html_no_rows",
    "table_html_implicit_close", "table_html_removed_unsafe", "table_html_canonicalized",
    "table_span_invalid", "table_nested_script", "table_formula_unresolved",
    "table_span_collision", "table_span_out_of_bounds", "table_grid_hole",
]
BuildErrorCode = Literal["table_build_limit", "table_html_encoding", "table_html_unsupported_structure"]


@dataclass(frozen=True, slots=True)
class TableDiagnostic:
    """只承载中性机器码和安全定位；严重度由后续质量 owner 判断。"""

    code: DiagnosticCode
    fragment_id: str
    cell_id: str | None = None
    run_id: str | None = None
    related_cell_id: str | None = None
    source_row_index: int | None = None
    source_cell_index: int | None = None
    row: int | None = None
    column: int | None = None
    end_column: int | None = None
    attribute: Literal["rowspan", "colspan"] | None = None


class TableBuildError(ValueError):
    """固定原因码与定位，不把 HTML、属性、路径或第三方异常拼入摘要。"""

    def __init__(self, code: BuildErrorCode, *, fragment_id: str,
                 source_row_index: int | None = None, source_cell_index: int | None = None) -> None:
        self.code = code
        self.fragment_id = fragment_id
        self.source_row_index = source_row_index
        self.source_cell_index = source_cell_index
        super().__init__(f"表格构建失败：{code}。")


@dataclass(frozen=True, slots=True)
class NormalizedCell:
    source_row_index: int
    source_cell_index: int
    is_header: bool
    rowspan: int
    colspan: int
    runs: tuple[CellRun, ...]


@dataclass(frozen=True, slots=True)
class NormalizedRow:
    cells: tuple[NormalizedCell, ...]


@dataclass(frozen=True, slots=True)
class NormalizedTableFragment:
    fragment_id: str
    normalized_html: str | None
    rows: tuple[NormalizedRow, ...]
    diagnostics: tuple[TableDiagnostic, ...]


@dataclass(slots=True)
class _Frame:
    tag: str
    output_tag: str | None
    kind: str


_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
_UNSAFE_TAGS = frozenset({"script", "style", "iframe", "template", "noscript", "link", "meta", "base"})
_PAYLOAD_TAGS = frozenset({"img", "svg", "object", "embed", "canvas", "video", "audio", "picture", "source", "input"})
_GROUP_TAGS = frozenset({"thead", "tbody", "tfoot"})
_DELIMITERS = re.compile(r"\$\$|\$|\\[()\[\]]")
_CLOSERS = {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}


def _formula_parts(text: str) -> tuple[list[tuple[str, str]], bool]:
    """仅在当前语义段配对界定符，保留转义和未配对内容。"""
    tokens = []
    cursor = 0
    while match := _DELIMITERS.search(text, cursor):
        index = match.start() - 1
        while index >= 0 and text[index] == "\\":
            index -= 1
        escaped = (match.start() - 1 - index) % 2
        if not escaped:
            tokens.append(match)
        # 转义只消耗当前字符，\$$ 的第二个 $ 仍可能是公式起点。
        cursor = match.start() + 1 if escaped else match.end()
    # 预先寻找同类闭合，未配对的候选不会吞掉后面的完整公式。
    next_closer: list[int | None] = [None] * len(tokens)
    last_seen: dict[str, int] = {}
    for index in range(len(tokens) - 1, -1, -1):
        token = tokens[index].group()
        next_closer[index] = last_seen.get(_CLOSERS.get(token, ""))
        last_seen[token] = index
    pairs: list[tuple[int, int]] = []
    unresolved = False
    index = 0
    while index < len(tokens):
        close = next_closer[index]
        if close is None:
            unresolved = True
            index += 1
        else:
            pairs.append((tokens[index].start(), tokens[close].end()))
            index = close + 1
    parts: list[tuple[str, str]] = []
    cursor = 0
    for start, end in pairs:
        if start > cursor:
            parts.append(("text", text[cursor:start]))
        parts.append(("formula", text[start:end]))
        cursor = end
    if cursor < len(text):
        parts.append(("text", text[cursor:]))
    return parts, unresolved


class _TableParser(HTMLParser):
    def __init__(self, fragment_id: str, *, render_script_precedence: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.fragment_id = fragment_id
        self.render_script_precedence = render_script_precedence
        self.stack: list[_Frame] = []
        self.output: list[str] = []
        self.rows: list[NormalizedRow] = []
        self.current_row: list[NormalizedCell] | None = None
        self.cell: tuple[bool, int, int] | None = None
        self.runs: list[CellRun] = []
        self.text: list[str] = []
        self.diagnostics: list[TableDiagnostic] = []
        self.table_seen = False
        self.cell_count = 0
        self.run_boundary = False

    def _fail(self, code: BuildErrorCode = "table_html_unsupported_structure") -> NoReturn:
        raise TableBuildError(code, fragment_id=self.fragment_id,
                              source_row_index=len(self.rows) if self.current_row is not None else None,
                              source_cell_index=len(self.current_row) if self.cell is not None else None)

    def _diagnose(self, code: DiagnosticCode, *, attribute: Literal["rowspan", "colspan"] | None = None) -> None:
        row = len(self.rows) if self.current_row is not None else None
        column = len(self.current_row) if self.cell is not None else None
        self.diagnostics.append(TableDiagnostic(
            code, self.fragment_id,
            cell_id=make_cell_id(self.fragment_id, row, column) if row is not None and column is not None else None,
            source_row_index=row, source_cell_index=column, attribute=attribute,
        ))

    def _has(self, kind: str) -> bool:
        return any(frame.kind == kind for frame in self.stack)

    def _semantics(self) -> tuple[str, bool, bool]:
        script = "text"
        for frame in self.stack:
            if frame.output_tag in {"sub", "sup"}:
                script = "subscript" if frame.output_tag == "sub" else "superscript"
        # 来源默认取最近作用域；仅内存 Word 视图保持既有双脚本时上标优先。
        if self.render_script_precedence and any(frame.output_tag == "sup" for frame in self.stack):
            script = "superscript"
        kind = "formula" if self._has("math") else script
        return kind, any(frame.output_tag == "b" for frame in self.stack), any(frame.output_tag == "i" for frame in self.stack)

    def _run(self, kind: str, text: str, bold: bool, italic: bool) -> None:
        if not text:
            return
        cell_id = make_cell_id(self.fragment_id, len(self.rows), len(self.current_row))
        if (self.runs and not self.run_boundary and kind not in {"formula", "line_break"} and
                (self.runs[-1].type, self.runs[-1].bold, self.runs[-1].italic) == (kind, bold, italic)):
            self.runs[-1] = self.runs[-1].model_copy(update={"source": self.runs[-1].source + text})
            return
        self.run_boundary = False
        index = len(self.runs)
        self.runs.append(CellRun(id=make_run_id(cell_id, index), source_run_index=index,
                                 type=kind, source=text, bold=bold, italic=italic))

    def _flush(self) -> None:
        if not self.text:
            return
        text = "".join(self.text)
        self.text.clear()
        kind, bold, italic = self._semantics()
        self._run(kind, text, bold, italic)

    def _final_runs(self) -> tuple[CellRun, ...]:
        """先合并完整语义段，再识别公式并分配最终身份，避免包装边界改变保护类型。"""
        cell_id = make_cell_id(self.fragment_id, len(self.rows), len(self.current_row))
        final: list[CellRun] = []
        for segment in self.runs:
            if segment.type in {"formula", "line_break"}:
                parts = [(segment.type, segment.source)]
                unresolved = False
            else:
                parts, unresolved = _formula_parts(segment.source)
            for kind, value in parts:
                index = len(final)
                final.append(CellRun(
                    id=make_run_id(cell_id, index), source_run_index=index,
                    type=segment.type if kind == "text" else kind, source=value,
                    bold=segment.bold, italic=segment.italic,
                ))
            if unresolved:
                self._diagnose("table_formula_unresolved")
        return tuple(final)

    def _push(self, tag: str, output_tag: str | None, kind: str) -> None:
        if len(self.stack) >= MAX_HTML_DEPTH:
            self._fail("table_build_limit")
        self.stack.append(_Frame(tag, output_tag, kind))

    def _pop(self, *, implicit: bool) -> None:
        frame = self.stack[-1]
        if implicit and frame.kind in {"cell", "row", "table", "group", "inline", "math"}:
            self._diagnose("table_html_implicit_close")
        if frame.kind == "cell":
            self._flush()
            is_header, rowspan, colspan = self.cell
            self.current_row.append(NormalizedCell(len(self.rows), len(self.current_row), is_header,
                                                   rowspan, colspan, self._final_runs()))
            self.cell = None
            self.runs = []
        elif frame.kind == "row":
            self.rows.append(NormalizedRow(tuple(self.current_row)))
            self.current_row = None
        elif frame.kind in {"inline", "math"}:
            before = self._semantics()
            after_stack = self.stack[:-1]
            # 脚本/公式作用域是身份分段边界；普通未知 wrapper 不切碎相邻文字。
            if frame.output_tag in {"sub", "sup"} or frame.kind == "math":
                self._flush()
                self.run_boundary = True
            else:
                self.stack = after_stack
                after = self._semantics()
                self.stack.append(frame)
                if before != after:
                    self._flush()
        self.stack.pop()
        if frame.output_tag is not None:
            self.output.append(f"</{frame.output_tag}>")

    def _close(self, kind: str, *, implicit: bool) -> None:
        index = next((index for index in range(len(self.stack) - 1, -1, -1) if self.stack[index].kind == kind), None)
        if index is not None:
            while len(self.stack) > index:
                self._pop(implicit=implicit or len(self.stack) - 1 > index)

    def _span(self, attrs: list[tuple[str, str | None]], name: Literal["rowspan", "colspan"]) -> int:
        values = [value for key, value in attrs if key == name]
        if not values:
            return 1
        value = values[0].strip() if len(values) == 1 and values[0] is not None else ""
        if not re.fullmatch(r"[0-9]+", value) or not value.strip("0"):
            self._diagnose("table_span_invalid", attribute=name)
            return 1
        significant = value.lstrip("0")
        if len(significant) > len(str(MAX_SPAN)) or (len(significant) == len(str(MAX_SPAN)) and significant > str(MAX_SPAN)):
            self._fail("table_build_limit")
        return int(significant)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._has("unsafe"):
            if tag not in _VOID_TAGS:
                self._push(tag, None, "unsafe")
            return
        if tag in _UNSAFE_TAGS:
            self._diagnose("table_html_removed_unsafe")
            if tag not in _VOID_TAGS:
                self._push(tag, None, "unsafe")
            return
        if tag in _PAYLOAD_TAGS:
            self._fail()
        if tag == "table":
            if self.table_seen:
                self._fail()
            self.table_seen = True
            self.output.append("<table>")
            self._push(tag, tag, "table")
        elif tag in _GROUP_TAGS:
            if not self._has("table"):
                self._fail()
            self._close("row", implicit=True)
            self._close("group", implicit=True)
            self.output.append(f"<{tag}>")
            self._push(tag, tag, "group")
        elif tag == "tr":
            if not self._has("table"):
                self._fail()
            self._close("row", implicit=True)
            self.current_row = []
            self.output.append("<tr>")
            self._push(tag, tag, "row")
        elif tag in {"td", "th"}:
            if self.current_row is None:
                self._fail()
            self._close("cell", implicit=True)
            self.cell_count += 1
            if self.cell_count > MAX_CELLS:
                self._fail("table_build_limit")
            self.cell = (tag == "th", 1, 1)
            rowspan, colspan = self._span(attrs, "rowspan"), self._span(attrs, "colspan")
            self.cell = (tag == "th", rowspan, colspan)
            spans = (f' rowspan="{rowspan}"' if rowspan != 1 else "") + (f' colspan="{colspan}"' if colspan != 1 else "")
            self.output.append(f"<{tag}{spans}>")
            self._push(tag, tag, "cell")
        else:
            output_tag = {"strong": "b", "em": "i"}.get(tag, tag)
            math = tag == "span" and any(key == "class" and value is not None and "math" in value.split() for key, value in attrs)
            output_tag = "span" if math else output_tag if output_tag in {"b", "i", "sup", "sub", "br"} else None
            if self.cell is None and output_tag is not None:
                self._fail()
            if self.cell is not None and (self._has("math") or tag == "math"):
                self._diagnose("table_formula_unresolved")
            if output_tag == "br":
                self._flush()
                _, bold, italic = self._semantics()
                self._run("line_break", "\n", bold, italic)
                self.output.append("<br>")
                return
            before = self._semantics()
            if output_tag in {"sub", "sup"} and before[0] in {"subscript", "superscript"}:
                self._diagnose("table_nested_script")
            if self.cell is not None:
                self._push(tag, output_tag, "math" if math else "inline")
                after = self._semantics()
                self.stack.pop()
                if before != after or output_tag in {"sup", "sub"} or math:
                    self._flush()
                if output_tag in {"sub", "sup"} or math:
                    self.run_boundary = True
            if output_tag is not None:
                self.output.append('<span class="math">' if math else f"<{output_tag}>")
            if tag not in _VOID_TAGS:
                self._push(tag, output_tag, "math" if math else "inline")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS:
            return
        if self._has("unsafe"):
            index = next((index for index in range(len(self.stack) - 1, -1, -1)
                          if self.stack[index].tag == tag and self.stack[index].kind == "unsafe"), None)
            if index is not None:
                del self.stack[index:]
            return
        index = next((index for index in range(len(self.stack) - 1, -1, -1) if self.stack[index].tag == tag), None)
        if index is None:
            return
        # 不让错配的内联闭合跨出 cell，以免后续文字被挪给其他来源。
        if any(frame.kind in {"cell", "row", "table"} for frame in self.stack[index + 1:]) and tag not in {"table", "tr", "td", "th", *_GROUP_TAGS}:
            self._fail()
        while len(self.stack) > index:
            self._pop(implicit=len(self.stack) - 1 > index)

    def handle_data(self, data: str) -> None:
        if self._has("unsafe"):
            return
        if self.cell is not None:
            self.text.append(data)
        elif data.strip():
            self._fail()
        self.output.append(escape(data))

    def parse_html_declaration(self, i: int) -> int:
        # 标准库还会直接把 <![...> 当注释、DOCTYPEX 当前缀匹配的 doctype。
        # 在分派前限定声明入口，避免默认回调吞掉未建模的技术载荷。
        if not re.match(r"<!doctype(?=\s|>)", self.rawdata[i:], re.IGNORECASE):
            self._fail()
        return super().parse_html_declaration(i)

    def unknown_decl(self, data: str) -> None:
        # HTMLParser 不会把未知声明中的文本交给 handle_data，不能静默丢弃。
        self._fail()

    def handle_pi(self, data: str) -> None:
        self._fail()

    def parse_bogus_comment(self, i: int, report: bool = True) -> int:
        # 标准库会把非注释声明当作 bogus comment 丢弃；这里不能悄悄吞掉技术载荷。
        self._fail()

    def finish(self) -> None:
        # 当前标准库 close 会直接消费残缺的字母起始标签，不触发 handle_data。
        # 已完成的标签仅缺 td/tr 闭合仍可修复；无法确定载荷的残缺 token 明确拒绝。
        if self.rawdata.startswith(("</", "<!", "<?")) or re.match(r"<[A-Za-z]", self.rawdata):
            self._fail()
        self.close()
        while self.stack:
            self._pop(implicit=True)


def normalize_table_fragment(
    source: TableSourceFragment, *, render_script_precedence: bool = False,
) -> NormalizedTableFragment:
    """默认保留源作用域；显式内存渲染策略只改变脚本投影，不改 raw 来源。"""
    raw = source.raw_html
    if raw is not None:
        try:
            byte_count = len(raw.encode("utf-8"))
        except UnicodeEncodeError:
            raise TableBuildError("table_html_encoding", fragment_id=source.fragment_id) from None
        if byte_count > MAX_RAW_HTML_BYTES:
            raise TableBuildError("table_build_limit", fragment_id=source.fragment_id)
    source = TableSourceFragment.model_validate(source)
    if source.html_state in {"missing", "empty"}:
        code = "table_html_missing" if raw is None else "table_html_empty"
        return NormalizedTableFragment(source.fragment_id, raw, (), (TableDiagnostic(code, source.fragment_id),))
    parser = _TableParser(source.fragment_id, render_script_precedence=render_script_precedence)
    parser.feed(raw)
    parser.finish()
    if not parser.rows:
        parser._diagnose("table_html_no_rows")
    normalized = "".join(parser.output)
    if normalized != raw:
        parser.diagnostics.append(TableDiagnostic("table_html_canonicalized", source.fragment_id))
    return NormalizedTableFragment(source.fragment_id, normalized, tuple(parser.rows), tuple(parser.diagnostics))
