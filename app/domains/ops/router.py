# File: app/domains/ops/router.py
# Purpose: Expose Admin-only operations governance, alert delivery, and recovery action APIs.

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext
from app.domains.ops.alert_delivery import OpsAlertDeliveryReport, OpsAlertDeliveryService
from app.domains.ops.recovery_actions import OpsRecoveryActionService
from app.domains.ops.schemas import (
    OpsAlertDeliveryFakeSendRequest,
    OpsAlertDeliveryPreviewRequest,
    OpsAlertDeliveryResponse,
    OpsAlertDeliverySafetyResponse,
    OpsRecoveryActionPreviewRequest,
    OpsRecoveryActionPreviewResponse,
    OpsRecoveryActionRegistryResponse,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/recovery-actions", response_model=OpsRecoveryActionRegistryResponse)
def list_ops_recovery_actions(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsRecoveryActionRegistryResponse:
    """列出 Admin-only 只读 recovery action registry，不执行任何动作。"""

    return _build_recovery_action_service(runtime).list_registry()


@router.post("/recovery-actions/preview", response_model=OpsRecoveryActionPreviewResponse)
def preview_ops_recovery_action(
    payload: OpsRecoveryActionPreviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsRecoveryActionPreviewResponse:
    """预览一个恢复动作对精确目标的适用性，不调度、不通知、不删除。"""

    return _build_recovery_action_service(runtime).preview_action(payload)


@router.post("/alert-deliveries/preview", response_model=OpsAlertDeliveryResponse)
def preview_ops_alert_delivery(
    payload: OpsAlertDeliveryPreviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsAlertDeliveryResponse:
    """预览精确 Ops alert codes 的 fake outbox delivery，不写审计或外发通知。"""

    report = _build_alert_delivery_service(runtime).preview(
        alert_codes=payload.alert_codes,
        channel=payload.channel,
        dedupe_window_minutes=payload.dedupe_window_minutes,
    )
    return _build_alert_delivery_response(report, audit_events_written=False)


@router.post("/alert-deliveries/fake-send", response_model=OpsAlertDeliveryResponse)
def fake_send_ops_alert_delivery(
    payload: OpsAlertDeliveryFakeSendRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> OpsAlertDeliveryResponse:
    """执行本地 fake outbox delivery，只写 compact audit，不发送外部通知。"""

    service = _build_alert_delivery_service(runtime)
    report = service.fake_send(
        alert_codes=payload.alert_codes,
        channel=payload.channel,
        reason=payload.reason,
        confirmation=payload.confirmation,
        dedupe_window_minutes=payload.dedupe_window_minutes,
    )
    audit_written = report.totals.get("audit_events_written", 0) > 0
    if audit_written:
        runtime.audit_service.record(
            actor=_actor_from_user(user),
            action="ops.alert_delivery_fake",
            target_type="ops_alert_delivery",
            target_id=report.delivery_id,
            reason=service.audit_reason(human_reason=payload.reason, report=report),
            trace_id=trace_id,
        )
    return _build_alert_delivery_response(report, audit_events_written=audit_written)


def _build_recovery_action_service(runtime: AppRuntime) -> OpsRecoveryActionService:
    """按当前 runtime 构建只读 recovery action service。"""

    return OpsRecoveryActionService(
        document_job_repository=runtime.document_job_repository,
        job_repository=runtime.job_repository,
        document_job_max_retries=runtime.settings.p0_document_job_max_retries,
        mineru_api_token_configured=bool(runtime.settings.mineru_api_token),
    )


def _build_alert_delivery_service(runtime: AppRuntime) -> OpsAlertDeliveryService:
    """按当前 health 和 audit repository 构建 fake alert delivery service。"""

    ops_alerts = runtime.health_service.build_ops_alerts_response()
    return OpsAlertDeliveryService(
        current_alerts=ops_alerts.alerts,
        audit_event_repository=runtime.audit_event_repository,
    )


def _build_alert_delivery_response(
    report: OpsAlertDeliveryReport,
    *,
    audit_events_written: bool,
) -> OpsAlertDeliveryResponse:
    """把 alert delivery report 映射为带安全声明的 API response。"""

    payload = report.to_dict()
    payload["safety"] = OpsAlertDeliverySafetyResponse(audit_events_written=audit_events_written)
    return OpsAlertDeliveryResponse(**payload)


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    """把 JWT 用户映射为审计 actor。"""

    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")
