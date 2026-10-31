"""CanonicalTableGrid v1 合同、稳定身份及来源指纹，不执行 HTML 或 Word 操作。"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel, ConfigDict, Field, JsonValue, ModelWrapValidatorHandler,
    ValidationError, field_validator, model_validator,
)
from pydantic_core import PydanticCustomError

from app.services.document_ir.models import RepeatedHeaderHint, SourceSpan


Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
FragmentId = Annotated[str, Field(pattern=r"^table-fragment:[0-9a-f]{64}$")]
CellId = Annotated[str, Field(pattern=r"^table-cell:[0-9a-f]{64}$")]
RunId = Annotated[str, Field(pattern=r"^table-run:[0-9a-f]{64}$")]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
RunType = Literal["text", "protected_token", "formula", "superscript", "subscript", "line_break"]
_ERROR_REASONS = frozenset({
    "table_model_version", "table_model_identity", "table_model_reference",
    "table_model_raw_hash", "table_model_content_hash", "table_model_run_target",
    "table_model_run_source", "table_model_scalar", "table_model_source_order",
    "table_model_header_rows", "table_model_field", "table_model_type", "table_model_encoding",
})


def canonical_json_bytes(value: JsonValue) -> bytes:
    """生成合同约定的 UTF-8 canonical JSON；不转义中文，不允许非有限数。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_sha256(value: JsonValue) -> str:
    """计算 canonical JSON 指纹；完整模型指纹由调用方按需计算，不存冗余字段。"""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def make_cell_id(fragment_id: str, source_row_index: int, source_cell_index: int) -> str:
    """身份只取源序号，网格重排、span 修正和译文不改变 cell 身份。"""
    return "table-cell:" + canonical_sha256([
        "table-cell/v1", fragment_id, source_row_index, source_cell_index,
    ])


def make_run_id(cell_id: str, source_run_index: int) -> str:
    """run 身份沿用 cell 的源身份，不从文字或当前坐标生成。"""
    return "table-run:" + canonical_sha256(["table-run/v1", cell_id, source_run_index])


def _fail(reason: str) -> None:
    raise PydanticCustomError(reason, f"表格模型合同无效：{reason}。")


def _check_utf8(value: str) -> None:
    """自由字符串必须能写入 UTF-8 Artifact，禁止将编码失败推迟到序列化。"""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("table_model_encoding")


class _TableModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True,
                              allow_inf_nan=False, revalidate_instances="always")

    @model_validator(mode="wrap")
    @classmethod
    def _safe_errors(cls, value: object, handler: ModelWrapValidatorHandler[Self]) -> Self:
        # 默认 extra 错误会把任意输入键放进 loc；统一成固定定位和有限原因码。
        # 调用方仍须使用 errors(include_input=False, include_context=False) 投影错误。
        try:
            return handler(value)
        except ValidationError as error:
            safe_errors = []
            for detail in error.errors(include_input=False, include_context=False, include_url=False):
                reason = detail["type"]
                location = detail["loc"]
                if reason in {"extra_forbidden", "invalid_key"}:
                    location = (*location[:-1], "__extra__")
                if reason not in _ERROR_REASONS:
                    if location and location[-1] == "schema_version":
                        reason = "table_model_version"
                    elif reason in {"missing", "extra_forbidden"}:
                        reason = "table_model_field"
                    else:
                        reason = "table_model_type"
                safe_errors.append({
                    "type": PydanticCustomError(reason, f"表格模型合同无效：{reason}。"),
                    "loc": location,
                    "input": None,
                })
            raise ValidationError.from_exception_data(cls.__name__, safe_errors, hide_input=True) from None


class TableQualityFlag(_TableModel):
    """只保存有界机器码和对象定位，空列表不表示任务质量通过。"""

    code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    severity: Literal["warning", "blocker"]
    fragment_id: FragmentId | None = None
    cell_id: CellId | None = None
    run_id: RunId | None = None


