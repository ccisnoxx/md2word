"""显式成功新代的唯一规则、不可变接受事实与私有账本；不执行对象 I/O。"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.domains.audit.models import AuditEvent
from app.domains.document_jobs.base_quality import fresh_quality_summary
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.review import ReviewExpectedSource, digest, observed_review_source
from app.domains.files.models import DocumentFileRecord
from app.services.document_ir.table_value_column_review import TableValueColumnReview

GENERATION_REQUESTS_ENVELOPE = "_generation_requests_v1"
_Checksum = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


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


class TableValueColumnReplay(BaseModel):
    """Worker 回放的同包输入，随新代接纳事务冻结。"""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: Literal["table-value-column-replay/v1"] = "table-value-column-replay/v1"
    source_file_id: str = Field(min_length=1)
    source_file_sha256: _Checksum
    raw_file_id: str = Field(min_length=1)
    raw_sha256: _Checksum
    reviews: tuple[TableValueColumnReview, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_manual_reviews(self) -> Self:
        source = self.source_file_sha256.removeprefix("sha256:")
        if (len({review.json_pointer for review in self.reviews}) != len(self.reviews)
                or len({review.content_list_sha256 for review in self.reviews}) != 1
                or any(review.source_pdf_sha256 != source or any(c.pdf_binding is not None for c in review.corrections)
                       for review in self.reviews)):
            raise ValueError("同包重生成需要同一版本的逐表人工核定。")
        return self


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
    table_value_column_replay: TableValueColumnReplay | None = None
    table_value_column_request_sha256: _Checksum | None = None
    table_value_column_files: tuple[DocumentFileRecord, ...] = ()

    _request_id = field_validator("request_id")(canonical_generation_request_id)

    @field_validator("note", mode="before")
    @classmethod
    def _note(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _validate_replay_submission(self) -> Self:
        if self.table_value_column_replay is None:
            if self.table_value_column_request_sha256 is not None or self.table_value_column_files:
                raise ValueError("普通新代不能携带同包核定输入。")
        elif self.table_value_column_request_sha256 is None or len(self.table_value_column_files) != 4:
            raise ValueError("同包核定缺少请求摘要或经认证的文件描述。")
        return self


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


class _TableValueColumnReplayEntry(BaseModel):
    """私有账本区分客户端请求摘要与累计核定、实物来源所形成的执行摘要。"""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    intent: TableValueColumnReplay
    request_sha256: _Checksum
    evidence_sha256: _Checksum
    execution_sha256: _Checksum


class NewGenerationLedgerEntry(BaseModel):
    """只在 job 私有 envelope 保存；审计与接受事实共用同一个提交点。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    acceptance: NewGenerationAcceptance
    audit: AuditEvent
    table_value_column_replay: _TableValueColumnReplayEntry | None = Field(
        default=None, exclude_if=lambda replay: replay is None,
    )


def new_generation_request_sha256(
    *, job_id: str, actor_id: str, expected_source: ReviewExpectedSource, note: str,
    table_value_column_request_sha256: str | None = None,
) -> str:
    payload = {"schema_version": "document-new-generation-request/v1", "job_id": job_id,
        "actor_id": actor_id, "expected_source": expected_source.model_dump(mode="json"), "note": note.strip()}
    if table_value_column_request_sha256 is not None:
        payload.update(schema_version="document-new-generation-request/v2", action="replay_table_value_columns",
                       table_value_column_request_sha256=table_value_column_request_sha256)
    return digest(payload)


def _replay_execution_sha256(
    intent: TableValueColumnReplay, receipt: NewGenerationAcceptance, evidence_sha256: str,
) -> str:
    return digest({"intent": intent.model_dump(mode="json"), "evidence_sha256": evidence_sha256,
        "accepted_generation": receipt.accepted_generation, "request_id": receipt.request_id,
        "request_snapshot_sha256": receipt.request_snapshot_sha256, "submission_sha256": receipt.submission_sha256})


