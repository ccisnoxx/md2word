from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import HealthLiveResponse, HealthReadyResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthLiveResponse)
def get_health_live(runtime: AppRuntime = Depends(get_runtime)) -> HealthLiveResponse:
    return HealthLiveResponse(status="ok", app_name=runtime.settings.app_name)


@router.get("/ready", response_model=HealthReadyResponse)
def get_health_ready(runtime: AppRuntime = Depends(get_runtime)) -> HealthReadyResponse:
    return runtime.health_service.build_ready_response()


@router.get("", response_model=HealthReadyResponse)
def get_health_ready_compat(runtime: AppRuntime = Depends(get_runtime)) -> HealthReadyResponse:
    return runtime.health_service.build_ready_response()
