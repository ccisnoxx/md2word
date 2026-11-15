"""接纳绑定 PDF 和 MinerU 原格的数值列校核，保留原始 Grid 供认证。"""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.document_ir.table_placeholder import PdfCropSource, checksum

if TYPE_CHECKING:
    from app.services.document_ir.models import DocumentIR, LogicalTableGroup, TableFragment
    from app.services.tables.models import TableGrid
    from app.services.tables.quality import TableFinding


_Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_Index = Annotated[int, Field(ge=0)]


class TableValueColumnReviewError(ValueError):
    """对外只携带固定失败码和定位类别。"""

    code = "table_value_column_review_invalid"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"{self.code}：人工数值列校核无效（{reason}）。")


class TableValueColumnCorrection(BaseModel):
    """以片内源格序号定位原值，列区间为零基左闭右开。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always")
    source_row_index: _Index
    source_cell_index: _Index
    content_sha256: _Sha256
    original_column_range: tuple[_Index, _Index]
    target_column: _Index
    target_header: Literal["MIN", "TYP", "MAX", "NOM", "LOW", "HIGH"]


class TableValueColumnReview(BaseModel):
    """保存一个原生表片段的来源版本及逐格校核记录。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always")
    schema_version: Literal["table-value-column-review/v1"]
    source_pdf_sha256: _Sha256
    content_list_sha256: _Sha256
    page_index: _Index
    json_pointer: Annotated[str, Field(pattern=r"^/(?:content_list/)?(?:0|[1-9][0-9]*)(?:/(?:0|[1-9][0-9]*))?$")]
    raw_html_sha256: _Sha256
    normalizer_version: Literal["table-html/v1"]
    corrections: Annotated[tuple[TableValueColumnCorrection, ...], Field(min_length=1)]

    @property
    def review_sha256(self) -> str:
        from app.services.tables.models import canonical_sha256

        return canonical_sha256(self.model_dump(mode="json"))

    def verify_fragment(self, fragment: TableFragment, content_list_sha256: str) -> None:
        """重读时核对当前来源账本，实际 PDF 由转换接纳时核验。"""
        if self.content_list_sha256 != content_list_sha256:
            raise TableValueColumnReviewError("content_list_fingerprint")
        span = fragment.source_span
        if (self.json_pointer != span.json_pointer or self.page_index != span.page_index
                or self.raw_html_sha256 != fragment.raw_html_sha256):
            raise TableValueColumnReviewError("source_binding")
        if fragment.block_id is None or fragment.html_state != "present":
            raise TableValueColumnReviewError("unsupported_shape")


def resolve_table_value_column_review(
    review: TableValueColumnReview, group: LogicalTableGroup, *, source_content_sha256: str,
) -> tuple[TableGrid, tuple[TableFinding, ...]]:
    """从原始 Grid 复算每条记录引用的跨列 blocker，顺序与核定记录相同。"""
    from app.services.tables.grid_builder import build_table_grid
    from app.services.tables.html_normalizer import TableBuildError
    from app.services.tables.quality import TableFinding, TableValidationPolicy, make_finding_id
    from app.services.tables.validator import iter_parameter_value_column_spans

    if len(group.fragments) != 1:
        raise TableValueColumnReviewError("unsupported_shape")
    fragment = group.fragments[0]
    review.verify_fragment(fragment, source_content_sha256)
    try:
        result = build_table_grid(group, source_content_sha256=source_content_sha256)
    except TableBuildError as error:
        raise TableValueColumnReviewError("unsupported_shape") from error
    grid = result.grid
    if result.normalizer_version != review.normalizer_version:
        raise TableValueColumnReviewError("normalizer_version")
    if not grid.rows or not grid.columns or any(diagnostic.code in {
        "table_span_invalid", "table_span_collision", "table_span_out_of_bounds",
    } for diagnostic in result.diagnostics):
        raise TableValueColumnReviewError("unsupported_shape")

    cells = {(cell.source_row_index, cell.source_cell_index): cell for cell in grid.cells}
    targets = [(item.source_row_index, item.source_cell_index) for item in review.corrections]
    if len(set(targets)) != len(targets):
        raise TableValueColumnReviewError("duplicate_target")
    candidates = {
        (evidence.source_row_index, evidence.source_cell_index): (flag, evidence, covered)
        for flag, evidence, covered in iter_parameter_value_column_spans(result, TableValidationPolicy())
    }

    findings = []
    for correction, target in zip(review.corrections, targets, strict=True):
        cell = cells.get(target)
        if (cell is None or correction.content_sha256 != cell.content_sha256
                or correction.original_column_range != (cell.column, cell.column + cell.colspan)):
            raise TableValueColumnReviewError("cell_binding")
        candidate = candidates.get(target)
        if cell.rowspan != 1 or candidate is None:
            raise TableValueColumnReviewError("unsupported_shape")
        flag, evidence, covered = candidate
        if flag.severity != "blocker" or len(covered) != cell.colspan:
            raise TableValueColumnReviewError("unsupported_shape")
        if covered.get(correction.target_column) != correction.target_header.lower():
            raise TableValueColumnReviewError("target_column")
        findings.append(TableFinding(finding_id=make_finding_id(grid.table_id, flag, evidence),
                                     flag=flag, evidence=evidence))
    return grid, tuple(findings)


def attach_table_value_column_reviews(
    document: DocumentIR,
    reviews: tuple[TableValueColumnReview, ...],
    source_hash: str,
    source_loader: Callable[[], PdfCropSource] | None,
) -> None:
    """整批校核成功后把记录挂到本次 IR，任何失败均不附加部分记录。"""
    from app.services.document_ir.integrity import is_visible_body_block

    if source_loader is None:
        raise TableValueColumnReviewError("pdf_source")
    source = source_loader()
    digest = checksum(source.content)
    if (source.file_id != document.metadata.source_file_id or source.checksum_sha256 != digest
            or not source.content.startswith(b"%PDF-")):
        raise TableValueColumnReviewError("pdf_source")

    targets = {
        fragment.source_span.json_pointer: (group, fragment)
        for group in document.metadata.logical_table_groups
        for fragment in group.fragments
    }
    visible = {block.id for block in document.blocks if block.type == "table" and is_visible_body_block(block)}
    pending = {}
    pdf_hash = digest.removeprefix("sha256:")
    for item in reviews:
        try:
            review = TableValueColumnReview.model_validate(item)
        except ValidationError:
            raise TableValueColumnReviewError("invalid_input") from None
        if review.source_pdf_sha256 != pdf_hash:
            raise TableValueColumnReviewError("pdf_fingerprint")
        if review.content_list_sha256 != source_hash:
            raise TableValueColumnReviewError("content_list_fingerprint")
        pointer = review.json_pointer
        if pointer in pending:
            raise TableValueColumnReviewError("duplicate_target")
        target = targets.get(pointer)
        if target is None:
            raise TableValueColumnReviewError("missing_target")
        group, fragment = target
        if fragment.block_id not in visible:
            raise TableValueColumnReviewError("unsupported_shape")
        resolve_table_value_column_review(review, group, source_content_sha256=source_hash)
        pending[pointer] = (fragment, review)
    for fragment, review in pending.values():
        fragment.value_column_review = review
