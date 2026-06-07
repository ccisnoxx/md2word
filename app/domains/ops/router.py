# File: app/domains/ops/router.py
# Purpose: Expose Admin-only operations governance APIs and structured safety audit evidence.

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext, AuditDetails
from app.domains.ops.alert_destinations import OpsAlertDestinationDryRunReport, OpsAlertDestinationDryRunService
from app.domains.ops.alert_delivery import OpsAlertDeliveryReport, OpsAlertDeliveryService
from app.domains.ops.provider_cancellation import (
    OpsProviderCancellationReport,
    OpsProviderCancellationService,
)
from app.domains.ops.recovery_actions import OpsRecoveryActionService
from app.domains.ops.schemas import (
    OpsAlertDestinationDryRunRequest,
    OpsAlertDestinationDryRunResponse,
    OpsAlertDestinationSafetyResponse,
    OpsAlertDeliveryFakeSendRequest,
    OpsAlertDeliveryPreviewRequest,
    OpsAlertDeliveryResponse,
    OpsAlertDeliverySafetyResponse,
    OpsProviderCancellationFakeRequest,
    OpsProviderCancellationPreviewRequest,
    OpsProviderCancellationResponse,
    OpsProviderCancellationSafetyResponse,
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


@router.post("/alert-destinations/dry-run", response_model=OpsAlertDestinationDryRunResponse)
def dry_run_ops_alert_destinations(
    payload: OpsAlertDestinationDryRunRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsAlertDestinationDryRunResponse:
    """只读 dry-run staged alert destination 配置，不发送通知或暴露 secret。"""

    report = _build_alert_destination_service(runtime).dry_run(
        alert_codes=payload.alert_codes,
        destination_ids=payload.destination_ids,
    )
    return _build_alert_destination_response(report)


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
            details=_build_alert_delivery_audit_details(
                report,
                audit_events_written=audit_written,
            ),
            trace_id=trace_id,
        )
    return _build_alert_delivery_response(report, audit_events_written=audit_written)


@router.post("/provider-cancellations/preview", response_model=OpsProviderCancellationResponse)
def preview_ops_provider_cancellation(
    payload: OpsProviderCancellationPreviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsProviderCancellationResponse:
    """预览精确目标的 provider fake cancellation eligibility，不调用 provider。"""

    report = _build_provider_cancellation_service(runtime).preview(
        target_type=payload.target_type,
        target_id=payload.target_id,
        provider=payload.provider,
        dedupe_window_minutes=payload.dedupe_window_minutes,
    )
    return _build_provider_cancellation_response(report, audit_events_written=False)


@router.post("/provider-cancellations/fake-cancel", response_model=OpsProviderCancellationResponse)
def fake_cancel_ops_provider_cancellation(
    payload: OpsProviderCancellationFakeRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> OpsProviderCancellationResponse:
    """执行 provider fake cancellation，只写审计，不调用真实 provider。"""

    service = _build_provider_cancellation_service(runtime)
    report = service.fake_cancel(
        target_type=payload.target_type,
        target_id=payload.target_id,
        provider=payload.provider,
        reason=payload.reason,
        confirmation=payload.confirmation,
        dedupe_window_minutes=payload.dedupe_window_minutes,
    )
    if report.audit_event_written:
        runtime.audit_service.record(
            actor=_actor_from_user(user),
            action="ops.provider_cancellation_fake",
            target_type="provider_operation",
            target_id=f"{report.provider}:{report.target.target_type}:{report.target.target_id}",
            reason=service.audit_reason(human_reason=payload.reason, report=report),
            details=_build_provider_cancellation_audit_details(
                report,
                audit_events_written=report.audit_event_written,
            ),
            trace_id=trace_id,
        )
    return _build_provider_cancellation_response(
        report,
        audit_events_written=report.audit_event_written,
    )


def _build_recovery_action_service(runtime: AppRuntime) -> OpsRecoveryActionService:
    """按当前 runtime 构建只读 recovery action service。"""

    return OpsRecoveryActionService(
        document_job_repository=runtime.document_job_repository,
        job_repository=runtime.job_repository,
        document_job_max_retries=runtime.settings.p0_document_job_max_retries,
        mineru_api_token_configured=bool(runtime.settings.mineru_api_token),
    )


def _build_alert_destination_service(runtime: AppRuntime) -> OpsAlertDestinationDryRunService:
    """按当前 settings 和 active ops alerts 构建 destination dry-run service。"""

    ops_alerts = runtime.health_service.build_ops_alerts_response()
    return OpsAlertDestinationDryRunService(
        destinations_json=runtime.settings.ops_alert_destinations_json,
        current_alerts=ops_alerts.alerts,
    )


def _build_alert_delivery_service(runtime: AppRuntime) -> OpsAlertDeliveryService:
    """按当前 health 和 audit repository 构建 fake alert delivery service。"""

    ops_alerts = runtime.health_service.build_ops_alerts_response()
    return OpsAlertDeliveryService(
        current_alerts=ops_alerts.alerts,
        audit_event_repository=runtime.audit_event_repository,
    )


def _build_provider_cancellation_service(runtime: AppRuntime) -> OpsProviderCancellationService:
    """按当前 metadata repositories 构建 provider fake cancellation service。"""

    return OpsProviderCancellationService(
        document_job_repository=runtime.document_job_repository,
        job_repository=runtime.job_repository,
        audit_event_repository=runtime.audit_event_repository,
    )


def _build_alert_destination_response(
    report: OpsAlertDestinationDryRunReport,
) -> OpsAlertDestinationDryRunResponse:
    """把 alert destination dry-run report 映射为带安全声明的 API response。"""

    payload = report.to_dict()
    payload["safety"] = OpsAlertDestinationSafetyResponse()
    return OpsAlertDestinationDryRunResponse(**payload)


def _build_alert_delivery_response(
    report: OpsAlertDeliveryReport,
    *,
    audit_events_written: bool,
) -> OpsAlertDeliveryResponse:
    """把 alert delivery report 映射为带安全声明的 API response。"""

    payload = report.to_dict()
    payload["safety"] = OpsAlertDeliverySafetyResponse(audit_events_written=audit_events_written)
    return OpsAlertDeliveryResponse(**payload)


def _build_provider_cancellation_response(
    report: OpsProviderCancellationReport,
    *,
    audit_events_written: bool,
) -> OpsProviderCancellationResponse:
    """把 provider cancellation report 映射为带安全声明的 API response。"""

    payload = report.to_dict()
    payload["safety"] = OpsProviderCancellationSafetyResponse(audit_events_written=audit_events_written)
    return OpsProviderCancellationResponse(**payload)


def _build_alert_delivery_audit_details(
    report: OpsAlertDeliveryReport,
    *,
    audit_events_written: bool,
) -> AuditDetails:
    """生成 alert fake delivery 的结构化审计证据，不包含外部通知 payload。"""

    return {
        "delivery_id": report.delivery_id,
        "action_mode": report.action_mode,
        "channel": report.channel,
        "dedupe_window_minutes": report.dedupe_window_minutes,
        "requested_alert_codes": list(report.requested_alert_codes),
        "totals": dict(report.totals),
        "items": [
            {
                "alert_code": item.alert_code,
                "severity": item.severity,
                "source": item.source,
                "title": item.title,
                "outcome": item.outcome,
                "dedupe_key": item.dedupe_key,
                "audit_event_written": item.audit_event_written,
            }
            for item in report.items
        ],
        "safety": {
            "external_delivery_executed": False,
            "provider_calls_executed": False,
            "cleanup_executed": False,
            "delete_executed": False,
            "conversion_workflow_executed": False,
            "audit_events_written": audit_events_written,
        },
    }


def _build_provider_cancellation_audit_details(
    report: OpsProviderCancellationReport,
    *,
    audit_events_written: bool,
) -> AuditDetails:
    """生成带 adapter 证据的 provider fake cancellation 审计 details。"""

    return {
        "provider": report.provider,
        "target": report.target.to_dict(),
        "provider_operation": report.provider_operation.to_dict(),
        "provider_adapter": report.provider_adapter.to_dict() if report.provider_adapter else None,
        "eligible": report.eligible,
        "missing_gates": list(report.missing_gates),
        "outcome": report.outcome,
        "dedupe_key": report.dedupe_key,
        "dedupe_window_minutes": report.dedupe_window_minutes,
        "safety": {
            "real_provider_cancel_executed": False,
            "provider_calls_executed": False,
            "local_job_mutated": False,
            "queue_mutated": False,
            "cleanup_executed": False,
            "delete_executed": False,
            "conversion_workflow_executed": False,
            "audit_events_written": audit_events_written,
        },
    }


def _actor_from_user(user: AuthenticatedUser) -> ActorContext:
    """把 JWT 用户映射为审计 actor。"""

    return ActorContext(actor_id=user.id, actor_role=user.role, source="jwt")
