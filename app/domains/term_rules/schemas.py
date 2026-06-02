from __future__ import annotations

# app/domains/term_rules/schemas.py: 定义 term-rules API 的 v1 请求/响应模型。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator


class TermRuleCategoryListItemResponse(BaseModel):
    id: str
    code: str
    name: str
    priority: int
    enabled: bool
    description: str
    rule_count: int
    enabled_rule_count: int


class TermRuleCategoryListResponse(BaseModel):
    items: list[TermRuleCategoryListItemResponse]


class TermRuleCategoryCreateRequest(BaseModel):
    id: str | None = None
    code: str
    name: str
    priority: int = 100
    enabled: bool = True
    description: str = ""


class TermRuleCategoryUpdateRequest(BaseModel):
    code: str | None = None
    name: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    description: str | None = None


class TermRuleSegmentResponse(BaseModel):
    seq: int
    segment_text: str
    render_type: str


class TermRuleSegmentWriteRequest(BaseModel):
    segment_text: str
    render_type: str


class TermRuleResponse(BaseModel):
    id: str
    category_id: str
    category_code: str
    category_name: str
    source_term: str
    rule_mode: str
    apply_scope: str
    case_sensitive: bool
    enabled: bool
    priority: int
    segments: list[TermRuleSegmentResponse]
    custom_html: str | None = None
    custom_markdown: str | None = None
    notes: str


class TermRuleListResponse(BaseModel):
    items: list[TermRuleResponse]
    page: int
    page_size: int
    total: int


class TermRuleCreateRequest(BaseModel):
    id: str | None = None
    category_id: str
    source_term: str
    apply_scope: str = "both"
    case_sensitive: bool = True
    enabled: bool = True
    priority: int = 100
    segments: list[TermRuleSegmentWriteRequest]
    custom_html: str | None = None
    custom_markdown: str | None = None
    notes: str = ""


class TermRuleUpdateRequest(BaseModel):
    category_id: str | None = None
    source_term: str | None = None
    apply_scope: str | None = None
    case_sensitive: bool | None = None
    enabled: bool | None = None
    priority: int | None = None
    segments: list[TermRuleSegmentWriteRequest] | None = None
    custom_html: str | None = None
    custom_markdown: str | None = None
    notes: str | None = None


class TermRuleDeleteResponse(BaseModel):
    id: str
    deleted: bool


class RuleExportResponse(BaseModel):
    yaml_text: str


class RuleImportRequest(BaseModel):
    yaml_text: str


class RuleSimulationRequest(BaseModel):
    text: str


class RuleSimulationResponse(BaseModel):
    original: str
    markdown_preview: str
    html_preview: str


class TermRuleImportValidationFindingResponse(BaseModel):
    code: str
    message: str
    path: str | None = None


class TermRuleImportValidationSummaryResponse(BaseModel):
    category_count: int
    rule_count: int
    error_count: int
    warning_count: int


class TermRuleImportValidationReportResponse(BaseModel):
    valid: bool
    summary: TermRuleImportValidationSummaryResponse
    errors: list[TermRuleImportValidationFindingResponse]
    warnings: list[TermRuleImportValidationFindingResponse]


class TermRuleFileSyncResponse(BaseModel):
    repository_backend: str
    category_count: int
    rule_count: int
    bootstrap_seed_path: str
    runtime_yaml_path: str
    warnings: list[str]


class TermRuleSetListItemResponse(BaseModel):
    id: str
    default_version: str | None = None
    version_count: int
    rule_count: int
    enabled_rule_count: int


class TermRuleSetListResponse(BaseModel):
    items: list[TermRuleSetListItemResponse]


class TermRuleSetVersionResponse(BaseModel):
    term_rule_set_id: str
    version: str
    status: str
    rule_count: int
    enabled_rule_count: int
    snapshot_hash: str | None = None
    is_default: bool = False
    published_by: str | None = None
    publish_reason: str | None = None
    published_at: datetime | None = None


class TermRuleSetDetailResponse(BaseModel):
    id: str
    default_version: str | None = None
    versions: list[TermRuleSetVersionResponse]


class TermRuleSetDraftResponse(BaseModel):
    term_rule_set_id: str
    base_version: str | None = None
    rule_count: int
    enabled_rule_count: int
    yaml_text: str
    snapshot_hash: str | None = None


class TermRuleSetDraftUpdateRequest(BaseModel):
    yaml_text: str


class TermRuleSetImportRequest(BaseModel):
    yaml_text: str
    target: Literal["draft", "seed"] = "draft"
    dedupe: Literal["reject", "keep_first"] = "reject"


class TermRuleSetImportDuplicateResponse(BaseModel):
    source_term: str
    path: str | None = None
    message: str


class TermRuleSetImportReportResponse(BaseModel):
    dedupe: str
    total_rules: int
    imported_rules: int
    duplicate_rules: int
    duplicates: list[TermRuleSetImportDuplicateResponse]


class TermRuleSetImportResponse(BaseModel):
    target: str
    term_rule_set_id: str
    version: str
    rule_count: int
    enabled_rule_count: int
    snapshot_hash: str | None = None
    validation: TermRuleImportValidationReportResponse
    import_report: TermRuleSetImportReportResponse


class TermRuleSetExportManifestResponse(BaseModel):
    set_id: str
    version: str
    format: str
    exported_at: datetime
    exported_by: str | None = None


class TermRuleSetExportResponse(BaseModel):
    manifest: TermRuleSetExportManifestResponse
    yaml_text: str


class TermRuleSetPublishRequest(BaseModel):
    make_default: bool = True
    published_by: str | None = None
    publish_reason: str

    @field_validator("publish_reason")
    @classmethod
    def _validate_publish_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("publish_reason 不能为空")
        return normalized


class TermRuleSetRollbackRequest(BaseModel):
    version: str


class TermRuleProposalCreateRequest(BaseModel):
    intent: str
    source_term: str | None = None
    category_id: str | None = None
    segments: list[TermRuleSegmentWriteRequest] | None = None
    reason: str
    source_job_id: str | None = None
    source_file_id: str | None = None
    page_number: int | None = None
    context_before: str | None = None
    context_after: str | None = None
    observed_term_rule_set_id: str | None = None
    observed_term_rule_version: str | None = None
    target_rule_id: str | None = None


class TermRuleProposalReviewRequest(BaseModel):
    review_comment: str | None = None


class TermRuleProposalApproveAndPublishRequest(BaseModel):
    review_comment: str | None = None
    publish_reason: str | None = None


class TermRuleProposalRejectRequest(BaseModel):
    review_comment: str


class TermRuleProposalResponse(BaseModel):
    id: str
    intent: str
    status: str
    source_term: str
    category_id: str
    segments: list[TermRuleSegmentResponse]
    reason: str
    source_job_id: str | None = None
    source_file_id: str | None = None
    page_number: int | None = None
    context_before: str | None = None
    context_after: str | None = None
    observed_term_rule_set_id: str | None = None
    observed_term_rule_version: str | None = None
    target_rule_id: str | None = None
    target_rule_snapshot: dict[str, Any] | None = None
    created_by: str
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    merged_term_rule_set_id: str | None = None
    merged_draft_snapshot_hash: str | None = None
    published_term_rule_set_id: str | None = None
    published_term_rule_set_version: str | None = None
    published_at: datetime | None = None


class TermRuleProposalListResponse(BaseModel):
    items: list[TermRuleProposalResponse]
    total: int
