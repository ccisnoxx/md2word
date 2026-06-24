from __future__ import annotations

# File: app/domains/document_jobs/schemas.py
# Purpose: 定义 document_jobs API 的 v1 请求/响应模型。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domains.files.schemas import DocumentFileSummaryResponse
from app.domains.translation.modes import DocumentJobMode, DocumentLanguage, TranslationMode

DocumentJobActionId = Literal["download", "retry", "cancel", "archive", "unarchive", "clone", "delete"]


class DocumentJobCreateRequest(BaseModel):
    source_file_id: str
    mode: DocumentJobMode | None = None
    translation_mode: TranslationMode | None = None
    document_language: DocumentLanguage = "auto"
    template_version_id: str | None = None
    term_version_id: str | None = None
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = None
    translation_term_version: str | None = None
    translation_profile_id: str | None = None
    translation_profile_version: str | None = None
    debug_full_text: bool = False


class DocumentJobAvailableActionResponse(BaseModel):
    enabled: bool
    disabled_reason: str | None = None
    retryable: bool = False


class DocumentJobResponse(BaseModel):
    id: str
    tenant_id: str
    company_id: str
    created_by: str
    source_file_id: str
    source_job_id: str | None = None
    mode: str
    translation_mode: TranslationMode = "direct"
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
    archived_at: datetime | None = None
    archived_by: str | None = None
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    delete_reason: str | None = None
    translation_qa_status: Literal["unreviewed", "approved", "needs_fix", "blocked"] = "unreviewed"
    translation_qa_issue_type: Literal[
        "translation",
        "terminology",
        "layout",
        "source_quality",
        "artifact_missing",
        "other",
    ] | None = None
    translation_qa_note: str | None = None
    translation_qa_reviewed_by: str | None = None
    translation_qa_reviewed_at: datetime | None = None
    request_snapshot: dict[str, Any] = Field(default_factory=dict)
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse] = Field(default_factory=dict)
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
    filtered_summary: dict[str, int] = Field(default_factory=dict)
    translation_qa_summary: dict[str, int] = Field(default_factory=dict)


class DocumentJobArchiveResponse(BaseModel):
    job_id: str
    archived_at: datetime
    job: DocumentJobResponse


class DocumentJobUnarchiveResponse(BaseModel):
    job_id: str
    restored_at: datetime
    job: DocumentJobResponse


class DocumentJobDeleteExecuteRequest(BaseModel):
    preview_hash: str
    reason: str | None = None
    confirmation: str | None = None


class DocumentJobDeleteFileResponse(BaseModel):
    file_id: str
    file_type: str | None = None
    storage_provider: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    size_bytes: int | None = None
    action: Literal["delete", "keep"]
    outcome: str
    reason: str
    deleted: bool = False
    metadata_updated: bool = False
    s3_delete_contract: dict[str, Any] | None = None


class DocumentJobDeleteSafetyResponse(BaseModel):
    physical_delete_executed: bool = False
    metadata_mutated: bool = False
    audit_events_written: bool = False
    s3_delete_executed: bool = False
    deleted_job_metadata_retained: bool = True


class DocumentJobDeletePreviewResponse(BaseModel):
    job_id: str
    action_mode: Literal["delete_preview"]
    confirmation_phrase: str
    preview_hash: str
    totals: dict[str, int] = Field(default_factory=dict)
    files: list[DocumentJobDeleteFileResponse] = Field(default_factory=list)
    safety: DocumentJobDeleteSafetyResponse


class DocumentJobDeleteExecuteResponse(BaseModel):
    job_id: str
    action_mode: Literal["delete_execute"]
    confirmation_phrase: str
    preview_hash: str
    totals: dict[str, int] = Field(default_factory=dict)
    files: list[DocumentJobDeleteFileResponse] = Field(default_factory=list)
    safety: DocumentJobDeleteSafetyResponse
    job: DocumentJobResponse


class DocumentJobCancelResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    canceled_at: datetime
    job: DocumentJobResponse


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


