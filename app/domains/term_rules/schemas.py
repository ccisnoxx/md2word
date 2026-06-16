# File: app/domains/term_rules/schemas.py
# Purpose: 定义 term-rules API 的 v1 请求和响应模型。

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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


class TermRuleDraftRuleMutationResponse(BaseModel):
    """返回 draft 规则写入结果和更新后的 draft 元数据。"""

    rule: TermRuleResponse
    draft: TermRuleSetDraftResponse


class TermRuleDraftRuleDeleteResponse(BaseModel):
    """返回 draft 规则移除结果和更新后的 draft 元数据。"""

    id: str
    removed: bool
    draft: TermRuleSetDraftResponse


class TermRuleSetVersionRefResponse(BaseModel):
    """描述 diff/preflight 中解析后的规则集版本引用。"""

    ref: str
    version: str
    snapshot_hash: str | None = None
    rule_count: int
    enabled_rule_count: int


class TermRuleSetDiffSummaryResponse(BaseModel):
    """汇总 draft 与基线版本之间的规则变化数量。"""

    added: int
    updated: int
    disabled: int
    removed: int
    unchanged: int
    total: int


class TermRuleSetDiffItemResponse(BaseModel):
    """描述一条规则在 diff 中的变化。"""

    change_type: Literal["added", "updated", "disabled", "removed", "unchanged"]
    rule_id: str
    source_term: str
    category_id: str
    changed_fields: list[str]
    before: TermRuleResponse | None = None
    after: TermRuleResponse | None = None


class TermRuleSetDiffResponse(BaseModel):
    """返回 Term Rule Set draft 相对基线版本的结构化差异。"""

    term_rule_set_id: str
    base_ref: TermRuleSetVersionRefResponse
    target_ref: TermRuleSetVersionRefResponse
    summary: TermRuleSetDiffSummaryResponse
    items: list[TermRuleSetDiffItemResponse]


class TermRuleGovernanceFindingResponse(BaseModel):
    """描述发布前治理校验的一条错误、告警或冲突。"""

    severity: Literal["error", "warning", "conflict"]
    code: str
    message: str
    path: str | None = None
    rule_id: str | None = None
    source_term: str | None = None
    category_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TermRuleSetPreflightSummaryResponse(BaseModel):
    """汇总发布前校验报告的发现数量和 draft 规模。"""

    error_count: int
    warning_count: int
    conflict_count: int
    rule_count: int
    enabled_rule_count: int


class TermRuleSetPreflightResponse(BaseModel):
    """返回 Term Rule Set draft 发布前校验结果。"""

    term_rule_set_id: str
    valid: bool
    blocking: bool
    base_ref: TermRuleSetVersionRefResponse
    draft_ref: TermRuleSetVersionRefResponse
    summary: TermRuleSetPreflightSummaryResponse
    errors: list[TermRuleGovernanceFindingResponse]
    warnings: list[TermRuleGovernanceFindingResponse]
    conflicts: list[TermRuleGovernanceFindingResponse]
    diff_summary: TermRuleSetDiffSummaryResponse


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


class TermRuleProposalBulkReviewRequest(BaseModel):
    """批量审核请求，共享同一条审核备注。"""

    proposal_ids: list[str] = Field(default_factory=list)
    review_comment: str | None = None


class TermRuleProposalBulkRejectRequest(BaseModel):
    """批量拒绝请求，共享同一条拒绝原因。"""

    proposal_ids: list[str] = Field(default_factory=list)
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


class TermRuleProposalConflictItemResponse(BaseModel):
    """描述 Term Rule Proposal 审核时发现的一条结构化冲突。"""

    type: Literal["stale_target_rule", "missing_target_rule", "source_term_segments_conflict"]
    message: str
    proposal_id: str
    target_rule_id: str | None = None
    source_term: str
    category_id: str
    current_rule: TermRuleResponse | None = None
    target_rule_snapshot: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TermRuleProposalConflictResponse(BaseModel):
    """返回 Term Rule Proposal 审核冲突的稳定 409 响应 payload。"""

    code: Literal["term_rule_proposal_conflict"] = "term_rule_proposal_conflict"
    message: str
    conflicts: list[TermRuleProposalConflictItemResponse]


class TermRuleProposalListResponse(BaseModel):
    items: list[TermRuleProposalResponse]
    total: int


class TermRuleProposalBulkItemResponse(BaseModel):
    """批量审核中单条 proposal 的成功或失败结果。"""

    proposal_id: str
    ok: bool
    status_code: int
    error_code: str | None = None
    detail: str | dict[str, Any] | None = None
    proposal: TermRuleProposalResponse | None = None


class TermRuleProposalBulkResponse(BaseModel):
    """批量审核响应；允许部分成功且不隐藏单条失败原因。"""

    action: Literal["approve", "reject"]
    total: int
    succeeded: int
    failed: int
    items: list[TermRuleProposalBulkItemResponse] = Field(default_factory=list)
