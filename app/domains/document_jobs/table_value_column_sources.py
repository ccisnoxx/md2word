"""表格值列取证与同包核定共用的 MinerU 源文件核验。"""

from __future__ import annotations

from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.files import FileUploadService
from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.result_registration import file_lifecycle_unavailable
from app.domains.resources.models import utc_now
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.table_placeholder import checksum


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
