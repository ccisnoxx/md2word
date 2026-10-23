from __future__ import annotations

# app/domains/document_jobs/models.py: 定义 PDF 到 Word 业务任务的状态机和事件模型。

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, JsonValue, StrictInt, model_validator

from app.domains.files.models import DocumentFileRecord
from app.domains.document_jobs.preview_state import WordPreviewState
from app.domains.resources.models import utc_now
from app.domains.translation.modes import DocumentJobMode, DocumentLanguage


DocumentJobStatus = Literal["pending", "queued", "running", "succeeded", "failed", "canceled"]
DocumentJobStage = Literal[
    "uploaded",
    "parsing",
    "parsed",
    "ir_converting",
    "translating",
    "translation_validating",
    "rendering",
    "quality_checking",
    "uploading",
    "completed",
    "failed",
    "canceled",
]
DocumentJobTranslationBatchStatus = Literal[
    "pending",
    "queued",
    "running",
    "succeeded",
    "failed",
    "split",
    "canceled",
]
DocumentJobEventLevel = Literal["info", "warning", "error"]
DocumentJobTranslationQaStatus = Literal["unreviewed", "approved", "needs_fix", "blocked"]
DocumentJobQualityStatus = Literal["pending", "passed", "warning", "blocked"]
DocumentJobReviewStatus = Literal["unreviewed", "approved", "needs_fix", "blocked"]
DocumentJobDeliveryStatus = Literal["internal_draft", "ready_to_publish", "published"]
DocumentJobTranslationQaIssueType = Literal[
    "translation",
    "terminology",
    "layout",
    "source_quality",
    "artifact_missing",
    "other",
]
DocumentJobEventType = Literal[
    "preview_started",
    "preview_succeeded",
    "preview_failed",
    "preview_retry_requested",
    "job_created",
    "job_archived",
    "job_unarchived",
    "job_deleted",
    "job_cloned",
    "job_canceled",
    "stage_started",
    "stage_succeeded",
    "stage_failed",
    "file_registered",
    "retry_requested",
    "download_authorized",
    "ai_call_logged",
    "debug_archive_saved",
    "translation_batch_queued",
    "translation_batch_running",
    "translation_batch_succeeded",
    "translation_batch_split",
    "translation_batch_failed",
    "translation_qa_updated",
    "mineru_callback_received",
    "mineru_callback_queued",
    "mineru_callback_processed",
    "mineru_callback_ignored",
    "recovery_replay_queued",
    "recovery_callback_ignored",
]
DocumentJobCallbackMessageKind = Literal["mineru_result_callback"]
DocumentJobCallbackMessageStatus = Literal["pending", "running", "processed", "failed", "ignored"]


DOCUMENT_JOB_ALLOWED_STAGES_BY_STATUS: dict[DocumentJobStatus, set[DocumentJobStage]] = {
    "pending": {"uploaded"},
    "queued": {"uploaded"},
    "running": {
        "parsing", "parsed", "ir_converting", "translating", "translation_validating",
        "rendering", "quality_checking", "uploading",
    },
    "succeeded": {"completed"},
    "failed": {"failed"},
    "canceled": {"canceled"},
}


class DocumentJobPreparedResult(BaseModel):
    """已通过质量检查且写入完成的结果凭据；首次持久化后身份不可替换。"""

    protocol_version: StrictInt = Field(default=1, ge=1, le=1)
    generation: StrictInt = Field(ge=0)
    document_ir_file_id: str
    file: DocumentFileRecord

    @model_validator(mode="after")
    def _validate_descriptor(self) -> "DocumentJobPreparedResult":
        file = self.file
        if file.file_type != "generated_word" or file.status != "uploaded":
            raise ValueError("结果凭据必须描述已写入的主 DOCX。")
        if not file.checksum_sha256 or re.fullmatch(r"sha256:[0-9a-f]{64}", file.checksum_sha256) is None:
            raise ValueError("结果凭据缺少 SHA-256。")
        if file.size_bytes <= 0 or not file.object_key or file.expires_at is None:
            raise ValueError("结果凭据的对象描述不完整。")
        return self


