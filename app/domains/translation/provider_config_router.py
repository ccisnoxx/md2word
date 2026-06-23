from __future__ import annotations

# File: app/domains/translation/provider_config_router.py
# Purpose: Expose admin-only AI provider runtime configuration endpoints.

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.translation.provider_config import EffectiveAiProviderConfig
from app.domains.translation.provider_config_schemas import (
    AiProviderConfigResponse,
    AiProviderConfigUpdateRequest,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/ai-provider-config", tags=["ai-provider-config"])


@router.get("", response_model=AiProviderConfigResponse)
def get_ai_provider_config(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> AiProviderConfigResponse:
    return _build_response(runtime.ai_provider_config_service.get_effective_config())


@router.put("", response_model=AiProviderConfigResponse)
def update_ai_provider_config(
    payload: AiProviderConfigUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> AiProviderConfigResponse:
    effective = runtime.ai_provider_config_service.update_config(
        backend=payload.backend,
        base_url=payload.base_url,
        model=payload.model,
        timeout_seconds=payload.timeout_seconds,
        max_output_tokens=payload.max_output_tokens,
        api_key=payload.api_key,
        clear_api_key=payload.clear_api_key,
        api_key_supplied="api_key" in payload.model_fields_set,
        updated_by=user.id,
    )
    runtime.audit_service.record(
        actor=ActorContext(actor_id=user.id, actor_role=user.role, source="jwt"),
        action="ai_provider_config.update",
        target_type="ai_provider_config",
        target_id="default",
        details={
            "backend": effective.backend,
            "api_key_configured": effective.api_key_configured,
            "model": effective.model,
        },
        trace_id=trace_id,
    )
    return _build_response(effective)


def _build_response(config: EffectiveAiProviderConfig) -> AiProviderConfigResponse:
    return AiProviderConfigResponse(
        backend=config.backend,
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        max_output_tokens=config.max_output_tokens,
        api_key_configured=config.api_key_configured,
        api_key_mask=_mask_api_key(config.api_key),
        source=config.source,
        updated_at=config.updated_at,
        updated_by=config.updated_by,
    )


def _mask_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"
