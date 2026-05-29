from __future__ import annotations

# app/schemas/jobs.py: 定义 jobs API 的 v1 请求/响应模型。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class JobAcceptedResponse(BaseModel):
    job_id: str
    trace_id: str
    status: Literal[
        "uploaded",
        "queued",
        "submitting",
        "parsing",
        "parsed",
        "converting",
        "completed",
        "failed",
        "canceled",
    ]
    translation_mode: Literal["direct", "en2zh"]
    resource_snapshot: "JobResourceSnapshotResponse | None" = None


class ResolvedResourceVersionResponse(BaseModel):
    resource_type: str
    resource_id: str
    version: str
    status: Literal["published"] = "published"
    snapshot_hash: str
    payload_ref: str | None = None


class JobMineruSnapshotResponse(BaseModel):
    model_version: str | None = None
    language: str | None = None
    enable_formula: bool | None = None
    enable_table: bool | None = None
    callback_enabled: bool = False
    data_id: str | None = None


class JobResourceSnapshotResponse(BaseModel):
    template: ResolvedResourceVersionResponse | None = None
    term_rule_set: ResolvedResourceVersionResponse | None = None
    translation_profile: ResolvedResourceVersionResponse | None = None
    mineru: JobMineruSnapshotResponse
    artifact_ids: dict[str, str] = Field(default_factory=dict)


class JobFileResponse(BaseModel):
    file_type: str
    path: str
    storage_backend: str
    object_key: str | None = None
    public_url: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    download_url: str | None = None
    created_at: datetime


class JobEventResponse(BaseModel):
    stage: str
    message: str
    status: str
    error_code: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    created_at: datetime


class JobSummaryResponse(BaseModel):
    id: str
    source_filename: str
    status: str
    progress: int
    translation_mode: str
    result_ready: bool
    result_download_url: str | None = None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    items: list[JobSummaryResponse]
    page: int
    page_size: int
    total: int
    summary: dict[str, int]


class JobDetailResponse(BaseModel):
    """当前 jobs 详情响应。

    `mineru_*` 字段对外仍保留，但它们在内部已被视为 source_pdf_context 的兼容投影。
    """

    id: str
    source_filename: str
    status: str
    progress: int
    source_kind: str
    translation_mode: str
    document_language: str
    resolved_document_language: str | None = None
    template_id: str | None = None
    resource_snapshot: JobResourceSnapshotResponse | None = None
    mineru_batch_id: str | None = Field(default=None, description="兼容投影字段，内部优先来自 source_pdf_context.batch_id")
    mineru_data_id: str | None = Field(default=None, description="兼容投影字段，内部优先来自 source_pdf_context.data_id")
    mineru_callback_seed: str | None = Field(default=None, description="兼容投影字段，内部优先来自 source_pdf_context.callback_seed")
    mineru_status: str | None = Field(default=None, description="兼容投影字段，内部优先来自 source_pdf_context.upstream_status")
    mineru_result_zip_url: str | None = Field(default=None, description="兼容投影字段，内部优先来自 source_pdf_context.result_zip_url")
    error_code: str | None = None
    error_message: str | None = None
    result_ready: bool
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    files: list[JobFileResponse]
    events: list[JobEventResponse]


class JobFileListResponse(BaseModel):
    job_id: str
    files: list[JobFileResponse]


class JobEventListResponse(BaseModel):
    job_id: str
    items: list[JobEventResponse]


class JobOperationAcceptedResponse(BaseModel):
    job_id: str
    operation: str
    accepted: bool
    status: str
    message: str


class JobCleanupLocalFilesResponse(BaseModel):
    job_id: str
    deleted_paths: list[str]
    skipped_paths: list[dict[str, str]]
    status: str
    message: str
