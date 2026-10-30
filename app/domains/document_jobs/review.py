"""正式复核记录、锁内提交与只读有效性规则；不承担对象 I/O。"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.domains.document_jobs.quality_state import effective_quality_status
from app.domains.files.models import DocumentFileRecord
from app.domains.users.models import InternalUserRole
from app.domains.files.result_registration import review_source_descriptor

ReviewStatus = Literal["unreviewed", "approved", "needs_fix", "blocked"]
ReviewIssueType = Literal["conversion", "translation", "terminology", "table_structure", "layout", "source_quality", "artifact_missing", "other"]
REVIEW_ENVELOPE = "_review_records_v1"


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def receipt_identity(job: Any) -> str | None:
    if job.prepared_result is None:
        return None
    # 来源计数不属于冻结的 receipt 内容身份。
    return digest(job.prepared_result.model_dump(mode="json", exclude={"file": {"review_source_revision"}}))


class ReviewExpectedSource(BaseModel):
    """调用内的登记观察前置条件；null 精确表示缺失，不是通配符。"""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    generation: StrictInt = Field(ge=0)
    result_file_id: str | None
    result_sha256: str | None = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    file_review_source_revision: StrictInt | None = Field(ge=0)
    receipt_sha256: str | None = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def observed_review_source(job: Any, file: DocumentFileRecord | None) -> ReviewExpectedSource:
    return ReviewExpectedSource(generation=job.retry_count, result_file_id=job.result_file_id,
        result_sha256=file.checksum_sha256 if file else None,
        file_review_source_revision=file.review_source_revision if file else None,
        receipt_sha256=receipt_identity(job))


class ReviewSubmissionConflict(ValueError):
    """锁内实际拒绝原因；旧调用仍保留 None 返回合同。"""
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__("复核提交条件已变化，请重新读取。")


class ReviewBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    generation: StrictInt = Field(ge=0)
    result_file_id: str | None
    binding_state: Literal["verified", "no_result", "unverified_result", "legacy_unbound"]
    result_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    file_review_source_revision: StrictInt | None = Field(default=None, ge=0)
    descriptor: dict[str, Any] | None = None
    receipt_sha256: str | None = None

    @model_validator(mode="after")
    def _verified(self):
        if self.binding_state == "verified" and (
            not self.result_file_id or not self.result_sha256 or self.descriptor is None
            or self.file_review_source_revision is None
        ):
            raise ValueError("已验证复核必须保存主件、实际摘要、描述与来源序号。")
        if self.binding_state == "no_result" and self.result_file_id is not None:
            raise ValueError("无结果绑定不能指定主件。")
        return self


class ReviewQualitySnapshot(BaseModel):
    """保留总体状态与完整摘要指纹，只复制有类型的安全定位信息。"""
    model_config = ConfigDict(extra="forbid", frozen=True)
    quality_status: Literal["pending", "passed", "warning", "blocked"]
    summary_sha256: str
    producers: dict[str, dict[str, str | int | bool | None]] = Field(default_factory=dict)
    flags: dict[Literal["quality_flags", "layout_quality_flags", "blocking_quality_flags"], list[str]] = Field(default_factory=dict)
    unknown_flag_count: StrictInt = Field(default=0, ge=0)


# 这里只允许当前 producer 的固定机器码；带正文或来源 ID 的未知标记仅计数。
_SAFE_FLAGS = frozenset({
    "docx_quality_unavailable", "docx_analysis_error", "docx_no_editable_content",
    "docx_image_only_suspected", "formula_text_fallback", "image_group_uncertain",
    "caption_binding_uncertain", "empty_content_list",
    "source_ir_integrity:block_count_mismatch", "source_ir_integrity:type_count_mismatch",
    "ir_layout_integrity:missing_blocks", "ir_layout_integrity:duplicate_blocks",
    "ir_docx_integrity:image_asset_missing", "ir_docx_integrity:inline_shape_count_mismatch",
    "ir_docx_integrity:table_count_mismatch", "ir_docx_integrity:heading_count_mismatch",
})
_COUNT_FLAG_PREFIXES = frozenset({"docx_latex_residue", "docx_manual_list_markers",
    "docx_plain_toc_entries", "docx_unstyled_heading_candidates", "final_promotional_page_filtered"})


def _safe_quality_flag(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if value in _SAFE_FLAGS:
        return True
    prefix, separator, count = value.partition(":")
    return prefix in _COUNT_FLAG_PREFIXES and separator == ":" and count.isascii() and count.isdecimal()


def quality_snapshot(job: Any) -> ReviewQualitySnapshot:
    """保存当前 producer 的安全计数与完整摘要指纹，不复制未知文本。"""
    producers = {}
    formula = job.quality_summary.get("formula")
    if isinstance(formula, dict):
        allowed_counts = {"formula_count", "omml_count", "semantic_count", "fallback_count"}
        summary = {key: value for key, value in formula.items()
                   if key in allowed_counts and type(value) is int and value >= 0}
        if formula.get("schema_version") == "formula-summary/v1":
            summary["schema_version"] = "formula-summary/v1"
        report_hash = formula.get("report_sha256")
        if isinstance(report_hash, str) and len(report_hash) == 64 and all(c in "0123456789abcdef" for c in report_hash):
            summary["report_sha256"] = report_hash
        producers["formula"] = summary
    flags, unknown_count = {}, 0
    for key in ("quality_flags", "layout_quality_flags", "blocking_quality_flags"):
        raw = job.quality_summary.get(key)
        if isinstance(raw, list):
            flags[key] = [value for value in raw if _safe_quality_flag(value)]
            unknown_count += sum(not _safe_quality_flag(value) for value in raw)
    return ReviewQualitySnapshot(quality_status=effective_quality_status(job),
        summary_sha256=digest(job.quality_summary), producers=producers, flags=flags, unknown_flag_count=unknown_count)


class ReviewSubmission(BaseModel):
    """受权应用层生成的可信上下文；sequence 和质量只在 job 锁内生成。"""
    model_config = ConfigDict(extra="forbid", frozen=True)
    record_id: str
    status: ReviewStatus
    issue_type: ReviewIssueType | None = None
    note: str | None = Field(default=None, max_length=1000)
    reviewed_by: str = Field(min_length=1)
    reviewed_at: datetime
    reviewer_role: InternalUserRole
    binding: ReviewBinding
    expected_source: ReviewExpectedSource | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _approval(self):
        if self.status == "approved" and self.binding.binding_state != "verified":
            raise ValueError("批准要求实际校验的主件绑定。")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("复核时间必须包含时区。")
        return self


class ReviewRecord(BaseModel):
    """追加后不可经业务端口修改；legacy 的未知身份保持空值。"""
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["document-review/v1"] = "document-review/v1"
    id: str
    job_id: str
    tenant_id: str
    company_id: str
    sequence: StrictInt = Field(ge=1)
    status: ReviewStatus
    issue_type: ReviewIssueType | None = None
    note: str | None = Field(default=None, max_length=1000)
    reviewed_by: str | None
    reviewed_at: datetime | None
    reviewer_role: InternalUserRole | None
    origin: Literal["live", "legacy_import"]
    binding: ReviewBinding
    quality: ReviewQualitySnapshot
    submission_sha256: str | None = None
    legacy_observed_status: ReviewStatus | None = None
    legacy_snapshot: dict[str, Any] | None = None
    import_version: str | None = None
    imported_at: datetime | None = None

    @model_validator(mode="after")
    def _live(self):
        if self.origin == "live" and (not self.reviewed_by or self.reviewed_at is None
                                      or self.reviewer_role is None or self.submission_sha256 is None):
            raise ValueError("正式复核缺少实际操作身份或提交指纹。")
        if self.status == "approved" and self.binding.binding_state != "verified":
            raise ValueError("批准记录缺少已验证的主件绑定。")
        return self


def legacy_issue(issue: ReviewIssueType | None) -> str | None:
    return "other" if issue in {"conversion", "table_structure"} else issue


def validate_history(job: Any, records: list[ReviewRecord]) -> None:
    if [r.sequence for r in records] != list(range(1, len(records) + 1)) or len({r.id for r in records}) != len(records):
        raise ValueError("复核历史序号或记录身份损坏。")
    if any((r.job_id, r.tenant_id, r.company_id) != (job.id, job.tenant_id, job.company_id) for r in records):
        raise ValueError("复核历史归属不一致。")
    if job.review_sequence != len(records):
        raise ValueError("复核历史与当前序号不一致。")
    if job.current_review_record_id is not None:
        current = next((r for r in records if r.id == job.current_review_record_id), None)
        if current is None or current.sequence != job.review_sequence or current.binding != job.current_review_binding or current.status != job.review_status:
            raise ValueError("当前复核引用与历史不一致。")


def decode_file_history(payload: dict) -> list[ReviewRecord]:
    raw = payload.get(REVIEW_ENVELOPE, [])
    if not isinstance(raw, list):
        raise ValueError("复核历史 envelope 必须为数组。")
    return [ReviewRecord.model_validate(item) for item in raw]


def submit_review(job: Any, submission: ReviewSubmission, prior: ReviewRecord | None):
    """单 job 序列化点内调用；同请求 ID 重放不推进当前指针。"""
    from app.domains.document_jobs.models import DocumentJobRecord
    from app.domains.translation.modes import is_translation_document_job_mode
    fingerprint = digest(submission.model_dump(mode="json"))
    if prior is not None:
        if prior.origin != "live" or prior.submission_sha256 != fingerprint:
            raise ValueError("复核记录 ID 已用于不同提交。")
        return job, None
    b = submission.binding
    reason = None
    if job.deleted_at is not None or job.delivery_status == "published":
        reason = "review_state_conflict"
    elif (job.retry_count != b.generation or job.result_file_id != b.result_file_id
            or receipt_identity(job) != b.receipt_sha256):
        reason = "review_source_changed"
    elif submission.status == "approved":
        if effective_quality_status(job) == "blocked":
            reason = "review_quality_blocked"
        elif job.status != "succeeded" or not job.result_file_id:
            reason = "review_result_unavailable"
    if reason is not None:
        if submission.expected_source is not None:
            raise ReviewSubmissionConflict(reason)
        return None, None
    record = ReviewRecord(id=submission.record_id, job_id=job.id, tenant_id=job.tenant_id, company_id=job.company_id,
        sequence=job.review_sequence + 1, status=submission.status, issue_type=submission.issue_type, note=submission.note,
        reviewed_by=submission.reviewed_by, reviewed_at=submission.reviewed_at, reviewer_role=submission.reviewer_role,
        origin="live", binding=b, quality=quality_snapshot(job), submission_sha256=fingerprint)
    patch = {"current_review_record_id": record.id, "current_review_binding": b, "review_sequence": record.sequence,
             "review_status": record.status, "updated_at": record.reviewed_at}
    if record.status != "approved":
        patch["delivery_status"] = "internal_draft"
    if is_translation_document_job_mode(job.mode):
        cleared = record.status == "unreviewed"
        patch.update(translation_qa_status=record.status, translation_qa_issue_type=None if cleared else legacy_issue(record.issue_type),
            translation_qa_note=None if cleared else record.note, translation_qa_reviewed_by=None if cleared else record.reviewed_by,
            translation_qa_reviewed_at=None if cleared else record.reviewed_at)
    return DocumentJobRecord.model_validate({**job.model_dump(mode="python"), **patch}), record


def receipt_matches_file(file: DocumentFileRecord, receipt: Any) -> bool:
    """复核读取允许保留期收紧，原内容、归属和 evidence 比较保持。"""
    return (file.expires_at is not None and receipt.file.expires_at is not None
        and file.expires_at <= receipt.file.expires_at
        and file == receipt.file.model_copy(update={"etag": file.etag, "updated_at": file.updated_at,
            "expires_at": file.expires_at, "review_source_revision": file.review_source_revision}))


def review_validity(job: Any, file: DocumentFileRecord | None, *, now: datetime) -> str | None:
    """返回内部失效原因；不读对象、不写回，也不将 published 快照降级。"""
    binding = job.current_review_binding
    if binding is None or job.current_review_record_id is None:
        return "legacy_unbound" if job.review_status == "approved" else None
    if binding.generation != job.retry_count or binding.result_file_id != job.result_file_id or binding.receipt_sha256 != receipt_identity(job):
        return "source_changed"
    if binding.binding_state != "verified":
        return "legacy_unbound" if job.review_status == "approved" else None
    if file is None:
        return "artifact_missing"
    expiry = file.expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if ((file.id, file.tenant_id, file.company_id, file.job_id, file.file_type, file.status)
        != (job.result_file_id, job.tenant_id, job.company_id, job.id, "generated_word", "uploaded")
        or (expiry is not None and expiry <= now)):
        return "artifact_unavailable"
    if file.review_source_revision != binding.file_review_source_revision or review_source_descriptor(file) != binding.descriptor:
        return "source_changed"
    if file.checksum_sha256 is not None and file.checksum_sha256 != binding.result_sha256:
        return "integrity_conflict"
    if job.prepared_result is not None and not receipt_matches_file(file, job.prepared_result):
        return "integrity_conflict"
    if job.review_status == "approved" and effective_quality_status(job) == "blocked":
        return "quality_blocked"
    return None


def effective_review_job(job: Any, file: DocumentFileRecord | None, *, now: datetime):
    quality = effective_quality_status(job)
    patch = {"quality_status": quality} if quality != job.quality_status else {}
    if job.delivery_status == "ready_to_publish" and quality in {"pending", "blocked"}:
        patch["delivery_status"] = "internal_draft"
    if patch:
        job = job.model_copy(update=patch)
    if review_validity(job, file, now=now) is None or job.delivery_status == "published":
        return job
    # 读副本不能送回写 owner；保留 raw 备注、历史和原提交绑定以便审计。
    return job.model_copy(update={"review_status": "unreviewed", "delivery_status": "internal_draft"})


IMPORT_VERSION = "document-review-import/v1"


def legacy_import_id(job: Any) -> str:
    return "review_import_v1_" + digest([job.tenant_id, job.company_id, job.id]).split(":")[1]


def legacy_source_sha256(payload: dict) -> str:
    # 排除迁移自身改写的字段；raw QA、来源、质量和原业务时间仍在源摘要内。
    excluded = {REVIEW_ENVELOPE, "current_review_record_id", "current_review_binding", "review_sequence",
                "review_status", "delivery_status"}
    return digest({key: value for key, value in payload.items() if key not in excluded})


def legacy_review_import(job: Any, payload: dict, records: list[ReviewRecord], *, now: datetime):
    """恢复优先识别已提交导入，不能把自己的批准降级当作外部源变化。"""
    from app.domains.document_jobs.models import DocumentJobRecord
    validate_history(job, records)
    if any(r.origin == "live" for r in records):
        if job.review_status == "approved" and (job.current_review_binding is None or job.current_review_binding.binding_state != "verified"):
            raise ValueError("当前批准缺少正式主件绑定。")
        return job, None, "live_skipped"
    imported = next((r for r in records if r.id == legacy_import_id(job)), None)
    if imported is not None:
        if (imported.origin != "legacy_import" or imported.import_version != IMPORT_VERSION
                or imported.legacy_snapshot is None
                or imported.legacy_snapshot.get("source_sha256") != legacy_source_sha256(payload)):
            raise ValueError("历史导入源发生冲突。")
        if imported.legacy_observed_status == "approved" and (
                job.review_status != "unreviewed" or job.delivery_status != "internal_draft"):
            raise ValueError("历史批准的迁移失效投影被改写。")
        return job, None, "already_imported"
    if records or job.current_review_record_id is not None:
        raise ValueError("正式复核引用与历史不一致。")
    if job.delivery_status == "published":
        raise ValueError("已发布任务缺少正式复核绑定，需独立迁移决策。")
    observed = job.review_status
    status = "unreviewed" if observed == "approved" else observed
    qa = {key: value for key, value in payload.items() if key.startswith("translation_qa_")}
    record = ReviewRecord(id=legacy_import_id(job), job_id=job.id, tenant_id=job.tenant_id, company_id=job.company_id,
        sequence=1, status=status, issue_type=job.translation_qa_issue_type, note=job.translation_qa_note,
        reviewed_by=job.translation_qa_reviewed_by, reviewed_at=job.translation_qa_reviewed_at, reviewer_role=None,
        origin="legacy_import", binding=ReviewBinding(generation=job.retry_count, result_file_id=job.result_file_id,
            binding_state="legacy_unbound", receipt_sha256=receipt_identity(job)), quality=quality_snapshot(job),
        legacy_observed_status=observed, legacy_snapshot={"qa": qa, "source_sha256": legacy_source_sha256(payload),
            "review_status": observed, "delivery_status": job.delivery_status}, import_version=IMPORT_VERSION, imported_at=now)
    patch = {"review_sequence": 1}
    if observed == "approved":
        patch.update(review_status="unreviewed", delivery_status="internal_draft",
                     current_review_record_id=None, current_review_binding=None)
    else:
        patch.update(current_review_record_id=record.id, current_review_binding=record.binding)
    updated = DocumentJobRecord.model_validate({**payload, **patch})
    return updated, record, "imported"
