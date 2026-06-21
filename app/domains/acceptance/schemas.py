"""Pydantic schemas for Acceptance Center APIs."""

from __future__ import annotations

# File: app/domains/acceptance/schemas.py
# Purpose: Define admin-safe Acceptance Center request and response contracts.

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.acceptance.models import (
    AcceptanceLatestOverallStatus,
    AcceptanceReviewDecision,
    AcceptanceRunRiskLevel,
    AcceptanceRunStatus,
    AcceptanceRunTier,
)


class AcceptanceRunResponse(BaseModel):
    id: str
    title: str
    tier: AcceptanceRunTier
    status: AcceptanceRunStatus
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
    updated_at: datetime


class AcceptanceRunListResponse(BaseModel):
    items: list[AcceptanceRunResponse]
    total: int


class AcceptanceRunUpsertRequest(BaseModel):
    id: str = Field(..., max_length=160)
    title: str = Field(..., max_length=240)
    tier: AcceptanceRunTier
    status: AcceptanceRunStatus = "unknown"
    environment: str = Field(..., max_length=120)
    source: str = Field(..., max_length=160)
    report_path_or_url: str | None = Field(default=None, max_length=1000)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=4000)
    blockers: list[str] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=100)


class AcceptanceLatestTierSummaryResponse(BaseModel):
    tier: AcceptanceRunTier
    run: AcceptanceRunResponse | None = None
    missing: bool = False
    risk_level: AcceptanceRunRiskLevel
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AcceptanceLatestSummaryResponse(BaseModel):
    overall_status: AcceptanceLatestOverallStatus
    missing_tiers: list[AcceptanceRunTier] = Field(default_factory=list)
    blocker_count: int = 0
    warning_count: int = 0
    latest_reviewed_run: AcceptanceRunResponse | None = None
    tiers: list[AcceptanceLatestTierSummaryResponse]
    generated_at: datetime


class AcceptanceRunReviewRequest(BaseModel):
    decision: AcceptanceReviewDecision
    review_note: str | None = Field(default=None, max_length=2000)
