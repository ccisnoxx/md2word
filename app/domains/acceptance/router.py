"""Admin HTTP API for Acceptance Center evidence runs."""

from __future__ import annotations

# File: app/domains/acceptance/router.py
# Purpose: Expose admin-only acceptance run list/detail/review endpoints.

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user
from app.core.runtime import AppRuntime
from app.domains.acceptance.models import AcceptanceRunRecord, AcceptanceRunStatus, AcceptanceRunTier
from app.domains.acceptance.schemas import (
    AcceptanceRunListResponse,
    AcceptanceRunResponse,
    AcceptanceRunReviewRequest,
)
from app.domains.audit.models import ActorContext
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/acceptance", tags=["acceptance"])


@router.get("/runs", response_model=AcceptanceRunListResponse)
def list_acceptance_runs(
    tier: AcceptanceRunTier | None = None,
    status_value: Annotated[AcceptanceRunStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> AcceptanceRunListResponse:
    """Return recent acceptance evidence runs for admin review."""

    records = runtime.acceptance_run_service.list_runs(tier=tier, status=status_value, limit=limit)
    return AcceptanceRunListResponse(items=[_build_run_response(record) for record in records], total=len(records))


@router.get("/runs/{run_id}", response_model=AcceptanceRunResponse)
def get_acceptance_run(
    run_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> AcceptanceRunResponse:
    """Return one acceptance evidence run by id."""

    return _build_run_response(runtime.acceptance_run_service.get_run(run_id))


@router.post("/runs/{run_id}/review", response_model=AcceptanceRunResponse)
def review_acceptance_run(
    run_id: str,
    request: AcceptanceRunReviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> AcceptanceRunResponse:
    """Record an admin review decision without changing the run evidence status."""

    record = runtime.acceptance_run_service.review_run(
        run_id,
        decision=request.decision,
        reviewer=user.id,
        review_note=request.review_note,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="acceptance_run.review",
        target_type="acceptance_run",
        target_id=record.id,
        trace_id=trace_id,
        reason=record.review_note,
        details={
            "decision": record.decision,
            "run_status": record.status,
            "tier": record.tier,
            "environment": record.environment,
            "source": record.source,
        },
    )
    return _build_run_response(record)


def _build_run_response(record: AcceptanceRunRecord) -> AcceptanceRunResponse:
    return AcceptanceRunResponse(
        id=record.id,
        title=record.title,
        tier=record.tier,
        status=record.status,
        environment=record.environment,
        source=record.source,
        report_path_or_url=record.report_path_or_url,
        started_at=record.started_at,
        finished_at=record.finished_at,
        summary=record.summary,
        blockers=record.blockers,
        warnings=record.warnings,
        reviewer=record.reviewer,
        decision=record.decision,
        reviewed_at=record.reviewed_at,
        review_note=record.review_note,
        updated_at=record.updated_at,
    )


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")