class CellRun(_TableModel):
    """源语义 run 的顺序和 marks 独立于 Word 样式；只有 text 可带译文。"""

    id: RunId
    source_run_index: NonNegativeInt
    type: RunType
    source: str
    target: str | None = None
    bold: bool = False
    italic: bool = False

    @field_validator("source", "target")
    @classmethod
    def _validate_utf8_text(cls, value: str | None) -> str | None:
        if value is not None:
            _check_utf8(value)
        return value

    @model_validator(mode="after")
    def _validate_text(self) -> Self:
        if self.type != "text" and self.target is not None:
            _fail("table_model_run_target")
        if self.type == "line_break" and self.source != "\n":
            _fail("table_model_run_source")
        return self


def cell_content_sha256(runs: Sequence[CellRun]) -> str:
    """源内容指纹包含语义、原文、顺序和 marks，不包含译文或布局。"""
    return canonical_sha256(["table-cell-content/v1", [
        [run.type, run.source, run.bold, run.italic] for run in runs
    ]])


class TableSourceFragment(_TableModel):
    """已验证 IR-205 fragment 的 HTML 快照，不复制来源账本或归组算法。"""

    fragment_id: FragmentId
    source_span: SourceSpan
    html_state: Literal["missing", "empty", "present"]
    raw_html: str | None
    raw_html_sha256: Sha256 | None
    repeated_header_hint: RepeatedHeaderHint | None = None

    @field_validator("source_span", "repeated_header_hint", mode="before")
    @classmethod
    def _strict_source_scalars(cls, value: object) -> object:
        # 从模型实例重新验证也创建独立快照，不把上游可变对象直接挂入 Grid。
        # 复用上游类型，但不让独立 JSON 边界把 bool/字符串截成源序号。
        data = value.model_dump(warnings=False) if isinstance(value, (SourceSpan, RepeatedHeaderHint)) else value
        if isinstance(data, dict):
            for key in ("source_index", "source_index_in_page", "page_index", "start_row", "row_count"):
                if key in data and data[key] is not None and type(data[key]) is not int:
                    _fail("table_model_scalar")
            for key in ("json_pointer", "source_type", "signature"):
                if key in data:
                    if not isinstance(data[key], str):
                        _fail("table_model_type")
                    _check_utf8(data[key])
            bbox = data.get("bbox")
            if bbox is not None and isinstance(bbox, (list, tuple)):
                if any(type(number) not in (int, float) or
                       (type(number) is float and not math.isfinite(number)) for number in bbox):
                    _fail("table_model_scalar")
        return data

    @model_validator(mode="after")
    def _validate_raw_html(self) -> Self:
        state = "missing" if self.raw_html is None else "present" if self.raw_html.strip() else "empty"
        checksum = hashlib.sha256(self.raw_html.encode("utf-8")).hexdigest() if self.raw_html is not None else None
        if self.html_state != state or self.raw_html_sha256 != checksum:
            _fail("table_model_raw_hash")
        return self


def raw_html_set_sha256(fragments: Sequence[TableSourceFragment]) -> str:
    """根指纹包含有序来源集合；逐字 HTML 指纹保存在每个 fragment 内。"""
    return canonical_sha256(["table-raw-html-set/v1", [
        [fragment.fragment_id, fragment.html_state, fragment.raw_html_sha256] for fragment in fragments
    ]])


class TableCell(_TableModel):
    """一个真实源 cell 只记录一次；正 span 尾端越界留给后续质量诊断。"""

    id: CellId
    source_fragment_id: FragmentId
    source_row_index: NonNegativeInt
    source_cell_index: NonNegativeInt
    row: NonNegativeInt
    column: NonNegativeInt
    rowspan: PositiveInt
    colspan: PositiveInt
    is_header: bool
    runs: list[CellRun]
    content_sha256: Sha256
    quality_flags: list[TableQualityFlag] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_source_identity(self) -> Self:
        if self.id != make_cell_id(self.source_fragment_id, self.source_row_index, self.source_cell_index):
            _fail("table_model_identity")
        indices = [run.source_run_index for run in self.runs]
        if len(set(indices)) != len(indices):
            _fail("table_model_identity")
        if indices != sorted(indices):
            _fail("table_model_source_order")
        if any(run.id != make_run_id(self.id, run.source_run_index) for run in self.runs):
            _fail("table_model_identity")
        if self.content_sha256 != cell_content_sha256(self.runs):
            _fail("table_model_content_hash")
        for flag in self.quality_flags:
            _validate_flag(flag, {self.source_fragment_id}, {self.id: self}, {
                run.id: self for run in self.runs
            })
        return self


