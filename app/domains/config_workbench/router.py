from __future__ import annotations

# File: app/domains/config_workbench/router.py
# Purpose: 提供配置工作台只读总览 API。

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime, require_admin_actor
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.config_workbench.schemas import ConfigWorkbenchSummaryResponse
from app.domains.config_workbench.summary import build_config_workbench_summary


router = APIRouter(prefix="/config-workbench", tags=["config-workbench"])


@router.get("/summary", response_model=ConfigWorkbenchSummaryResponse)
def get_config_workbench_summary(
    _actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
) -> ConfigWorkbenchSummaryResponse:
    return build_config_workbench_summary(runtime)

