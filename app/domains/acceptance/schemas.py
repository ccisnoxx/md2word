"""Pydantic schemas for Acceptance Center APIs."""

from __future__ import annotations

# File: app/domains/acceptance/schemas.py
# Purpose: Define admin-safe Acceptance Center request and response contracts.

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.acceptance.models import AcceptanceReviewDecision, AcceptanceRunStatus, AcceptanceRunTier


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


class AcceptanceRunReviewRequest(BaseModel):
    decision: AcceptanceReviewDecision
    review_note: str | None = Field(default=None, max_length=2000)
