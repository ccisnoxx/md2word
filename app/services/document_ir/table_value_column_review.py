"""接纳绑定 PDF 和 MinerU 原格的数值列校核，保留原始 Grid 供认证。"""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal, Self, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.services.document_ir.table_placeholder import PdfCropSource, checksum

if TYPE_CHECKING:
    from app.services.document_ir.models import DocumentIR, DocumentIRPage, LogicalTableGroup, TableFragment
    from app.services.tables.grid_builder import TableBuildResult
    from app.services.tables.models import TableGrid
    from app.services.tables.quality import TableFinding, TableValidationPolicy, ValidatorVersion


LegacyValueColumnReplay = Literal["blocker", "shared_limits"]
_Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_ArtifactSha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
_Index = Annotated[int, Field(ge=0)]
_Point = Annotated[float, Field(ge=0, allow_inf_nan=False)]
_Interval = tuple[_Point, _Point]
_Box = tuple[_Point, _Point, _Point, _Point]
_AxisSegment = tuple[_Point, _Point, _Point]
TABLE_EDGE_SEARCH_LIMIT = 1.0
TABLE_EDGE_CONTACT_TOLERANCE = 0.02
TABLE_EDGE_STROKE_OVERHANG = 0.5
# v1 的 Poppler SVG 与文字输出各自舍入。余量只用于词框内字形锚，行列归属仍用实际词框。
_GLYPH_POSITION_ROUNDING = 0.02


class TableValueColumnReviewError(ValueError):
    """对外只携带固定失败码和定位类别。"""

    code = "table_value_column_review_invalid"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"{self.code}：人工数值列校核无效（{reason}）。")


