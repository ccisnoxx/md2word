"""异常中心队列、详情与批量处置的用例输出模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domains.document_jobs.views.jobs import DocumentJobFailureDiagnosticResponse, DocumentJobResponse


DocumentJobIncidentFailureType = Literal[
    "conversion_failed",
    "translation_failed",
    "qa_unavailable",
    "artifact_missing",
    "timeout_or_stalled",
    "worker_or_dispatch_failed",
    "page_degraded",
    "unknown",
]


DocumentJobIncidentSort = Literal[
    "priority",
    "updated_at_desc",
    "updated_at_asc",
    "retry_count_desc",
    "retry_count_asc",
]


DocumentJobIncidentRetryCountBucket = Literal["0", "1_2", "3_plus"]


class DocumentJobIncidentQueueItemResponse(BaseModel):
    """异常处理队列中的轻量投影，不创建持久 Incident 资源。"""

    job: DocumentJobResponse
    failure_type: DocumentJobIncidentFailureType
    priority: int
    is_incident: bool = True
    retryable: bool = False
    retry_disabled_reason: str | None = None
    stalled: bool = False
    stalled_minutes: int | None = None
    blocked: bool = False
    suggested_action: str
    evidence_summary: list[str] = Field(default_factory=list)


class DocumentJobIncidentSummaryResponse(BaseModel):
    """异常队列筛选后的顶部统计。"""

    total: int = 0
    failed: int = 0
    blocked: int = 0
    stalled: int = 0
    retryable: int = 0
    non_retryable: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_failure_type: dict[str, int] = Field(default_factory=dict)


class DocumentJobIncidentListResponse(BaseModel):
    items: list[DocumentJobIncidentQueueItemResponse]
    page: int
    page_size: int
    total: int
    summary: DocumentJobIncidentSummaryResponse


class DocumentJobIncidentEvidenceLinkResponse(BaseModel):
    kind: Literal["detail", "events", "files", "translation_qa"]
    title: str
    target: str
    available: bool = True
    helper: str | None = None


class DocumentJobIncidentEventSummaryResponse(BaseModel):
    id: str
    stage: str
    level: str
    event_type: str
    message: str
    duration_ms: int | None = None
    trace_id: str | None = None
    created_at: datetime


class DocumentJobIncidentFileSummaryResponse(BaseModel):
    file_id: str
    file_type: str | None = None
    original_filename: str | None = None
    storage_provider: str | None = None
    status: str | None = None
    size_bytes: int | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DocumentJobIncidentDiagnosticResponse(BaseModel):
    item: DocumentJobIncidentQueueItemResponse
    failure_diagnostic: DocumentJobFailureDiagnosticResponse | None = None
    evidence_links: list[DocumentJobIncidentEvidenceLinkResponse] = Field(default_factory=list)
    recent_events: list[DocumentJobIncidentEventSummaryResponse] = Field(default_factory=list)
    files: list[DocumentJobIncidentFileSummaryResponse] = Field(default_factory=list)


class DocumentJobIncidentBulkItemResponse(BaseModel):
    job_id: str
    ok: bool
    skipped: bool = False
    status_code: int
    error_code: str | None = None
    detail: str | None = None
    item: DocumentJobIncidentQueueItemResponse | None = None


class DocumentJobIncidentBulkResponse(BaseModel):
    action: Literal["retry", "refresh"]
    total: int
    succeeded: int
    failed: int
    skipped: int
    items: list[DocumentJobIncidentBulkItemResponse] = Field(default_factory=list)
