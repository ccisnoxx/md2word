"""将人工表头行数绑定到经核验的 PDF 与 MinerU 表格位置。"""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.services.document_ir.table_placeholder import PdfCropSource, checksum

if TYPE_CHECKING:
    from app.services.document_ir.models import DocumentIR, TableFragment


_Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class TableHeaderReviewError(ValueError):
    code = "table_header_review_invalid"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"人工表头校核无效：{reason}。")


class TableHeaderReview(BaseModel):
    """只保存来源身份和经核对的连续首部行数。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always")
    source_pdf_sha256: _Sha256
    content_list_sha256: _Sha256
    json_pointer: Annotated[str, Field(pattern=r"^/(?:content_list/)?(?:0|[1-9][0-9]*)(?:/(?:0|[1-9][0-9]*))?$")]
    page_index: int = Field(ge=0)
    raw_html_sha256: _Sha256
    header_row_count: int = Field(gt=0)

    def verify_fragment(self, fragment: TableFragment, content_list_sha256: str) -> None:
        span = fragment.source_span
        if (fragment.block_id is None or fragment.html_state != "present"
                or self.content_list_sha256 != content_list_sha256
                or self.json_pointer != span.json_pointer or self.page_index != span.page_index
                or self.raw_html_sha256 != fragment.raw_html_sha256):
            raise TableHeaderReviewError("source_binding")


def attach_table_header_reviews(
    document: DocumentIR,
    reviews: tuple[TableHeaderReview, ...],
    source_hash: str,
    source_loader: Callable[[], PdfCropSource] | None,
) -> None:
    """在已定组的来源账本上验证校核，不让校核参与续表判断。"""
    from app.services.tables.grid_builder import build_table_grid

    if source_loader is None:
        raise TableHeaderReviewError("pdf_source")
    source = source_loader()
    digest = checksum(source.content)
    if (source.file_id != document.metadata.source_file_id or source.checksum_sha256 != digest
            or not source.content.startswith(b"%PDF-")):
        raise TableHeaderReviewError("pdf_source")

    groups_by_pointer = {
        fragment.source_span.json_pointer: (group, fragment)
        for group in document.metadata.logical_table_groups
        for fragment in group.fragments
    }
    pending = {}
    pdf_hash = digest.removeprefix("sha256:")
    for item in reviews:
        review = TableHeaderReview.model_validate(item)
        pointer = review.json_pointer
        if review.source_pdf_sha256 != pdf_hash:
            raise TableHeaderReviewError("pdf_fingerprint")
        if pointer in pending:
            raise TableHeaderReviewError("duplicate_target")
        target = groups_by_pointer.get(pointer)
        if target is None:
            raise TableHeaderReviewError("missing_target")
        group, fragment = target
        review.verify_fragment(fragment, source_hash)
        pending[pointer] = (group, fragment, review)

    # 单次转换尚未发布 IR。先统一解析受影响的组，保留实际采用的校核。
    affected = {}
    for group, fragment, review in pending.values():
        fragment.header_review = review
        affected[group.logical_group_id] = group
    for group in affected.values():
        grid = build_table_grid(group, source_content_sha256=source_hash).grid
        for fragment, grid_source in zip(group.fragments, grid.source_fragments, strict=True):
            fragment.header_review = grid_source.header_review
