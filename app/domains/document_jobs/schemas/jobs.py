"""任务创建、详情、列表、生命周期操作、事件、文件、可用动作、重试/克隆、批量操作与下载 URL 的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, JsonValue, ValidationInfo, field_validator
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
    """当前代失败定位投影（MinerU 验证、渲染或表格占位操作）；页码为 1 起始，文档级问题不伪造页码。"""

    source: Literal["mineru_validation", "render_operation", "table_placeholder"] = "mineru_validation"
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
    block_ids: list[str] = Field(default_factory=list, description="失败操作涉及的 IR 块 ID。")
    operation_kind: str | None = Field(default=None, description="失败的渲染计划或表格占位操作类型。")
    source_page_count: int | None = Field(default=None, description="源 PDF 总页数；无法得知时为 null。")
    page_count_basis: Literal["mineru_layout", "content_blocks"] | None = Field(
        default=None, description="content_blocks 时空白页可能未计入，总页数只能当下限。")


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