class DocumentJobFileListResponse(BaseModel):
    """任务详情页使用的文件汇总响应，不包含存储对象定位、raw metadata 或长期下载地址。"""

    job_id: str
    files: list[DocumentFileSummaryResponse]


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


class DocumentJobTranslationQaStateResponse(BaseModel):
    """任务级翻译 QA 复核状态。"""

    status: Literal["unreviewed", "approved", "needs_fix", "blocked"]
    issue_type: Literal[
        "translation",
        "terminology",
        "layout",
        "source_quality",
        "artifact_missing",
        "other",
    ] | None = None
    note: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class DocumentJobTranslationQaArtifactsResponse(BaseModel):
    document_ir_file_id: str | None = None
    ai_call_log_file_ids: list[str] = Field(default_factory=list)
    ai_debug_archive_file_ids: list[str] = Field(default_factory=list)
    ai_debug_archive_expires_at: datetime | None = None
    ai_debug_archive_expired: bool = False
    ai_debug_archive_contains_full_text: bool = False


class DocumentJobTranslationQaSummaryResponse(BaseModel):
    final_segment_count: int = 0
    returned_segment_count: int = 0
    quality_flags: list[str] = Field(default_factory=list)
    ai_call_count: int = 0
    ai_call_statuses: dict[str, int] = Field(default_factory=dict)
    term_trace_count: int = 0
    debug_full_text_enabled: bool = False
    source_comparison_available: bool = False
    source_comparison_reason: str | None = None


class DocumentJobTranslationQaSegmentResponse(BaseModel):
    id: str
    block_id: str
    page_index: int | None = None
    order: int
    block_type: str
    field: str
    index: int | None = None
    source_text: str | None = None
    ai_translation_text: str | None = None
    final_text: str
    source_available: bool = False


class DocumentJobTranslationQaTermTraceResponse(BaseModel):
    segment_id: str | None = None
    batch_id: str | None = None
    translation_term_set_id: str | None = None
    translation_term_version: str | None = None
    source_term: str | None = None
    target_term: str | None = None
    match_start: int | None = None
    match_end: int | None = None
    context: dict[str, Any] | None = None
    injected_to_glossary: bool = False
    provider_trace_id: str | None = None


class DocumentJobTranslationQaAiCallResponse(BaseModel):
    file_id: str
    call_id: str | None = None
    status: str | None = None
    provider: dict[str, Any] = Field(default_factory=dict)
    language_pair: str | None = None
    source_language: str | None = None
    target_language: str | None = None
    term_version_id: str | None = None
    term_snapshot_hash: str | None = None
    term_count: int = 0
    item_count: int = 0
    char_count: int = 0
    duration_ms: int | None = None
    created_at: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class DocumentJobTranslationQaResponse(BaseModel):
    job_id: str
    available: bool
    availability_reason: str | None = None
    qa: DocumentJobTranslationQaStateResponse
    artifacts: DocumentJobTranslationQaArtifactsResponse
    summary: DocumentJobTranslationQaSummaryResponse
    segments: list[DocumentJobTranslationQaSegmentResponse] = Field(default_factory=list)
    term_traces: list[DocumentJobTranslationQaTermTraceResponse] = Field(default_factory=list)
    ai_calls: list[DocumentJobTranslationQaAiCallResponse] = Field(default_factory=list)


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


class DocumentJobConfigVersionOption(BaseModel):
    """任务创建配置中一个可绑定的 published 资源版本。"""

    resource_id: str
    version: str
    label: str
    status: str = "published"
    is_default: bool = False
    snapshot_hash: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class DocumentJobConfigDefaults(BaseModel):
    template: DocumentJobConfigVersionOption | None = None
    term_rule_set: DocumentJobConfigVersionOption | None = None
    translation_term_set: DocumentJobConfigVersionOption | None = None
    translation_profile: DocumentJobConfigVersionOption | None = None


