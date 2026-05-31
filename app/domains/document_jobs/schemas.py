from __future__ import annotations

# app/domains/document_jobs/schemas.py: 定义 document_jobs API 的 v1 请求/响应模型。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domains.files.schemas import DocumentFileResponse


class DocumentJobCreateRequest(BaseModel):
    source_file_id: str
    mode: Literal["direct_pdf_to_word", "en2zh_pdf_to_word"] = "direct_pdf_to_word"
    document_language: Literal["auto", "zh", "en"] = "auto"
    template_version_id: str | None = None
    term_version_id: str | None = None
    debug_full_text: bool = False


class DocumentJobResponse(BaseModel):
    id: str
    tenant_id: str
    company_id: str
    created_by: str
    source_file_id: str
    mode: str
    document_language: str
    status: str
    stage: str
    progress: int
    template_version_id: str
    term_version_id: str | None = None
    result_file_id: str | None = None
    mineru_raw_result_file_id: str | None = None
    document_ir_file_id: str | None = None
    image_asset_file_ids: list[str] = Field(default_factory=list)
    debug_full_text_enabled: bool = False
    mineru_batch_id: str | None = None
    mineru_data_id: str | None = None
    failed_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int
    timeout_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    canceled_at: datetime | None = None
    request_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentJobCreateResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    job: DocumentJobResponse


class DocumentJobListResponse(BaseModel):
    items: list[DocumentJobResponse]
    page: int
    page_size: int
    total: int
    summary: dict[str, int] = Field(default_factory=dict)


class DocumentJobEventResponse(BaseModel):
    id: str
    job_id: str
    tenant_id: str
    company_id: str
    created_by: str
    stage: str
    level: str
    event_type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
    trace_id: str | None = None
    created_at: datetime


class DocumentJobEventListResponse(BaseModel):
    job_id: str
    items: list[DocumentJobEventResponse]


class DocumentJobDownloadUrlResponse(BaseModel):
    job_id: str
    file_id: str
    download_url: str
    method: Literal["GET"] = "GET"
    expires_at: datetime
    file: DocumentFileResponse


class DocumentJobRetryRequest(BaseModel):
    reason: str | None = None


class DocumentJobRetryResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    retry_count: int
    job: DocumentJobResponse
