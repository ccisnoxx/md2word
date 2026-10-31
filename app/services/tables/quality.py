"""表格验证的纯值合同、严重度策略与独立质量贡献，不决定任务发布状态。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ModelWrapValidatorHandler, ValidationError, ValidationInfo, model_validator
from pydantic_core import PydanticCustomError

from app.services.tables.models import (
    CellId, FragmentId, NonNegativeInt, PositiveInt, RunId, RunType, Sha256,
    TableQualityFlag, canonical_sha256, make_cell_id, make_run_id,
)


VALIDATOR_VERSION = "table-validator/v1"
NORMALIZER_VERSION = "table-html/v1"
POLICY_VERSION = "table-validation-policy/v1"
GROUPS_VERSION = "logical-table-groups/v1"
TableId = Annotated[str, Field(pattern=r"^logical-table:[0-9a-f]{64}$")]
Severity = Literal["warning", "blocker"]
ValidationErrorCode = Literal["table_validation_input", "table_validation_config", "table_validation_limit"]

RULE_DEFAULTS: dict[str, Severity] = {
    "table_html_missing": "blocker", "table_html_empty": "blocker", "table_html_no_rows": "blocker",
    "table_zero_columns": "blocker", "table_span_collision": "blocker", "table_span_out_of_bounds": "blocker",
    "table_grid_hole": "blocker", "table_column_count_mismatch": "warning",
    "table_column_count_mismatch.severe_underfill": "blocker", "table_number_glued": "blocker",
    "table_unit_glued": "blocker", "table_abnormal_long_number": "warning",
    "table_cross_page_inconsistent.column_mismatch": "blocker",
    "table_cross_page_inconsistent.header_mismatch": "warning", "table_continuation_uncertain": "warning",
    "table_span_invalid": "warning", "table_html_removed_unsafe": "warning",
    "table_formula_unresolved": "warning", "table_nested_script": "warning",
}
HARD_BLOCKERS = frozenset({"table_html_missing", "table_html_empty", "table_html_no_rows", "table_zero_columns",
                           "table_span_collision", "table_span_out_of_bounds"})
RULE_CODES = {rule: rule.split(".")[0] for rule in RULE_DEFAULTS}
CODES = frozenset(RULE_CODES.values())
Reason = Literal[
    "missing", "empty", "no_rows", "zero_columns", "span_collision", "span_out_of_bounds", "internal_hole",
    "row_underfill", "severe_underfill", "repeated_units", "compressed_value_columns", "glued_units",
    "long_decimal", "column_mismatch", "header_mismatch", "missing_geometry", "geometry_mismatch",
    "page_not_adjacent", "page_body_boundary", "insufficient_evidence", "unreliable_columns",
    "invalid_span", "unsafe_removed", "formula_unresolved", "nested_script",
]
RULE_REASONS = {
    "table_html_missing": {"missing"}, "table_html_empty": {"empty"}, "table_html_no_rows": {"no_rows"},
    "table_zero_columns": {"zero_columns"}, "table_span_collision": {"span_collision"},
    "table_span_out_of_bounds": {"span_out_of_bounds"}, "table_grid_hole": {"internal_hole"},
    "table_column_count_mismatch": {"row_underfill"},
    "table_column_count_mismatch.severe_underfill": {"severe_underfill"},
    "table_number_glued": {"repeated_units", "compressed_value_columns"},
    "table_unit_glued": {"glued_units"}, "table_abnormal_long_number": {"long_decimal"},
    "table_cross_page_inconsistent.column_mismatch": {"column_mismatch"},
    "table_cross_page_inconsistent.header_mismatch": {"header_mismatch"},
    "table_continuation_uncertain": {"missing_geometry", "geometry_mismatch", "page_not_adjacent",
                                      "page_body_boundary", "insufficient_evidence", "unreliable_columns"},
    "table_span_invalid": {"invalid_span"}, "table_html_removed_unsafe": {"unsafe_removed"},
    "table_formula_unresolved": {"formula_unresolved"}, "table_nested_script": {"nested_script"},
}


class TableValidationError(ValueError):
    """调用边界只暴露固定码；不把上游异常、原文或任意配置键拼入错误。"""

    def __init__(self, code: ValidationErrorCode) -> None:
        self.code = code
        super().__init__(f"表格验证失败：{code}。")


def _invalid(code: ValidationErrorCode = "table_validation_input") -> None:
    raise PydanticCustomError(code, f"表格验证合同无效：{code}。")


class _QualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              allow_inf_nan=False, revalidate_instances="always")
    failure_code: ClassVar[ValidationErrorCode] = "table_validation_input"
    json_tuple_fields: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="before")
    @classmethod
    def _json_arrays(cls, value: object, info: ValidationInfo) -> object:
        # wrap validator 的 Python handler 不保留 strict tuple 的 JSON 特例。
        # 只恢复已声明数组字段的 JSON 表达，不放宽 bool/数值或 Python 输入。
        if info.mode == "json" and isinstance(value, dict):
            return {key: tuple(item) if key in cls.json_tuple_fields and isinstance(item, list) else item
                    for key, item in value.items()}
        return value

    @model_validator(mode="wrap")
    @classmethod
    def _safe_validation(cls, value: object, handler: ModelWrapValidatorHandler[Self]) -> Self:
        try:
            return handler(value)
        except ValidationError:
            # 连 loc 也不沿用：映射 key 或未知字段可能本身就是凭证/原文。
            raise ValidationError.from_exception_data(cls.__name__, [{
                "type": PydanticCustomError(cls.failure_code, f"表格验证合同无效：{cls.failure_code}。"),
                "loc": ("__contract__",), "input": None,
            }], hide_input=True) from None


class TableValidationPolicy(_QualityModel):
    """可追溯的显式策略；仅启发式允许分级，硬结构损坏不能降级。"""

    failure_code: ClassVar[ValidationErrorCode] = "table_validation_config"
    version: Literal["table-validation-policy/v1"] = POLICY_VERSION
    long_number_min_digits: Annotated[int, Field(ge=8, le=64)] = 10
    max_findings: Annotated[int, Field(ge=1, le=100_000)] = 100_000
    code_severities: dict[str, Severity] = Field(default_factory=dict)
    rule_severities: dict[str, Severity] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_overrides(self) -> Self:
        if (not self.code_severities.keys() <= CODES or not self.rule_severities.keys() <= RULE_DEFAULTS.keys() or
                any(code in HARD_BLOCKERS and severity != "blocker" for code, severity in self.code_severities.items()) or
                any(RULE_CODES[rule] in HARD_BLOCKERS and severity != "blocker"
                    for rule, severity in self.rule_severities.items())):
            _invalid("table_validation_config")
        return self

    @property
    def policy_sha256(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", warnings=False))

    def severity_for(self, rule_id: str) -> Severity:
        if rule_id not in RULE_DEFAULTS:
            raise TableValidationError("table_validation_config")
        return self.rule_severities.get(rule_id, self.code_severities.get(RULE_CODES[rule_id], RULE_DEFAULTS[rule_id]))


class TableFragmentReference(_QualityModel):
    """报告仅保留来源定位及指纹，不复制 HTML、题注或原始属性。"""

    json_tuple_fields: ClassVar[tuple[str, ...]] = ("bbox",)
    fragment_id: FragmentId
    source_index: NonNegativeInt
    json_pointer: Annotated[str, Field(pattern=r"^/(?:content_list/)?(?:0|[1-9][0-9]*)(?:/(?:0|[1-9][0-9]*))?$")]
    page_index: NonNegativeInt | None
    bbox: tuple[float, float, float, float] | None
    html_state: Literal["missing", "empty", "present"]
    raw_html_sha256: Sha256 | None
    row_start: NonNegativeInt
    row_count: NonNegativeInt
    columns: NonNegativeInt

    @model_validator(mode="after")
    def _check_state(self) -> Self:
        if ((self.html_state == "missing") != (self.raw_html_sha256 is None) or
                (self.html_state != "present" and (self.row_count or self.columns))):
            _invalid()
        return self


class TableRunReference(_QualityModel):
    id: RunId
    source_run_index: NonNegativeInt
    type: RunType
    length: NonNegativeInt


class TableCellReference(_QualityModel):
    json_tuple_fields: ClassVar[tuple[str, ...]] = ("runs",)
    id: CellId
    fragment_id: FragmentId
    source_row_index: NonNegativeInt
    source_cell_index: NonNegativeInt
    row: NonNegativeInt
    column: NonNegativeInt
    rowspan: PositiveInt
    colspan: PositiveInt
    is_header: bool
    content_sha256: Sha256
    runs: tuple[TableRunReference, ...]

    @model_validator(mode="after")
    def _check_identity(self) -> Self:
        if (self.id != make_cell_id(self.fragment_id, self.source_row_index, self.source_cell_index) or
                [run.source_run_index for run in self.runs] != sorted({run.source_run_index for run in self.runs}) or
                any(run.id != make_run_id(self.id, run.source_run_index) for run in self.runs)):
            _invalid()
        return self


class TableRunRange(_QualityModel):
    run_id: RunId
    start_char: NonNegativeInt
    end_char: PositiveInt

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.end_char <= self.start_char:
            _invalid()
        return self


class TableFindingEvidence(_QualityModel):
    json_tuple_fields: ClassVar[tuple[str, ...]] = ("bbox", "run_ranges")
    rule_id: str
    reason: Reason
    fragment_id: FragmentId
    related_fragment_id: FragmentId | None = None
    cell_id: CellId | None = None
    related_cell_id: CellId | None = None
    run_id: RunId | None = None
    source_row_index: NonNegativeInt | None = None
    source_cell_index: NonNegativeInt | None = None
    row: NonNegativeInt | None = None
    column: NonNegativeInt | None = None
    end_column: PositiveInt | None = None
    source_index: NonNegativeInt
    json_pointer: Annotated[str, Field(pattern=r"^/(?:content_list/)?(?:0|[1-9][0-9]*)(?:/(?:0|[1-9][0-9]*))?$")]
    page_index: NonNegativeInt | None
    bbox: tuple[float, float, float, float] | None
    expected: NonNegativeInt | None = None
    actual: NonNegativeInt | None = None
    digit_count: PositiveInt | None = None
    unit_count: PositiveInt | None = None
    start_char: NonNegativeInt | None = None
    end_char: PositiveInt | None = None
    run_ranges: tuple[TableRunRange, ...] = ()
    attribute: Literal["rowspan", "colspan"] | None = None

    @model_validator(mode="after")
    def _check_rule(self) -> Self:
        if self.rule_id not in RULE_REASONS or self.reason not in RULE_REASONS[self.rule_id]:
            _invalid()
        if ((self.start_char is None) != (self.end_char is None) or
                (self.start_char is not None and self.end_char <= self.start_char) or
                (self.end_column is not None and (self.column is None or self.end_column <= self.column))):
            _invalid()
        return self


def make_finding_id(table_id: str, flag: TableQualityFlag, evidence: TableFindingEvidence) -> str:
    """身份不含 severity/策略；同对象的不同字符区间仍是不同问题。"""
    return "table-finding:" + canonical_sha256([
        "table-finding/v1", table_id, flag.code, flag.fragment_id, flag.cell_id, flag.run_id,
        evidence.related_fragment_id, evidence.related_cell_id, evidence.source_row_index,
        evidence.source_cell_index, evidence.row, evidence.column, evidence.end_column,
        evidence.start_char, evidence.end_char,
        [[item.run_id, item.start_char, item.end_char] for item in evidence.run_ranges], evidence.attribute,
    ])


class TableFinding(_QualityModel):
    finding_id: Annotated[str, Field(pattern=r"^table-finding:[0-9a-f]{64}$")]
    flag: TableQualityFlag
    evidence: TableFindingEvidence

    @model_validator(mode="after")
    def _check_flag(self) -> Self:
        evidence = self.evidence
        if (self.flag.code != RULE_CODES[evidence.rule_id] or
                (self.flag.fragment_id, self.flag.cell_id, self.flag.run_id) !=
                (evidence.fragment_id, evidence.cell_id, evidence.run_id)):
            _invalid()
        return self


def finding_sort_key(finding: TableFinding, fragment_order: Mapping[str, int], run_order: Mapping[str, int]) -> tuple:
    evidence = finding.evidence
    return (fragment_order[evidence.fragment_id],
            evidence.source_row_index if evidence.source_row_index is not None else -1,
            evidence.source_cell_index if evidence.source_cell_index is not None else -1,
            run_order.get(evidence.run_id, -1), finding.flag.code,
            fragment_order.get(evidence.related_fragment_id, -1), evidence.related_cell_id or "",
            evidence.row if evidence.row is not None else -1, evidence.column if evidence.column is not None else -1,
            evidence.start_char if evidence.start_char is not None else -1,
            evidence.end_char if evidence.end_char is not None else -1, finding.finding_id)


def _ordered_findings(findings: Sequence[TableFinding], fragments: Sequence[TableFragmentReference],
                      cells: Sequence[TableCellReference]) -> tuple[TableFinding, ...]:
    fragment_order = {item.fragment_id: item.source_index for item in fragments}
    run_order = {run.id: run.source_run_index for cell in cells for run in cell.runs}
    return tuple(sorted(findings, key=lambda item: finding_sort_key(item, fragment_order, run_order)))


def source_binding_sha256(table_id: str, source_hash: str, raw_hash: str,
                          fragments: Sequence[TableFragmentReference], related: Sequence[TableFragmentReference],
                          cells: Sequence[TableCellReference]) -> str:
    return canonical_sha256(["table-validation-sources/v1", table_id, source_hash, raw_hash,
                             [item.model_dump(mode="json", warnings=False) for item in fragments],
                             [item.model_dump(mode="json", warnings=False) for item in related],
                             [item.model_dump(mode="json", warnings=False) for item in cells]])


class TableValidationReport(_QualityModel):
    """自洽可重读的单表报告；hash 绑定快照，不是签名或来源授权。"""

    json_tuple_fields: ClassVar[tuple[str, ...]] = ("fragments", "related_fragments", "cells", "findings")
    schema_version: Literal["table-validation/v1"]
    validator_version: Literal["table-validator/v1"]
    normalizer_version: Literal["table-html/v1"]
    table_id: TableId
    source_content_sha256: Sha256
    raw_html_sha256: Sha256
    policy: TableValidationPolicy
    policy_sha256: Sha256
    source_binding_sha256: Sha256
    fragments: Annotated[tuple[TableFragmentReference, ...], Field(min_length=1)]
    related_fragments: tuple[TableFragmentReference, ...]
    cells: tuple[TableCellReference, ...]
    findings: tuple[TableFinding, ...]
    report_sha256: Sha256

    @model_validator(mode="after")
    def _check_report(self) -> Self:
        fragments = {item.fragment_id: item for item in self.fragments}
        related = {item.fragment_id: item for item in self.related_fragments}
        all_fragments = {**fragments, **related}
        if (len(fragments) != len(self.fragments) or len(related) != len(self.related_fragments) or
                fragments.keys() & related.keys() or
                len({item.json_pointer for item in all_fragments.values()}) != len(all_fragments) or
                len({item.source_index for item in all_fragments.values()}) != len(all_fragments) or
                [item.source_index for item in self.fragments] != sorted(item.source_index for item in self.fragments) or
                [item.source_index for item in self.related_fragments] != sorted(item.source_index for item in self.related_fragments)):
            _invalid()
        offset = 0
        for fragment in self.fragments:
            if fragment.row_start != offset:
                _invalid()
            offset += fragment.row_count
        raw_hash = canonical_sha256(["table-raw-html-set/v1", [
            [item.fragment_id, item.html_state, item.raw_html_sha256] for item in self.fragments]])
        if (self.raw_html_sha256 != raw_hash or self.policy_sha256 != self.policy.policy_sha256 or
                self.source_binding_sha256 != source_binding_sha256(
                    self.table_id, self.source_content_sha256, raw_hash, self.fragments, self.related_fragments, self.cells)):
            _invalid()
        cells = {cell.id: cell for cell in self.cells}
        positions = []
        runs = {}
        segment_offsets = {}
        row_positions: dict[tuple[str, int], list[int]] = {}
        fragment_widths = {identity: 0 for identity in fragments}
        for cell in self.cells:
            fragment = fragments.get(cell.fragment_id)
            if (fragment is None or cell.source_row_index >= fragment.row_count or
                    cell.row != fragment.row_start + cell.source_row_index or cell.column + cell.colspan > fragment.columns):
                _invalid()
            positions.append((fragment.source_index, cell.source_row_index, cell.source_cell_index))
            row_positions.setdefault((cell.fragment_id, cell.source_row_index), []).append(cell.source_cell_index)
            fragment_widths[cell.fragment_id] = max(fragment_widths[cell.fragment_id], cell.column + cell.colspan)
            if [run.source_run_index for run in cell.runs] != list(range(len(cell.runs))):
                _invalid()
            segment_offset = 0
            for run in cell.runs:
                if run.id in runs:
                    _invalid()
                runs[run.id] = (cell, run)
                if run.type == "text":
                    segment_offsets[run.id] = segment_offset
                    segment_offset += run.length
                else:
                    segment_offset = 0
        if (len(cells) != len(self.cells) or positions != sorted(set(positions)) or
                any(indices != list(range(len(indices))) for indices in row_positions.values()) or
                any(fragment.columns != fragment_widths[fragment.fragment_id] for fragment in self.fragments)):
            _invalid()
        related_used = set()
        for finding in self.findings:
            evidence = finding.evidence
            fragment = fragments.get(evidence.fragment_id)
            if (fragment is None or
                    (evidence.source_index, evidence.json_pointer, evidence.page_index, evidence.bbox) !=
                    (fragment.source_index, fragment.json_pointer, fragment.page_index, fragment.bbox) or
                    (evidence.related_fragment_id is not None and evidence.related_fragment_id not in all_fragments) or
                    finding.flag.severity != self.policy.severity_for(evidence.rule_id) or
                    finding.finding_id != make_finding_id(self.table_id, finding.flag, evidence)):
                _invalid()
            cell = cells.get(evidence.cell_id)
            if evidence.related_fragment_id is not None:
                related_used.add(evidence.related_fragment_id)
            if evidence.cell_id is not None:
                if (cell is None or cell.fragment_id != fragment.fragment_id or
                        (evidence.source_row_index, evidence.source_cell_index) !=
                        (cell.source_row_index, cell.source_cell_index)):
                    _invalid()
            if evidence.related_cell_id is not None:
                other = cells.get(evidence.related_cell_id)
                if other is None or (evidence.related_fragment_id is not None and other.fragment_id != evidence.related_fragment_id):
                    _invalid()
            if evidence.row is not None and not fragment.row_start <= evidence.row < fragment.row_start + fragment.row_count:
                _invalid()
            if evidence.source_row_index is not None and (evidence.source_row_index >= fragment.row_count or
                    (evidence.row is not None and evidence.row != fragment.row_start + evidence.source_row_index)):
                # collision 的 row 可位于 rowspan 内，source_row_index 仍指向锚点。
                if cell is None or evidence.row is None or not cell.row <= evidence.row < cell.row + cell.rowspan:
                    _invalid()
            if evidence.column is not None and evidence.column >= fragment.columns:
                _invalid()
            if evidence.end_column is not None and evidence.end_column > fragment.columns:
                _invalid()
            if evidence.run_id is not None and (evidence.run_id not in runs or runs[evidence.run_id][0].id != evidence.cell_id):
                _invalid()
            last = (-1, -1)
            previous_range = None
            for run_range in evidence.run_ranges:
                pair = runs.get(run_range.run_id)
                if pair is None or pair[0].id != evidence.cell_id or pair[1].type != "text" or run_range.end_char > pair[1].length:
                    _invalid()
                position = (pair[1].source_run_index, run_range.start_char)
                if position <= last:
                    _invalid()
                if previous_range is not None and (position[0] != last[0] + 1 or run_range.start_char != 0 or
                        previous_range.end_char != runs[previous_range.run_id][1].length):
                    _invalid()
                last = position
                previous_range = run_range
            if evidence.run_ranges and evidence.run_id != evidence.run_ranges[0].run_id:
                _invalid()
            if evidence.run_ranges and (evidence.start_char is None or
                    sum(item.end_char - item.start_char for item in evidence.run_ranges) != evidence.end_char - evidence.start_char):
                _invalid()
            if evidence.run_ranges:
                # start/end 是当前连续 text 段的偏移；公式、上下标和 br 都重置起点。
                first_range, last_range = evidence.run_ranges[0], evidence.run_ranges[-1]
                if (evidence.start_char != segment_offsets[first_range.run_id] + first_range.start_char or
                        evidence.end_char != segment_offsets[last_range.run_id] + last_range.end_char):
                    _invalid()
            if evidence.rule_id in {"table_number_glued", "table_abnormal_long_number", "table_unit_glued"}:
                if cell is None or not evidence.run_ranges or evidence.start_char is None:
                    _invalid()
                if evidence.rule_id != "table_unit_glued" and (
                        evidence.digit_count is None or evidence.digit_count < self.policy.long_number_min_digits):
                    _invalid()
            if evidence.rule_id == "table_number_glued":
                if evidence.reason == "repeated_units":
                    other = cells.get(evidence.related_cell_id)
                    if (other is None or cell is None or other.id == cell.id or other.fragment_id != cell.fragment_id or
                            other.source_row_index != cell.source_row_index or evidence.unit_count is None or
                            evidence.unit_count < 2 or evidence.expected != evidence.unit_count or evidence.actual != 1):
                        _invalid()
                elif evidence.expected is None or evidence.actual is None or evidence.expected <= evidence.actual:
                    _invalid()
            if evidence.rule_id == "table_unit_glued" and (evidence.unit_count is None or evidence.unit_count < 2):
                _invalid()
            if evidence.rule_id == "table_span_collision":
                other = cells.get(evidence.related_cell_id)
                if (cell is None or other is None or cell.fragment_id != other.fragment_id or
                        evidence.row is None or evidence.column is None or not all(
                            owner.row <= evidence.row < owner.row + owner.rowspan and
                            owner.column <= evidence.column < owner.column + owner.colspan for owner in (cell, other))):
                    _invalid()
            if evidence.rule_id == "table_span_out_of_bounds" and (cell is None or
                    cell.source_row_index + cell.rowspan <= fragment.row_count):
                _invalid()
            if evidence.rule_id == "table_span_invalid" and evidence.attribute is None:
                _invalid()
            if ((evidence.rule_id == "table_html_missing" and fragment.html_state != "missing") or
                    (evidence.rule_id == "table_html_empty" and fragment.html_state != "empty") or
                    (evidence.rule_id == "table_html_no_rows" and (fragment.html_state != "present" or fragment.row_count)) or
                    (evidence.rule_id == "table_zero_columns" and (not fragment.row_count or fragment.columns))):
                _invalid()
            if evidence.rule_id.startswith("table_column_count_mismatch") and (
                    evidence.expected != fragment.columns or evidence.actual != evidence.column or
                    evidence.actual is None or evidence.actual >= evidence.expected):
                _invalid()
            if evidence.rule_id.startswith("table_cross_page") or evidence.rule_id == "table_continuation_uncertain":
                if evidence.related_fragment_id is None or all_fragments[evidence.related_fragment_id].source_index >= fragment.source_index:
                    _invalid()
        if set(related) - related_used:
            _invalid()
        if (len({finding.finding_id for finding in self.findings}) != len(self.findings) or
                _ordered_findings(self.findings, tuple(all_fragments.values()), self.cells) != self.findings):
            _invalid()
        if len(self.findings) > self.policy.max_findings:
            _invalid()
        if self.report_sha256 != canonical_sha256(["table-validation-report/v1", self.model_dump(mode="json", warnings=False, exclude={"report_sha256"})]):
            _invalid()
        return self


def make_table_report(*, table_id: str, source_content_sha256: str, raw_html_sha256: str,
                      policy: TableValidationPolicy, fragments: tuple[TableFragmentReference, ...],
                      related_fragments: tuple[TableFragmentReference, ...], cells: tuple[TableCellReference, ...],
                      findings: Sequence[TableFinding]) -> TableValidationReport:
    """只在生产者完成检查后封装；重读仍执行全部跨字段校验。"""
    ordered = _ordered_findings(findings, fragments + related_fragments, cells)
    payload = dict(schema_version="table-validation/v1", validator_version=VALIDATOR_VERSION,
                   normalizer_version=NORMALIZER_VERSION, table_id=table_id,
                   source_content_sha256=source_content_sha256, raw_html_sha256=raw_html_sha256,
                   policy=policy.model_dump(mode="json", warnings=False), policy_sha256=policy.policy_sha256,
                   source_binding_sha256=source_binding_sha256(table_id, source_content_sha256, raw_html_sha256,
                                                              fragments, related_fragments, cells),
                   fragments=[item.model_dump(mode="json", warnings=False) for item in fragments],
                   related_fragments=[item.model_dump(mode="json", warnings=False) for item in related_fragments],
                   cells=[item.model_dump(mode="json", warnings=False) for item in cells],
                   findings=[item.model_dump(mode="json", warnings=False) for item in ordered])
    # strict tuple 字段通过 JSON 边界接收数组；避免 model_copy/model_construct 跳过验证。
    from app.services.tables.models import canonical_json_bytes
    payload["report_sha256"] = canonical_sha256(["table-validation-report/v1", payload])
    return TableValidationReport.model_validate_json(canonical_json_bytes(payload))


class TableQualityContribution(_QualityModel):
    json_tuple_fields: ClassVar[tuple[str, ...]] = ("expected_table_ids", "evaluated_table_ids", "reports", "findings")
    schema_version: Literal["table-quality-contribution/v1"]
    producer: Literal["table_validator"]
    source_content_sha256: Sha256 | None
    validator_version: Literal["table-validator/v1"]
    normalizer_version: Literal["table-html/v1"]
    policy: TableValidationPolicy
    policy_sha256: Sha256
    source_groups_version: Literal["logical-table-groups/v1"] | None
    expected_fragment_count: NonNegativeInt | None
    expected_table_ids: tuple[TableId, ...]
    evaluated_table_ids: tuple[TableId, ...]
    coverage: Literal["complete", "unavailable"]
    reason: Literal["source_groups_unavailable"] | None
    status: Literal["pending", "passed", "warning", "blocked"]
    blocker_count: NonNegativeInt
    warning_count: NonNegativeInt
    reports: tuple[TableValidationReport, ...]
    findings: tuple[TableFinding, ...]

    @model_validator(mode="after")
    def _check_contribution(self) -> Self:
        if self.policy_sha256 != self.policy.policy_sha256 or len(set(self.expected_table_ids)) != len(self.expected_table_ids):
            _invalid()
        if self.coverage == "unavailable":
            if (self.source_groups_version is not None or self.expected_fragment_count is not None or
                    self.reason != "source_groups_unavailable" or self.status != "pending" or self.reports or self.findings or
                    self.expected_table_ids or self.evaluated_table_ids or self.blocker_count or self.warning_count):
                _invalid()
            return self
        if (self.source_groups_version != GROUPS_VERSION or self.source_content_sha256 is None or
                self.expected_fragment_count is None or self.reason is not None or
                self.evaluated_table_ids != self.expected_table_ids or
                tuple(report.table_id for report in self.reports) != self.expected_table_ids or
                sum(len(report.fragments) for report in self.reports) != self.expected_fragment_count):
            _invalid()
        seen_fragments = {}
        source_indices = set()
        first_indices = []
        for report in self.reports:
            if report.source_content_sha256 != self.source_content_sha256 or report.policy_sha256 != self.policy_sha256:
                _invalid()
            for fragment in report.fragments:
                if fragment.fragment_id in seen_fragments or fragment.source_index in source_indices:
                    _invalid()
                seen_fragments[fragment.fragment_id] = fragment
                source_indices.add(fragment.source_index)
            first_indices.append(report.fragments[0].source_index)
        if first_indices != sorted(first_indices):
            _invalid()
        for report in self.reports:
            for reference in report.related_fragments:
                owner = seen_fragments.get(reference.fragment_id)
                if owner is None or owner.model_dump(exclude={"row_start"}) != reference.model_dump(exclude={"row_start"}):
                    _invalid()
        findings = tuple(item for report in self.reports for item in report.findings)
        blockers = sum(item.flag.severity == "blocker" for item in findings)
        warnings = len(findings) - blockers
        status = "blocked" if blockers else "warning" if warnings else "passed"
        if (self.findings != findings or self.blocker_count != blockers or self.warning_count != warnings or
                self.status != status or len(findings) > self.policy.max_findings):
            _invalid()
        return self


def aggregate_table_quality(reports: Sequence[TableValidationReport], *, expected_table_ids: Sequence[str],
                            source_content_sha256: str | None, source_groups_version: str | None,
                            expected_fragment_count: int | None,
                            policy: TableValidationPolicy | None = None) -> TableQualityContribution:
    """仅聚合表格来源；缺覆盖与同表冲突拒绝，完全相同的重投幂等。"""
    if not all(isinstance(report, TableValidationReport) for report in reports):
        raise TableValidationError("table_validation_input")
    if policy is not None and not isinstance(policy, TableValidationPolicy):
        raise TableValidationError("table_validation_config")
    selected = TableValidationPolicy.model_validate((policy or TableValidationPolicy()).model_dump(warnings=False))
    unique = {}
    for report in reports:
        checked = TableValidationReport.model_validate(report.model_dump(warnings=False))
        previous = unique.get(checked.table_id)
        if previous is not None and previous != checked:
            raise TableValidationError("table_validation_input")
        unique[checked.table_id] = checked
    expected = tuple(expected_table_ids)
    if any(not isinstance(identity, str) for identity in expected):
        raise TableValidationError("table_validation_input")
    if len(set(expected)) != len(expected) or set(unique) != set(expected):
        raise TableValidationError("table_validation_input")
    ordered = tuple(unique[identity] for identity in expected)
    if sum(len(report.findings) for report in ordered) > selected.max_findings:
        raise TableValidationError("table_validation_limit")
    findings = tuple(finding for report in ordered for finding in report.findings)
    blockers = sum(item.flag.severity == "blocker" for item in findings)
    return TableQualityContribution(
        schema_version="table-quality-contribution/v1", producer="table_validator",
        source_content_sha256=source_content_sha256, validator_version=VALIDATOR_VERSION,
        normalizer_version=NORMALIZER_VERSION, policy=selected, policy_sha256=selected.policy_sha256,
        source_groups_version=source_groups_version, expected_fragment_count=expected_fragment_count,
        expected_table_ids=expected, evaluated_table_ids=tuple(report.table_id for report in ordered),
        coverage="unavailable" if source_groups_version is None else "complete",
        reason="source_groups_unavailable" if source_groups_version is None else None,
        status="pending" if source_groups_version is None else "blocked" if blockers else "warning" if findings else "passed",
        blocker_count=blockers, warning_count=len(findings) - blockers, reports=ordered, findings=findings,
    )