def _validate_flag(flag: TableQualityFlag, fragments: set[str], cells: dict[str, TableCell],
                   runs: dict[str, TableCell]) -> None:
    cell = cells.get(flag.cell_id) if flag.cell_id is not None else None
    run_cell = runs.get(flag.run_id) if flag.run_id is not None else None
    if ((flag.fragment_id is not None and flag.fragment_id not in fragments) or
            (flag.cell_id is not None and cell is None) or
            (flag.run_id is not None and run_cell is None)):
        _fail("table_model_reference")
    if cell is not None and run_cell is not None and cell.id != run_cell.id:
        _fail("table_model_reference")
    owner = cell if cell is not None else run_cell
    if owner is not None and flag.fragment_id is not None and owner.source_fragment_id != flag.fragment_id:
        _fail("table_model_reference")


class TableGrid(_TableModel):
    """独立 canonical-table/v1 根合同；不构建 occupancy，不推断质量状态。"""

    schema_version: Literal["canonical-table/v1"]
    table_id: Annotated[str, Field(pattern=r"^logical-table:[0-9a-f]{64}$")]
    source_content_sha256: Sha256
    raw_html_sha256: Sha256
    rows: NonNegativeInt
    columns: NonNegativeInt
    source_fragments: Annotated[list[TableSourceFragment], Field(min_length=1)]
    cells: list[TableCell]
    header_rows: list[NonNegativeInt] = Field(default_factory=list)
    quality_flags: list[TableQualityFlag] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_grid(self) -> Self:
        fragment_ids = [fragment.fragment_id for fragment in self.source_fragments]
        pointers = [fragment.source_span.json_pointer for fragment in self.source_fragments]
        indices = [fragment.source_span.source_index for fragment in self.source_fragments]
        if (len(set(fragment_ids)) != len(fragment_ids) or len(set(pointers)) != len(pointers) or
                len(set(indices)) != len(indices)):
            _fail("table_model_identity")
        if indices != sorted(indices):
            _fail("table_model_source_order")
        if self.raw_html_sha256 != raw_html_set_sha256(self.source_fragments):
            _fail("table_model_raw_hash")
        if self.header_rows != sorted(set(self.header_rows)) or any(row >= self.rows for row in self.header_rows):
            _fail("table_model_header_rows")
        if (self.rows == 0 or self.columns == 0) and self.cells:
            _fail("table_model_scalar")
        cells = {cell.id: cell for cell in self.cells}
        all_runs = [run for cell in self.cells for run in cell.runs]
        if len(cells) != len(self.cells) or len({run.id for run in all_runs}) != len(all_runs):
            _fail("table_model_identity")
        fragment_order = {identity: index for index, identity in enumerate(fragment_ids)}
        positions = []
        for cell in self.cells:
            if cell.source_fragment_id not in fragment_order:
                _fail("table_model_reference")
            if cell.row >= self.rows or cell.column >= self.columns:
                _fail("table_model_scalar")
            positions.append((fragment_order[cell.source_fragment_id], cell.source_row_index, cell.source_cell_index))
        if len(set(positions)) != len(positions):
            _fail("table_model_identity")
        if positions != sorted(positions):
            _fail("table_model_source_order")
        runs = {run.id: cell for cell in self.cells for run in cell.runs}
        for flag in self.quality_flags:
            _validate_flag(flag, set(fragment_ids), cells, runs)
        return self
