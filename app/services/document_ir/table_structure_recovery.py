"""普通直转中有来源证据的表格结构回退。"""

from __future__ import annotations

from collections.abc import Callable

from app.services.document_ir.integrity import build_page_counts, is_visible_body_block
from app.services.document_ir.models import DocumentIR, DocumentIRBlock, TableFragment, TableStructureReview
from app.services.document_ir.page_degradation import degradation_closure, drop_degraded_table_groups, replace_degraded_pages
from app.services.document_ir.table_placeholder import (
    MAX_TOTAL_BYTES, PdfCropSource, PdfPageRasterizer, PdfTableCropProvider, TablePlaceholderError, TableStructureReason, checksum,
    prepare_placeholders, validate_image,
)
from app.services.failure_context import attach_failure_context
from app.services.tables.grid_builder import build_render_table_grid
from app.services.tables.html_normalizer import TableBuildError


_MERGE_DIAGNOSTICS = {"table_span_invalid", "table_span_collision", "table_span_out_of_bounds"}


def inspect_structure(block: DocumentIRBlock, index: int, *, invalid_html: bool) -> tuple[TableStructureReason | None, bool]:
    """原生表只接受可解析、几何完整且没有丢弃载荷的网格。"""
    try:
        result = build_render_table_grid(block, block_index=index)
    except TableBuildError as error:
        if error.code != "table_html_unsupported_structure":
            raise
        return "invalid_table_html", False
    codes = {item.code for item in result.diagnostics}
    if codes & _MERGE_DIAGNOSTICS:
        return "invalid_table_merge", False
    if result.grid.rows <= 0 or result.grid.columns <= 0:
        return "invalid_table_html", False
    if invalid_html or ("table_html_implicit_close" in codes and "</table>" not in (block.html or "").lower()):
        return "invalid_table_html", "table_html_removed_unsafe" not in codes
    return None, True


def _located_failure(document: DocumentIR, fragment: TableFragment, *, page_index: int | None = None,
                     code: str = "table_structure_recovery_unavailable") -> TablePlaceholderError:
    counts = build_page_counts(document) or {}
    error = TablePlaceholderError(code)
    attach_failure_context(error, operation_kind="table_placeholder", block_ids=[fragment.render_owner_block_id],
                           source_page_index=fragment.source_span.page_index if page_index is None else page_index,
                           source_page_count=counts.get("source_page_count"), page_count_basis=counts.get("page_count_basis"))
    return error


def _preserve_pages(document: DocumentIR, fallback_fragments: list[TableFragment], *, source_loader, rasterizer):
    """按跨页表闭包一次处理，所有依赖页均须可靠保留。"""
    fragment = fallback_fragments[0]
    pages = {item.source_span.page_index for item in fallback_fragments}
    if None in pages or source_loader is None or rasterizer is None:
        raise _located_failure(document, fragment)
    closure = degradation_closure(document.metadata.logical_table_groups, pages)
    if closure is None:
        raise _located_failure(document, fragment)
    try:
        source = source_loader()
    except TablePlaceholderError as error:
        if error.code != "table_placeholder_source_unavailable":
            raise
        raise _located_failure(document, fragment) from error
    if source.file_id != document.metadata.source_file_id or checksum(source.content) != source.checksum_sha256:
        raise TablePlaceholderError("table_placeholder_integrity_failed")
    reasons: dict[int, dict] = {}
    for target in fallback_fragments:
        info = reasons.setdefault(target.source_span.page_index, {"reason_codes": [], "issue_pointers": []})
        info["reason_codes"].append(target.structure_recovery or "empty_table_html")
        info["issue_pointers"].append(target.source_span.json_pointer)
    rasters = {}
    total_bytes = 0
    for page in sorted(closure):
        try:
            rasters[page] = rasterizer.rasterize(source, page)
        except TablePlaceholderError as error:
            if error.code not in {"table_placeholder_source_unavailable", "table_placeholder_geometry_invalid",
                                  "table_placeholder_crop_failed"}:
                raise
            raise _located_failure(document, fragment, page_index=page) from error
        validate_image(rasters[page])
        total_bytes += len(rasters[page])
        if total_bytes > MAX_TOTAL_BYTES:
            raise _located_failure(document, fragment, page_index=page, code="table_structure_recovery_limit")
    removed, pending = replace_degraded_pages(document, rasters, reasons, source_pdf_sha256=source.checksum_sha256,
                                               dpi=getattr(rasterizer, "DPI", None), trigger="validation")
    drop_degraded_table_groups(document, removed, prune_removed_diagnostics=True)
    document.quality_flags = [
        flag for flag in document.quality_flags
        if not (flag.startswith("layout_two_column_candidate:") and flag.split(":")[1] in removed)
    ]
    return closure, removed, pending


