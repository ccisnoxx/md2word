from __future__ import annotations

# app/domains/term_rules/models.py: 定义 term_rules live store 和导入校验模型。

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RuleMode(str, Enum):
    SIMPLE = "simple"
    ADVANCED = "advanced"


class RuleRenderType(str, Enum):
    PLAIN = "plain"
    SUBSCRIPT = "subscript"
    SUPERSCRIPT = "superscript"


class RuleApplyScope(str, Enum):
    MARKDOWN = "markdown"
    TABLE = "table"
    BOTH = "both"


class TermRuleScopeType(str, Enum):
    GLOBAL = "global"
    DEPARTMENT = "department"


class TermRuleReviewAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class TermRuleReviewItemStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONFLICT = "conflict"


def normalize_term_key(value: str) -> str:
    """Build the stable conflict/matching key for effective terminology rules."""

    return str(value or "").strip().casefold()


class TermRuleCategoryRecord(BaseModel):
    id: str
    code: str
    name: str
    priority: int = 100
    enabled: bool = True
    description: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TermRuleSegmentRecord(BaseModel):
    seq: int
    segment_text: str
    render_type: RuleRenderType


class TermRuleRecord(BaseModel):
    id: str
    category_id: str
    source_term: str
    normalized_term: str = ""
    scope_type: TermRuleScopeType = TermRuleScopeType.GLOBAL
    scope_id: str | None = None
    current_version: int = 1
    active: bool = True
    rule_mode: RuleMode
    apply_scope: RuleApplyScope = RuleApplyScope.BOTH
    case_sensitive: bool = True
    enabled: bool = True
    priority: int = 100
    segments: List[TermRuleSegmentRecord] = Field(default_factory=list)
    custom_html: str | None = None
    custom_markdown: str | None = None
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def normalize_effective_identity(self) -> "TermRuleRecord":
        self.normalized_term = self.normalized_term or normalize_term_key(self.source_term)
        if self.scope_type == TermRuleScopeType.GLOBAL:
            self.scope_id = None
        elif not str(self.scope_id or "").strip():
            raise ValueError("department-scoped term rule requires scope_id")
        if self.current_version < 1:
            self.current_version = 1
        return self


class TermRulesStore(BaseModel):
    categories: List[TermRuleCategoryRecord] = Field(default_factory=list)
    rules: List[TermRuleRecord] = Field(default_factory=list)


class TermRuleProposalIntent(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DISABLE = "disable"


class TermRuleProposalStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class TermRuleProposalRecord(BaseModel):
    """持久化 operator 术语建议和 admin 审核结果。"""

    id: str
    intent: TermRuleProposalIntent
    status: TermRuleProposalStatus = TermRuleProposalStatus.PENDING_REVIEW
    source_term: str
    category_id: str
    segments: List[TermRuleSegmentRecord] = Field(default_factory=list)
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
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    merged_term_rule_set_id: str | None = None
    merged_draft_snapshot_hash: str | None = None
    published_term_rule_set_id: str | None = None
    published_term_rule_set_version: str | None = None
    published_at: datetime | None = None


class TermRuleReviewBatchRecord(BaseModel):
    """Submission batch grouping one or more terminology rule review items."""

    id: str
    submitted_by: str
    submitter_department_id: str
    source_job_id: str | None = None
    source_file_id: str | None = None
    reason: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TermRuleReviewItemRecord(BaseModel):
    """One pending or reviewed terminology rule change under a review batch."""

    id: str
    batch_id: str
    seq: int
    action: TermRuleReviewAction
    status: TermRuleReviewItemStatus = TermRuleReviewItemStatus.PENDING
    scope_type: TermRuleScopeType
    scope_id: str | None = None
    normalized_term: str
    target_rule_id: str | None = None
    base_version: int | None = None
    submitted_snapshot: dict[str, Any]
    rejection_reason: str | None = None
    conflict_reason: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def normalize_review_identity(self) -> "TermRuleReviewItemRecord":
        self.normalized_term = normalize_term_key(self.normalized_term)
        if self.scope_type == TermRuleScopeType.GLOBAL:
            self.scope_id = None
        elif not str(self.scope_id or "").strip():
            raise ValueError("department-scoped review item requires scope_id")
        return self


class TermRuleVersionRecord(BaseModel):
    """Audit history for an approved create, update, or soft-delete action."""

    id: str
    rule_id: str
    version: int
    action: TermRuleReviewAction
    scope_type: TermRuleScopeType
    scope_id: str | None = None
    normalized_term: str
    review_item_id: str | None = None
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)


class TermRuleImportValidationFinding(BaseModel):
    code: str
    message: str
    path: str | None = None


class TermRuleImportValidationSummary(BaseModel):
    category_count: int = 0
    rule_count: int = 0
    error_count: int = 0
    warning_count: int = 0


class TermRuleImportValidationReport(BaseModel):
    valid: bool
    summary: TermRuleImportValidationSummary
    errors: list[TermRuleImportValidationFinding] = Field(default_factory=list)
    warnings: list[TermRuleImportValidationFinding] = Field(default_factory=list)
