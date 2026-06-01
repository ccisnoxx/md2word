from __future__ import annotations

# app/domains/document_jobs/models.py: 定义 PDF 到 Word 业务任务的状态机和事件模型。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.domains.jobs.models import utc_now


DocumentJobMode = Literal["direct_pdf_to_word", "en2zh_pdf_to_word"]
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
DocumentJobEventLevel = Literal["info", "warning", "error"]
DocumentJobEventType = Literal[
    "job_created",
    "stage_started",
    "stage_succeeded",
    "stage_failed",
    "file_registered",
    "retry_requested",
    "download_authorized",
    "ai_call_logged",
    "debug_archive_saved",
]


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
    mode: DocumentJobMode = "direct_pdf_to_word"
    document_language: Literal["auto", "zh", "en"] = "auto"
    status: DocumentJobStatus = "pending"
    stage: DocumentJobStage = "uploaded"
    progress: int = Field(default=0, ge=0, le=100)
    template_version_id: str
    term_version_id: str | None = None
    result_file_id: str | None = None
    mineru_raw_result_file_id: str | None = None
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
