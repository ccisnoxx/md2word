from __future__ import annotations

# app/domains/translation/sets_router.py: 提供 Translation Term Set CSV 导入导出接口。

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_actor
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.translation.schemas import (
    TranslationTermSetExportManifestResponse,
    TranslationTermSetExportResponse,
    TranslationTermSetImportDuplicateResponse,
    TranslationTermSetImportReportResponse,
    TranslationTermSetImportRequest,
    TranslationTermSetImportResponse,
    TranslationTermValidationFindingResponse,
    TranslationTermValidationReportResponse,
)
from app.domains.translation.term_set_version_service import TranslationTermSetVersionService


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
