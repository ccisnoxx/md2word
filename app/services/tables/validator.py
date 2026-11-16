"""消费已验证来源与既有 builder，只输出确定性标记，不修表或接线生产状态。"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
import re
from typing import get_args

from pydantic import ValidationError

from app.services.document_ir.models import DocumentIR, LogicalTableGroup, TableFragment
from app.services.tables.grid_builder import TableBuildResult, build_table_grid
from app.services.tables.html_normalizer import DiagnosticCode, TableDiagnostic
from app.services.tables.measurement import (
    MEASUREMENT_UNITS, ValueColumnLabel, is_measurement_unit, split_parameter_value,
)
from app.services.tables.models import (
    LEGACY_VALUE_COLUMN_SPAN_AMBIGUOUS, VALUE_COLUMN_SPAN_AMBIGUOUS, TableCell, TableGrid, TableQualityFlag,
)
from app.services.tables.quality import (
    BINDING_VALIDATOR_VERSION, GROUPS_VERSION, LEGACY_SHARED_LIMITS_RULE, LEGACY_VALIDATOR_VERSION,
    NORMALIZER_VERSION, RULE_CODES, VALIDATOR_VERSION, LegacyValueColumnReplay, TableCellReference,
    TableFinding, TableFindingEvidence, TableFragmentReference, TableQualityContribution, TableRunRange,
    TableRunReference, TableValidationError, TableValidationPolicy, TableValidationReport, ValidatorVersion,
    ValueColumn, ValueColumnSpan, aggregate_table_quality, default_table_validation_policy, make_finding_id,
    make_table_report,
)


_IGNORED_DIAGNOSTICS = frozenset({"table_html_implicit_close", "table_html_canonicalized"})
_DIAGNOSTIC_REASONS = {
    "table_html_missing": "missing", "table_html_empty": "empty", "table_html_no_rows": "no_rows",
    "table_span_collision": "span_collision", "table_span_out_of_bounds": "span_out_of_bounds",
    "table_span_invalid": "invalid_span", "table_html_removed_unsafe": "unsafe_removed",
    "table_formula_unresolved": "formula_unresolved", "table_nested_script": "nested_script",
}
_UNIT_ORDER = tuple(sorted(MEASUREMENT_UNITS, key=lambda unit: (-len(unit), unit)))
MAX_UNIT_TOKEN_CHARS = 4096
_UNIT_WORD = re.compile(r"(?<![\wµμΩ°])(?:[0-9]+(?:\.[0-9]+)\s*)?([A-Za-zµμΩ°%]+)(?![\wµμΩ°])")
_NUMBER = re.compile(r"(?<![\w.])[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?(?![\w.])")
_RANGE = re.compile(r"\s*[+-]?[0-9]+(?:\.[0-9]+)?\s*[-–—~～]\s*[+-]?[0-9]+(?:\.[0-9]+)?\s*")
_ID_HEADERS = frozenset({"id", "serial number", "serial no", "serial no.", "序号", "序列号", "编号"})
_VALUE_HEADERS = frozenset({"min", "min.", "minimum", "typ", "typ.", "typical", "max", "max.", "maximum",
                            "最小", "最小值", "典型", "典型值", "最大", "最大值"})
# 已登记 v1 跨列报告按原数值表达式重算。
_LEGACY_SINGLE_VALUE = re.compile(
    r"[<>≤≥]?\s*[±+\-−–]?\s*[0-9]+(?:\.[0-9]+)?"
    r"(?:[eE][+\-−]?[0-9]+)?(?:\s*(?P<suffix>[A-Za-zµμΩ°%/√·]+))?"
)
_LEGACY_SHARED_LIMIT_VALUE = re.compile(r"[<>≤≥]?\s*[±+\-−–]?\s*[0-9]+(?:\.[0-9]+)?(?:\s*[A-Za-zµμΩ°%/√·]+)?")
_UNIT_HEADERS = frozenset({"unit", "units", "单位"})
_SYMBOL_HEADERS = frozenset({"symbol", "symbols", "符号", "信号"})
_VALUE_COLUMN_LABELS: dict[str, ValueColumnLabel] = {
    "min": "MIN", "minimum": "MIN", "typ": "TYP", "typical": "TYP", "max": "MAX", "maximum": "MAX",
    "low": "LOW", "nom": "NOM", "nominal": "NOM", "high": "HIGH",
    "最小": "最小", "最小值": "最小", "典型": "典型", "典型值": "典型", "最大": "最大", "最大值": "最大",
}
_VALUE_COLUMN_ORDERS: tuple[tuple[ValueColumnLabel, ...], ...] = (
    ("MIN", "TYP", "MAX"), ("MIN", "MAX"), ("LOW", "NOM", "HIGH"), ("最小", "典型", "最大"),
)
_BINDING_VALUE_COLUMN_ORDERS: tuple[tuple[ValueColumnLabel, ...], ...] = (
    *_VALUE_COLUMN_ORDERS, ("MIN", "NOM", "MAX"), ("MIN", "TYP"), ("TYP", "MAX"), ("LOW", "HIGH"),
)
_REVIEW_LABEL_ALIASES = {"最小": "min", "典型": "typ", "最大": "max"}
# MinerU 可把表头全部写成 td。首部三行涵盖标题、器件分组和最末级数值列。
_IMPLICIT_VALUE_HEADER_ROWS = 3


def _source_grid_signature(grid: TableGrid) -> dict:
    return grid.model_dump(mode="json", warnings=False, exclude={
        "quality_flags": True,
        "cells": {"__all__": {"quality_flags": True, "runs": {"__all__": {"target": True}}}},
    })


def _fragment_references(result: TableBuildResult) -> tuple[TableFragmentReference, ...]:
    widths: dict[str, int] = defaultdict(int)
    for cell in result.grid.cells:
        widths[cell.source_fragment_id] = max(widths[cell.source_fragment_id], cell.column + cell.colspan)
    references = []
    offset = 0
    for source, normalized in zip(result.grid.source_fragments, result.normalized_fragments, strict=True):
        # 只数 builder 返回的受控标记：源文本中的 '<tr>' 已被 escape。
        # 这保留零 cell 的显式行，不增加第二套 HTML parser/occupancy。
        rows = normalized.normalized_html.count("<tr>") if source.html_state == "present" else 0
        columns = widths[source.fragment_id]
        span = source.source_span
        references.append(TableFragmentReference(
            fragment_id=source.fragment_id, source_index=span.source_index, json_pointer=span.json_pointer,
            page_index=span.page_index, bbox=span.bbox, html_state=source.html_state,
            raw_html_sha256=source.raw_html_sha256, row_start=offset, row_count=rows, columns=columns,
            header_review=source.header_review, upstream_coverage=source.upstream_coverage,
        ))
        offset += rows
    if offset != result.grid.rows:
        raise TableValidationError("table_validation_input")
    return tuple(references)


def _cell_reference(cell: TableCell) -> TableCellReference:
    return TableCellReference(
        id=cell.id, fragment_id=cell.source_fragment_id, source_row_index=cell.source_row_index,
        source_cell_index=cell.source_cell_index, row=cell.row, column=cell.column,
        rowspan=cell.rowspan, colspan=cell.colspan, is_header=cell.is_header, content_sha256=cell.content_sha256,
        runs=tuple(TableRunReference(id=run.id, source_run_index=run.source_run_index,
                                    type=run.type, length=len(run.source)) for run in cell.runs),
    )


@dataclass(frozen=True)
class _TextSegment:
    text: str
    # (run_id, segment_start, segment_end)；只连续拼接 text，其他语义 run 均切断。
    runs: tuple[tuple[str, int, int], ...]

    def ranges(self, start: int, end: int) -> tuple[TableRunRange, ...]:
        return tuple(TableRunRange(run_id=identity, start_char=max(start, left) - left,
                                   end_char=min(end, right) - left)
                     for identity, left, right in self.runs if max(start, left) < min(end, right))


def _segments(cell: TableCell) -> tuple[_TextSegment, ...]:
    segments = []
    pieces = []
    length = 0
    offsets = []
    for run in cell.runs:
        if run.type == "text":
            offsets.append((run.id, length, length + len(run.source)))
            pieces.append(run.source)
            length += len(run.source)
        else:
            if pieces:
                segments.append(_TextSegment("".join(pieces), tuple(offsets)))
            pieces, offsets, length = [], [], 0
    if pieces:
        segments.append(_TextSegment("".join(pieces), tuple(offsets)))
    return tuple(segments)


def _cell_text(cell: TableCell) -> str:
    return "".join(run.source for run in cell.runs).strip()


@dataclass(frozen=True)
class _ParameterHeader:
    row: int
    columns: dict[int, ValueColumn]
    unit_column: int | None


def _parameter_header(rows: list[list[TableCell]], *, include_binding_groups: bool) -> _ParameterHeader | None:
    group_titles: set[tuple[int, int]] = set()
    unit_columns: set[int] = set()
    implicit = None
    orders = _BINDING_VALUE_COLUMN_ORDERS if include_binding_groups else _VALUE_COLUMN_ORDERS
    for row in rows:
        source_row = row[0].source_row_index
        labels = {}
        explicit = set()
        row_titles = set()
        for cell in row:
            text = " ".join(_cell_text(cell).casefold().split())
            if cell.colspan > 1:
                if text:
                    row_titles.add((cell.column, cell.column + cell.colspan))
                continue
            if text in _UNIT_HEADERS:
                unit_columns.add(cell.column)
            label = _VALUE_COLUMN_LABELS.get(text.removesuffix("."))
            if label is not None:
                labels[cell.column] = label
                if cell.is_header:
                    explicit.add(cell.column)
        groups = []
        for start in labels:
            # v3 可识别独立的双列 LIMIT；三列完整组优先占位。
            if include_binding_groups and groups and start < groups[-1][0] + len(groups[-1][1]):
                continue
            for label_order in orders:
                if all(labels.get(start + index) == label for index, label in enumerate(label_order)):
                    groups.append((start, label_order))
                    break
        if groups and (len(groups) == 1 or all(
            (start, start + len(label_order)) in group_titles for start, label_order in groups
        )):
            columns = {
                start + index: ValueColumn(column=start + index, label=label, group_start_column=start)
                for start, label_order in groups for index, label in enumerate(label_order)
            }
            unit_column, = unit_columns if len(unit_columns) == 1 else (None,)
            header = _ParameterHeader(source_row, columns, unit_column)
            if columns.keys() <= explicit:
                # 同一数值列布局的重复表头继续使用首部定位，覆盖中间的数据行。
                if implicit is not None and implicit.columns == columns:
                    return implicit
                return header
            if implicit is None and source_row < _IMPLICIT_VALUE_HEADER_ROWS:
                implicit = header
        group_titles.update(row_titles)
    return implicit


def parameter_value_header_label(text: str) -> str | None:
    """PDF 取证和人工核定共用的规范列标签。"""
    label = _VALUE_COLUMN_LABELS.get(" ".join(text.casefold().split()).rstrip("."))
    return _REVIEW_LABEL_ALIASES.get(label, label.lower()) if label is not None else None


def is_unit_header_label(text: str) -> bool:
    return " ".join(text.casefold().split()) in _UNIT_HEADERS


def _finding_details(
    fragment: TableFragmentReference,
    policy: TableValidationPolicy,
    rule_id: str,
    reason: str,
    *,
    cell: TableCell | None = None,
    **location,
) -> tuple[TableQualityFlag, TableFindingEvidence]:
    if cell is not None:
        location = {"cell_id": cell.id, "source_row_index": cell.source_row_index,
                    "source_cell_index": cell.source_cell_index, "row": cell.row, "column": cell.column, **location}
    evidence = TableFindingEvidence(
        rule_id=rule_id, reason=reason, fragment_id=fragment.fragment_id,
        source_index=fragment.source_index, json_pointer=fragment.json_pointer,
        page_index=fragment.page_index, bbox=fragment.bbox, **location,
    )
    flag = TableQualityFlag(code=RULE_CODES[rule_id], severity=policy.severity_for(rule_id),
                            fragment_id=fragment.fragment_id, cell_id=evidence.cell_id, run_id=evidence.run_id)
    return flag, evidence


def _iter_legacy_value_column_spans(
    result: TableBuildResult,
    policy: TableValidationPolicy,
    by_fragment: Mapping[str, TableFragmentReference],
    replay: LegacyValueColumnReplay,
) -> Iterator[tuple[TableQualityFlag, TableFindingEvidence, dict[int, str]]]:
    """以分支曾交付的 v1 算法重算原报告身份。"""
    rows: dict[int, list[TableCell]] = defaultdict(list)
    for cell in result.grid.cells:
        rows[cell.row].append(cell)
    value_columns: dict[int, str] = {}
    for row in sorted(rows):
        labels = {}
        for cell in rows[row]:
            label = parameter_value_header_label(_cell_text(cell))
            if label is not None and cell.colspan == 1:
                labels[cell.column] = label
        if len(set(labels.values())) >= 2:
            value_columns = labels
            continue
        if not value_columns:
            continue
        for cell in rows[row]:
            if cell.is_header or cell.colspan < 2:
                continue
            end_column = cell.column + cell.colspan
            covered = {column: value_columns[column] for column in range(cell.column, end_column)
                       if column in value_columns}
            if len(covered) < 2 or not cell.runs or any(run.type != "text" for run in cell.runs):
                continue
            text = _cell_text(cell)
            rule_id, reason = LEGACY_VALUE_COLUMN_SPAN_AMBIGUOUS, "value_column_span"
            if replay == "shared_limits":
                if _LEGACY_SHARED_LIMIT_VALUE.fullmatch(text) is None or text.upper().endswith(("REF", "BSC")):
                    continue
                if (list(covered.values()) in (["min", "max"], ["low", "high"])
                        and not {"typ", "nom"}.intersection(value_columns.values())):
                    rule_id, reason = LEGACY_SHARED_LIMITS_RULE, "shared_limit_value"
            else:
                value = _LEGACY_SINGLE_VALUE.fullmatch(text)
                if value is None or (value["suffix"] or "").upper() in {"REF", "BSC"}:
                    continue
            flag, evidence = _finding_details(
                by_fragment[cell.source_fragment_id], policy, rule_id, reason, cell=cell,
                end_column=end_column, expected=1, actual=len(covered),
            )
            yield flag, evidence, covered


def iter_parameter_value_column_spans(
    result: TableBuildResult,
    policy: TableValidationPolicy,
    *,
    group: LogicalTableGroup | None = None,
    by_fragment: Mapping[str, TableFragmentReference] | None = None,
    validator_version: ValidatorVersion = BINDING_VALIDATOR_VERSION,
    legacy_value_column_replay: LegacyValueColumnReplay | None = None,
) -> Iterator[tuple[TableQualityFlag, TableFindingEvidence, dict[int, str]]]:
    """唯一来源为源 Grid；核定范围仅包括同一数值组中的完整占列。"""
    if by_fragment is None:
        by_fragment = {fragment.fragment_id: fragment for fragment in _fragment_references(result)}
    if legacy_value_column_replay:
        yield from _iter_legacy_value_column_spans(result, policy, by_fragment, legacy_value_column_replay)
        return
    rows_by_fragment: dict[str, dict[int, list[TableCell]]] = defaultdict(lambda: defaultdict(list))
    for cell in result.grid.cells:
        rows_by_fragment[cell.source_fragment_id][cell.source_row_index].append(cell)
    preceding = {item.to_fragment_id: item.from_fragment_id for item in group.continuation_relations
                 if item.kind == "verified_continuation"} if group is not None else {}
    headers: dict[str, _ParameterHeader] = {}
    for identity, fragment in by_fragment.items():
        rows = list(rows_by_fragment.get(identity, {}).values())
        if not rows:
            continue
        header = _parameter_header(rows, include_binding_groups=validator_version == BINDING_VALIDATOR_VERSION)
        previous = preceding.get(identity)
        if (header is None and previous in headers and by_fragment[previous].columns == fragment.columns
                and not any(cell.is_header for cell in rows[0])):
            # 已核验的同宽无头续片继承列义，位置和值取自本片。
            header = replace(headers[previous], row=-1)
        if header is None:
            continue
        headers[identity] = header
        unit_cell = None
        for row in rows:
            source_row = row[0].source_row_index
            if source_row <= header.row:
                continue
            unit_cell = next(
                (cell for cell in row if cell.column == header.unit_column and cell.colspan == 1), unit_cell,
            )
            unit = None
            if unit_cell is not None and source_row < unit_cell.source_row_index + unit_cell.rowspan:
                text = _cell_text(unit_cell)
                if is_measurement_unit(text):
                    unit = text
            for cell in row:
                if cell.is_header or cell.colspan < 2:
                    continue
                end = cell.column + cell.colspan
                covered = [header.columns[column] for column in range(cell.column, end) if column in header.columns]
                counts = Counter(item.group_start_column for item in covered)
                columns = tuple(item for item in covered if counts[item.group_start_column] >= 2)
                if not columns:
                    continue
                value = split_parameter_value(" ".join(_cell_text(cell).split()))
                if value is None:
                    continue
                token, inline_unit = value
                flag, evidence = _finding_details(
                    fragment, policy, VALUE_COLUMN_SPAN_AMBIGUOUS, "value_column_span_ambiguous", cell=cell,
                    end_column=end, value_column_span=ValueColumnSpan(value=token, unit=inline_unit or unit,
                                                                    columns=columns),
                )
                labels = {column.column: _REVIEW_LABEL_ALIASES.get(column.label, column.label.lower())
                          for column in columns} if len(counts) == 1 else {}
                yield flag, evidence, labels


def _unit_count(token: str) -> int:
    """完整合法 token 优先；最长 token 贪心扫描，不分配随组合数增长的路径。"""
    if token in MEASUREMENT_UNITS:
        return 1
    if len(token) > MAX_UNIT_TOKEN_CHARS:
        raise TableValidationError("table_validation_limit")
    index = count = 0
    while index < len(token):
        for unit in _UNIT_ORDER:
            if token.startswith(unit, index):
                index += len(unit)
                count += 1
                break
        else:
            return 0
    return count


def _unit_list_count(text: str) -> int:
    tokens = [item for item in re.split(r"[\s|,;]+", text.strip()) if item]
    if len(tokens) < 2:
        return 0
    # 复合单位保留分隔符作为合法边界，绝不去掉 '/' 后再判断粘连。
    if all(all(part in MEASUREMENT_UNITS for part in re.split(r"[/·⋅*√]+", token) if part)
           and any(character.isalpha() for character in token) for token in tokens):
        return len(tokens)
    return 0


class _TableValidator:
    def __init__(self, result: TableBuildResult, group: LogicalTableGroup, policy: TableValidationPolicy,
                 related_fragments: Mapping[str, TableFragment], finding_budget: int) -> None:
        self.result, self.group, self.policy = result, group, policy
        self.finding_budget = finding_budget
        self.fragments = _fragment_references(result)
        self.by_fragment = {item.fragment_id: item for item in self.fragments}
        self.cells = result.grid.cells
        self.by_cell = {cell.id: cell for cell in self.cells}
        self.cell_references = tuple(_cell_reference(cell) for cell in self.cells)
        self.related = []
        for identity in sorted({item.from_fragment_id for item in group.diagnostics} - self.by_fragment.keys()):
            source = related_fragments.get(identity)
            if source is None or source.fragment_id != identity:
                raise TableValidationError("table_validation_input")
            standalone = LogicalTableGroup(logical_group_id=group.logical_group_id, fragments=[source])
            built = build_table_grid(standalone, source_content_sha256=result.grid.source_content_sha256)
            self.related.append(_fragment_references(built)[0])
        self.related.sort(key=lambda item: item.source_index)
        self.findings: dict[str, TableFinding] = {}
        self.row_cells: dict[tuple[str, int], list[TableCell]] = defaultdict(list)
        for cell in self.cells:
            self.row_cells[(cell.source_fragment_id, cell.source_row_index)].append(cell)
        self.row_widths = {(fragment.fragment_id, row): fragment.columns for fragment in self.fragments
                           for row in range(fragment.row_count)}
        for diagnostic in result.diagnostics:
            if diagnostic.code == "table_grid_hole" and diagnostic.end_column == result.grid.columns:
                fragment = self.by_fragment[diagnostic.fragment_id]
                if diagnostic.column < fragment.columns:
                    self.row_widths[(fragment.fragment_id, diagnostic.source_row_index)] = diagnostic.column

    def emit(self, rule_id: str, reason: str, fragment_id: str, *, cell: TableCell | None = None, **location) -> None:
        flag, evidence = _finding_details(self.by_fragment[fragment_id], self.policy, rule_id, reason, cell=cell, **location)
        self._record_finding(flag, evidence)

    def _record_finding(self, flag: TableQualityFlag, evidence: TableFindingEvidence) -> None:
        identity = make_finding_id(self.result.grid.table_id, flag, evidence)
        # 重投不扣额度；在分配新的 finding 和序列化报告之前使用文档剩余额度。
        if identity not in self.findings and len(self.findings) >= self.finding_budget:
            raise TableValidationError("table_validation_limit")
        finding = TableFinding(finding_id=identity, flag=flag, evidence=evidence)
        previous = self.findings.get(finding.finding_id)
        if previous is not None and previous != finding:
            raise TableValidationError("table_validation_input")
        self.findings[finding.finding_id] = finding

    def structures(self) -> None:
        incoming = {relation.to_fragment_id: relation.from_fragment_id for relation in self.group.continuation_relations}
        severe_fragments = set()
        for fragment in self.fragments:
            rows = [cells for (identity, _), cells in self.row_cells.items() if identity == fragment.fragment_id]
            header_width = max((max(cell.column + cell.colspan for cell in cells) for cells in rows
                                if cells and all(cell.is_header for cell in cells)), default=0)
            data = [cells for cells in rows if cells and not all(cell.is_header for cell in cells)]
            underfilled = [cells for cells in data if all(cell.rowspan == cell.colspan == 1 for cell in cells) and
                           self.row_widths[(fragment.fragment_id, cells[0].source_row_index)] <= 2]
            if header_width >= 6 and len(data) >= 2 and len(underfilled) * 2 >= len(data):
                severe_fragments.add(fragment.fragment_id)
            if fragment.row_count and fragment.columns == 0:
                self.emit("table_zero_columns", "zero_columns", fragment.fragment_id)
        for diagnostic in self.result.diagnostics:
            code, identity = diagnostic.code, diagnostic.fragment_id
            if code in _IGNORED_DIAGNOSTICS:
                continue
            fragment = self.by_fragment[identity]
            if code == "table_grid_hole":
                if diagnostic.column >= fragment.columns or fragment.columns == 0:
                    continue
                end = min(diagnostic.end_column, fragment.columns)
                if end < fragment.columns:
                    self.emit("table_grid_hole", "internal_hole", identity, source_row_index=diagnostic.source_row_index,
                              row=diagnostic.row, column=diagnostic.column, end_column=end)
                else:
                    severe = identity in severe_fragments and diagnostic.column <= 2
                    self.emit("table_column_count_mismatch.severe_underfill" if severe else "table_column_count_mismatch",
                              "severe_underfill" if severe else "row_underfill", identity,
                              source_row_index=diagnostic.source_row_index, row=diagnostic.row,
                              column=diagnostic.column, expected=fragment.columns, actual=diagnostic.column)
                continue
            cell = self.by_cell.get(diagnostic.cell_id)
            location = {key: getattr(diagnostic, key) for key in (
                "run_id", "related_cell_id", "source_row_index", "source_cell_index", "row", "column", "end_column", "attribute"
            ) if getattr(diagnostic, key) is not None}
            if identity in incoming and code in {"table_html_missing", "table_html_empty"}:
                location["related_fragment_id"] = incoming[identity]
            self.emit(code, _DIAGNOSTIC_REASONS[code], identity, cell=cell, **location)

    def contents(self) -> None:
        id_columns: dict[str, set[int]] = defaultdict(set)
        value_columns: dict[str, set[int]] = defaultdict(set)
        unit_columns: dict[str, set[int]] = defaultdict(set)
        symbol_columns: dict[str, set[int]] = defaultdict(set)
        for cell in self.cells:
            if not cell.is_header:
                continue
            text = " ".join(_cell_text(cell).lower().split())
            columns = set(range(cell.column, cell.column + cell.colspan))
            if text in _ID_HEADERS:
                id_columns[cell.source_fragment_id].update(columns)
            if text in _VALUE_HEADERS:
                value_columns[cell.source_fragment_id].update(columns)
            if is_unit_header_label(text):
                unit_columns[cell.source_fragment_id].update(columns)
            if text in _SYMBOL_HEADERS:
                symbol_columns[cell.source_fragment_id].update(columns)
        for (identity, source_row), row in self.row_cells.items():
            unit_evidence: list[tuple[TableCell, int]] = []
            for cell in row:
                for segment in _segments(cell):
                    count = _unit_list_count(segment.text)
                    if count:
                        unit_evidence.append((cell, count))
                    for match in _UNIT_WORD.finditer(segment.text):
                        token = match.group(1)
                        # 斜线/乘点/根号两侧是复合单位；VA 等本身也优先作为完整单位。
                        if ((match.start(1) and segment.text[match.start(1) - 1] in "/·⋅*√") or
                                (match.end(1) < len(segment.text) and segment.text[match.end(1)] in "/·⋅*√")):
                            continue
                        # 同行数字不足以证明单位语境；全大写符号只在显式单位列/数值后扫描。
                        # 无表头的 pspsMHz 仍有小写单位证据，Symbol 列则属于器件符号。
                        context = (cell.column not in symbol_columns[identity] and (
                            cell.column in unit_columns[identity] or match.start(1) > match.start() or
                            (segment.text.strip() == token and any(character.islower() for character in token))))
                        if not context:
                            continue
                        count = _unit_count(token)
                        if count < 2:
                            continue
                        ranges = segment.ranges(match.start(1), match.end(1))
                        self.emit("table_unit_glued", "glued_units", identity, cell=cell, unit_count=count,
                                  run_id=ranges[0].run_id, start_char=match.start(1), end_char=match.end(1), run_ranges=ranges)
                        unit_evidence.append((cell, count))
            expected_value_columns = value_columns[identity]
            for cell in row:
                if cell.is_header or cell.column in id_columns[identity]:
                    continue
                for segment in _segments(cell):
                    if _RANGE.fullmatch(segment.text):
                        continue
                    for match in _NUMBER.finditer(segment.text):
                        token = match.group().lstrip("+-")
                        if (not token.isascii() or not token.isdigit() or len(token) < self.policy.long_number_min_digits or
                                (len(token) in {8, 16, 32, 64} and set(token) <= {"0", "1"})):
                            continue
                        ranges = segment.ranges(match.start(), match.end())
                        location = dict(cell=cell, digit_count=len(token), run_id=ranges[0].run_id,
                                        start_char=match.start(), end_char=match.end(), run_ranges=ranges)
                        supporting = next(((other, count) for other, count in unit_evidence if other.id != cell.id), None)
                        if supporting is not None:
                            other, count = supporting
                            self.emit("table_number_glued", "repeated_units", identity, **location,
                                      related_cell_id=other.id, unit_count=count, expected=count, actual=1)
                        elif (len(expected_value_columns) >= 2 and cell.colspan == cell.rowspan == 1 and
                              cell.column in expected_value_columns and
                              self.row_widths[(identity, source_row)] < self.by_fragment[identity].columns):
                            self.emit("table_number_glued", "compressed_value_columns", identity, **location,
                                      expected=self.by_fragment[identity].columns,
                                      actual=self.row_widths[(identity, source_row)])
                        else:
                            self.emit("table_abnormal_long_number", "long_decimal", identity, **location)

    def continuations(self) -> None:
        all_fragments = {item.fragment_id: item for item in (*self.fragments, *self.related)}
        emitted_pairs = set()
        for relation in self.group.continuation_relations:
            before = self.by_fragment.get(relation.from_fragment_id)
            after = self.by_fragment.get(relation.to_fragment_id)
            if before is None or after is None or before.source_index >= after.source_index:
                raise TableValidationError("table_validation_input")
            if before.columns and after.columns and before.columns != after.columns:
                self.emit("table_cross_page_inconsistent.column_mismatch", "column_mismatch", after.fragment_id,
                          related_fragment_id=before.fragment_id, expected=before.columns, actual=after.columns)
                emitted_pairs.add((before.fragment_id, after.fragment_id, "column_mismatch"))
        for diagnostic in self.group.diagnostics:
            before, after = all_fragments.get(diagnostic.from_fragment_id), self.by_fragment.get(diagnostic.to_fragment_id)
            if before is None or after is None or before.source_index >= after.source_index:
                raise TableValidationError("table_validation_input")
            if (before.fragment_id, after.fragment_id, diagnostic.reason) in emitted_pairs:
                continue
            if after.html_state != "present":
                continue
            if diagnostic.reason in {"column_mismatch", "header_mismatch"}:
                self.emit("table_cross_page_inconsistent." + diagnostic.reason, diagnostic.reason, after.fragment_id,
                          related_fragment_id=before.fragment_id,
                          expected=before.columns if diagnostic.reason == "column_mismatch" else None,
                          actual=after.columns if diagnostic.reason == "column_mismatch" else None)
            else:
                self.emit("table_continuation_uncertain", diagnostic.reason, after.fragment_id, related_fragment_id=before.fragment_id)

    def validate(self, validator_version: ValidatorVersion, *, legacy_value_column_replay: LegacyValueColumnReplay | None) -> TableValidationReport:
        self.structures()
        self.contents()
        if validator_version != LEGACY_VALIDATOR_VERSION or legacy_value_column_replay:
            for flag, evidence, _ in iter_parameter_value_column_spans(
                self.result, self.policy, group=self.group, by_fragment=self.by_fragment,
                validator_version=validator_version, legacy_value_column_replay=legacy_value_column_replay,
            ):
                self._record_finding(flag, evidence)
        self.continuations()
        return make_table_report(table_id=self.result.grid.table_id,
                                 source_content_sha256=self.result.grid.source_content_sha256,
                                 raw_html_sha256=self.result.grid.raw_html_sha256, policy=self.policy,
                                 fragments=self.fragments, related_fragments=tuple(
                                     item for item in self.related if any(
                                         finding.evidence.related_fragment_id == item.fragment_id
                                         for finding in self.findings.values())), cells=self.cell_references,
                                 findings=tuple(self.findings.values()), validator_version=validator_version)


def validate_table(result: TableBuildResult, group: LogicalTableGroup, *, policy: TableValidationPolicy | None = None,
                   related_fragments: Mapping[str, TableFragment] | None = None,
                   source_content_sha256: str | None = None,
                   validator_version: ValidatorVersion = VALIDATOR_VERSION,
                   legacy_value_column_replay: LegacyValueColumnReplay | None = None,
                   _remaining_findings: int | None = None) -> TableValidationReport:
    """重新校验可变输入；构建事实复用原 builder，译文与既有 flags 不参与检查。"""
    if (validator_version not in (LEGACY_VALIDATOR_VERSION, VALIDATOR_VERSION, BINDING_VALIDATOR_VERSION)
            or legacy_value_column_replay and validator_version != LEGACY_VALIDATOR_VERSION
            or not isinstance(result, TableBuildResult) or not isinstance(result.grid, TableGrid) or
            not isinstance(group, LogicalTableGroup)):
        raise TableValidationError("table_validation_input")
    if policy is not None and not isinstance(policy, TableValidationPolicy):
        raise TableValidationError("table_validation_config")
    selected = TableValidationPolicy.model_validate(
        (policy or default_table_validation_policy(validator_version)).model_dump(warnings=False),
    )
    grid = TableGrid.model_validate(result.grid)
    if (result.normalizer_version != NORMALIZER_VERSION or grid.table_id != group.logical_group_id or
            (source_content_sha256 is not None and source_content_sha256 != grid.source_content_sha256) or
            not isinstance(result.diagnostics, tuple) or
            any(not isinstance(item, TableDiagnostic) or item.code not in get_args(DiagnosticCode) for item in result.diagnostics)):
        raise TableValidationError("table_validation_input")
    for diagnostic in result.diagnostics:
        if (any(value is not None and type(value) is not int for value in (
                diagnostic.source_row_index, diagnostic.source_cell_index, diagnostic.row,
                diagnostic.column, diagnostic.end_column)) or
                any(value is not None and not isinstance(value, str) for value in (
                    diagnostic.fragment_id, diagnostic.cell_id, diagnostic.run_id, diagnostic.related_cell_id)) or
                diagnostic.attribute not in (None, "rowspan", "colspan")):
            raise TableValidationError("table_validation_input")
    try:
        checked_group = LogicalTableGroup.model_validate(group.model_dump(warnings=False), strict=True)
        checked_related = {identity: TableFragment.model_validate(source.model_dump(warnings=False), strict=True)
                           for identity, source in (related_fragments or {}).items()}
    except (ValidationError, ValueError, TypeError, AttributeError):
        raise TableValidationError("table_validation_input") from None
    expected = build_table_grid(checked_group, source_content_sha256=grid.source_content_sha256)
    # 复用唯一构建 owner 核对诊断遗漏、坐标伪造及 normalized 快照；允许重复投递同一诊断。
    # target/flags 是下游拥有的可变值，只读保留，不据此改写源质量。
    if (_source_grid_signature(grid) != _source_grid_signature(expected.grid) or
            result.normalized_fragments != expected.normalized_fragments or
            set(result.diagnostics) != set(expected.diagnostics)):
        raise TableValidationError("table_validation_input")
    checked = TableBuildResult(result.normalizer_version, grid, result.normalized_fragments, result.diagnostics)
    budget = selected.max_findings if _remaining_findings is None else _remaining_findings
    if type(budget) is not int or not 0 <= budget <= selected.max_findings:
        raise TableValidationError("table_validation_input")
    return _TableValidator(checked, checked_group, selected, checked_related, budget).validate(
        validator_version, legacy_value_column_replay=legacy_value_column_replay,
    )


def document_table_validator_version(document: DocumentIR) -> ValidatorVersion:
    metadata = document.metadata
    if metadata.legacy_value_column_replay is not None:
        return LEGACY_VALIDATOR_VERSION
    if metadata.pdf_value_column_unresolved or any(
        fragment.value_column_review is not None for group in metadata.logical_table_groups for fragment in group.fragments
    ):
        return BINDING_VALIDATOR_VERSION
    return VALIDATOR_VERSION


def validate_document_tables(document: DocumentIR, *, policy: TableValidationPolicy | None = None,
                             validator_version: ValidatorVersion | None = None,
                             legacy_value_column_replay: LegacyValueColumnReplay | None = None) -> TableQualityContribution:
    """正式 DocumentIR 来源账本的显式 producer；旧 IR 返回未评估。"""
    if not isinstance(document, DocumentIR):
        raise TableValidationError("table_validation_input")
    if policy is not None and not isinstance(policy, TableValidationPolicy):
        raise TableValidationError("table_validation_config")
    try:
        checked = DocumentIR.model_validate(document.model_dump(warnings=False), strict=True)
    except (ValidationError, ValueError, KeyError, TypeError, UnicodeError):
        raise TableValidationError("table_validation_input") from None
    validator_version = validator_version or document_table_validator_version(checked)
    legacy_value_column_replay = legacy_value_column_replay or checked.metadata.legacy_value_column_replay
    selected = TableValidationPolicy.model_validate(
        (policy or default_table_validation_policy(validator_version)).model_dump(warnings=False),
    )
    metadata = checked.metadata
    source_hash = metadata.mineru_validation.content_list_sha256 if metadata.mineru_validation is not None else None
    if metadata.logical_table_groups_version is None:
        return aggregate_table_quality((), expected_table_ids=(), source_content_sha256=source_hash,
                                       source_groups_version=None, expected_fragment_count=None, policy=selected,
                                       validator_version=validator_version)
    if metadata.logical_table_groups_version != GROUPS_VERSION or source_hash is None:
        raise TableValidationError("table_validation_input")
    fragments = {fragment.fragment_id: fragment for group in metadata.logical_table_groups for fragment in group.fragments}
    reports = []
    count = 0
    for group in metadata.logical_table_groups:
        report = validate_table(build_table_grid(group, source_content_sha256=source_hash), group, policy=selected,
                                related_fragments=fragments, source_content_sha256=source_hash,
                                validator_version=validator_version,
                                legacy_value_column_replay=legacy_value_column_replay,
                                _remaining_findings=selected.max_findings - count)
        reports.append(report)
        count += len(report.findings)
        if count > selected.max_findings:
            raise TableValidationError("table_validation_limit")
    return aggregate_table_quality(reports, expected_table_ids=[group.logical_group_id for group in metadata.logical_table_groups],
                                   source_content_sha256=source_hash, source_groups_version=GROUPS_VERSION,
                                   expected_fragment_count=metadata.logical_table_group_counts["fragment_count"], policy=selected,
                                   validator_version=validator_version)
