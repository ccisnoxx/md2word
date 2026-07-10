"""提供管理员专用的 MinerU 密钥读取与轮换接口。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user
from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.mineru.config import EffectiveMinerUConfig
from app.domains.mineru.schemas import MinerUConfigResponse, MinerUConfigUpdateRequest
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/mineru-config", tags=["mineru-config"])
logger = logging.getLogger("system")


@router.get("", response_model=MinerUConfigResponse)
def get_mineru_config(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> MinerUConfigResponse:
    """返回当前 MinerU 密钥状态，不返回密钥原文或片段。"""

    return _build_response(runtime.mineru_config_service.get_effective_config())


@router.put("", response_model=MinerUConfigResponse)
def update_mineru_config(
    payload: MinerUConfigUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> MinerUConfigResponse:
    """保存新密钥并记录不含密钥信息的审计事件。"""

    effective = runtime.mineru_config_service.update_api_token(
        api_token=payload.api_token,
        updated_by=user.id,
    )
    try:
        runtime.audit_service.record(
            actor=ActorContext(actor_id=user.id, actor_role=user.role, source="jwt"),
            action="mineru_config.update",
            target_type="mineru_config",
            target_id="default",
            details={"api_token_configured": True},
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.exception(
            "[trace_id=%s action=mineru_config.update] MinerU 密钥已保存，但审计记录失败",
            trace_id,
        )
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "service_unavailable",
            "MinerU 密钥已保存，但审计记录失败，请刷新页面确认配置状态。",
        ) from exc
    return _build_response(effective)


def _build_response(config: EffectiveMinerUConfig) -> MinerUConfigResponse:
    return MinerUConfigResponse(
        api_token_configured=config.api_token_configured,
        source=config.source,
        updated_at=config.updated_at,
        updated_by=config.updated_by,
    )
