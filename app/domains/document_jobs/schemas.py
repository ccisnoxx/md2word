from __future__ import annotations

# 文件：app/domains/document_jobs/schemas.py
# 用途：定义 document_jobs API 的 v1 请求/响应模型。

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator

from app.domains.document_jobs.models import (
    DocumentJobDeliveryStatus,
    DocumentJobQualityStatus,
    DocumentJobReviewStatus,
)

from app.domains.files.schemas import DocumentFileSummaryResponse
from app.domains.translation.modes import (
    DocumentJobMode,
    DocumentLanguage,
    LEGACY_DIRECT_TRANSLATION_MODES,
    TranslationMode,
    normalize_translation_mode,
)

DocumentJobActionId = Literal["download", "retry", "cancel", "archive", "unarchive", "clone", "delete", "publish", "new_generation"]
DocumentJobDownloadClassification = Literal["internal_only"]
TRANSLATION_SELECTION_DESCRIPTION = "仅适用于跨语言翻译任务；原文转换（direct）不得显式绑定翻译资源。"


class DocumentJobTableReferenceResponse(BaseModel):
    """审核白名单投影，不包含包内路径、对象定位或原始 metadata。"""

    block_id: str
    fragment_id: str
    logical_group_id: str
    page_index: int | None
    bbox: tuple[float, float, float, float] | None
    asset_id: str | None
    file_id: str | None
    source_status: Literal["valid", "missing", "invalid"]
    availability: Literal["available", "source_missing", "source_invalid", "missing", "expired", "deleted", "not_uploaded"]
    mime_type: str | None
    checksum_sha256: str | None
    size_bytes: int | None
    warning_codes: list[str] = Field(default_factory=list)
    display_supported: bool
    content_path: str | None


class DocumentJobTableReferenceListResponse(BaseModel):
    job_id: str
    generation: int
    ir_file_id: str | None
    evidence_status: Literal["not_ready", "legacy_unavailable", "registered"]
    items: list[DocumentJobTableReferenceResponse] = Field(default_factory=list)


class DocumentJobCreateRequest(BaseModel):
    source_file_id: str
    mode: DocumentJobMode | None = None
    translation_mode: TranslationMode | None = Field(
        default=None, description="使用五种规范模式；兼容历史 zh2zh / zh_to_zh 输入并归一为 direct。"
    )
    document_language: DocumentLanguage = "auto"
    template_version_id: str | None = None
    term_version_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_term_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_profile_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_profile_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    debug_full_text: bool = Field(default=False, description="仅 Admin 可为翻译任务开启；direct 请求不得为 true。")

    @field_validator("translation_mode", mode="before")
    @classmethod
    def _normalize_historical_direct_mode(cls, value: Any) -> Any:
        """仅接纳已约定的历史输入，其他值继续由五值 Literal 严格校验。"""

        if isinstance(value, str) and value.strip().lower() in LEGACY_DIRECT_TRANSLATION_MODES:
            return normalize_translation_mode(value)
        return value


class DocumentJobActionDisabledReasonResponse(BaseModel):
    code: str
    message: str


class DocumentJobAvailableActionResponse(BaseModel):
    enabled: bool
    disabled_reason: str | None = None
    retryable: bool = False
    disabled_reason_code: str | None = Field(default=None, json_schema_extra={"readOnly": True})
    disabled_reasons: list[DocumentJobActionDisabledReasonResponse] | None = Field(
        default=None, json_schema_extra={"readOnly": True}, description="发布禁用原因，按优先级排列。"
    )
    classification: DocumentJobDownloadClassification | None = Field(
        default=None, json_schema_extra={"readOnly": True}, description="当前主 DOCX 仅供内部使用，不代表最终交付件。"
    )
    warning_code: str | None = Field(default=None, json_schema_extra={"readOnly": True})
    warning_message: str | None = Field(default=None, json_schema_extra={"readOnly": True})
    eligible: bool | None = Field(
        default=None, json_schema_extra={"readOnly": True}, description="仅表示发布核心资格；执行许可仍由 enabled 表达。"
    )


