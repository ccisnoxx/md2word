from __future__ import annotations

# app/api/v1/routers/health.py: 暴露后端 live/ready 健康检查接口。

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime
from app.core.runtime import AppRuntime
from app.schemas.health import HealthLiveResponse, HealthMetricsResponse, HealthReadyResponse


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


@router.get("", response_model=HealthReadyResponse)
def get_health_ready_compat(runtime: AppRuntime = Depends(get_runtime)) -> HealthReadyResponse:
    return runtime.health_service.build_ready_response()
