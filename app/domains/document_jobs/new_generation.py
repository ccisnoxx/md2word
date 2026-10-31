"""显式成功新代的唯一规则、不可变接受事实与私有账本；不执行对象 I/O。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from app.domains.audit.models import AuditEvent
from app.domains.document_jobs.base_quality import fresh_quality_summary
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.review import ReviewExpectedSource, digest, observed_review_source
from app.domains.files.models import DocumentFileRecord

GENERATION_REQUESTS_ENVELOPE = "_generation_requests_v1"


class NewGenerationConflict(ValueError):
    """固定拒绝原因由应用层映射，不公开登记描述或底层错误。"""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__("新代接受条件已变化，请重新读取任务。")


class NewGenerationCommitUnknownError(RuntimeError):
    """提交点已开始但结果不可确认；只能用原 key 在主库对账。"""

    reason_code = "new_generation_acceptance_unknown"

    def __init__(self):
        super().__init__("新代接受结果暂不可确认，请使用原请求标识查询。")


def canonical_generation_request_id(value: str) -> str:
    return str(UUID(value))


class NewGenerationSubmission(BaseModel):
    """应用层锁外认证的冻结观察；新 key 必须在 metadata 锁内重新比较。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: str
    actor_id: str = Field(min_length=1)
    note: str = Field(min_length=1, max_length=1000)
    expected_source: ReviewExpectedSource
    expected_request_snapshot_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_file: DocumentFileRecord
    audit_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)

    _request_id = field_validator("request_id")(canonical_generation_request_id)

    @field_validator("note", mode="before")
    @classmethod
    def _note(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class NewGenerationAcceptance(BaseModel):
    """接受代次与当前代次分离；只含不可变标量及冻结来源，不含私有文件描述。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["document-new-generation/v1"] = "document-new-generation/v1"
    request_id: str
    job_id: str
    tenant_id: str
    company_id: str
    actor_id: str
    note: str
    submission_sha256: str
    expected_source: ReviewExpectedSource
    request_snapshot_sha256: str
    accepted_generation: StrictInt = Field(ge=1)
    accepted_at: datetime
    audit_id: str


class NewGenerationLedgerEntry(BaseModel):
    """只在 job 私有 envelope 保存；审计与接受事实共用同一个提交点。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    acceptance: NewGenerationAcceptance
    audit: AuditEvent


def new_generation_request_sha256(
    *, job_id: str, actor_id: str, expected_source: ReviewExpectedSource, note: str,
) -> str:
    return digest({"schema_version": "document-new-generation-request/v1", "job_id": job_id,
        "actor_id": actor_id, "expected_source": expected_source.model_dump(mode="json"), "note": note.strip()})


def decode_generation_requests(payload: dict[str, Any]) -> dict[str, NewGenerationLedgerEntry]:
    """只解码 owner 的版本化账本；坏数据不能解释为空账本后重复扣预算。"""

    raw = payload.get(GENERATION_REQUESTS_ENVELOPE, {})
    if not isinstance(raw, dict):
        raise ValueError("新代请求账本必须为对象。")
    entries = {}
    for key, value in raw.items():
        entry = NewGenerationLedgerEntry.model_validate(value)
        receipt, audit = entry.acceptance, entry.audit
        if (key != canonical_generation_request_id(key) or receipt.request_id != key
                or receipt.job_id != payload["id"] or receipt.tenant_id != payload["tenant_id"]
                or receipt.company_id != payload["company_id"]
                or receipt.accepted_generation != receipt.expected_source.generation + 1
                or receipt.submission_sha256 != new_generation_request_sha256(job_id=receipt.job_id,
                    actor_id=receipt.actor_id, expected_source=receipt.expected_source, note=receipt.note)
                or receipt.accepted_at.tzinfo is None
                or (audit.audit_id, audit.target_id, audit.actor_id, audit.action)
                   != (receipt.audit_id, receipt.job_id, receipt.actor_id, "document_job.new_generation.accepted")):
            raise ValueError("新代请求账本的接受身份或审计损坏。")
        entries[key] = entry
    return entries


def ensure_generation_ledger_not_patched(patch: dict[str, Any]) -> None:
    if GENERATION_REQUESTS_ENVELOPE in patch:
        raise NewGenerationConflict("new_generation_immutable")


def read_generation_request(
    payload: dict[str, Any], *, request_id: str, actor_id: str,
) -> NewGenerationLedgerEntry | None:
    entry = decode_generation_requests(payload).get(canonical_generation_request_id(request_id))
    if entry is not None and entry.acceptance.actor_id != actor_id:
        raise NewGenerationConflict("new_generation_request_conflict")
    return entry


def replay_generation_request(
    payload: dict[str, Any], submission: NewGenerationSubmission,
) -> NewGenerationLedgerEntry | None:
    entry = read_generation_request(payload, request_id=submission.request_id, actor_id=submission.actor_id)
    if entry is not None and entry.acceptance.submission_sha256 != new_generation_request_sha256(
        job_id=payload["id"], actor_id=submission.actor_id, expected_source=submission.expected_source, note=submission.note,
    ):
        raise NewGenerationConflict("new_generation_request_conflict")
    return entry


def new_generation_eligibility_reason(job: DocumentJobRecord, *, max_retries: int) -> str | None:
    if job.delivery_status == "published" or job.current_publication_id is not None:
        return "publication_immutable"
    if job.status != "succeeded" or job.archived_at is not None or job.deleted_at is not None:
        return "new_generation_state_invalid"
    if job.retry_count >= max_retries:
        return "new_generation_budget_exhausted"
    return None


def accept_new_generation(
    job: DocumentJobRecord, submission: NewGenerationSubmission, *, current_files: dict[str, DocumentFileRecord],
    max_retries: int, now: datetime,
) -> tuple[DocumentJobRecord, NewGenerationLedgerEntry]:
    """仅供查账后且已持有 job/有序文件锁的新 key 调用。"""

    reason = new_generation_eligibility_reason(job, max_retries=max_retries)
    if reason is not None:
        raise NewGenerationConflict(reason)
    if observed_review_source(job, current_files.get(job.result_file_id)) != submission.expected_source:
        raise NewGenerationConflict("new_generation_source_changed")
    if digest(job.request_snapshot) != submission.expected_request_snapshot_sha256:
        raise NewGenerationConflict("new_generation_snapshot_changed")
    source = current_files.get(job.source_file_id)
    if source is None:
        raise NewGenerationConflict("new_generation_source_unavailable")
    if source.model_dump(mode="json") != submission.source_file.model_dump(mode="json"):
        raise NewGenerationConflict("new_generation_source_changed")
    expiry = source.expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if ((source.id, source.tenant_id, source.company_id, source.file_type, source.mime_type, source.status)
            != (job.source_file_id, job.tenant_id, job.company_id, "source_pdf", "application/pdf", "uploaded")
            or source.deletion_claim is not None or not source.checksum_sha256 or source.size_bytes <= 0
            or (expiry is not None and expiry <= now)):
        raise NewGenerationConflict("new_generation_source_unavailable")
    generation = job.retry_count + 1
    patch = dict(retry_count=generation, status="pending", stage="uploaded", progress=0,
        result_file_id=None, prepared_result=None, word_preview_state=None, mineru_raw_result_file_id=None,
        source_document_ir_file_id=None, document_ir_file_id=None, image_asset_file_ids=[],
        mineru_batch_id=None, mineru_data_id=None, mineru_callback_seed=None, failed_stage=None,
        error_code=None, error_message=None, timeout_at=None, started_at=None, completed_at=None, canceled_at=None,
        quality_status="pending", quality_summary=fresh_quality_summary(generation), review_status="unreviewed",
        delivery_status="internal_draft", current_review_record_id=None, current_review_binding=None,
        translation_qa_status="unreviewed", translation_qa_issue_type=None, translation_qa_note=None,
        translation_qa_reviewed_by=None, translation_qa_reviewed_at=None, updated_at=now)
    updated = DocumentJobRecord.model_validate({**job.model_dump(mode="python"), **patch})
    receipt = NewGenerationAcceptance(request_id=submission.request_id, job_id=job.id,
        tenant_id=job.tenant_id, company_id=job.company_id, actor_id=submission.actor_id, note=submission.note,
        submission_sha256=new_generation_request_sha256(job_id=job.id, actor_id=submission.actor_id,
            expected_source=submission.expected_source, note=submission.note), expected_source=submission.expected_source,
        request_snapshot_sha256=submission.expected_request_snapshot_sha256, accepted_generation=generation,
        accepted_at=now, audit_id=submission.audit_id)
    audit = AuditEvent(audit_id=receipt.audit_id, actor_id=receipt.actor_id, actor_role="admin",
        action="document_job.new_generation.accepted", target_type="document_job", target_id=job.id,
        reason=receipt.note, trace_id=submission.trace_id, created_at=now,
        details={"request_id": receipt.request_id, "source_generation": job.retry_count,
            "accepted_generation": generation, "reason_code": "new_generation_accepted",
            "source_sha256": source.checksum_sha256, "submission_sha256": receipt.submission_sha256})
    return updated, NewGenerationLedgerEntry(acceptance=receipt, audit=audit)