class DocumentJobFailureDiagnosticResponse(BaseModel):
    """当前代失败定位投影（MinerU 验证或渲染操作）；页码为 1 起始，文档级问题不伪造页码。"""

    source: Literal["mineru_validation", "render_operation"] = "mineru_validation"
    stage: str
    scope: Literal["page", "document"]
    page_number: int | None = None
    source_type: str | None = None
    json_pointer: str | None = None
    reason_code: str
    reason: str | None = None
    affected_page_numbers: list[int] = Field(default_factory=list)
    fatal_count: int = 0
    warning_count: int = 0
    details_truncated: bool = Field(default=False, description="为 true 时受影响页列表可能不完整。")
    block_ids: list[str] = Field(default_factory=list, description="渲染来源时为失败操作涉及的 IR 块 ID。")
    operation_kind: str | None = Field(default=None, description="渲染来源时为失败的 RenderPlan 操作类型。")


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
    source_document_ir_file_id: str | None = None
    document_ir_file_id: str | None = None
    image_asset_file_ids: list[str] = Field(default_factory=list)
    debug_full_text_enabled: bool = False
    mineru_batch_id: str | None = None
    mineru_data_id: str | None = None
    failed_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    failure_diagnostic: DocumentJobFailureDiagnosticResponse | None = Field(
        default=None, json_schema_extra={"readOnly": True}, description="仅任务详情接口填充；列表等其他接口恒为 null。"
    )
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
    quality_status: DocumentJobQualityStatus = Field(
        default="pending", json_schema_extra={"readOnly": True}, description="当前任务的系统质量结论。"
    )
    review_status: DocumentJobReviewStatus = Field(
        default="unreviewed", json_schema_extra={"readOnly": True}, description="当前复核状态的唯一真源。"
    )
    delivery_status: DocumentJobDeliveryStatus = Field(
        default="internal_draft", json_schema_extra={"readOnly": True}, description="当前交付状态；QA 批准不触发发布。"
    )
    quality_summary: dict[str, JsonValue] = Field(
        default_factory=dict, json_schema_extra={"readOnly": True}, description="系统提供的安全质量摘要；legacy 可为 {}，fresh 任务含本代 document_base pending 贡献。"
    )
    @field_validator("quality_summary")
    @classmethod
    def project_page_quality_summary(cls, value: dict[str, Any], info: ValidationInfo) -> dict[str, Any]:
        """内部 CAS 指针不出响应；命名贡献仅公开各 owner 的安全摘要。"""
        from app.domains.document_jobs.base_quality import project_base_quality
        checks = value.get("checks_v1")
        if isinstance(checks, dict) and "document_base" in checks:
            checks = {**checks, "document_base": project_base_quality(checks["document_base"], generation=info.data.get("retry_count"))}
            value = {**value, "checks_v1": checks}
        if not isinstance(checks, dict) or "word_page_quality" not in checks:
            return value
        page = checks["word_page_quality"]
        if not isinstance(page, dict):
            public = {"quality_status": "pending", "evaluation_state": "incomplete"}
        else:
            public = {key: page[key] for key in ("quality_status", "evaluation_state") if key in page}
            summary = page.get("summary")
            if isinstance(summary, dict):
                public["summary"] = {key: summary[key] for key in (
                    "schema_version", "quality_status", "evaluation_state", "reason_code") if key in summary}
                counts = summary.get("counts")
                if isinstance(counts, dict):
                    public["summary"]["counts"] = {key: counts[key] for key in (
                        "pages", "observed_pages", "flags", "manual_checks", "checked_rules", "not_checked_rules")
                        if type(counts.get(key)) is int}
        return {**value, "checks_v1": {**checks, "word_page_quality": public}}

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

    @field_validator("request_snapshot")
    @classmethod
    def project_page_quality_policy(cls, value: dict[str, Any]) -> dict[str, Any]:
        """页面区域与校准引用只保留在内部快照；所有响应入口共用安全投影。"""
        if "page_quality" not in value:
            return value
        from app.services.preview.page_quality import parse_page_quality_policy, policy_sha256
        try:
            policy = parse_page_quality_policy(value["page_quality"])
        except ValueError:
            return {**value, "page_quality": {"available": False}}
        return {**value, "page_quality": {
            "schema_version": policy.schema_version, "enabled": policy.enabled,
            "policy_version": policy.policy_version, "analyzer_version": policy.analyzer_version,
            "policy_sha256": policy_sha256(policy),
        }}

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
    classification: DocumentJobDownloadClassification | None = Field(
        default=None, json_schema_extra={"readOnly": True}, description="当前主 DOCX 为 internal_only，普通 Artifact 为空。"
    )
    warning_code: str | None = Field(default=None, json_schema_extra={"readOnly": True})
    warning_message: str | None = Field(default=None, json_schema_extra={"readOnly": True})