class PdfValueColumnTableEdge(BaseModel):
    """保存与上传 PDF 相接线段对应的单侧取证范围。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always")
    side: Literal["left", "right"]
    layout_bbox: _Box
    corrected_bbox: _Box
    wall: _Point
    horizontal_lines: Annotated[tuple[_AxisSegment, ...], Field(min_length=3)]
    vertical_lines: Annotated[tuple[_AxisSegment, ...], Field(min_length=1)]

    def verify_original(self, original: _Box) -> None:
        edge, direction = (0, -1) if self.side == "left" else (2, 1)
        opposite = 2 - edge
        resolved = self.corrected_bbox[edge]
        tolerance = TABLE_EDGE_CONTACT_TOLERANCE
        overhang = TABLE_EDGE_STROKE_OVERHANG
        if (len(self.horizontal_lines) > 4 or len(self.vertical_lines) != 1
                or any(self.corrected_bbox[i] != original[i] for i in range(4) if i != edge)
                or direction * (resolved - original[edge]) <= 0
                or direction * (self.wall - original[edge]) < -overhang
                or abs(self.wall - self.layout_bbox[edge]) > TABLE_EDGE_SEARCH_LIMIT
                or abs(resolved - self.layout_bbox[edge]) > TABLE_EDGE_SEARCH_LIMIT
                or resolved != direction * max(direction * point for point in (
                    self.wall, *(line[edge] for line in self.horizontal_lines)))
                or len({line[1] for line in self.horizontal_lines}) != len(self.horizontal_lines)):
            raise ValueError("PDF 表框校正必须由实测边线确定唯一侧缘。")
        x, top, bottom = self.vertical_lines[0]
        if x != self.wall or not original[1] <= top < bottom <= original[3]:
            raise ValueError("PDF 表框校正缺少有效的外竖线。")
        for left, y, right in self.horizontal_lines:
            points = (left, y, right)
            if (not original[1] <= y <= original[3]
                    or not -tolerance <= direction * (points[edge] - self.wall) <= overhang
                    or direction * (original[edge] - points[opposite]) < overhang
                    or direction * (points[opposite] - original[opposite]) < -tolerance
                    or not top - tolerance <= y <= bottom + tolerance):
                raise ValueError("PDF 表框校正缺少相接的横线。")


class PdfValueColumnBinding(BaseModel):
    """冻结自动核定涉及的 PDF 左上原点坐标，单位为点。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always")
    schema_version: Literal["pdf-value-column-binding/v1"] = "pdf-value-column-binding/v1"
    extractor_version: str = Field(min_length=1, max_length=128)
    layout_sha256: _Sha256
    table_bbox: _Box
    table_edge: PdfValueColumnTableEdge | None = Field(default=None, exclude_if=lambda value: value is None)
    row_range: _Interval
    column_range: _Interval
    header_bbox: _Box
    value_bbox: _Box
    unit_bbox: _Box
    row_anchor_bboxes: tuple[_Box, ...] = Field(min_length=1)
    glyph_anchors: tuple[_Interval, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_geometry(self) -> Self:
        evidence_bbox = self.table_bbox
        if self.table_edge is not None:
            self.table_edge.verify_original(self.table_bbox)
            evidence_bbox = self.table_edge.corrected_bbox
        left, top, right, bottom = evidence_bbox
        row_top, row_bottom = self.row_range
        column_left, column_right = self.column_range
        value_left, value_top, value_right, value_bottom = self.value_bbox
        header_left, _, header_right, _ = self.header_bbox
        rounding = _GLYPH_POSITION_ROUNDING
        if (not left <= column_left <= header_left < header_right <= column_right <= right
                or not column_left < value_left < value_right < column_right
                or not top <= row_top < value_top < value_bottom < row_bottom <= bottom
                or any(not (left <= x0 < x1 <= right and top <= y0 < y1 <= bottom)
                       for x0, y0, x1, y1 in (self.header_bbox, self.unit_bbox, *self.row_anchor_bboxes))
                or len(set(self.glyph_anchors)) != len(self.glyph_anchors)
                or any(not (value_left - rounding <= x < value_right
                            and value_top - rounding <= y <= value_bottom + rounding) for x, y in self.glyph_anchors)):
            raise ValueError("PDF 数值列核定的坐标超出表、行、列或值框。")
        return self

    @property
    def binding_sha256(self) -> str:
        from app.services.tables.models import canonical_sha256

        return canonical_sha256(self.model_dump(mode="json"))


class PdfValueColumnUnresolved(BaseModel):
    """将未获证的候选连回原始跨列发现，供人工定位。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    fragment_id: Annotated[str, Field(pattern=r"^table-fragment:[0-9a-f]{64}$")]
    finding_id: Annotated[str, Field(pattern=r"^table-finding:[0-9a-f]{64}$")]
    source_row_index: _Index
    source_cell_index: _Index
    reason: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


class PdfValueColumnPageLineage(BaseModel):
    """逐页比对只接受当前任务经服务端回显认证的原解析结果。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    batch_id: str = Field(min_length=1)
    data_id: str = Field(min_length=1)
    parse_generation: _Index
    raw_file_id: str = Field(min_length=1)
    raw_sha256: _ArtifactSha256
    source_pdf_sha256: _ArtifactSha256


class PdfValueColumnPageEquivalence(BaseModel):
    """冻结比对输入、版面和原解析代，供已认证 IR 的同包重放核对。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    schema_version: Literal["pdf-value-column-page-equivalence/v1"] = "pdf-value-column-page-equivalence/v1"
    lineage: PdfValueColumnPageLineage
    returned_pdf_sha256: _ArtifactSha256
    content_list_sha256: _ArtifactSha256
    layout_sha256: _ArtifactSha256
    observation_sha256: _ArtifactSha256
    page_count: int = Field(gt=0)
    poppler_version: str = Field(min_length=1, max_length=128)

    @property
    def source_pdf_sha256(self) -> str:
        return self.lineage.source_pdf_sha256


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
    pdf_binding: PdfValueColumnBinding | None = Field(default=None, exclude_if=lambda value: value is None)


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

    def verify_pdf_geometry(self, fragment: TableFragment, page: DocumentIRPage | None) -> None:
        """重读时核对出处的表框仍对应本次 IR 的来源页及原始 bbox。"""
        bindings = [item.pdf_binding for item in self.corrections if item.pdf_binding is not None]
        if not bindings:
            return
        from app.services.document_ir.layout_signals import NORMALIZED_BBOX_SPACE, _parse_page_size, pdf_point_bbox

        if page is None or page.metadata.get("bbox_coordinate_space") != NORMALIZED_BBOX_SPACE:
            raise TableValueColumnReviewError("pdf_binding_geometry")
        point_bbox = pdf_point_bbox(fragment.source_span.bbox, page)
        if any(binding.table_bbox != point_bbox for binding in bindings):
            raise TableValueColumnReviewError("pdf_binding_geometry")
        corrected = bindings[0].table_edge
        if any(binding.table_edge != corrected for binding in bindings):
            raise TableValueColumnReviewError("pdf_binding_geometry")
        if corrected is not None:
            frame = _parse_page_size(page.metadata.get("pdf_page_size"))
            if (frame is None
                    or any(value > frame[index % 2] for box in (corrected.layout_bbox, corrected.corrected_bbox)
                           for index, value in enumerate(box))
                    or tuple(int(value * 1000 / frame[index % 2])
                             for index, value in enumerate(corrected.layout_bbox)) != fragment.source_span.bbox):
                raise TableValueColumnReviewError("pdf_binding_geometry")


def supports_value_column_review_grid(result: TableBuildResult) -> bool:
    return bool(result.grid.rows and result.grid.columns) and not any(diagnostic.code in {
        "table_span_invalid", "table_span_collision", "table_span_out_of_bounds",
    } for diagnostic in result.diagnostics)


def resolve_table_value_column_review(
    review: TableValueColumnReview, group: LogicalTableGroup, *, source_content_sha256: str,
    policy: TableValidationPolicy | None = None, validator_version: ValidatorVersion | None = None,
    legacy_value_column_replay: LegacyValueColumnReplay | None = None,
) -> tuple[TableGrid, tuple[TableFinding, ...]]:
    """从原始 Grid 复算每条记录引用的跨列 blocker，顺序与核定记录相同。"""
    from app.services.tables.grid_builder import build_table_grid
    from app.services.tables.html_normalizer import TableBuildError
    from app.services.tables.quality import (
        BINDING_VALIDATOR_VERSION, LEGACY_VALIDATOR_VERSION, TableFinding, default_table_validation_policy, make_finding_id,
    )
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
    if not supports_value_column_review_grid(result):
        raise TableValueColumnReviewError("unsupported_shape")

    cells = {(cell.source_row_index, cell.source_cell_index): cell for cell in grid.cells}
    targets = [(item.source_row_index, item.source_cell_index) for item in review.corrections]
    if len(set(targets)) != len(targets):
        raise TableValueColumnReviewError("duplicate_target")
    validator_version = validator_version or (
        LEGACY_VALIDATOR_VERSION if legacy_value_column_replay is not None else BINDING_VALIDATOR_VERSION
    )
    selected_policy = policy or default_table_validation_policy(validator_version)
    candidates = {
        (evidence.source_row_index, evidence.source_cell_index): (flag, evidence, covered)
        for flag, evidence, covered in iter_parameter_value_column_spans(
            result, selected_policy, group=group, validator_version=validator_version,
            legacy_value_column_replay=legacy_value_column_replay,
        )
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
    source = _verified_value_column_review_pdf(document, source_loader)
    pending = _validate_value_column_reviews(document, reviews, source_hash, source)
    for fragment, review in pending.values():
        fragment.value_column_review = review


def _verified_value_column_review_pdf(
    document: DocumentIR, source_loader: Callable[[], PdfCropSource] | None,
) -> PdfCropSource:
    if source_loader is None:
        raise TableValueColumnReviewError("pdf_source")
    source = source_loader()
    digest = checksum(source.content)
    if (source.file_id != document.metadata.source_file_id or source.checksum_sha256 != digest
            or not source.content.startswith(b"%PDF-")):
        raise TableValueColumnReviewError("pdf_source")
    return source


def _validate_value_column_reviews(
    document: DocumentIR,
    reviews: tuple[TableValueColumnReview, ...],
    source_hash: str,
    verified_source: PdfCropSource,
    *,
    pdf_generated: bool = False,
) -> dict[str, tuple[TableFragment, TableValueColumnReview]]:
    """校验来源与原格并准备挂载，自动出处只由 PDF 取证流程接纳。"""
    from app.services.document_ir.integrity import is_visible_body_block

    targets = {
        fragment.source_span.json_pointer: (group, fragment)
        for group in document.metadata.logical_table_groups
        for fragment in group.fragments
    }
    visible = {block.id for block in document.blocks if block.type == "table" and is_visible_body_block(block)}
    pending = {}
    pdf_hash = verified_source.checksum_sha256.removeprefix("sha256:")
    for item in reviews:
        try:
            review = TableValueColumnReview.model_validate(item)
        except ValidationError:
            raise TableValueColumnReviewError("invalid_input") from None
        if any((item.pdf_binding is not None) != pdf_generated for item in review.corrections):
            raise TableValueColumnReviewError("invalid_input")
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
        resolve_table_value_column_review(
            review, group, source_content_sha256=source_hash,
            legacy_value_column_replay=document.metadata.legacy_value_column_replay,
        )
        pending[pointer] = (fragment, review)
    return pending