def decode_generation_requests(payload: dict[str, Any]) -> dict[str, NewGenerationLedgerEntry]:
    """只解码 owner 的版本化账本；坏数据不能解释为空账本后重复扣预算。"""

    raw = payload.get(GENERATION_REQUESTS_ENVELOPE, {})
    if not isinstance(raw, dict):
        raise ValueError("新代请求账本必须为对象。")
    entries = {}
    for key, value in raw.items():
        # 核定记录沿第三阶段严格 JSON 装载，JSON 数组对应其不可变 tuple。
        entry = (NewGenerationLedgerEntry.model_validate_json(json.dumps(value, ensure_ascii=False))
                 if isinstance(value, dict) and "table_value_column_replay" in value
                 else NewGenerationLedgerEntry.model_validate(value))
        receipt, audit = entry.acceptance, entry.audit
        replay = entry.table_value_column_replay
        audit_details = audit.details or {}
        if (key != canonical_generation_request_id(key) or receipt.request_id != key
                or receipt.job_id != payload["id"] or receipt.tenant_id != payload["tenant_id"]
                or receipt.company_id != payload["company_id"]
                or receipt.accepted_generation != receipt.expected_source.generation + 1
                or receipt.submission_sha256 != new_generation_request_sha256(job_id=receipt.job_id,
                    actor_id=receipt.actor_id, expected_source=receipt.expected_source, note=receipt.note,
                    table_value_column_request_sha256=replay.request_sha256 if replay else None)
                or receipt.accepted_at.tzinfo is None
                or (audit.audit_id, audit.target_id, audit.actor_id, audit.action)
                   != (receipt.audit_id, receipt.job_id, receipt.actor_id, "document_job.new_generation.accepted")
                or replay is not None and (
                    replay.execution_sha256 != _replay_execution_sha256(replay.intent, receipt, replay.evidence_sha256)
                    or audit_details.get("execution_sha256") != replay.execution_sha256
                    or audit_details.get("action") != "replay_table_value_columns"
                )):
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
        table_value_column_request_sha256=submission.table_value_column_request_sha256,
    ):
        raise NewGenerationConflict("new_generation_request_conflict")
    return entry


def read_table_value_column_replay(
    payload: dict[str, Any], *, job: DocumentJobRecord, generation: int,
) -> TableValueColumnReplay | None:
    """最新显式新代决定动作。失败重试只有仍绑定同一资源和原包才可沿用。"""
    entries = decode_generation_requests(payload).values()
    generations = [entry.acceptance.accepted_generation for entry in entries]
    if len(set(generations)) != len(generations):
        raise ValueError("新代请求账本有重复的接受代次。")
    latest = max(entries, key=lambda entry: entry.acceptance.accepted_generation, default=None)
    if latest is None or latest.table_value_column_replay is None:
        return None
    intent = latest.table_value_column_replay.intent
    if (job.retry_count != generation or latest.acceptance.accepted_generation > generation
            or job.mode != "direct_pdf_to_word" or job.source_file_id != intent.source_file_id
            or job.mineru_raw_result_file_id != intent.raw_file_id
            or digest(job.request_snapshot) != latest.acceptance.request_snapshot_sha256):
        raise NewGenerationConflict("new_generation_source_changed")
    return intent


def new_generation_file_ids(job: DocumentJobRecord, submission: NewGenerationSubmission) -> tuple[str, ...]:
    """三个适配器按相同的身份顺序读取并锁定提交依赖。"""
    identities = {job.source_file_id, *(file.id for file in submission.table_value_column_files)}
    if job.result_file_id is not None:
        identities.add(job.result_file_id)
    return tuple(sorted(identities))


def new_generation_eligibility_reason(job: DocumentJobRecord, *, max_retries: int) -> str | None:
    if job.delivery_status == "published" or job.current_publication_id is not None:
        return "publication_immutable"
    if job.status != "succeeded" or job.archived_at is not None or job.deleted_at is not None:
        return "new_generation_state_invalid"
    if job.retry_count >= max_retries:
        return "new_generation_budget_exhausted"
    return None


def _file_available(file: DocumentFileRecord, now: datetime) -> bool:
    expiry = file.expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return (file.status == "uploaded" and file.deletion_claim is None and bool(file.checksum_sha256)
            and file.size_bytes > 0 and (expiry is None or expiry > now))