class DocumentJobRetryRequest(BaseModel):
    reason: str | None = None
    use_latest_term_assets: bool = False
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_term_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)


class DocumentJobCloneRequest(BaseModel):
    reason: str | None = None
    config_strategy: Literal["keep_source_snapshot", "use_current_defaults", "select_published_versions"] = "keep_source_snapshot"
    document_language: DocumentLanguage | None = None
    template_version_id: str | None = None
    term_version_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    term_rule_set_id: str | None = None
    term_rule_set_version: str | None = None
    translation_term_set_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_term_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_profile_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_profile_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    debug_full_text: bool | None = Field(default=None, description="仅 Admin 可为翻译任务开启；direct 请求不得为 true。")


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
    translation_term_set_id: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)
    translation_term_version: str | None = Field(default=None, description=TRANSLATION_SELECTION_DESCRIPTION)


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
    failure_diagnostic: DocumentJobFailureDiagnosticResponse | None = None
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


# 新复核 API 使用独立严格 DTO；不改变旧 QA 和任务详情的序列化合同。
QualityId = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:\-]+$")]
QualityCount = Annotated[int, Field(strict=True, ge=0)]
QualityHash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
QualityChecksum = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
QualityVersion = Annotated[str, Field(max_length=100, pattern=r"^[a-z][a-z0-9-]*/v[0-9]+$")]
QualityAvailability = Literal["available", "legacy_unavailable", "not_ready", "disabled", "unavailable"]
QualityRule = Literal["clipping", "overflow", "blank", "overlap", "density"]
QualityIssue = Literal["conversion", "translation", "terminology", "table_structure", "layout", "source_quality", "artifact_missing", "other"]
QualityMetric = Literal["native_outside_area_pt2", "foreground_union_area_pt2", "outside_area_ratio", "outside_object_count",
    "max_outside_distance_pt", "edge_ink_ratio", "outside_body_area_ratio", "clearance_pt", "excluded_object_count",
    "ink_area_ratio", "foreground_object_count", "char_count", "positive_pair_count", "max_intersection_min_area_ratio",
    "body_ink_ratio", "native_foreground_body_area_ratio", "char_density", "group_median", "median_absolute_deviation"]


class QualityReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class DocumentQualitySourceResponse(QualityReviewModel):
    generation: QualityCount
    ir_file_id: QualityId | None
    result_file_id: QualityId | None
    result_sha256: QualityChecksum | None
    file_review_source_revision: QualityCount | None
    receipt_sha256: QualityChecksum | None


class ReviewExpectedSourceRequest(QualityReviewModel):
    """五字段均必填；null 表示登记值缺失，不能作为任意来源通配符。"""
    generation: QualityCount
    result_file_id: QualityId | None
    result_sha256: QualityChecksum | None
    file_review_source_revision: QualityCount | None
    receipt_sha256: QualityChecksum | None


