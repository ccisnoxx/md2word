"""表格值列取证与同包核定共用的 MinerU 源文件核验。"""

from __future__ import annotations

from pydantic import ValidationError

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.files import FileUploadService
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.result_registration import file_lifecycle_unavailable
from app.domains.resources.models import utc_now
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.table_placeholder import checksum
from app.services.document_ir.table_value_column_review import PdfValueColumnPageLineage


MINERU_RESULT_IDENTITY_VERIFIED = "mineru_result_identity_verified"
MINERU_UPLOADED_SOURCE_SHA256 = "mineru_uploaded_source_sha256"


def _input_failure(code: str) -> DocumentIntegrityError:
    return DocumentIntegrityError("MinerU→DocumentIR", {"blocking_quality_flags": [code]})


def _attempt_source(job: DocumentJobRecord) -> tuple:
    return (
        job.tenant_id, job.company_id, job.retry_count, job.status, job.stage,
        job.source_file_id, job.mineru_raw_result_file_id, job.mineru_batch_id, job.mineru_data_id,
        job.document_ir_file_id, job.result_file_id, job.archived_at, job.deleted_at,
    )


def ensure_table_value_mineru_result_current(
    job: DocumentJobRecord,
    raw_file: DocumentFileRecord,
    *,
    job_repository: DocumentJobRepositoryProtocol,
    file_repository: DocumentFileRepositoryProtocol,
) -> None:
    """在慢读两侧核对同一任务来源及同一文件描述。"""
    current = job_repository.get_document_job(job.id)
    if (current is None or _attempt_source(current) != _attempt_source(job)
            or current.archived_at is not None or current.deleted_at is not None
            or (raw_file.tenant_id, raw_file.company_id, raw_file.job_id) != (job.tenant_id, job.company_id, job.id)
            or raw_file.file_type != "mineru_raw_result" or raw_file.mime_type != "application/zip"
            or job.mineru_raw_result_file_id not in {None, raw_file.id}
            or file_repository.get_document_file(raw_file.id) != raw_file
            or file_lifecycle_unavailable(raw_file, file_repository, now=utc_now())):
        raise _input_failure("mineru_raw_result_binding_mismatch")


def read_table_value_mineru_result(
    job: DocumentJobRecord,
    raw_file: DocumentFileRecord,
    *,
    job_repository: DocumentJobRepositoryProtocol,
    file_repository: DocumentFileRepositoryProtocol,
    file_service: FileUploadService,
) -> tuple[bytes, bool]:
    """读取实际 ZIP。旧登记仅在身份相符但解析血缘不完整时保留普通转换资格。"""
    snapshot = raw_file.model_copy(deep=True)
    ensure_table_value_mineru_result_current(
        job, snapshot, job_repository=job_repository, file_repository=file_repository,
    )
    metadata = snapshot.metadata
    source_binding = (
        (job.source_file_id, metadata.get("source_file_id")),
        (job.mineru_batch_id, metadata.get("mineru_batch_id")),
        (job.mineru_data_id, metadata.get("mineru_data_id")),
    )
    parse_attempt = metadata.get("retry_count")
    if (any(expected and registered and expected != registered for expected, registered in source_binding)
            or type(parse_attempt) is int and not 0 <= parse_attempt <= job.retry_count):
        raise _input_failure("mineru_raw_result_binding_mismatch")
    content = file_service.read_file_content(snapshot)
    ensure_table_value_mineru_result_current(
        job, snapshot, job_repository=job_repository, file_repository=file_repository,
    )
    if (len(content) != snapshot.size_bytes
            or snapshot.checksum_sha256 is not None and checksum(content) != snapshot.checksum_sha256):
        raise _input_failure("mineru_raw_result_content_mismatch")
    return content, (
        snapshot.id == job.mineru_raw_result_file_id
        and bool(snapshot.checksum_sha256)
        and type(parse_attempt) is int
        and all(isinstance(registered, str) and bool(registered) and expected == registered
                for expected, registered in source_binding)
    )


def table_value_page_lineage(
    job: DocumentJobRecord, raw_file: DocumentFileRecord, *, frozen: PdfValueColumnPageLineage | None = None,
) -> PdfValueColumnPageLineage | None:
    """原包通过实读校验后，只有独立回显和明确的原解析代才能授权逐页比对。"""
    metadata = raw_file.metadata
    generation = metadata.get("retry_count")
    uploaded_sha256 = metadata.get(MINERU_UPLOADED_SOURCE_SHA256)
    if (
        metadata.get(MINERU_RESULT_IDENTITY_VERIFIED) is not True
        or not isinstance(uploaded_sha256, str)
        or raw_file.id != job.mineru_raw_result_file_id
        or not raw_file.checksum_sha256
        or not job.mineru_batch_id or not job.mineru_data_id
        or (job.source_file_id, job.mineru_batch_id, job.mineru_data_id) != (
            metadata.get("source_file_id"), metadata.get("mineru_batch_id"), metadata.get("mineru_data_id"))
        or type(generation) is not int or not 0 <= generation <= job.retry_count
        or (frozen is None and generation != job.retry_count)
    ):
        return None
    try:
        lineage = PdfValueColumnPageLineage(
            batch_id=job.mineru_batch_id, data_id=job.mineru_data_id,
            parse_generation=generation, raw_file_id=raw_file.id, raw_sha256=raw_file.checksum_sha256,
            source_pdf_sha256=uploaded_sha256,
        )
    except ValidationError:
        return None
    return lineage if frozen is None or frozen == lineage else None
