# File: app/domains/ops/router.py
# Purpose: Expose Admin-only read-only operations recovery action governance APIs.

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime, require_admin_user
from app.core.runtime import AppRuntime
from app.domains.ops.recovery_actions import OpsRecoveryActionService
from app.domains.ops.schemas import (
    OpsRecoveryActionPreviewRequest,
    OpsRecoveryActionPreviewResponse,
    OpsRecoveryActionRegistryResponse,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/ops/recovery-actions", tags=["ops"])


@router.get("", response_model=OpsRecoveryActionRegistryResponse)
def list_ops_recovery_actions(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsRecoveryActionRegistryResponse:
    """列出 Admin-only 只读 recovery action registry，不执行任何动作。"""

    return _build_service(runtime).list_registry()


@router.post("/preview", response_model=OpsRecoveryActionPreviewResponse)
def preview_ops_recovery_action(
    payload: OpsRecoveryActionPreviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsRecoveryActionPreviewResponse:
    """预览一个恢复动作对精确目标的适用性，不调度、不通知、不删除。"""

    return _build_service(runtime).preview_action(payload)


def _build_service(runtime: AppRuntime) -> OpsRecoveryActionService:
    """按当前 runtime 构建只读 recovery action service。"""

    return OpsRecoveryActionService(
        document_job_repository=runtime.document_job_repository,
        job_repository=runtime.job_repository,
        document_job_max_retries=runtime.settings.p0_document_job_max_retries,
        mineru_api_token_configured=bool(runtime.settings.mineru_api_token),
    )