class DocumentJobRecord(BaseModel):
    """一次 PDF 到 Word 业务任务；P0 先只作为 metadata 权威记录。"""

    id: str
    tenant_id: str
    company_id: str
    created_by: str
    source_file_id: str
    source_job_id: str | None = None
    mode: DocumentJobMode = "direct_pdf_to_word"
    document_language: DocumentLanguage = "auto"
    status: DocumentJobStatus = "pending"
    stage: DocumentJobStage = "uploaded"
    progress: int = Field(default=0, ge=0, le=100)
    template_version_id: str
    term_version_id: str | None = None
    result_file_id: str | None = None
    prepared_result: DocumentJobPreparedResult | None = None
    word_preview_state: WordPreviewState | None = None
    mineru_raw_result_file_id: str | None = None
    source_document_ir_file_id: str | None = None
    document_ir_file_id: str | None = None
    image_asset_file_ids: list[str] = Field(default_factory=list)
    debug_full_text_enabled: bool = False
    mineru_batch_id: str | None = None
    mineru_data_id: str | None = None
    mineru_callback_seed: str | None = None
    failed_stage: DocumentJobStage | None = None
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    timeout_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    canceled_at: datetime | None = None
    archived_at: datetime | None = None
    archived_by: str | None = None
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    delete_reason: str | None = None
    quality_status: DocumentJobQualityStatus = "pending"
    review_status: DocumentJobReviewStatus = "unreviewed"
    delivery_status: DocumentJobDeliveryStatus = "internal_draft"
    quality_summary: dict[str, JsonValue] = Field(default_factory=dict)
    translation_qa_status: DocumentJobTranslationQaStatus = "unreviewed"
    translation_qa_issue_type: DocumentJobTranslationQaIssueType | None = None
    translation_qa_note: str | None = None
    translation_qa_reviewed_by: str | None = None
    translation_qa_reviewed_at: datetime | None = None
    request_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate_state(self) -> "DocumentJobRecord":
        allowed_stages = DOCUMENT_JOB_ALLOWED_STAGES_BY_STATUS[self.status]
        if self.stage not in allowed_stages:
            raise ValueError(f"document job 状态不允许阶段: status={self.status} stage={self.stage}")
        if self.review_status == "approved":
            if self.status != "succeeded" or not self.result_file_id or self.quality_status == "blocked":
                raise ValueError("批准复核要求执行成功、当前主件和非阻断质量。")
        if self.delivery_status in {"ready_to_publish", "published"}:
            if (self.quality_status not in {"passed", "warning"} or self.review_status != "approved"
                    or self.status != "succeeded" or not self.result_file_id):
                raise ValueError("交付晋升要求质量通过或警告、已批准复核及成功的当前主件。")
        receipt = self.prepared_result
        if receipt is not None:
            if self.stage not in {"uploading", "completed", "failed", "canceled"}:
                raise ValueError("结果凭据仅能保留在上传阶段或终态。")
            if receipt.generation != self.retry_count or receipt.document_ir_file_id != self.document_ir_file_id:
                raise ValueError("结果凭据与当前代或最终 IR 不一致。")
            if (receipt.file.tenant_id, receipt.file.company_id, receipt.file.job_id) != (self.tenant_id, self.company_id, self.id):
                raise ValueError("结果凭据与任务归属不一致。")
            if ((self.status == "succeeded" or self.result_file_id is not None)
                    and self.result_file_id != receipt.file.id):
                raise ValueError("任务主件与选定的结果凭据不一致。")
        return self


class DocumentJobEventRecord(BaseModel):
    """记录 document_job 阶段事件；payload 默认只放非敏感摘要。"""

    id: str
    tenant_id: str
    company_id: str
    job_id: str
    created_by: str
    stage: DocumentJobStage
    level: DocumentJobEventLevel = "info"
    event_type: DocumentJobEventType
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
    trace_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class DocumentJobCallbackMessage(BaseModel):
    """document_jobs 专用 MinerU callback 消息；HTTP 只落消息，Worker 幂等消费。"""

    id: str
    job_id: str
    kind: DocumentJobCallbackMessageKind = "mineru_result_callback"
    status: DocumentJobCallbackMessageStatus = "pending"
    job_retry_count: int = 0
    dedupe_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    trace_id: str | None = None
    lease_owner: str | None = None
    leased_at: datetime | None = None
    lease_expires_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DocumentJobTranslationBatchRecord(BaseModel):
    """Provider translation batch state for one DocumentIR translation generation."""

    id: str
    job_id: str
    job_retry_count: int = 0
    generation: int = 0
    root_batch_id: str
    parent_batch_id: str | None = None
    status: DocumentJobTranslationBatchStatus = "pending"
    page_start: int | None = None
    page_end: int | None = None
    item_ids: list[str] = Field(default_factory=list)
    item_count: int = 0
    char_count: int = 0
    split_level: int = 0
    attempt_count: int = 0
    max_attempts: int = 2
    deterministic_batch_count: int = 1
    provider_call_budget: int = 12
    source_document_ir_file_id: str
    language_pair: str
    term_version_id: str | None = None
    term_snapshot_hash: str | None = None
    lease_owner: str | None = None
    leased_at: datetime | None = None
    lease_expires_at: datetime | None = None
    result_file_id: str | None = None
    ai_call_log_file_ids: list[str] = Field(default_factory=list)
    debug_archive_file_ids: list[str] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    response_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    truncation_retry: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
