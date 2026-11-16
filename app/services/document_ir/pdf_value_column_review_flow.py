"""把同包源 PDF 的坐标证据接入现有数值列核定。"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any, TYPE_CHECKING

from app.services.document_ir.artifact_validator import parse_valid_bbox
from app.services.document_ir.integrity import is_visible_body_block
from app.services.document_ir.layout_signals import (
    NORMALIZED_BBOX_MIN_VERSION, NORMALIZED_BBOX_SPACE, _parse_page_size, _parse_version, pdf_point_bbox,
    read_same_document_layout,
)
from app.services.document_ir.mineru_package import (
    DEFAULT_POLICY, MinerUValidationPolicy, extract_zip, find_content_list, package_sha256,
)
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, DocumentIRPage, TableFragment
from app.services.document_ir.table_placeholder import PdfCropSource, TablePlaceholderError, checksum
from app.services.document_ir.table_upstream_coverage import _match_table
from app.services.document_ir.table_value_column_review import (
    PdfValueColumnPageEquivalence, PdfValueColumnPageLineage, PdfValueColumnUnresolved,
    TableValueColumnReview, TableValueColumnReviewError,
    _validate_value_column_reviews, _verified_value_column_review_pdf, supports_value_column_review_grid,
)
from app.services.tables.grid_builder import build_table_grid
from app.services.tables.html_normalizer import TableBuildError
from app.services.tables.quality import (
    BINDING_VALIDATOR_VERSION, LEGACY_VALIDATOR_VERSION, default_table_validation_policy, make_finding_id,
)
from app.services.tables.validator import iter_parameter_value_column_spans

if TYPE_CHECKING:
    from app.services.document_ir.pdf_value_column_observer import PdfValueColumnPage

_Box = tuple[float, float, float, float]


def _package_origin(content_list_path: Path) -> Path | None:
    """只选择实际选中 v2 同目录、同文档名的归档原件。"""
    if not content_list_path.name.endswith("content_list_v2.json"):
        return None
    origin_name = content_list_path.name.removesuffix("content_list_v2.json") + "origin.pdf"
    return next((path for path in content_list_path.parent.iterdir()
                 if path.name == origin_name and path.is_file()), None)


def _verified_package_source(
    content_list_path: Path, source: PdfCropSource, source_hash: str,
    same_document_layout: tuple[Any, str] | None,
    *,
    page_lineage: PdfValueColumnPageLineage | None,
    frozen_page_equivalence: PdfValueColumnPageEquivalence | None,
    source_path: Path | None = None,
    deadline: float | None = None,
) -> bool | PdfValueColumnPageEquivalence:
    origin = _package_origin(content_list_path)
    if origin is None:
        return False
    returned_sha256 = "sha256:" + package_sha256(origin)
    if returned_sha256.removeprefix("sha256:") == source.checksum_sha256.removeprefix("sha256:"):
        return frozen_page_equivalence is None
    if (page_lineage is None or same_document_layout is None
            or page_lineage.source_pdf_sha256 != source.checksum_sha256):
        return False
    layout, layout_sha256 = same_document_layout
    layout_pages = _layout_pages(layout)
    if not layout_pages:
        return False
    binding = dict(
        lineage=page_lineage, returned_pdf_sha256=returned_sha256,
        content_list_sha256="sha256:" + source_hash, layout_sha256="sha256:" + layout_sha256,
        page_count=len(layout_pages),
    )
    if frozen_page_equivalence is not None:
        # 复用已经认证并冻结的页面事实，重读时逐一绑定实际原件、原包和选件版本。
        return frozen_page_equivalence if all(
            getattr(frozen_page_equivalence, key) == value for key, value in binding.items()
        ) else False
    if source_path is None or deadline is None:
        return False

    from app.services.document_ir.pdf_value_source_equivalence import compare_pdf_pages

    source_path.write_bytes(source.content)
    comparison = compare_pdf_pages(source_path, origin, deadline=deadline)
    if comparison is None or comparison.page_sizes != tuple(
        _parse_page_size(page.get("page_size")) for page in layout_pages
    ):
        return False
    return PdfValueColumnPageEquivalence(
        **binding, poppler_version=comparison.poppler_version, observation_sha256="sha256:" + comparison.observation_sha256,
    )


def verify_table_value_package_origin(
    content: bytes, source: PdfCropSource, *, policy: MinerUValidationPolicy = DEFAULT_POLICY,
    page_lineage: PdfValueColumnPageLineage | None = None,
    frozen_page_equivalence: PdfValueColumnPageEquivalence | None = None,
) -> str | None:
    """接纳人工重放时，按正式选包规则核对已核验的源 PDF 与选中的 v2 字节。"""
    if frozen_page_equivalence is not None and (
        page_lineage is None or checksum(content) != page_lineage.raw_sha256
    ):
        return None
    with TemporaryDirectory(prefix="table_value_review_source_") as directory:
        root = Path(directory)
        zip_path = root / "input.zip"
        zip_path.write_bytes(content)
        package_root = root / "package"
        package_root.mkdir()
        extract_zip(zip_path, package_root, policy=policy)
        content_list_path = find_content_list(package_root)
        source_hash = package_sha256(content_list_path)
        layout = (read_same_document_layout(content_list_path, policy=policy)
                  if frozen_page_equivalence is not None else None)
        paired = _verified_package_source(
            content_list_path, source, source_hash, layout,
            page_lineage=page_lineage, frozen_page_equivalence=frozen_page_equivalence,
        )
        return source_hash if paired else None


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


@dataclass(frozen=True)
class _TableRegion:
    source_bbox: _Box
    layout_bbox: _Box
    protected: tuple[_Box, ...]


def _neighbouring_layout_boxes(
    layout_page: dict[str, Any], matched: dict[str, Any], body_bbox: _Box,
) -> set[_Box]:
    protected = set()
    for stage in ("para_blocks", "preproc_blocks", "discarded_blocks"):
        blocks = layout_page.get(stage)
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            box = parse_valid_bbox(block.get("bbox"))
            # 两个布局阶段可能记录同一表体，表题和表注仍算邻块。
            same_table = (stage != "discarded_blocks" and block.get("type") == "table"
                          and block.get("index") == matched.get("index") and box == body_bbox)
            if same_table:
                children = block.get("blocks")
                if isinstance(children, list):
                    for child in children:
                        if (isinstance(child, dict)
                                and (child_box := parse_valid_bbox(child.get("bbox"))) is not None
                                and (child.get("type") != "table_body" or child_box != body_bbox
                                     or child.get("index") != matched.get("index"))):
                            protected.add(child_box)
            elif box is not None:
                protected.add(box)
    return protected


def _matching_table_box(
    fragment: TableFragment,
    page: DocumentIRPage | None,
    layout_page: dict[str, Any],
    other_tables: list[TableFragment],
    page_blocks: list[DocumentIRBlock],
) -> _TableRegion | str:
    """先唯一定位表体，再保留同页可占用拟校正条带的邻块。"""
    span = fragment.source_span
    box = pdf_point_bbox(span.bbox, page)
    frame = _parse_page_size(layout_page.get("page_size"))
    if (page is None or page.metadata.get("bbox_coordinate_space") != NORMALIZED_BBOX_SPACE
            or box is None or frame is None or _parse_page_size(page.metadata.get("pdf_page_size")) != frame
            or (match := _match_table(layout_page, frame, fragment, "para_blocks")) is None):
        return "table_layout_unverified"
    matched, (_, layout_bbox), _ = match
    protected = _neighbouring_layout_boxes(layout_page, matched, layout_bbox)
    for other in other_tables:
        if other.fragment_id == fragment.fragment_id:
            continue
        other_box = pdf_point_bbox(other.source_span.bbox, page)
        if other_box is None:
            continue
        if max(box[0], other_box[0]) < min(box[2], other_box[2]) and max(box[1], other_box[1]) < min(box[3], other_box[3]):
            return "table_region_ambiguous"
        protected.add(other_box)
    for block in page_blocks:
        if block.id == fragment.block_id or block.layout is None:
            continue
        block_box = pdf_point_bbox(block.layout.bbox, page)
        # 同表拆出的条件段继承表体框。其物理表题框仍由 layout 邻块保护。
        inherited_context = (block_box == box and block.metadata.get("annotation_role") == "table_context"
                             and block.metadata.get("source_block_id") == fragment.block_id)
        if block_box is not None and not inherited_context:
            protected.add(block_box)
    return _TableRegion(box, layout_bbox, tuple(sorted(protected)))


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
    page_lineage: PdfValueColumnPageLineage | None,
    frozen_page_equivalence: PdfValueColumnPageEquivalence | None,
) -> tuple[tuple[TableValueColumnReview, ...], tuple[PdfValueColumnUnresolved, ...]]:
    from app.services.document_ir.pdf_value_column_binding import match_pdf_value_columns
    from app.services.document_ir.pdf_value_column_observer import (
        PDF_OBSERVATION_BUDGET_EXHAUSTED, PdfObservationUnavailable, observe_pdf_value_column_page,
    )

    layout_payload, layout_sha256 = same_document_layout or (None, "")
    layout_pages = _layout_pages(layout_payload)
    def budget_exhausted() -> bool:
        return observation_deadline is not None and monotonic() >= observation_deadline

    pages = {page.index: page for page in document.pages}
    tables_by_page: dict[int, list[TableFragment]] = defaultdict(list)
    blocks_by_page: dict[int, list[DocumentIRBlock]] = defaultdict(list)
    for block in document.blocks:
        if block.layout is not None and block.layout.page_index is not None:
            blocks_by_page[block.layout.page_index].append(block)
    visible = {block.id for block in document.blocks if block.type == "table" and is_visible_body_block(block)}
    for group in document.metadata.logical_table_groups:
        for fragment in group.fragments:
            if (fragment.block_id in visible and fragment.source_span.page_index is not None
                    and fragment.source_span.bbox is not None):
                tables_by_page[fragment.source_span.page_index].append(fragment)
    replay = document.metadata.legacy_value_column_replay
    version = LEGACY_VALIDATOR_VERSION if replay is not None else BINDING_VALIDATOR_VERSION
    policy = default_table_validation_policy(version)
    proposed: list[TableValueColumnReview] = []
    unresolved: list[PdfValueColumnUnresolved] = []
    with TemporaryDirectory(prefix="document_ir_pdf_value_") as directory:
        pdf_path = Path(directory) / "source.pdf"
        observation_options = {"deadline": observation_deadline} if observation_deadline is not None else {}

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
            try:
                paired = _verified_package_source(
                    content_list_path, source, source_hash, same_document_layout,
                    page_lineage=page_lineage, frozen_page_equivalence=frozen_page_equivalence,
                    source_path=pdf_path, deadline=observation_deadline,
                )
            except PdfObservationUnavailable as error:
                return error.reason if error.reason == PDF_OBSERVATION_BUDGET_EXHAUSTED else "source_pair_unverified"
            if not paired:
                return "source_pair_unverified"
            if isinstance(paired, PdfValueColumnPageEquivalence):
                document.metadata.pdf_value_column_page_equivalence = paired
            return source if layout_pages else "layout_unverified"

        if frozen_page_equivalence is not None and isinstance(paired_source(), str):
            raise TableValueColumnReviewError("source_binding")

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
                (flag, evidence) for flag, evidence, _ in iter_parameter_value_column_spans(
                    result, policy, group=group, validator_version=version, legacy_value_column_replay=replay,
                ) if flag.severity == "blocker" and (
                    evidence.fragment_id != fragment.fragment_id
                    or (evidence.source_row_index, evidence.source_cell_index) not in skip
                )
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
                    region = _matching_table_box(
                        fragment, pages.get(page_index), layout_pages[page_index],
                        tables_by_page[page_index], blocks_by_page[page_index],
                    )
                    observation = region if isinstance(region, str) else observe(page_index)
                    if isinstance(observation, str):
                        reason = observation
                    else:
                        assert isinstance(region, _TableRegion)
                        corrections, undecided = match_pdf_value_columns(
                            result, observation, region.source_bbox, layout_sha256=layout_sha256, skip_cells=skip,
                            layout_bbox=region.layout_bbox, protected_regions=region.protected,
                            legacy_value_column_replay=replay,
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
    page_lineage: PdfValueColumnPageLineage | None = None,
    frozen_page_equivalence: PdfValueColumnPageEquivalence | None = None,
) -> None:
    """先接纳人工版本，整批验证自动修正后再一次挂载两类记录。"""
    @cache
    def verified_source() -> PdfCropSource:
        return _verified_value_column_review_pdf(document, source_loader)

    pending = _validate_value_column_reviews(document, reviews, source_hash, verified_source()) if reviews else {}
    proposed, unresolved = _propose_reviews(
        document, source_hash, content_list_path, same_document_layout, verified_source, pending,
        source_pair_eligible=source_pair_eligible, observation_deadline=observation_deadline,
        page_lineage=page_lineage, frozen_page_equivalence=frozen_page_equivalence,
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
