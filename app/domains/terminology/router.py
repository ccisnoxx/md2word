"""HTTP API for terminology governance package releases."""

from __future__ import annotations

# File: app/domains/terminology/router.py
# Purpose: Expose terminology governance package release list, preflight, publish, rollback, and copy endpoints.

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_actor, require_current_user
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.terminology.models import (
    TerminologyGovernanceFinding,
    TerminologyGovernanceValidationReport,
    TerminologyReleaseAssetRef,
    TerminologyReleaseRecord,
    TerminologyReleaseScope,
    TerminologyReleaseStatus,
)
from app.domains.terminology.schemas import (
    TerminologyReleaseAssetResponse,
    TerminologyReleaseCopyResponse,
    TerminologyReleaseCreateRequest,
    TerminologyReleaseFindingResponse,
    TerminologyReleaseListResponse,
    TerminologyReleaseResponse,
    TerminologyReleaseScopeResponse,
    TerminologyReleaseValidationReportResponse,
    TerminologyReleaseValidationSummaryResponse,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/terminology-releases", tags=["terminology-releases"])


@router.get("", response_model=TerminologyReleaseListResponse)
def list_terminology_releases(
    status_value: TerminologyReleaseStatus | None = Query(default=None, alias="status"),
    project: str | None = None,
    language_pair: str | None = None,
    content_type: str | None = None,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_current_user),
) -> TerminologyReleaseListResponse:
    """Return terminology governance releases, optionally filtered by lifecycle and scope."""

    records = runtime.terminology_release_service.list_releases(
        status=status_value,
        project=project,
        language_pair=language_pair,
        content_type=content_type,
    )
    return TerminologyReleaseListResponse(items=[_build_release_response(record) for record in records], total=len(records))


@router.get("/{release_id}", response_model=TerminologyReleaseResponse)
def get_terminology_release(
    release_id: str,
    version: str | None = None,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_current_user),
) -> TerminologyReleaseResponse:
    """Return one terminology governance release version or the latest version."""

    return _build_release_response(runtime.terminology_release_service.get_release(release_id, version))


@router.post("/preflight", response_model=TerminologyReleaseValidationReportResponse)
def preflight_terminology_release(
    request: TerminologyReleaseCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_current_user),
) -> TerminologyReleaseValidationReportResponse:
    """Run read-only preflight for a terminology governance release request."""

    return _build_validation_report_response(runtime.terminology_release_service.preflight(request))


@router.post("", response_model=TerminologyReleaseResponse, status_code=status.HTTP_201_CREATED)
def publish_terminology_release(
    request: TerminologyReleaseCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    actor: ActorContext = Depends(require_admin_actor),
) -> TerminologyReleaseResponse:
    """Publish a terminology governance package after preflight passes."""

    record = runtime.terminology_release_service.publish(request, actor_id=actor.actor_id)
    runtime.audit_service.record(
        actor=actor,
        action="terminology_release.publish",
        target_type="terminology_release",
        target_id=f"{record.id}@{record.version}",
        trace_id=trace_id,
        reason=record.release_note,
        details={
            "scope": record.scope.model_dump(),
            "translation_term_set": record.translation_term_set.model_dump(),
            "term_rule_set": record.term_rule_set.model_dump(),
            "validation_summary": record.validation_report.summary.model_dump(),
        },
    )
    return _build_release_response(record)


@router.post("/{release_id}/rollback", response_model=TerminologyReleaseResponse)
def rollback_terminology_release(
    release_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    actor: ActorContext = Depends(require_admin_actor),
) -> TerminologyReleaseResponse:
    """Rollback the latest active terminology governance release version."""

    record = runtime.terminology_release_service.rollback(release_id, actor_id=actor.actor_id)
    runtime.audit_service.record(
        actor=actor,
        action="terminology_release.rollback",
        target_type="terminology_release",
        target_id=f"{record.id}@{record.version}",
        trace_id=trace_id,
        details={"scope": record.scope.model_dump()},
    )
    return _build_release_response(record)


@router.post("/{release_id}/copy", response_model=TerminologyReleaseCopyResponse)
def copy_terminology_release(
    release_id: str,
    version: str | None = None,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_current_user),
) -> TerminologyReleaseCopyResponse:
    """Return a create request prefilled from an existing release."""

    source = runtime.terminology_release_service.get_release(release_id, version)
    return TerminologyReleaseCopyResponse(
        source=_build_release_response(source),
        draft=runtime.terminology_release_service.copy_request(release_id, version),
    )


def _build_release_response(record: TerminologyReleaseRecord) -> TerminologyReleaseResponse:
    return TerminologyReleaseResponse(
        id=record.id,
        version=record.version,
        status=record.status,
        scope=_build_scope_response(record.scope),
        translation_term_set=_build_asset_response(record.translation_term_set),
        term_rule_set=_build_asset_response(record.term_rule_set),
        validation_report=_build_validation_report_response(record.validation_report),
        release_note=record.release_note,
        source_release_id=record.source_release_id,
        source_release_version=record.source_release_version,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        published_at=record.published_at,
        rolled_back_by=record.rolled_back_by,
        rolled_back_at=record.rolled_back_at,
    )


def _build_scope_response(scope: TerminologyReleaseScope) -> TerminologyReleaseScopeResponse:
    return TerminologyReleaseScopeResponse(
        project=scope.project,
        language_pair=scope.language_pair,
        content_type=scope.content_type,
    )


def _build_asset_response(asset: TerminologyReleaseAssetRef) -> TerminologyReleaseAssetResponse:
    return TerminologyReleaseAssetResponse(
        resource_id=asset.resource_id,
        version=asset.version,
        snapshot_hash=asset.snapshot_hash,
        item_count=asset.item_count,
    )


def _build_validation_report_response(
    report: TerminologyGovernanceValidationReport,
) -> TerminologyReleaseValidationReportResponse:
    return TerminologyReleaseValidationReportResponse(
        valid=report.valid,
        blocking=report.blocking,
        summary=TerminologyReleaseValidationSummaryResponse(**report.summary.model_dump()),
        errors=[_build_finding_response(item) for item in report.errors],
        warnings=[_build_finding_response(item) for item in report.warnings],
        conflicts=[_build_finding_response(item) for item in report.conflicts],
    )


def _build_finding_response(finding: TerminologyGovernanceFinding) -> TerminologyReleaseFindingResponse:
    return TerminologyReleaseFindingResponse(
        severity=finding.severity,
        code=finding.code,
        message=finding.message,
        path=finding.path,
        metadata=finding.metadata,
    )
