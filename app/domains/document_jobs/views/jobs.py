"""任务读视图：任务详情、可用动作与禁用原因、失败诊断等用例输出模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, JsonValue, ValidationInfo, field_validator

from app.domains.document_jobs.models import (
    DocumentJobDeliveryStatus,
    DocumentJobQualityStatus,
    DocumentJobReviewStatus,
)
from app.domains.translation.modes import TranslationMode


DocumentJobActionId = Literal["download", "retry", "cancel", "archive", "unarchive", "clone", "delete", "publish", "new_generation"]


DocumentJobDownloadClassification = Literal["internal_only"]


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
