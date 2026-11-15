"""在接纳锁外核对同包重放的当前实物、同源原件和累计人工记录。"""

from __future__ import annotations

from pydantic import ValidationError

from app.core.errors import ApplicationError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.new_generation import NewGenerationConflict, TableValueColumnReplay
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.document_jobs.table_value_column_sources import read_table_value_mineru_result, table_value_page_lineage
from app.domains.document_jobs.table_evidence import VerifiedTableEvidence, verify_report
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.service import FileUploadService
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.mineru_package import MinerUPackageError
from app.services.document_ir.models import TableReferenceProvenance
from app.services.document_ir.pdf_value_column_review_flow import verify_table_value_package_origin
from app.services.document_ir.table_placeholder import PdfCropSource
from app.services.document_ir.table_value_column_review import (
    TableValueColumnReview,
    TableValueColumnReviewError,
    resolve_table_value_column_review,
)
from app.services.tables.evidence import TableEvidenceError
from app.services.tables.models import make_cell_id


def _verified_reviews(
    verified: VerifiedTableEvidence,
    submitted: tuple[TableValueColumnReview, ...],
    *,
    pdf_sha256: str,
    content_list_sha256: str,
) -> tuple[TableValueColumnReview, ...]:
    tables = verified.envelope.report.tables
    native_groups = {table.logical_group_id for table in tables if table.render_state == "native"}
    targets = {fragment.source_span.json_pointer: (group, fragment)
        for group in verified.document.metadata.logical_table_groups if group.logical_group_id in native_groups
        for fragment in group.fragments}
    pending = verified.unresolved_value_columns
    reviews: dict[str, TableValueColumnReview] = {}
    for review in submitted:
        pointer = review.json_pointer
        if (pointer not in targets or pointer in reviews or review.source_pdf_sha256 != pdf_sha256
                or any("pdf_binding" in item.model_fields_set for item in review.corrections)):
            raise NewGenerationConflict(TableValueColumnReviewError.code)
        group, _ = targets[pointer]
        try:
            _, findings = resolve_table_value_column_review(review, group, source_content_sha256=content_list_sha256)
        except TableValueColumnReviewError:
            raise NewGenerationConflict(TableValueColumnReviewError.code) from None
        if any(finding.finding_id not in pending or pending[finding.finding_id][1] != finding for finding in findings):
            raise NewGenerationConflict(TableValueColumnReviewError.code)
        reviews[pointer] = review

    certified_manual = {(item.review_sha256, item.source_cell_id, item.target_column)
        for table in tables for item in table.value_column_corrections or () if item.pdf_binding_sha256 is None}
    for pointer, (_, fragment) in targets.items():
        prior = fragment.value_column_review
        if prior is None:
            continue
        prior_sha256 = prior.review_sha256
        carried = tuple(item for item in prior.corrections if item.pdf_binding is None and (
            prior_sha256, make_cell_id(fragment.fragment_id, item.source_row_index, item.source_cell_index),
            item.target_column,
        ) in certified_manual)
        if carried:
            if prior.source_pdf_sha256 != pdf_sha256 or prior.content_list_sha256 != content_list_sha256:
                raise NewGenerationConflict("table_value_column_source_unverified")
            new_review = reviews.get(pointer)
            reviews[pointer] = prior.model_copy(update={
                "corrections": carried + (new_review.corrections if new_review is not None else ()),
            })
    return tuple(reviews[pointer] for pointer in sorted(reviews))


def prepare_table_value_column_replay(
    job: DocumentJobRecord,
    result: DocumentFileRecord | None,
    source: PdfCropSource,
    submitted: tuple[TableValueColumnReview, ...],
    *,
    job_repository: DocumentJobRepositoryProtocol,
    file_repository: DocumentFileRepositoryProtocol,
    file_service: FileUploadService,
) -> tuple[TableValueColumnReplay, tuple[DocumentFileRecord, ...]]:
    """冻结已认证的实物描述及复用指纹，交给新代事务复核。"""
    if result is None or result.status != "uploaded":
        raise NewGenerationConflict("quality_evidence_conflict")
    try:
        verified = verify_report(job, result, job_repository=job_repository,
            file_repository=file_repository, file_service=file_service)
    except (TableEvidenceError, DocumentIntegrityError, FileNotFoundError):
        raise NewGenerationConflict("quality_evidence_conflict") from None
    except RuntimeError:
        raise ApplicationError("service_unavailable", "表格证据存储暂不可用。",
            reason_code="new_generation_storage_unavailable") from None
    if verified is None:
        raise NewGenerationConflict("quality_evidence_conflict")
    if not verified.unresolved_value_columns:
        raise NewGenerationConflict(TableValueColumnReviewError.code)
    raw = file_repository.get_document_file(job.mineru_raw_result_file_id) if job.mineru_raw_result_file_id else None
    metadata = verified.document.metadata
    report = metadata.mineru_validation
    page_equivalence = metadata.pdf_value_column_page_equivalence
    try:
        provenance = TableReferenceProvenance.model_validate(metadata.mineru_validation_input)
    except ValidationError:
        raise NewGenerationConflict("table_value_column_source_unverified") from None
    if (raw is None or report is None or provenance.mineru_raw_result_file_id != raw.id
            or provenance.mineru_raw_result_sha256 != raw.checksum_sha256 or provenance.retry_count > job.retry_count
            or (page_equivalence is not None and page_equivalence.lineage.parse_generation > provenance.retry_count)
            or report.package_sha256 != raw.checksum_sha256.removeprefix("sha256:")
            or not source.content.startswith(b"%PDF-")):
        raise NewGenerationConflict("table_value_column_source_unverified")
    try:
        content, qualified = read_table_value_mineru_result(job, raw, job_repository=job_repository,
            file_repository=file_repository, file_service=file_service)
        lineage = (table_value_page_lineage(job, raw, frozen=page_equivalence.lineage)
                   if qualified and page_equivalence is not None else None)
        content_sha256 = verify_table_value_package_origin(
            content, source, page_lineage=lineage, frozen_page_equivalence=page_equivalence,
        ) if qualified else None
    except (DocumentIntegrityError, MinerUPackageError, FileNotFoundError):
        raise NewGenerationConflict("table_value_column_source_unverified") from None
    if content_sha256 is None or content_sha256 != report.content_list_sha256:
        raise NewGenerationConflict("table_value_column_source_unverified")
    cumulative = _verified_reviews(verified, submitted, pdf_sha256=source.checksum_sha256.removeprefix("sha256:"),
        content_list_sha256=content_sha256)
    replay = TableValueColumnReplay(source_file_id=source.file_id, source_file_sha256=source.checksum_sha256,
        raw_file_id=raw.id, raw_sha256=raw.checksum_sha256, reviews=cumulative, page_equivalence=page_equivalence)
    return replay, (*verified.files, raw.model_copy(deep=True))
