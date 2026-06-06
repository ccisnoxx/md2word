# File: app/api/v1/routers/health.py
# Purpose: Expose health, metrics, and Admin-only read-only operations alert APIs.

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime, require_admin_user
from app.api.v1.routers.health_schemas import (
    HealthLiveResponse,
    HealthMetricsResponse,
    HealthOpsAlertsResponse,
    HealthReadyResponse,
)
from app.core.runtime import AppRuntime
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthLiveResponse)
def get_health_live(runtime: AppRuntime = Depends(get_runtime)) -> HealthLiveResponse:
    return HealthLiveResponse(status="ok", app_name=runtime.settings.app_name)


@router.get("/ready", response_model=HealthReadyResponse)
def get_health_ready(runtime: AppRuntime = Depends(get_runtime)) -> HealthReadyResponse:
    return runtime.health_service.build_ready_response()


@router.get("/metrics", response_model=HealthMetricsResponse)
def get_health_metrics(runtime: AppRuntime = Depends(get_runtime)) -> HealthMetricsResponse:
    return runtime.health_service.build_metrics_response()


@router.get("/ops-alerts", response_model=HealthOpsAlertsResponse)
def get_health_ops_alerts(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> HealthOpsAlertsResponse:
    """返回 Admin-only 只读运维告警 readiness，不执行恢复动作。"""

    return runtime.health_service.build_ops_alerts_response()


@router.get("", response_model=HealthReadyResponse)
def get_health_ready_compat(runtime: AppRuntime = Depends(get_runtime)) -> HealthReadyResponse:
    return runtime.health_service.build_ready_response()
