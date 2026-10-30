"""不可变发布记录与短事务内的唯一门禁；不在此执行对象 I/O。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
import posixpath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.domains.document_jobs.quality_state import effective_quality_status
from app.domains.audit.models import AuditEvent
from app.domains.document_jobs.review import ReviewExpectedSource, ReviewRecord, digest, observed_review_source, review_validity
from app.domains.files.models import DocumentFileRecord

PUBLICATION_ENVELOPE = "_publication_records_v1"


class PublicationConflict(ValueError):
    """固定机器码由 HTTP owner 映射，避免公开存储或配置内容。"""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__("发布条件不满足，请刷新并核对当前文档。")


class PublicationExpectedSource(ReviewExpectedSource):
    review_record_id: str | None
    review_sequence: StrictInt = Field(ge=0)
    preview_run_id: str | None
    preview_revision: StrictInt | None = Field(ge=0)
    quality_summary_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def observed_publication_source(job: Any, file: DocumentFileRecord | None) -> PublicationExpectedSource:
    state = job.word_preview_state
    return PublicationExpectedSource(**observed_review_source(job, file).model_dump(),
        review_record_id=job.current_review_record_id, review_sequence=job.review_sequence,
        preview_run_id=state.current_run.run_id if state is not None else None,
        preview_revision=state.revision if state is not None else None,
        quality_summary_sha256=digest(job.quality_summary))


class PublicationRecord(BaseModel):
    """私有 payload 不能直接作为 API DTO；每次序列化返回独立嵌套副本。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["document-publication/v1"] = "document-publication/v1"
    id: str
    job_id: str
    tenant_id: str
    company_id: str
    generation: StrictInt = Field(ge=0)
    request_id: str
    submission_sha256: str
    published_by: str
    publisher_role: Literal["admin"] = "admin"
    published_at: datetime
    note: str = Field(min_length=1, max_length=1000)
    trace_id: str
    source_file_id: str
    source_sha256: str
    result_file_id: str
    result_sha256: str
    expected_source: PublicationExpectedSource
    review_record_id: str
    review_sequence: StrictInt = Field(ge=1)
    files: tuple[DocumentFileRecord, ...]
    quality: dict[str, Any]
    preview: dict[str, Any]
    configuration: dict[str, Any]
    protected_file_ids: tuple[str, ...]
    audit: AuditEvent


