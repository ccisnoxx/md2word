from __future__ import annotations

# File: app/domains/document_jobs/incidents_router.py
# Purpose: Expose lightweight document_job incident queue APIs for operator triage.

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_runtime, get_trace_id, require_current_user
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.document_jobs.incidents import (
    DOCUMENT_JOB_INCIDENT_FAILURE_TYPES,
    DOCUMENT_JOB_INCIDENT_RETRY_BUCKETS,
    DOCUMENT_JOB_INCIDENT_SORTS,
)
from app.domains.document_jobs.schemas import (
    DocumentJobIncidentBulkRequest,
    DocumentJobIncidentBulkResponse,
    DocumentJobIncidentDiagnosticResponse,
    DocumentJobIncidentListResponse,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/document-job-incidents", tags=["document-job-incidents"])


@router.get("", response_model=DocumentJobIncidentListResponse)
def list_document_job_incidents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    stage: str | None = Query(default=None),
    failure_type: str | None = Query(default=None, json_schema_extra={"enum": sorted(DOCUMENT_JOB_INCIDENT_FAILURE_TYPES)}),
    retryable: bool | None = Query(default=None),
    retry_count: str | None = Query(default=None, json_schema_extra={"enum": sorted(DOCUMENT_JOB_INCIDENT_RETRY_BUCKETS)}),
    stalled_minutes: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None),
    sort: str = Query(default="priority", json_schema_extra={"enum": sorted(DOCUMENT_JOB_INCIDENT_SORTS)}),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobIncidentListResponse:
    return runtime.document_job_incident_service.list_incidents(
        user=user,
        page=page,
        page_size=page_size,
        status_filter=status_filter.strip() if status_filter else None,
        stage_filter=stage.strip() if stage else None,
        failure_type=failure_type.strip() if failure_type else None,
        retryable=retryable,
        retry_count=retry_count.strip() if retry_count else None,
        stalled_minutes=stalled_minutes,
        q=q,
        sort=sort,
    )


@router.get("/{job_id}/diagnostics", response_model=DocumentJobIncidentDiagnosticResponse)
def get_document_job_incident_diagnostics(
    job_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobIncidentDiagnosticResponse:
    return runtime.document_job_incident_service.get_diagnostics(job_id, user=user)


@router.post("/bulk-retry", response_model=DocumentJobIncidentBulkResponse)
def bulk_retry_document_job_incidents(
    payload: DocumentJobIncidentBulkRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
    trace_id: str = Depends(get_trace_id),
) -> DocumentJobIncidentBulkResponse:
    response = runtime.document_job_incident_service.bulk_retry(
        user=user,
        job_ids=payload.job_ids,
        reason=payload.reason,
        trace_id=trace_id,
    )
    for item in response.items:
        if not item.ok:
            continue
        runtime.audit_service.record(
            actor=_actor_from_user(user),
            action="document_job.retry",
            target_type="document_job",
            target_id=item.job_id,
            reason=payload.reason,
            trace_id=trace_id,
        )
    return response


@router.post("/bulk-refresh", response_model=DocumentJobIncidentBulkResponse)
def bulk_refresh_document_job_incidents(
    payload: DocumentJobIncidentBulkRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> DocumentJobIncidentBulkResponse:
    return runtime.document_job_incident_service.bulk_refresh(
        user=user,
        job_ids=payload.job_ids,
    )


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")