def _validate_table_value_column_files(
    job: DocumentJobRecord, submission: NewGenerationSubmission, source: DocumentFileRecord,
    current_files: dict[str, DocumentFileRecord], now: datetime,
) -> str:
    """锁内只复核字节认证时见到的版本描述和当前指针。"""
    from app.domains.document_jobs.table_evidence import validate_candidate_binding

    replay = submission.table_value_column_replay
    result = current_files.get(job.result_file_id)
    if (job.mode != "direct_pdf_to_word" or replay is None or result is None
            or job.mineru_raw_result_file_id != replay.raw_file_id
            or (source.id, source.checksum_sha256) != (replay.source_file_id, replay.source_file_sha256)):
        raise NewGenerationConflict("new_generation_source_changed")
    try:
        binding = validate_candidate_binding(job, result)
    except ValueError:
        raise NewGenerationConflict("new_generation_source_changed") from None
    if binding is None:
        raise NewGenerationConflict("new_generation_source_changed")
    descriptor, _, _ = binding
    expected = {
        replay.raw_file_id: ("mineru_raw_result", replay.raw_sha256),
        descriptor.ir_file_id: ("document_ir", descriptor.ir_file_sha256),
        descriptor.report_file_id: ("quality_report", descriptor.checksum_sha256),
        result.id: ("generated_word", submission.expected_source.result_sha256),
    }
    snapshots = {file.id: file for file in submission.table_value_column_files}
    if len(expected) != 4 or expected.keys() != snapshots.keys():
        raise NewGenerationConflict("new_generation_source_changed")
    for identity, (role, checksum) in expected.items():
        file = current_files.get(identity)
        if (file is None or file != snapshots[identity] or not _file_available(file, now)
                or (file.tenant_id, file.company_id, file.job_id, file.file_type, file.checksum_sha256)
                   != (job.tenant_id, job.company_id, job.id, role, checksum)):
            raise NewGenerationConflict("new_generation_source_changed")
    return digest([source.model_dump(mode="json"),
                   *[snapshots[identity].model_dump(mode="json") for identity in sorted(snapshots)]])


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
    if ((source.id, source.tenant_id, source.company_id, source.file_type, source.mime_type)
            != (job.source_file_id, job.tenant_id, job.company_id, "source_pdf", "application/pdf")
            or not _file_available(source, now)):
        raise NewGenerationConflict("new_generation_source_unavailable")
    replay = submission.table_value_column_replay
    evidence_sha256 = _validate_table_value_column_files(job, submission, source, current_files, now) if replay else None
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
    if replay is not None:
        patch.update(status="running", stage="parsed", progress=30,
            mineru_raw_result_file_id=replay.raw_file_id,
            mineru_batch_id=job.mineru_batch_id, mineru_data_id=job.mineru_data_id)
    updated = DocumentJobRecord.model_validate({**job.model_dump(mode="python"), **patch})
    receipt = NewGenerationAcceptance(request_id=submission.request_id, job_id=job.id,
        tenant_id=job.tenant_id, company_id=job.company_id, actor_id=submission.actor_id, note=submission.note,
        submission_sha256=new_generation_request_sha256(job_id=job.id, actor_id=submission.actor_id,
            expected_source=submission.expected_source, note=submission.note,
            table_value_column_request_sha256=submission.table_value_column_request_sha256),
        expected_source=submission.expected_source,
        request_snapshot_sha256=submission.expected_request_snapshot_sha256, accepted_generation=generation,
        accepted_at=now, audit_id=submission.audit_id)
    details = {"request_id": receipt.request_id, "source_generation": job.retry_count,
        "accepted_generation": generation, "reason_code": "new_generation_accepted",
        "source_sha256": source.checksum_sha256, "submission_sha256": receipt.submission_sha256}
    table_value_column_entry = None
    if replay is not None:
        execution_sha256 = _replay_execution_sha256(replay, receipt, evidence_sha256)
        table_value_column_entry = _TableValueColumnReplayEntry(intent=replay,
            request_sha256=submission.table_value_column_request_sha256, evidence_sha256=evidence_sha256,
            execution_sha256=execution_sha256)
        details.update(action="replay_table_value_columns", execution_sha256=execution_sha256)
    audit = AuditEvent(audit_id=receipt.audit_id, actor_id=receipt.actor_id, actor_role="admin",
        action="document_job.new_generation.accepted", target_type="document_job", target_id=job.id,
        reason=receipt.note, trace_id=submission.trace_id, created_at=now,
        details=details)
    return updated, NewGenerationLedgerEntry(acceptance=receipt, audit=audit,
        table_value_column_replay=table_value_column_entry)
