from __future__ import annotations

# app/domains/term_rules/schemas.py: 定义 term-rules API 的 v1 请求/响应模型。

from datetime import datetime

from pydantic import BaseModel


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


class TermRuleSetPublishRequest(BaseModel):
    make_default: bool = True
    published_by: str | None = None
    publish_reason: str | None = None


class TermRuleSetRollbackRequest(BaseModel):
    version: str
