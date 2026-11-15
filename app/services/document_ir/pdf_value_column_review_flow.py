"""把同包源 PDF 的坐标证据接入现有数值列核定。"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any, TYPE_CHECKING

from app.services.document_ir.integrity import is_visible_body_block
from app.services.document_ir.layout_signals import (
    NORMALIZED_BBOX_MIN_VERSION, NORMALIZED_BBOX_SPACE, _parse_page_size, _parse_version, pdf_point_bbox,
)
from app.services.document_ir.mineru_package import (
    DEFAULT_POLICY, MinerUValidationPolicy, extract_zip, find_content_list, package_sha256,
)
from app.services.document_ir.models import DocumentIR, DocumentIRPage, TableFragment
from app.services.document_ir.table_placeholder import PdfCropSource, TablePlaceholderError
from app.services.document_ir.table_upstream_coverage import _match_table
from app.services.document_ir.table_value_column_review import (
    PdfValueColumnUnresolved, TableValueColumnReview, TableValueColumnReviewError,
    _validate_value_column_reviews, _verified_value_column_review_pdf, supports_value_column_review_grid,
)
from app.services.tables.grid_builder import build_table_grid
from app.services.tables.html_normalizer import TableBuildError
from app.services.tables.quality import TableValidationPolicy, make_finding_id
from app.services.tables.validator import iter_parameter_value_column_spans

if TYPE_CHECKING:
    from app.services.document_ir.pdf_value_column_observer import PdfValueColumnPage

_Box = tuple[float, float, float, float]


def _paired_origin(content_list_path: Path, source: PdfCropSource) -> bool:
    """只相信实际选中 v2 同目录、同文档名的归档原件和逐字节摘要。"""
    if not content_list_path.name.endswith("content_list_v2.json"):
        return False
    origin_name = content_list_path.name.removesuffix("content_list_v2.json") + "origin.pdf"
    origin = next((path for path in content_list_path.parent.iterdir()
                   if path.name == origin_name and path.is_file()), None)
    return origin is not None and package_sha256(origin) == source.checksum_sha256.removeprefix("sha256:")


def verify_table_value_package_origin(
    content: bytes, source: PdfCropSource, *, policy: MinerUValidationPolicy = DEFAULT_POLICY,
) -> str | None:
    """接纳人工重放时，按正式选包规则核对已核验的源 PDF 与选中的 v2 字节。"""
    with TemporaryDirectory(prefix="table_value_review_source_") as directory:
        root = Path(directory)
        zip_path = root / "input.zip"
        zip_path.write_bytes(content)
        package_root = root / "package"
        package_root.mkdir()
        extract_zip(zip_path, package_root, policy=policy)
        content_list_path = find_content_list(package_root)
        return package_sha256(content_list_path) if _paired_origin(content_list_path, source) else None


def _layout_pages(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    version = _parse_version(payload.get("_version_name"))
    pages = payload.get("pdf_info")
    if (version is None or version < NORMALIZED_BBOX_MIN_VERSION or not isinstance(pages, list)
            or any(not isinstance(page, dict) or type(page.get("page_idx")) is not int
                   or page["page_idx"] != index for index, page in enumerate(pages))):
        return []
    return pages


def _matching_table_box(
    fragment: TableFragment,
    page: DocumentIRPage | None,
    layout_page: dict[str, Any],
    other_tables: list[TableFragment],
) -> _Box | str:
    """同一表的点框须可在同文档 layout 中唯一复算，避免两张源表重复把同一证据领走。"""
    span = fragment.source_span
    box = pdf_point_bbox(span.bbox, page)
    frame = _parse_page_size(layout_page.get("page_size"))
    if (page is None or page.metadata.get("bbox_coordinate_space") != NORMALIZED_BBOX_SPACE
            or box is None or frame is None or _parse_page_size(page.metadata.get("pdf_page_size")) != frame
            or _match_table(layout_page, frame, fragment, "para_blocks") is None):
        return "table_layout_unverified"
    for other in other_tables:
        if other.fragment_id == fragment.fragment_id:
            continue
        other_box = pdf_point_bbox(other.source_span.bbox, page)
        if (other_box is not None and max(box[0], other_box[0]) < min(box[2], other_box[2])
                and max(box[1], other_box[1]) < min(box[3], other_box[3])):
            return "table_region_ambiguous"
    return box


def _propose_reviews(
    document: DocumentIR,
    source_hash: str,
    content_list_path: Path,
    same_document_layout: tuple[Any, str] | None,
    verified_source: Callable[[], PdfCropSource],
    manual: dict[str, tuple[TableFragment, TableValueColumnReview]],
    *,
    source_pair_eligible: bool,
    observation_deadline: float | None,
) -> tuple[tuple[TableValueColumnReview, ...], tuple[PdfValueColumnUnresolved, ...]]:
    from app.services.document_ir.pdf_value_column_binding import match_pdf_value_columns
    from app.services.document_ir.pdf_value_column_observer import (
        PDF_OBSERVATION_BUDGET_EXHAUSTED, PdfObservationUnavailable, observe_pdf_value_column_page,
    )

    layout_payload, layout_sha256 = same_document_layout or (None, "")
    layout_pages = _layout_pages(layout_payload)
    @cache
    def paired_source() -> PdfCropSource | str:
        if not source_pair_eligible:
            return "source_pair_unverified"
        try:
            source = verified_source()
        except TableValueColumnReviewError:
            return "source_pair_unverified"
        except TablePlaceholderError as error:
            if error.code != "table_placeholder_source_unavailable":
                raise
            return "pdf_source_unavailable"
        if not _paired_origin(content_list_path, source):
            return "source_pair_unverified"
        return source if layout_pages else "layout_unverified"

    def budget_exhausted() -> bool:
        return observation_deadline is not None and monotonic() >= observation_deadline

    pages = {page.index: page for page in document.pages}
    tables_by_page: dict[int, list[TableFragment]] = defaultdict(list)
    visible = {block.id for block in document.blocks if block.type == "table" and is_visible_body_block(block)}
    for group in document.metadata.logical_table_groups:
        for fragment in group.fragments:
            if (fragment.block_id in visible and fragment.source_span.page_index is not None
                    and fragment.source_span.bbox is not None):
                tables_by_page[fragment.source_span.page_index].append(fragment)
    policy = TableValidationPolicy()
    proposed: list[TableValueColumnReview] = []
    unresolved: list[PdfValueColumnUnresolved] = []
    with TemporaryDirectory(prefix="document_ir_pdf_value_") as directory:
        pdf_path = Path(directory) / "source.pdf"
        observation_options = {"deadline": observation_deadline} if observation_deadline is not None else {}

        @cache
        def observe(page_index: int) -> PdfValueColumnPage | str:
            if budget_exhausted():
                return PDF_OBSERVATION_BUDGET_EXHAUSTED
            if not pdf_path.is_file():
                # Poppler 读取已核验的不可变字节快照，不重新打开调用方原路径。
                source = paired_source()
                assert isinstance(source, PdfCropSource)
                pdf_path.write_bytes(source.content)
            try:
                observed = observe_pdf_value_column_page(pdf_path, page_index=page_index, **observation_options)
            except PdfObservationUnavailable as error:
                return error.reason
            if (observed.page_count != len(layout_pages)
                    or (observed.width, observed.height) != _parse_page_size(layout_pages[page_index].get("page_size"))):
                return "pdf_geometry_unverified"
            return observed

        for group in document.metadata.logical_table_groups:
            try:
                result = build_table_grid(group, source_content_sha256=source_hash)
            except TableBuildError:
                # 无有效 Grid 时没有可定位的数值 finding，正式表格质量入口仍会处理构建错误。
                continue
            fragment = group.fragments[0]
            span = fragment.source_span
            anchored = manual.get(span.json_pointer)
            skip = (frozenset((item.source_row_index, item.source_cell_index) for item in anchored[1].corrections)
                    if anchored is not None else frozenset())
            findings = [
                (flag, evidence) for flag, evidence, _ in iter_parameter_value_column_spans(result, policy)
                if flag.severity == "blocker"
                and (evidence.source_row_index, evidence.source_cell_index) not in skip
            ]
            if not findings:
                continue
            if (len(group.fragments) != 1 or fragment.block_id not in visible
                    or not supports_value_column_review_grid(result)):
                reason = "unsupported_table_shape"
            elif budget_exhausted():
                reason = PDF_OBSERVATION_BUDGET_EXHAUSTED
            elif isinstance(source := paired_source(), str):
                reason = source
            else:
                page_index = span.page_index
                if page_index is None or page_index >= len(layout_pages):
                    reason = "table_layout_unverified"
                else:
                    box = _matching_table_box(fragment, pages.get(page_index), layout_pages[page_index],
                                              tables_by_page[page_index])
                    observation = box if isinstance(box, str) else observe(page_index)
                    if isinstance(observation, str):
                        reason = observation
                    else:
                        assert not isinstance(box, str)
                        corrections, undecided = match_pdf_value_columns(
                            result, observation, box, layout_sha256=layout_sha256, skip_cells=skip,
                        )
                        if budget_exhausted():
                            reason = PDF_OBSERVATION_BUDGET_EXHAUSTED
                        else:
                            unresolved.extend(undecided)
                            if corrections:
                                proposed.append(TableValueColumnReview(
                                    schema_version="table-value-column-review/v1",
                                    source_pdf_sha256=source.checksum_sha256.removeprefix("sha256:"),
                                    content_list_sha256=source_hash,
                                    page_index=page_index,
                                    json_pointer=span.json_pointer,
                                    raw_html_sha256=fragment.raw_html_sha256,
                                    normalizer_version=result.normalizer_version,
                                    corrections=corrections,
                                ))
                            continue
            unresolved.extend(
                PdfValueColumnUnresolved(
                    fragment_id=evidence.fragment_id,
                    finding_id=make_finding_id(result.grid.table_id, flag, evidence),
                    source_row_index=evidence.source_row_index,
                    source_cell_index=evidence.source_cell_index,
                    reason=reason,
                )
                for flag, evidence in findings
            )
    return tuple(proposed), tuple(unresolved)


def attach_automatic_table_value_column_reviews(
    document: DocumentIR,
    reviews: tuple[TableValueColumnReview, ...],
    source_hash: str,
    source_loader: Callable[[], PdfCropSource] | None,
    *,
    content_list_path: Path,
    same_document_layout: tuple[Any, str] | None,
    source_pair_eligible: bool = True,
    observation_deadline: float | None = None,
) -> None:
    """先接纳人工版本，整批验证自动修正后再一次挂载两类记录。"""
    @cache
    def verified_source() -> PdfCropSource:
        return _verified_value_column_review_pdf(document, source_loader)

    pending = _validate_value_column_reviews(document, reviews, source_hash, verified_source()) if reviews else {}
    proposed, unresolved = _propose_reviews(
        document, source_hash, content_list_path, same_document_layout, verified_source, pending,
        source_pair_eligible=source_pair_eligible, observation_deadline=observation_deadline,
    )
    if proposed:
        for pointer, (fragment, automatic) in _validate_value_column_reviews(
            document, proposed, source_hash, verified_source(), pdf_generated=True,
        ).items():
            if pointer not in pending:
                pending[pointer] = (fragment, automatic)
                continue
            manual = pending[pointer][1]
            corrections = (*manual.corrections, *automatic.corrections)
            if len({(item.source_row_index, item.source_cell_index) for item in corrections}) != len(corrections):
                raise TableValueColumnReviewError("duplicate_target")
            pending[pointer] = (fragment, manual.model_copy(update={"corrections": corrections}))
    for fragment, review in pending.values():
        fragment.value_column_review = review
    document.metadata.pdf_value_column_unresolved = unresolved