class DocumentJobNewGenerationRequest(QualityReviewModel):
    """固定原模式与快照的新代命令，不接受配置或状态覆盖。"""

    request_id: str = Field(description="客户端生成并保留的 UUID；接受前归一为规范格式。")
    note: str
    expected_source: ReviewExpectedSourceRequest

    @field_validator("request_id")
    @classmethod
    def _request_key(cls, value: str) -> str:
        from uuid import UUID
        try:
            key = str(UUID(value))
        except ValueError:
            raise ValueError("request_id 必须是 UUID。") from None
        return key

    @field_validator("note")
    @classmethod
    def _request_note(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 1000:
            raise ValueError("新代原因去除首尾空白后必须为 1..1000 字。")
        return value


class DocumentJobGenerationCurrentResponse(BaseModel):
    """对账仅公开当前任务状态，不附带原配置、私有账本或下载能力。"""

    id: str
    status: str
    stage: str
    progress: int
    retry_count: int
    result_file_id: str | None
    quality_status: DocumentJobQualityStatus
    review_status: DocumentJobReviewStatus
    delivery_status: DocumentJobDeliveryStatus


class DocumentJobNewGenerationResponse(BaseModel):
    """不可变接受事实与当前观察分列，重放可能已观察到后续代次。"""

    accepted: Literal[True] = True
    request_id: str
    job_id: str
    accepted_generation: int
    accepted_at: datetime
    source: ReviewExpectedSourceRequest
    audit_id: str
    replayed: bool
    current_generation: int
    current_job: DocumentJobGenerationCurrentResponse


class DocumentJobNewGenerationErrorDetailResponse(QualityReviewModel):
    code: str
    message: str
    status_code: int
    request_id: str | None
    trace_id: str | None
    reason_code: str | None = None
    generation_request_id: str | None = None
    accepted: Literal[True] | None = None
    accepted_generation: int | None = None


class DocumentJobNewGenerationErrorResponse(QualityReviewModel):
    detail: JsonValue
    error_code: str
    request_id: str | None
    trace_id: str | None
    error: DocumentJobNewGenerationErrorDetailResponse


class DocumentReviewUpdateRequest(QualityReviewModel):
    status: DocumentJobReviewStatus
    issue_type: QualityIssue | None = None
    note: str | None = Field(default=None, max_length=1000)
    expected_source: ReviewExpectedSourceRequest


class DocumentQualityCountsResponse(QualityReviewModel):
    formula_count: QualityCount | None = None
    omml_count: QualityCount | None = None
    semantic_count: QualityCount | None = None
    fallback_count: QualityCount | None = None
    table_count: QualityCount | None = None
    fragment_count: QualityCount | None = None
    native_count: QualityCount | None = None
    placeholder_count: QualityCount | None = None
    blocker_count: QualityCount | None = None
    warning_count: QualityCount | None = None
    page_count: QualityCount | None = None
    complete_page_count: QualityCount | None = None
    flag_count: QualityCount | None = None
    count: QualityCount | None = None
    pages: QualityCount | None = None
    observed_pages: QualityCount | None = None
    flags: QualityCount | None = None
    manual_checks: QualityCount | None = None
    checked_rules: QualityCount | None = None
    not_checked_rules: QualityCount | None = None


class DocumentQualityProducerResponse(QualityReviewModel):
    producer: Literal["formula", "table_evidence", "table_placeholder", "word_preview", "word_page_quality", "document_base", "unattributed"]
    schema_version: QualityVersion | None = None
    quality_status: DocumentJobQualityStatus | None = None
    evaluation_state: Literal["complete", "incomplete"] | None = None
    availability: QualityAvailability | None = None
    coverage: Literal["complete", "unavailable"] | None = None
    report_sha256: QualityHash | None = None
    reason_code: str | None = None
    counts: DocumentQualityCountsResponse
    flags: list[str] = Field(default_factory=list)
    unknown_flag_count: QualityCount = 0


class DocumentQualityProducersResponse(QualityReviewModel):
    items: list[DocumentQualityProducerResponse]
    unknown_producer_count: QualityCount


class DocumentQualitySummaryResponse(QualityReviewModel):
    quality_flags: list[str] = Field(default_factory=list)
    layout_quality_flags: list[str] = Field(default_factory=list)
    blocking_quality_flags: list[str] = Field(default_factory=list)
    unknown_flag_count: QualityCount = 0


class DocumentReviewBindingResponse(QualityReviewModel):
    generation: QualityCount
    result_file_id: QualityId | None
    binding_state: Literal["verified", "no_result", "unverified_result", "legacy_unbound"]
    result_sha256: QualityChecksum | None
    file_review_source_revision: QualityCount | None
    receipt_sha256: QualityChecksum | None


class DocumentReviewQualityResponse(QualityReviewModel):
    quality_status: DocumentJobQualityStatus
    summary_sha256: QualityChecksum
    summary: DocumentQualitySummaryResponse
    producers: DocumentQualityProducersResponse


class DocumentReviewResponse(QualityReviewModel):
    status: DocumentJobReviewStatus
    current_record_id: QualityId | None
    sequence: QualityCount | None
    issue_type: QualityIssue | None
    note: str | None
    reviewed_by: QualityId | None
    reviewed_at: datetime | None
    binding: DocumentReviewBindingResponse | None
    validity_reason: Literal["legacy_unbound", "source_changed", "artifact_missing", "artifact_unavailable", "integrity_conflict", "quality_blocked"] | None
    quality: DocumentReviewQualityResponse | None


class DocumentReviewHistoryItemResponse(QualityReviewModel):
    id: QualityId
    sequence: QualityCount
    record_status: DocumentJobReviewStatus
    issue_type: QualityIssue | None
    note: str | None
    reviewed_by: QualityId | None
    reviewed_at: datetime | None
    origin: Literal["live", "legacy_import"]
    legacy_observed_status: DocumentJobReviewStatus | None
    binding: DocumentReviewBindingResponse
    quality: DocumentReviewQualityResponse


class DocumentQualityStatesResponse(QualityReviewModel):
    execution_status: Literal["pending", "queued", "running", "succeeded", "failed", "canceled"]
    quality_status: DocumentJobQualityStatus
    review_status: DocumentJobReviewStatus
    delivery_status: DocumentJobDeliveryStatus


class DocumentQualityResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    states: DocumentQualityStatesResponse
    summary: DocumentQualitySummaryResponse
    producers: DocumentQualityProducersResponse
    review: DocumentReviewResponse
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]


