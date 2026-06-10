from __future__ import annotations

# File: app/domains/config_workbench/router.py
# Purpose: 提供配置工作台只读总览 API。

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_runtime, require_admin_actor
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.config_workbench.schemas import (
    ConfigWorkbenchGroup,
    ConfigWorkbenchGroupId,
    ConfigWorkbenchSummaryResponse,
)
from app.domains.config_workbench.summary import (
    build_config_workbench_group,
    build_config_workbench_summary,
)


router = APIRouter(prefix="/config-workbench", tags=["config-workbench"])


@router.get("/summary", response_model=ConfigWorkbenchSummaryResponse)
def get_config_workbench_summary(
    mode: Literal["overview", "full"] = Query(default="full"),
    _actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
) -> ConfigWorkbenchSummaryResponse:
    return build_config_workbench_summary(runtime, mode=mode)


@router.get("/groups/{group_id}", response_model=ConfigWorkbenchGroup)
def get_config_workbench_group(
    group_id: ConfigWorkbenchGroupId,
    mode: Literal["overview", "full"] = Query(default="full"),
    _actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
) -> ConfigWorkbenchGroup:
    try:
        return build_config_workbench_group(runtime, group_id, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="配置工作台分组不存在。") from exc