class DocumentJobTranslationResourceDefaults(BaseModel):
    """Default translation resources for one supported language pair."""

    translation_term_set: DocumentJobConfigVersionOption | None = None
    translation_profile: DocumentJobConfigVersionOption | None = None


class DocumentJobConfigOptions(BaseModel):
    templates: list[DocumentJobConfigVersionOption] = Field(default_factory=list)
    term_rule_sets: list[DocumentJobConfigVersionOption] = Field(default_factory=list)
    translation_term_sets: list[DocumentJobConfigVersionOption] = Field(default_factory=list)
    translation_profiles: list[DocumentJobConfigVersionOption] = Field(default_factory=list)


class DocumentJobConfigReadiness(BaseModel):
    en2zh_available: bool = False
    ru2zh_available: bool = False
    translation_modes: dict[str, bool] = Field(default_factory=dict)
    p0_document_jobs_required: bool = False
    p0_document_jobs_ready: bool = True
    document_jobs_worker_backend: str = "disabled"
    document_jobs_automatic_execution_enabled: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentJobConfigSummaryResponse(BaseModel):
    role: str
    resource_mode: Literal["legacy", "versioned"]
    defaults: DocumentJobConfigDefaults
    translation_defaults: dict[str, DocumentJobTranslationResourceDefaults] = Field(default_factory=dict)
    options: DocumentJobConfigOptions
    readiness: DocumentJobConfigReadiness


class DocumentJobDownloadUrlResponse(BaseModel):
    job_id: str
    file_id: str
    download_url: str
    method: Literal["GET"] = "GET"
    expires_at: datetime
    file: DocumentFileSummaryResponse


class DocumentJobRetryRequest(BaseModel):
    reason: str | None = None
    use_latest_term_assets: bool = False
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = None
    translation_term_version: str | None = None


class DocumentJobCloneRequest(BaseModel):
    reason: str | None = None
    config_strategy: Literal["keep_source_snapshot", "use_current_defaults", "select_published_versions"] = "keep_source_snapshot"
    document_language: DocumentLanguage | None = None
    template_version_id: str | None = None
    term_version_id: str | None = None
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = None
    translation_term_version: str | None = None
    translation_profile_id: str | None = None
    translation_profile_version: str | None = None
    debug_full_text: bool | None = None


class DocumentJobRetryResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    retry_count: int
    job: DocumentJobResponse


class DocumentJobCloneResponse(BaseModel):
    source_job_id: str
    job_id: str
    status: str
    stage: str
    progress: int
    job: DocumentJobResponse


class DocumentJobBulkJobIdsRequest(BaseModel):
    """批量任务操作的 job_id 列表。"""

    job_ids: list[str] = Field(default_factory=list)


class DocumentJobBulkRetryRequest(BaseModel):
    """批量重试请求；重试选项与单任务重试保持一致。"""

    job_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    use_latest_term_assets: bool = False
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = None
    translation_term_version: str | None = None


class DocumentJobBulkItemResponse(BaseModel):
    """批量操作中单个任务的成功或失败结果。"""

    job_id: str
    ok: bool
    status_code: int
    error_code: str | None = None
    detail: str | None = None
    job: DocumentJobResponse | None = None


class DocumentJobBulkResponse(BaseModel):
    """批量任务操作响应；允许部分成功。"""

    action: Literal["retry", "archive", "cancel"]
    total: int
    succeeded: int
    failed: int
    items: list[DocumentJobBulkItemResponse] = Field(default_factory=list)


DocumentJobIncidentFailureType = Literal[
    "conversion_failed",
    "translation_failed",
    "qa_unavailable",
    "artifact_missing",
    "timeout_or_stalled",
    "worker_or_dispatch_failed",
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
    evidence_links: list[DocumentJobIncidentEvidenceLinkResponse] = Field(default_factory=list)
    recent_events: list[DocumentJobIncidentEventSummaryResponse] = Field(default_factory=list)
    files: list[DocumentJobIncidentFileSummaryResponse] = Field(default_factory=list)


class DocumentJobIncidentBulkRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


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