class DocumentQualitySourceSpanResponse(QualityReviewModel):
    fragment_id: QualityId | None = None
    source_page_index: QualityCount | None
    bbox: tuple[float, float, float, float] | None
    html_state: Literal["missing", "empty", "present"] | None = None
    row_start: QualityCount | None = None
    row_count: QualityCount | None = None
    columns: QualityCount | None = None


class DocumentQualityGridResponse(QualityReviewModel):
    rows: QualityCount
    columns: QualityCount
    header_rows: list[QualityCount]
    rowspan_count: QualityCount
    colspan_count: QualityCount


class DocumentQualityTableReferenceResponse(QualityReviewModel):
    fragment_id: QualityId
    source_status: Literal["valid", "missing", "invalid", "unavailable"]
    asset_id: QualityId | None
    file_id: QualityId | None
    mime_type: str | None
    registered: bool


class DocumentQualityCellShapeResponse(QualityReviewModel):
    grid_span: QualityCount
    vertical_merge: Literal["restart", "continue"] | None


class DocumentQualityRowShapeResponse(QualityReviewModel):
    cells: list[DocumentQualityCellShapeResponse]
    header: bool
    cant_split: bool


class DocumentQualityFragmentResponse(QualityReviewModel):
    fragment_id: QualityId
    block_id: QualityId | None
    render_owner_block_id: QualityId
    source_rows: list[QualityCount]
    retained_source_rows: list[QualityCount]
    output_rows: list[QualityCount]
    removed_header_rows: list[QualityCount] | None
    shared_header_rows: list[QualityCount] | None
    status: Literal["rendered", "header_only", "empty", "missing"]


class DocumentQualityNativeTableResponse(QualityReviewModel):
    output_table_key: QualityId
    anchor_block_id: QualityId
    table_index: QualityCount
    grid_columns: QualityCount
    rows: list[DocumentQualityRowShapeResponse]
    fragments: list[DocumentQualityFragmentResponse]


class DocumentQualityPlaceholderResponse(QualityReviewModel):
    placeholder_id: QualityId
    fragment_id: QualityId
    owner_block_id: QualityId
    asset_ref: QualityId
    source_kind: Literal["mineru_reference", "source_pdf_crop"]
    issue_code: Literal["table_noneditable_placeholder"]


class DocumentQualityTableFlagResponse(QualityReviewModel):
    producer: Literal["table_validator", "table_rendering", "table_reference", "table_placeholder"]
    code: str
    severity: Literal["blocker", "warning"]
    fragment_id: QualityId | None


class DocumentQualityTableItemResponse(QualityReviewModel):
    table_id: QualityId
    logical_group_id: QualityId
    member_block_ids: list[QualityId]
    anchor_block_id: QualityId
    source_spans: list[DocumentQualitySourceSpanResponse]
    source_grid: DocumentQualityGridResponse
    references: list[DocumentQualityTableReferenceResponse]
    outputs: list[DocumentQualityNativeTableResponse]
    placeholders: list[DocumentQualityPlaceholderResponse]
    render_state: Literal["native", "placeholder", "mixed", "excluded_margin_artifact"]
    flags: list[DocumentQualityTableFlagResponse]
    unknown_flag_count: QualityCount
    status: DocumentJobQualityStatus


class DocumentQualityTableReportResponse(QualityReviewModel):
    schema_version: QualityVersion
    report_file_id: QualityId
    report_sha256: QualityHash
    coverage: Literal["complete", "unavailable"] | None
    status: DocumentJobQualityStatus | None
    counts: DocumentQualityCountsResponse


class DocumentQualityTablesResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    availability: QualityAvailability
    reason_code: str | None
    report: DocumentQualityTableReportResponse | None
    items: list[DocumentQualityTableItemResponse]
    next_cursor: str | None


class DocumentQualityPageRuleResponse(QualityReviewModel):
    rule_version: Literal["v1"]
    checked: bool
    reason_code: str | None
    metrics: dict[QualityMetric, float | int | None]
    units: dict[QualityMetric, Literal["pt", "pt2", "ratio", "count", "char/pt2"]]


class DocumentQualityPageFlagResponse(QualityReviewModel):
    code: Literal["page_clip_risk", "page_overflow_risk", "unexpected_blank_page_suspected", "page_overlap_suspected", "page_density_low", "page_density_high"]
    severity: Literal["warning", "info"]
    rule_version: Literal["v1"]
    preview_page_index: QualityCount
    metric_refs: list[str]
    evidence_kind: Literal["native_and_raster"]
    manual_check_required: Literal[True]


class DocumentQualityBlockCandidateResponse(QualityReviewModel):
    block_id: QualityId
    association: Literal["single_page", "estimated_start", "navigation_fallback"]
    confidence: Literal["high", "low"]
    source_page_indices: list[QualityCount]
    source_spans: list[DocumentQualitySourceSpanResponse]


class DocumentQualityPageItemResponse(QualityReviewModel):
    preview_page_index: QualityCount
    rules: dict[QualityRule, DocumentQualityPageRuleResponse]
    flags: list[DocumentQualityPageFlagResponse]
    unknown_flag_count: QualityCount
    manual_checks: list[str]
    block_candidates: list[DocumentQualityBlockCandidateResponse]


class DocumentQualityCoverageResponse(QualityReviewModel):
    checked: QualityCount
    not_checked: QualityCount


class DocumentQualityPageReportResponse(QualityReviewModel):
    schema_version: QualityVersion
    analyzer_version: QualityVersion
    id: QualityId
    run_sha256: QualityHash
    generation: QualityCount
    preview_run_id: QualityId
    revision: QualityCount
    attempt: QualityCount
    manifest_file_id: QualityId
    profile_id: QualityId
    profile_sha256: QualityChecksum
    page_count: QualityCount
    evaluation_state: Literal["complete", "incomplete"]
    quality_status: Literal["pending", "passed", "warning"]
    reason_code: str | None
    manual_checks: list[str]
    coverage: dict[QualityRule, DocumentQualityCoverageResponse]
    counts: DocumentQualityCountsResponse


class DocumentQualityPagesResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    availability: QualityAvailability
    reason_code: str | None
    report: DocumentQualityPageReportResponse | None
    items: list[DocumentQualityPageItemResponse]
    next_cursor: str | None


class DocumentPreviewPageResponse(QualityReviewModel):
    file_id: QualityId
    page_index: QualityCount
    width: QualityCount
    height: QualityCount


class DocumentPreviewRunResponse(QualityReviewModel):
    run_id: QualityId
    revision: QualityCount
    attempt: QualityCount
    status: Literal["pending", "running", "succeeded", "failed", "unavailable"]
    profile_id: QualityId
    profile_sha256: QualityChecksum
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None


class DocumentPreviewResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    status: Literal["not_ready", "disabled", "pending", "running", "succeeded", "failed", "unavailable"]
    availability: QualityAvailability
    reason_code: str | None
    run: DocumentPreviewRunResponse | None
    pdf_file_id: QualityId | None
    page_count: QualityCount | None
    items: list[DocumentPreviewPageResponse]
    next_cursor: str | None


class DocumentCurrentReviewResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    review: DocumentReviewResponse
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]


class DocumentReviewComponentResponse(QualityReviewModel):
    availability: Literal["available", "unavailable", "not_ready", "disabled", "not_applicable"]
    reason_code: str | None = None


class DocumentReviewContentSnapshotResponse(QualityReviewModel):
    snapshot_id: QualityHash
    source_pdf_file_id: QualityId
    source_ir_file_id: QualityId | None
    final_ir_file_id: QualityId | None
    preview_run_id: QualityId | None
    preview_revision: QualityCount | None
    preview_attempt: QualityCount | None
    basis: Literal["source", "final", "none"]
    source_content: DocumentReviewComponentResponse
    target_content: DocumentReviewComponentResponse
    translation: DocumentReviewComponentResponse
    preview: DocumentReviewComponentResponse
    mapping: DocumentReviewComponentResponse
    tables: DocumentReviewComponentResponse


