from __future__ import annotations

# app/domains/document_jobs/models.py: 定义 PDF 到 Word 业务任务的状态机和事件模型。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.domains.resources.models import utc_now
from app.domains.translation.modes import DocumentJobMode, DocumentLanguage


DocumentJobStatus = Literal["pending", "queued", "running", "succeeded", "failed", "canceled"]
DocumentJobStage = Literal[
    "uploaded",
    "parsing",
    "parsed",
    "ir_converting",
    "rendering",
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
DocumentJobTranslationQaIssueType = Literal[
    "translation",
    "terminology",
    "layout",
    "source_quality",
    "artifact_missing",
    "other",
]
DocumentJobEventType = Literal[
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
    "running": {"parsing", "parsed", "ir_converting", "rendering", "uploading"},
    "succeeded": {"completed"},
    "failed": {"failed"},
    "canceled": {"canceled"},
}


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
