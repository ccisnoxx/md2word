"""翻译批次诊断、callback 消息摘要、翻译 QA 与表格引用的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domains.document_jobs.views.jobs import DocumentJobResponse
from app.domains.document_jobs.views.translation import DocumentJobTranslationQaStateResponse


class DocumentJobTranslationBatchSummaryResponse(BaseModel):
    """翻译 provider batch 只读诊断摘要，不包含原文或译文内容。"""

    batch_id: str
    job_id: str
    generation: int
    root_batch_id: str
    parent_batch_id: str | None = None
    status: str
    page_start: int | None = None
    page_end: int | None = None
    item_count: int = 0
    char_count: int = 0
    split_level: int = 0
    attempt_count: int = 0
    max_attempts: int = 0
    deterministic_batch_count: int = 0
    provider_call_budget: int = 0
    source_document_ir_file_id: str | None = None
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
    is_effective_leaf: bool = True
    failure_disposition: Literal[
        "none", "retrying", "terminal", "stopped", "superseded"
    ] = "none"
    lease_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DocumentJobTranslationBatchExecutionResponse(BaseModel):
    """当前代翻译批次的权威执行结论与安全原因摘要。"""

    outcome: Literal[
        "not_started", "running", "retrying", "validating", "failed", "completed", "canceled"
    ]
    leaf_count: int = 0
    succeeded_leaf_count: int = 0
    active_leaf_count: int = 0
    retryable_failed_leaf_count: int = 0
    terminal_failed_leaf_count: int = 0
    failure_batch_id: str | None = None
    reason_code: str | None = None
    reason_message: str | None = None
    partial_artifacts_debug_only: bool = True


class DocumentJobTranslationBatchListResponse(BaseModel):
    job_id: str
    generation: int
    items: list[DocumentJobTranslationBatchSummaryResponse] = Field(default_factory=list)
    execution: DocumentJobTranslationBatchExecutionResponse | None = None


class DocumentJobCallbackProblemSummaryResponse(BaseModel):
    """任务详情页展示的 callback message 问题摘要，不包含原始 payload。"""

    message_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    attempts: int = 0
    updated_at: datetime


class DocumentJobCallbackMessageSummaryResponse(BaseModel):
    """任务级 callback message 观测摘要。"""

    job_id: str
    status_counts: dict[str, int] = Field(default_factory=dict)
    replayable_count: int = 0
    oldest_replayable_age_seconds: int = 0
    recent_problem_messages: list[DocumentJobCallbackProblemSummaryResponse] = Field(default_factory=list)


class DocumentJobTranslationQaUpdateRequest(BaseModel):
    status: Literal["unreviewed", "approved", "needs_fix", "blocked"]
    issue_type: Literal[
        "translation",
        "terminology",
        "layout",
        "source_quality",
        "artifact_missing",
        "other",
    ] | None = None
    note: str | None = Field(default=None, max_length=1000)


class DocumentJobTranslationQaUpdateResponse(BaseModel):
    job_id: str
    qa: DocumentJobTranslationQaStateResponse
    job: DocumentJobResponse