class DocumentReviewSourceSpanResponse(QualityReviewModel):
    source_page_index: QualityCount | None
    bbox: tuple[float, float, float, float] | None
    page_width: float | None
    page_height: float | None
    coordinate_unit: Literal["mineru"] = "mineru"
    coordinate_verified: bool
    reason_code: Literal["coordinate_space_unverified"] | None
    fragment_id: QualityId | None = None


class DocumentReviewLocationResponse(QualityReviewModel):
    kind: Literal["single_page", "estimated_start", "unavailable"]
    preview_page_index: QualityCount | None
    confidence: Literal["high", "low", "none"]
    reason_code: str | None
    bookmark_label: str | None = Field(default=None, max_length=100)
    disposition: Literal["rendered", "coalesced", "suppressed", "superseded", "not_emitted"] | None = None
    representative_block_id: QualityId | None = None
    fallback_page_index: QualityCount | None = None
    fallback_block_id: QualityId | None = None
    provenance_status: Literal["verified_ir205", "legacy_layout", "unavailable"] = "unavailable"


class DocumentReviewBlockFlagResponse(QualityReviewModel):
    code: str
    severity: Literal["blocker", "warning", "info"]
    table_id: QualityId | None = None


class DocumentReviewBlockItemResponse(QualityReviewModel):
    block_id: QualityId
    order: QualityCount
    block_type: Literal["heading", "paragraph", "table", "image", "list", "formula"]
    source_type: str | None = Field(default=None, max_length=100)
    excerpt: str = Field(max_length=240)
    source_spans: list[DocumentReviewSourceSpanResponse]
    location: DocumentReviewLocationResponse
    flags: list[DocumentReviewBlockFlagResponse]
    table_ids: list[QualityId]


class DocumentReviewBlocksResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    content_snapshot: DocumentReviewContentSnapshotResponse
    availability: Literal["available", "not_ready", "unavailable"]
    reason_code: str | None
    total: QualityCount
    items: list[DocumentReviewBlockItemResponse]
    next_cursor: str | None


class DocumentReviewTermResponse(QualityReviewModel):
    unit_id: QualityId
    batch_id: QualityId
    source_term: str = Field(max_length=4096)
    target_term: str = Field(max_length=4096)
    version: str | None = Field(default=None, max_length=100)


class DocumentReviewTokenCountsResponse(QualityReviewModel):
    formula: QualityCount = 0
    literal_placeholder: QualityCount = 0
    address: QualityCount = 0
    bit_field: QualityCount = 0
    model: QualityCount = 0
    standard: QualityCount = 0
    version: QualityCount = 0
    signal: QualityCount = 0
    quantity: QualityCount = 0
    unit: QualityCount = 0
    url: QualityCount = 0
    email: QualityCount = 0
    number: QualityCount = 0
    symbol: QualityCount = 0
    technical_literal: QualityCount = 0


class DocumentReviewBatchResponse(QualityReviewModel):
    scope: Literal["batch"] = "batch"
    batch_id: QualityId
    attempt: QualityCount
    status: Literal["succeeded", "failed"]
    provider_backend: Literal["fake", "openai_compatible"] | None = None
    provider_model: str | None = Field(default=None, max_length=200)
    schema_version: QualityVersion | None = None
    validator_version: QualityVersion | None = None
    codec_version: Literal["MD2W_PT_v1"] | None = None
    instruction_version: QualityVersion | None = None
    instruction_sha256: QualityChecksum | None = None
    integrity_status: Literal["passed", "failed", "pending"] | None = None
    error_code: str | None = None
    expected_item_count: QualityCount | None = None
    actual_item_count: QualityCount | None = None
    checked_item_count: QualityCount | None = None
    failed_item_count: QualityCount | None = None
    expected_token_counts: DocumentReviewTokenCountsResponse | None = None
    actual_token_counts: DocumentReviewTokenCountsResponse | None = None
    source_sha256: QualityChecksum | None = None
    restored_sha256: QualityChecksum | None = None