def preserve_table_structures(
    document: DocumentIR, references, *, invalid_html_pointers: set[str],
    source_loader: Callable[[], PdfCropSource] | None, crop_provider: PdfTableCropProvider | None,
    page_rasterizer: PdfPageRasterizer | None,
):
    """保留原始片段账本，只有已选图像负责覆盖的 Word 消费视图才清空 HTML。"""
    blocks = {block.id: (index, block) for index, block in enumerate(document.blocks)}
    choices = {}
    for group in document.metadata.logical_table_groups:
        for fragment in group.fragments:
            index, block = blocks[fragment.render_owner_block_id]
            if not is_visible_body_block(block) or fragment.upstream_coverage is not None:
                continue
            pointer = fragment.source_span.json_pointer
            if fragment.html_state in {"empty", "missing"}:
                reason = "invalid_table_html" if pointer in invalid_html_pointers else "empty_table_html"
                native = False
            else:
                reason, native = inspect_structure(block, index, invalid_html=pointer in invalid_html_pointers)
            if reason is None:
                continue
            choices[fragment.fragment_id] = (fragment, reason, native)
            if not native and reason != "empty_table_html":
                fragment.structure_recovery = reason
                if fragment.block_id is not None:
                    block.html = None

    unavailable: list[str] = []
    placeholders = prepare_placeholders(document, references, source_loader=source_loader, crop_provider=crop_provider,
                                         unavailable_fragments=unavailable, reviewable_fragments=frozenset(choices))
    closure, removed, pages = set(), set(), []
    if unavailable:
        closure, removed, pages = _preserve_pages(
            document, [choices[identity][0] for identity in unavailable],
            source_loader=source_loader, rasterizer=page_rasterizer,
        )
    assets = {asset.id for asset in document.assets}
    bindings = {binding.fragment_id: binding for binding in document.metadata.table_placeholders}
    reviews = []
    for fragment, reason, native in choices.values():
        span = fragment.source_span
        covered = span.page_index in closure
        if reason == "empty_table_html" and fragment.fragment_id not in unavailable:
            continue
        if covered:
            method = "pdf_page"
        elif native:
            method = "native"
        else:
            method = ("reference_image" if bindings[fragment.fragment_id].source_kind == "mineru_reference"
                      else "pdf_crop")
        reviews.append(TableStructureReview(
            source_pointer=span.json_pointer, page_index=span.page_index,
            block_id=None if covered else fragment.render_owner_block_id, reason=reason, preserved_as=method,
        ))
    if not invalid_html_pointers <= ({item.source_pointer for item in reviews} | {
        pointer for page in document.metadata.degraded_pages for pointer in page.get("removed_source_pointers", [])
    }):
        # 被来源校验标为坏表的片段必须拥有实际的保留方式。
        raise TablePlaceholderError("table_structure_recovery_unavailable")
    document.metadata.table_structure_reviews = reviews
    return [item for item in placeholders if item.asset_id in assets], removed, pages


def validate_structure_reviews(document: DocumentIR) -> None:
    """重读时逐个核对来源片段和已选输出方式，禁止以标记替代实物。"""
    reviews = document.metadata.table_structure_reviews
    by_source = {review.source_pointer: review for review in reviews}
    fragments = {fragment.source_span.json_pointer: fragment
                 for group in document.metadata.logical_table_groups for fragment in group.fragments}
    blocks = {block.id: block for block in document.blocks}
    bindings = {binding.fragment_id: binding for binding in document.metadata.table_placeholders}
    pages = {record["page_index"]: record for record in document.metadata.degraded_pages}
    assets = {asset.id: asset for asset in document.assets}
    if (len(by_source) != len(reviews) or document.metadata.translation_item_scope is not None
            or document.metadata.legacy_value_column_replay is not None):
        raise TablePlaceholderError("table_placeholder_integrity_failed")
    if any(fragment.structure_recovery is not None and fragment.source_span.json_pointer not in by_source
           for fragment in fragments.values()):
        raise TablePlaceholderError("table_placeholder_integrity_failed")
    for review in reviews:
        fragment = fragments.get(review.source_pointer)
        if review.preserved_as == "pdf_page":
            page = pages.get(review.page_index)
            if (fragment is None and review.block_id is None and page is not None
                    and review.source_pointer in page.get("removed_source_pointers", [])
                    and page.get("page_image_asset_id") in assets
                    and any(block.page_index == review.page_index and block.asset_ref == page["page_image_asset_id"]
                            and block.metadata.get("source_type") == "degraded_page_image" for block in blocks.values())):
                continue
        elif (fragment is not None and fragment.source_span.page_index == review.page_index
                and fragment.render_owner_block_id == review.block_id and review.block_id in blocks):
            block = blocks[review.block_id]
            binding = bindings.get(fragment.fragment_id)
            if review.preserved_as == "native":
                if (binding is None and review.reason == "invalid_table_html" and fragment.structure_recovery is None
                        and fragment.raw_html == block.html and bool(block.html)):
                    continue
            elif (binding is not None and fragment.structure_recovery == review.reason
                  and binding.structure_recovery == review.reason
                  and (review.preserved_as == "reference_image") == (binding.source_kind == "mineru_reference")
                  and (fragment.block_id is None or not block.html)):
                continue
        raise TablePlaceholderError("table_placeholder_integrity_failed")
