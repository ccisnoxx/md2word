from __future__ import annotations

# File: app/domains/translation/schemas.py
# Purpose: 定义 Translation Profile、Translation Term Proposal 和 Translation Term Set API 的 v1 请求/响应模型。

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TranslationProfileListItemResponse(BaseModel):
    id: str
    default_version: str | None = None
    version_count: int
    target_language: str
    domain: str
    prompt_version: str
    model: str | None = None
    max_pages_per_batch: int
    max_chars_per_batch: int


class TranslationProfileListResponse(BaseModel):
    items: list[TranslationProfileListItemResponse]


class TranslationProfileVersionResponse(BaseModel):
    translation_profile_id: str
    version: str
    status: str
    snapshot_hash: str | None = None
    is_default: bool = False
    target_language: str
    domain: str
    prompt_version: str
    model: str | None = None
    max_pages_per_batch: int
    max_chars_per_batch: int
    published_at: datetime | None = None


class TranslationProfileDetailResponse(BaseModel):
    id: str
    default_version: str | None = None
    versions: list[TranslationProfileVersionResponse]


class TranslationProfileDraftResponse(BaseModel):
    translation_profile_id: str
    base_version: str | None = None
    target_language: str
    domain: str
    prompt_version: str
    model: str | None = None
    max_pages_per_batch: int
    max_chars_per_batch: int
    snapshot_hash: str | None = None