class DocumentReviewContentPartResponse(QualityReviewModel):
    kind: Literal["text", "list_item", "caption", "footnote", "latex", "table_text", "html_summary", "term", "batch", "table", "reference"]
    side: Literal["source", "target", "shared"]
    field: str
    index: QualityCount | None = None
    unit_id: QualityId | None = None
    fragment_id: QualityId | None = None
    offset: QualityCount = 0
    text: str | None = Field(default=None, max_length=4096)
    total_chars: QualityCount | None = None
    truncated: bool = False
    html_state: Literal["missing", "empty", "present"] | None = None
    sha256: QualityHash | None = None
    term: DocumentReviewTermResponse | None = None
    batch: DocumentReviewBatchResponse | None = None
    table: DocumentQualityTableItemResponse | None = None
    reference: DocumentJobTableReferenceResponse | None = None


class DocumentReviewBlockDetailResponse(QualityReviewModel):
    job_id: QualityId
    source: DocumentQualitySourceResponse
    content_snapshot: DocumentReviewContentSnapshotResponse
    block: DocumentReviewBlockItemResponse
    items: list[DocumentReviewContentPartResponse]
    next_cursor: str | None


class DocumentReviewHistoryResponse(QualityReviewModel):
    job_id: QualityId
    through_sequence: QualityCount
    items: list[DocumentReviewHistoryItemResponse]
    next_cursor: str | None


class DocumentReviewUpdateResponse(QualityReviewModel):
    job_id: QualityId
    accepted_record_id: QualityId
    accepted_sequence: QualityCount
    source: DocumentQualitySourceResponse
    review: DocumentReviewResponse
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]


class QualityReviewErrorDetailResponse(QualityReviewModel):
    code: str
    message: str
    status_code: int
    request_id: str | None
    trace_id: str | None
    reason_code: str | None = None


class QualityReviewErrorResponse(QualityReviewModel):
    """受控质量、复核和发布操作的安全错误模型，兼容原 detail 结构。"""
    detail: JsonValue
    error_code: str
    request_id: str | None
    trace_id: str | None
    error: QualityReviewErrorDetailResponse


from app.domains.document_jobs.publication import PublicationExpectedSource


class DocumentPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=36, max_length=36, description="客户端生成并保留的规范 UUID 幂等键。")
    note: str = Field(min_length=1, max_length=1000)
    expected_source: PublicationExpectedSource

    @field_validator("request_id")
    @classmethod
    def _publication_key(cls, value):
        from uuid import UUID
        try:
            parsed = str(UUID(value))
        except ValueError:
            raise ValueError("request_id 必须是 UUID。") from None
        if parsed != value:
            raise ValueError("request_id 必须使用规范 UUID 格式。")
        return parsed

    @field_validator("note")
    @classmethod
    def _publication_note(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("发布备注不能为空。")
        return value


class DocumentPublicationResourceVersionResponse(BaseModel):
    resource_id: str
    version: str
    snapshot_hash: str


class DocumentPublicationVersionsResponse(BaseModel):
    template: DocumentPublicationResourceVersionResponse
    symbol_rules: DocumentPublicationResourceVersionResponse
    renderer_implementation_sha256: str
    translation_status: Literal["complete", "not_applicable"]
    models: list[str]


class DocumentPublicationRecordResponse(BaseModel):
    publication_id: str
    job_id: str
    generation: int
    source_file_id: str
    source_sha256: str
    result_file_id: str
    result_sha256: str
    review_record_id: str
    review_sequence: int
    preview_run_id: str
    published_by: str
    published_at: datetime
    note: str
    versions: DocumentPublicationVersionsResponse


class DocumentPublishResponse(BaseModel):
    publication: DocumentPublicationRecordResponse
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]


class DocumentPublicationPreflightCheckResponse(BaseModel):
    code: str
    status: Literal["passed", "blocked", "not_checked"]
    reason_code: str | None
    message: str


class DocumentPublicationDownloadUrlResponse(BaseModel):
    publication_id: str
    job_id: str
    result_file_id: str
    result_sha256: QualityChecksum
    size_bytes: int = Field(ge=0)
    download_url: str
    expires_at: datetime
    method: Literal["GET"] = "GET"
    classification: Literal["final_delivery"] = "final_delivery"


class DocumentPublicationsResponse(BaseModel):
    preflight_checks: list[DocumentPublicationPreflightCheckResponse]
    download_actions: dict[str, DocumentJobAvailableActionResponse]
    job_id: str
    expected_source: PublicationExpectedSource
    items: list[DocumentPublicationRecordResponse]
    available_actions: dict[DocumentJobActionId, DocumentJobAvailableActionResponse]
