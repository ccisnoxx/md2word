"""Persisted metadata records for Acceptance Center evidence runs."""

from __future__ import annotations

# File: app/domains/acceptance/models.py
# Purpose: Define small Acceptance Center metadata records for admin review.

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domains.resources.models import utc_now


AcceptanceRunTier = Literal["P0", "P1", "P2"]
AcceptanceRunStatus = Literal["passed", "failed", "unknown"]
AcceptanceReviewDecision = Literal["approved", "rejected", "needs_changes"]
AcceptanceLatestOverallStatus = Literal["accepted", "blocked", "incomplete", "needs_attention"]
AcceptanceRunRiskLevel = Literal["success", "warning", "danger", "unknown"]


class AcceptanceRunRecord(BaseModel):
    """One compact acceptance evidence run; artifacts stay outside metadata storage."""

    id: str
    title: str
    tier: AcceptanceRunTier
    status: AcceptanceRunStatus = "unknown"
    environment: str
    source: str
    report_path_or_url: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: str | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reviewer: str | None = None
    decision: AcceptanceReviewDecision | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def normalize_metadata(self) -> "AcceptanceRunRecord":
        """Normalize compact text fields and reject inconsistent review metadata."""

        self.id = _normalize_required_text(self.id, "id")
        self.title = _normalize_required_text(self.title, "title")
        self.environment = _normalize_required_text(self.environment, "environment")
        self.source = _normalize_required_text(self.source, "source")
        self.report_path_or_url = _normalize_optional_text(self.report_path_or_url)
        self.summary = _normalize_optional_text(self.summary)
        self.reviewer = _normalize_optional_text(self.reviewer)
        self.review_note = _normalize_optional_text(self.review_note)
        self.blockers = _normalize_text_list(self.blockers)
        self.warnings = _normalize_text_list(self.warnings)
        if self.started_at is not None and self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at must not be earlier than started_at")
        review_parts = (self.reviewer, self.decision, self.reviewed_at)
        if any(part is not None for part in review_parts) and not all(part is not None for part in review_parts):
            raise ValueError("reviewer, decision, and reviewed_at must be stored together")
        return self


class AcceptanceLatestTierSummary(BaseModel):
    """Latest Acceptance Center evidence state for one release tier."""

    tier: AcceptanceRunTier
    run: AcceptanceRunRecord | None = None
    missing: bool = False
    risk_level: AcceptanceRunRiskLevel
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AcceptanceLatestSummary(BaseModel):
    """Derived P0/P1/P2 acceptance state; this is not a persisted source of truth."""

    overall_status: AcceptanceLatestOverallStatus
    missing_tiers: list[AcceptanceRunTier] = Field(default_factory=list)
    blocker_count: int = 0
    warning_count: int = 0
    latest_reviewed_run: AcceptanceRunRecord | None = None
    tiers: list[AcceptanceLatestTierSummary]
    generated_at: datetime = Field(default_factory=utc_now)


def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_text_list(values: list[str]) -> list[str]:
    return [normalized for value in values if (normalized := value.strip())]
