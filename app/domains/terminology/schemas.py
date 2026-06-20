from __future__ import annotations

# File: app/domains/terminology/schemas.py
# Purpose: Define terminology governance release API request and response contracts.

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domains.terminology.models import (
    TerminologyFindingSeverity,
    TerminologyReleaseStatus,
)


class TerminologyReleaseScopeRequest(BaseModel):
    project: str = Field(min_length=1, max_length=128)
    language_pair: str = Field(min_length=1, max_length=32)
    content_type: str = Field(min_length=1, max_length=128)


class TerminologyReleaseScopeResponse(BaseModel):
    project: str
    language_pair: str
    content_type: str


class TerminologyReleaseCreateRequest(BaseModel):
    translation_term_set_id: str = Field(min_length=1, max_length=128)
    translation_term_version: str = Field(min_length=1, max_length=128)
    term_rule_set_id: str = Field(min_length=1, max_length=128)
    term_rule_set_version: str = Field(min_length=1, max_length=128)
    scope: TerminologyReleaseScopeRequest
    release_note: str | None = Field(default=None, max_length=500)
    source_release_id: str | None = Field(default=None, max_length=128)
    source_release_version: str | None = Field(default=None, max_length=128)


class TerminologyReleaseFindingResponse(BaseModel):
    severity: TerminologyFindingSeverity
    code: str
    message: str
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TerminologyReleaseValidationSummaryResponse(BaseModel):
    error_count: int = 0
    warning_count: int = 0
    conflict_count: int = 0
    publishable_term_count: int = 0
    overlapping_release_count: int = 0


class TerminologyReleaseValidationReportResponse(BaseModel):
    valid: bool
    blocking: bool
    summary: TerminologyReleaseValidationSummaryResponse
    errors: list[TerminologyReleaseFindingResponse] = Field(default_factory=list)
    warnings: list[TerminologyReleaseFindingResponse] = Field(default_factory=list)
    conflicts: list[TerminologyReleaseFindingResponse] = Field(default_factory=list)


class TerminologyReleaseAssetResponse(BaseModel):
    resource_id: str
    version: str
    snapshot_hash: str | None = None
    item_count: int | None = None


class TerminologyReleaseResponse(BaseModel):
    id: str
    version: str
    status: TerminologyReleaseStatus
    scope: TerminologyReleaseScopeResponse
    translation_term_set: TerminologyReleaseAssetResponse
    term_rule_set: TerminologyReleaseAssetResponse
    validation_report: TerminologyReleaseValidationReportResponse
    release_note: str | None = None
    source_release_id: str | None = None
    source_release_version: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime
    rolled_back_by: str | None = None
    rolled_back_at: datetime | None = None


class TerminologyReleaseListResponse(BaseModel):
    items: list[TerminologyReleaseResponse]
    total: int


class TerminologyReleaseRollbackRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class TerminologyReleaseCopyResponse(BaseModel):
    source: TerminologyReleaseResponse
    draft: TerminologyReleaseCreateRequest