class PublicationSubmission(BaseModel):
    """受权服务在锁外认证后形成的观察，仓储必须在锁内重新比较。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    record: PublicationRecord
    expected_job_sha256: str
    files: tuple[DocumentFileRecord, ...]


def publication_request_sha256(*, job_id: str, actor_id: str, expected_source: PublicationExpectedSource, note: str) -> str:
    return digest({"job_id": job_id, "actor_id": actor_id,
                   "expected_source": expected_source.model_dump(mode="json"), "note": note})


def physical_identity(file: DocumentFileRecord) -> tuple[str, str, str]:
    """锁内按保守本地 namespace 比较；真实根和 symlink 由文件 owner 锁外认证。"""
    from app.domains.files.result_registration import ensure_new_file_identity
    path = PurePosixPath(file.object_key)
    try:
        ensure_new_file_identity(file)
    except ValueError:
        raise PublicationConflict("publication_object_identity_unverified") from None
    provider = "local" if file.storage_provider in {"local_file", "local_object"} else file.storage_provider
    return provider, file.bucket if provider == "s3" else "", str(path)


def ensure_publication_object_identities(files: list[DocumentFileRecord], all_files: list[DocumentFileRecord]) -> None:
    for file in files:
        identity = physical_identity(file)
        for other in all_files:
            if other.id == file.id:
                continue
            # 非规范历史别名同样必须识别，不能只验证候选自身布局。
            provider = "local" if other.storage_provider in {"local_file", "local_object"} else other.storage_provider
            other_identity = (provider, other.bucket if provider == "s3" else "", posixpath.normpath(other.object_key))
            if identity == other_identity:
                raise PublicationConflict("publication_object_identity_unverified")


def publication_file_available(file: DocumentFileRecord, *, now: datetime) -> bool:
    expiry = file.expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return file.status == "uploaded" and file.deletion_claim is None and (expiry is None or expiry > now)


def commit_publication(job: Any, submission: PublicationSubmission, *, prior: list[PublicationRecord],
                       current_files: list[DocumentFileRecord], all_files: list[DocumentFileRecord],
                       reviews: list[ReviewRecord], now: datetime):
    """由 adapter 持有 job 与全部依赖 file 序列化点时调用；成功审计属于返回记录。"""
    from app.domains.document_jobs.models import DocumentJobRecord

    record = submission.record
    replay = next((item for item in prior if item.job_id == job.id and item.request_id == record.request_id), None)
    if replay is not None:
        if replay.submission_sha256 != record.submission_sha256:
            raise PublicationConflict("publication_request_conflict")
        return job, replay, False
    if any(item.result_file_id == record.result_file_id or
           (item.job_id == job.id and item.generation == record.generation) for item in prior):
        raise PublicationConflict("publication_already_exists")
    if (job.id, job.tenant_id, job.company_id) != (record.job_id, record.tenant_id, record.company_id):
        raise PublicationConflict("publication_source_changed")
    if digest(job.model_dump(mode="json")) != submission.expected_job_sha256:
        raise PublicationConflict("publication_source_changed")
    if (job.status != "succeeded" or job.stage != "completed" or job.deleted_at is not None
            or job.archived_at is not None or job.delivery_status == "published" or job.current_publication_id is not None):
        raise PublicationConflict("publication_state_conflict")
    quality = effective_quality_status(job)
    if quality not in {"passed", "warning"}:
        raise PublicationConflict("publication_quality_" + quality)
    files = {file.id: file for file in current_files}
    if len(files) != len(submission.files) or set(files) != set(record.protected_file_ids):
        raise PublicationConflict("publication_source_changed")
    for observed in submission.files:
        current = files.get(observed.id)
        if current != observed or not publication_file_available(current, now=now):
            raise PublicationConflict("publication_result_unavailable")
        if (current.tenant_id, current.company_id) != (job.tenant_id, job.company_id):
            raise PublicationConflict("publication_source_changed")
    result = files.get(job.result_file_id)
    if result is None or observed_publication_source(job, result) != record.expected_source:
        raise PublicationConflict("publication_source_changed")
    review = next((item for item in reviews if item.id == job.current_review_record_id), None)
    if (job.review_status != "approved" or review is None or review.origin != "live" or review.status != "approved"
            or review.sequence != record.review_sequence or review.binding != job.current_review_binding
            or review_validity(job, result, now=now) is not None):
        raise PublicationConflict("publication_review_invalid")
    state = job.word_preview_state
    if (state is None or state.current_run.status != "succeeded"
            or state.current_run.artifact_stage != "confirmed"
            or state.current_run.confirmed_attempt != state.current_run.attempt_count):
        raise PublicationConflict("publication_preview_unavailable")
    ensure_publication_object_identities(list(submission.files), all_files)
    updated = DocumentJobRecord.model_validate({**job.model_dump(mode="python"),
        "current_publication_id": record.id, "delivery_status": "published", "updated_at": record.published_at})
    return updated, record, True


def decode_file_publications(payload: dict) -> list[PublicationRecord]:
    raw = payload.get(PUBLICATION_ENVELOPE, [])
    if not isinstance(raw, list):
        raise ValueError("发布记录 envelope 必须为数组。")
    return [PublicationRecord.model_validate(item) for item in raw]


def validate_publication_history(job: Any, records: list[PublicationRecord]) -> None:
    if len(records) > 1 or len({record.id for record in records}) != len(records):
        raise ValueError("当前任务的发布历史身份损坏。")
    if any((record.job_id, record.tenant_id, record.company_id) != (job.id, job.tenant_id, job.company_id) for record in records):
        raise ValueError("发布记录归属不一致。")
    if job.current_publication_id is not None and (
        len(records) != 1 or records[0].id != job.current_publication_id or job.delivery_status != "published"
    ):
        raise ValueError("发布引用与不可变历史不一致。")
