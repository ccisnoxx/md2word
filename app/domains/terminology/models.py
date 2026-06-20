from __future__ import annotations

# File: app/domains/terminology/models.py
# Purpose: Define terminology governance package release records and validation findings.

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


TerminologyReleaseStatus = Literal["active", "rolled_back"]
TerminologyFindingSeverity = Literal["error", "warning", "conflict"]


def utc_now() -> datetime:
    """Return the UTC timestamp used for release lifecycle records."""

    return datetime.now(timezone.utc)


class TerminologyReleaseScope(BaseModel):
    """Applicability scope for one terminology governance package release."""

    project: str
    language_pair: str
    content_type: str


class TerminologyReleaseAssetRef(BaseModel):
    """Published asset version bound into a terminology governance package."""

    resource_id: str
    version: str
    snapshot_hash: str | None = None
    item_count: int | None = None


class TerminologyGovernanceFinding(BaseModel):
    """Structured preflight finding persisted with the release validation report."""

    severity: TerminologyFindingSeverity
    code: str
    message: str
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TerminologyGovernanceValidationSummary(BaseModel):
    """Aggregated validation counts for a terminology release preflight."""

    error_count: int = 0
    warning_count: int = 0
    conflict_count: int = 0
    publishable_term_count: int = 0
    overlapping_release_count: int = 0


class TerminologyGovernanceValidationReport(BaseModel):
    """Full preflight result for a terminology governance package release."""

    valid: bool
    blocking: bool
    summary: TerminologyGovernanceValidationSummary
    errors: list[TerminologyGovernanceFinding] = Field(default_factory=list)
    warnings: list[TerminologyGovernanceFinding] = Field(default_factory=list)
    conflicts: list[TerminologyGovernanceFinding] = Field(default_factory=list)


class TerminologyReleaseRecord(BaseModel):
    """Persisted immutable release version plus rollback lifecycle metadata."""

    id: str
    version: str
    status: TerminologyReleaseStatus = "active"
    scope: TerminologyReleaseScope
    translation_term_set: TerminologyReleaseAssetRef
    term_rule_set: TerminologyReleaseAssetRef
    validation_report: TerminologyGovernanceValidationReport
    release_note: str | None = None
    source_release_id: str | None = None
    source_release_version: str | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    published_at: datetime = Field(default_factory=utc_now)
    rolled_back_by: str | None = None
    rolled_back_at: datetime | None = None
