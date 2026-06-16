from __future__ import annotations

# File: app/domains/translation/sets_router.py
# Purpose: 提供 Translation Term Set CSV 导入导出、版本指针和治理预览接口。

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_actor
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.translation.schemas import (
    TranslationTermSetDetailResponse,
    TranslationTermSetDiffResponse,
    TranslationTermSetExportManifestResponse,
    TranslationTermSetExportResponse,
    TranslationTermSetDraftChangesApplyRequest,
    TranslationTermSetDraftResponse,
    TranslationTermSetImportDuplicateResponse,
    TranslationTermSetImportReportResponse,
    TranslationTermSetImportRequest,
    TranslationTermSetImportResponse,
    TranslationTermSetListResponse,
    TranslationTermSetPreflightResponse,
    TranslationTermProposalCompatibilityResponse,
    TranslationTermSetPublishRequest,
    TranslationTermSetRollbackRequest,
    TranslationTermSetVersionResponse,
    TranslationTermValidationFindingResponse,
    TranslationTermValidationReportResponse,
)
from app.domains.translation.term_set_version_service import (
    TranslationTermSetDraftSnapshotConflictError,
    TranslationTermSetVersionService,
)


router = APIRouter(prefix="/translation-term-sets", tags=["translation-term-sets"])


def _require_translation_term_set_version_service(runtime: AppRuntime) -> TranslationTermSetVersionService:
    service = runtime.translation_term_set_version_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation Term Set 版本导入导出需要 JOBS_REPOSITORY_BACKEND=mysql。",
        )
    return service


def _validation_response(report) -> TranslationTermValidationReportResponse:
    return TranslationTermValidationReportResponse(
        valid=report.valid,
        errors=[
            TranslationTermValidationFindingResponse(
                code=item.code,
                message=item.message,
                normalized_source_term=item.normalized_source_term,
            )
            for item in report.errors
        ],
        warnings=[
            TranslationTermValidationFindingResponse(
                code=item.code,
                message=item.message,
                normalized_source_term=item.normalized_source_term,
            )
            for item in report.warnings
        ],
    )


def _import_report_response(report) -> TranslationTermSetImportReportResponse:
    return TranslationTermSetImportReportResponse(
        dedupe=report.dedupe,
        total_rows=report.total_rows,
        imported_rows=report.imported_rows,
        duplicate_rows=report.duplicate_rows,
        duplicates=[
            TranslationTermSetImportDuplicateResponse(
                row_number=item.row_number,
                kept_row_number=item.kept_row_number,
                source_term=item.source_term,
                normalized_source_term=item.normalized_source_term,
            )
            for item in report.duplicates
        ],
    )


def _draft_snapshot_conflict_http_exception(exc: TranslationTermSetDraftSnapshotConflictError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "draft_snapshot_conflict",
            "message": str(exc),
            "expected_snapshot_hash": exc.expected_snapshot_hash,
            "actual_snapshot_hash": exc.actual_snapshot_hash,
        },
    )