class TranslationProfileDraftUpdateRequest(BaseModel):
    target_language: str = Field(default="zh-CN", min_length=1, max_length=32)
    domain: str = Field(default="electronics engineering technical document", min_length=1, max_length=200)
    prompt_version: str = Field(default="translation-minimal-v1", min_length=1, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    max_pages_per_batch: int = Field(default=20, ge=1, le=500)
    max_chars_per_batch: int = Field(default=60000, ge=1, le=500000)


class TranslationProfilePublishRequest(BaseModel):
    make_default: bool = True


class TranslationProfileRollbackRequest(BaseModel):
    version: str


class TranslationTermProposalChangeRequest(BaseModel):
    action: str
    source_term: str
    target_term: str | None = None
    case_sensitive: bool | None = None
    status: str | None = None
    priority: int | None = None
    domain: str | None = None
    category: str | None = None
    note: str | None = None


class TranslationTermProposalCreateRequest(BaseModel):
    language_pair: str = Field(default="en2zh", min_length=1, max_length=32)
    source_job_id: str | None = None
    source_file_id: str | None = None
    observed_translation_term_set_id: str | None = None
    observed_translation_term_version: str | None = None
    changes: list[TranslationTermProposalChangeRequest]


class TranslationTermProposalReviewRequest(BaseModel):
    review_note: str | None = None


class TranslationTermProposalApproveAndPublishRequest(BaseModel):
    review_note: str | None = None
    release_note: str | None = None


class TranslationTermProposalRejectRequest(BaseModel):
    review_note: str


class TranslationTermProposalChangeResponse(BaseModel):
    seq: int
    action: str
    source_term: str
    normalized_source_term: str
    target_term: str | None = None
    case_sensitive: bool | None = None
    status: str | None = None
    priority: int | None = None
    domain: str | None = None
    category: str | None = None
    note: str | None = None


class TranslationTermProposalResponse(BaseModel):
    id: str
    status: str
    submitted_by: str
    source_job_id: str | None = None
    source_file_id: str | None = None
    observed_translation_term_set_id: str | None = None
    observed_translation_term_version: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    published_translation_term_set_id: str | None = None
    published_translation_term_version: str | None = None
    published_at: datetime | None = None
    changes: list[TranslationTermProposalChangeResponse]
    created_at: datetime


class TranslationTermProposalListResponse(BaseModel):
    items: list[TranslationTermProposalResponse]
    total: int


class TranslationTermValidationFindingResponse(BaseModel):
    code: str
    message: str
    normalized_source_term: str | None = None


class TranslationTermValidationReportResponse(BaseModel):
    valid: bool
    errors: list[TranslationTermValidationFindingResponse]
    warnings: list[TranslationTermValidationFindingResponse]


class TranslationTermSetImportRequest(BaseModel):
    csv_text: str
    target: Literal["draft", "seed"] = "draft"
    dedupe: Literal["reject", "keep_first"] = "reject"


class TranslationTermSetImportDuplicateResponse(BaseModel):
    row_number: int
    kept_row_number: int
    source_term: str
    normalized_source_term: str


class TranslationTermSetImportReportResponse(BaseModel):
    dedupe: str
    total_rows: int
    imported_rows: int
    duplicate_rows: int
    duplicates: list[TranslationTermSetImportDuplicateResponse]


class TranslationTermSetImportResponse(BaseModel):
    target: str
    set_id: str
    language_pair: str
    version: str
    term_count: int
    snapshot_hash: str
    validation: TranslationTermValidationReportResponse
    import_report: TranslationTermSetImportReportResponse


class TranslationTermSetExportManifestResponse(BaseModel):
    set_id: str
    language_pair: str
    version: str
    format: str
    exported_at: datetime
    exported_by: str | None = None


class TranslationTermSetExportResponse(BaseModel):
    manifest: TranslationTermSetExportManifestResponse
    csv_text: str


class TranslationTermEntryResponse(BaseModel):
    language_pair: str
    source_term: str
    normalized_source_term: str
    target_term: str
    version: str
    set_id: str
    case_sensitive: bool = False
    status: str
    priority: int = 0
    domain: str | None = None
    category: str | None = None
    note: str = ""


class TranslationTermSetListItemResponse(BaseModel):
    set_id: str
    language_pair: str
    default_version: str | None = None
    draft_version: str | None = None
    version_count: int
    default_term_count: int = 0
    draft_term_count: int = 0
    snapshot_hash: str | None = None


class TranslationTermSetListResponse(BaseModel):
    items: list[TranslationTermSetListItemResponse]


class TranslationTermSetVersionResponse(BaseModel):
    set_id: str
    language_pair: str
    version: str
    status: str
    snapshot_hash: str | None = None
    term_count: int
    is_default: bool = False
    published_by: str | None = None
    published_at: datetime | None = None
    release_note: str | None = None
    created_at: datetime
    updated_at: datetime


class TranslationTermSetDetailResponse(BaseModel):
    set_id: str
    language_pair: str
    default_version: str | None = None
    draft_version: str | None = None
    versions: list[TranslationTermSetVersionResponse]


class TranslationTermSetDraftResponse(BaseModel):
    set_id: str
    language_pair: str
    version: str
    base_version: str | None = None
    term_count: int
    snapshot_hash: str
    validation: TranslationTermValidationReportResponse
    entries: list[TranslationTermEntryResponse]


class TranslationTermSetDiffSummaryResponse(BaseModel):
    """Translation Term Set 版本 diff 的聚合计数。"""

    added: int = 0
    removed: int = 0
    changed: int = 0
    unchanged: int = 0
    total_before: int = 0
    total_after: int = 0


class TranslationTermSetDiffEntryResponse(BaseModel):
    """Translation Term Set diff 中的一条术语级变化。"""

    kind: Literal["added", "removed", "changed", "unchanged"]
    normalized_source_term: str
    source_term: str
    changed_fields: list[str] = Field(default_factory=list)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class TranslationTermSetDiffResponse(BaseModel):
    """返回两个 Translation Term Set 版本之间的 read-only diff。"""

    set_id: str
    language_pair: str
    base_version: str
    target_version: str
    summary: TranslationTermSetDiffSummaryResponse
    items: list[TranslationTermSetDiffEntryResponse]


class TranslationTermSetPreflightResponse(BaseModel):
    """返回发布前 read-only 校验、阻断原因和 diff 摘要。"""

    set_id: str
    language_pair: str
    base_version: str
    target_version: str
    publish_blocked: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    validation: TranslationTermValidationReportResponse
    diff_summary: TranslationTermSetDiffSummaryResponse


class TranslationTermSetPublishRequest(BaseModel):
    make_default: bool = True
    release_note: str | None = Field(default=None, max_length=500)


class TranslationTermSetRollbackRequest(BaseModel):
    version: str = Field(min_length=1, max_length=128)


class TranslationTermProposalCompatibilityFindingResponse(BaseModel):
    """pending Translation Term Proposal 与当前 draft 的兼容性 finding。"""

    severity: Literal["warning", "conflict"]
    code: str
    message: str
    normalized_source_term: str | None = None
    action: str | None = None
    current_entry: dict[str, Any] | None = None
    observed_entry: dict[str, Any] | None = None


class TranslationTermProposalCompatibilityItemResponse(BaseModel):
    """单个 pending Translation Term Proposal 的 read-only 兼容性预览。"""

    proposal_id: str
    compatibility: Literal["compatible", "warning", "conflict"]
    observed_version: str | None = None
    change_count: int
    conflicts: list[TranslationTermProposalCompatibilityFindingResponse] = Field(default_factory=list)
    warnings: list[TranslationTermProposalCompatibilityFindingResponse] = Field(default_factory=list)


class TranslationTermProposalCompatibilitySummaryResponse(BaseModel):
    """Translation Term Proposal 兼容性预览的聚合计数。"""

    total: int = 0
    compatible: int = 0
    warning: int = 0
    conflict: int = 0


class TranslationTermProposalCompatibilityResponse(BaseModel):
    """返回当前 set 的 pending proposal 兼容性预览，不修改 proposal 或 draft。"""

    set_id: str
    language_pair: str
    summary: TranslationTermProposalCompatibilitySummaryResponse
    items: list[TranslationTermProposalCompatibilityItemResponse]
