from __future__ import annotations

# app/api/v1/routers/translation_profiles.py: 提供 Translation Profile 草稿、发布、默认版本和回滚接口。

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_access, require_admin_actor
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.core.audit_models import ActorContext
from app.core.runtime import AppRuntime
from app.schemas.translation_profiles import (
    TranslationProfileDetailResponse,
    TranslationProfileDraftResponse,
    TranslationProfileDraftUpdateRequest,
    TranslationProfileListResponse,
    TranslationProfilePublishRequest,
    TranslationProfileRollbackRequest,
    TranslationProfileVersionResponse,
)


router = APIRouter(prefix="/translation-profiles", tags=["translation-profiles"])


def _require_translation_profile_service(runtime: AppRuntime):
    service = runtime.translation_profile_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation Profile 版本发布需要 JOBS_REPOSITORY_BACKEND=mysql。",
        )
    return service


@router.get("", response_model=TranslationProfileListResponse)
def list_translation_profiles(
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationProfileListResponse:
    return _require_translation_profile_service(runtime).list_profiles()


@router.get("/{profile_id}", response_model=TranslationProfileDetailResponse)
def get_translation_profile(
    profile_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationProfileDetailResponse:
    try:
        return _require_translation_profile_service(runtime).get_profile_detail(profile_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{profile_id}/draft", response_model=TranslationProfileDraftResponse)
def get_translation_profile_draft(
    profile_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationProfileDraftResponse:
    try:
        return _require_translation_profile_service(runtime).get_draft(profile_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.put("/{profile_id}/draft", response_model=TranslationProfileDraftResponse, dependencies=[Depends(require_admin_access)])
def update_translation_profile_draft(
    profile_id: str,
    payload: TranslationProfileDraftUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
) -> TranslationProfileDraftResponse:
    try:
        return _require_translation_profile_service(runtime).update_draft(profile_id, payload)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{profile_id}/publish", response_model=TranslationProfileVersionResponse)
def publish_translation_profile_draft(
    profile_id: str,
    payload: TranslationProfilePublishRequest | None = None,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationProfileVersionResponse:
    request = payload or TranslationProfilePublishRequest()
    try:
        return _require_translation_profile_service(runtime).publish_draft(
            profile_id,
            make_default=request.make_default,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{profile_id}/versions/{version}/set-default", response_model=TranslationProfileVersionResponse)
def set_default_translation_profile_version(
    profile_id: str,
    version: str,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationProfileVersionResponse:
    try:
        return _require_translation_profile_service(runtime).set_default_version(
            profile_id,
            version,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{profile_id}/rollback", response_model=TranslationProfileVersionResponse)
def rollback_translation_profile_version(
    profile_id: str,
    payload: TranslationProfileRollbackRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TranslationProfileVersionResponse:
    try:
        return _require_translation_profile_service(runtime).rollback(
            profile_id,
            payload.version,
            actor=actor,
            trace_id=trace_id,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