@router.get("", response_model=TranslationTermSetListResponse)
def list_translation_term_sets(
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationTermSetListResponse:
    return _require_translation_term_set_version_service(runtime).list_sets()


@router.get("/{set_id}", response_model=TranslationTermSetDetailResponse)
def get_translation_term_set(
    set_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationTermSetDetailResponse:
    try:
        return _require_translation_term_set_version_service(runtime).get_set_detail(set_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/draft", response_model=TranslationTermSetDraftResponse)
def get_translation_term_set_draft(
    set_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationTermSetDraftResponse:
    try:
        return _require_translation_term_set_version_service(runtime).get_draft_response(set_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{set_id}/draft/changes", response_model=TranslationTermSetDraftResponse)
def apply_translation_term_set_draft_changes(
    set_id: str,
    payload: TranslationTermSetDraftChangesApplyRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermSetDraftResponse:
    try:
        return _require_translation_term_set_version_service(runtime).apply_draft_changes_response(
            set_id,
            expected_snapshot_hash=payload.expected_snapshot_hash,
            changes=payload.changes,
            reason=payload.reason,
            actor=actor,
            trace_id=trace_id,
        )
    except TranslationTermSetDraftSnapshotConflictError as exc:
        raise _draft_snapshot_conflict_http_exception(exc) from exc
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/diff", response_model=TranslationTermSetDiffResponse)
def get_translation_term_set_diff(
    set_id: str,
    base_version: str | None = Query(default=None),
    target_version: str | None = Query(default=None),
    _actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationTermSetDiffResponse:
    """返回 Translation Term Set 的 read-only 版本 diff，不修改 draft。"""

    try:
        return _require_translation_term_set_version_service(runtime).get_diff_response(
            set_id,
            base_version=base_version,
            target_version=target_version,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/preflight", response_model=TranslationTermSetPreflightResponse)
def get_translation_term_set_preflight(
    set_id: str,
    base_version: str | None = Query(default=None),
    target_version: str | None = Query(default=None),
    _actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationTermSetPreflightResponse:
    """返回 Translation Term Set 发布前 read-only 校验和 diff 摘要。"""

    try:
        return _require_translation_term_set_version_service(runtime).get_preflight_response(
            set_id,
            base_version=base_version,
            target_version=target_version,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{set_id}/proposal-compatibility", response_model=TranslationTermProposalCompatibilityResponse)
def get_translation_term_set_proposal_compatibility(
    set_id: str,
    proposal_status: str = Query(default="pending", alias="status"),
    _actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationTermProposalCompatibilityResponse:
    """预览 pending Translation Term Proposals 和当前 draft 的兼容性。"""

    try:
        return _require_translation_term_set_version_service(runtime).get_proposal_compatibility_response(
            set_id,
            status=proposal_status,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{set_id}/import", response_model=TranslationTermSetImportResponse)
def import_translation_term_set(
    set_id: str,
    payload: TranslationTermSetImportRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermSetImportResponse:
    try:
        result = _require_translation_term_set_version_service(runtime).import_csv_text(
            set_id,
            payload.csv_text,
            target=payload.target,
            dedupe=payload.dedupe,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return TranslationTermSetImportResponse(
        target=result.target,
        set_id=result.set_id,
        language_pair=result.language_pair,
        version=result.version,
        term_count=result.term_count,
        snapshot_hash=result.snapshot_hash,
        validation=_validation_response(result.validation),
        import_report=_import_report_response(result.import_report),
    )


@router.get("/{set_id}/export", response_model=TranslationTermSetExportResponse)
def export_translation_term_set(
    set_id: str,
    version: str | None = Query(default=None),
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermSetExportResponse:
    try:
        result = _require_translation_term_set_version_service(runtime).export_csv(
            set_id,
            version=version,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return TranslationTermSetExportResponse(
        manifest=TranslationTermSetExportManifestResponse(
            set_id=result.set_id,
            language_pair=result.language_pair,
            version=result.version,
            format="csv",
            exported_at=result.exported_at,
            exported_by=result.exported_by,
        ),
        csv_text=result.csv_text,
    )


@router.post("/{set_id}/publish", response_model=TranslationTermSetVersionResponse)
def publish_translation_term_set_draft(
    set_id: str,
    payload: TranslationTermSetPublishRequest | None = None,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermSetVersionResponse:
    request = payload or TranslationTermSetPublishRequest()
    try:
        return _require_translation_term_set_version_service(runtime).publish_draft_response(
            set_id,
            make_default=request.make_default,
            published_by=actor.actor_id,
            release_note=request.release_note,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{set_id}/versions/{version}/set-default", response_model=TranslationTermSetVersionResponse)
def set_default_translation_term_set_version(
    set_id: str,
    version: str,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermSetVersionResponse:
    try:
        return _require_translation_term_set_version_service(runtime).set_default_version_response(
            set_id,
            version,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{set_id}/rollback", response_model=TranslationTermSetVersionResponse)
def rollback_translation_term_set_version(
    set_id: str,
    payload: TranslationTermSetRollbackRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationTermSetVersionResponse:
    try:
        return _require_translation_term_set_version_service(runtime).rollback_response(
            set_id,
            payload.version,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
