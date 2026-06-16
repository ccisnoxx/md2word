from __future__ import annotations

# app/domains/term_rules/models.py: 定义 term_rules live store 和导入校验模型。

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List

from pydantic import BaseModel, Field


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
