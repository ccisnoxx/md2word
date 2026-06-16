# File: app/domains/ops/router.py
# Purpose: Expose Admin-only operations governance APIs and structured safety audit evidence.

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user
from app.core.errors import ApiError
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext, AuditDetails
from app.domains.ops.alert_delivery_contract import (
    OpsAlertDeliveryAdapterContractReport,
    OpsAlertDeliveryAdapterContractService,
)
from app.domains.ops.alert_destinations import OpsAlertDestinationDryRunReport, OpsAlertDestinationDryRunService
from app.domains.ops.alert_delivery import OpsAlertDeliveryReport, OpsAlertDeliveryService
from app.domains.ops.integration_control import OpsIntegrationControlPlaneReport, OpsIntegrationControlPlaneService
from app.domains.ops.provider_cancellation import (
    OpsProviderCancellationReport,
    OpsProviderCancellationService,
)
from app.domains.ops.provider_cancellation_semantics import (
    OpsProviderCancellationSemanticsReport,
    OpsProviderCancellationSemanticsService,
)
from app.domains.ops.real_alert_delivery import (
    EnvironmentSecretResolver,
    OpsRealAlertDeliveryReport,
    OpsRealAlertDeliveryService,
    REAL_ALERT_DELIVERY_AUDIT_ACTION,
    SlackWebhookAlertDeliveryProvider,
)
from app.domains.ops.recovery_actions import OpsRecoveryActionService
from app.domains.ops.s3_delete_contract import (
    OpsS3DeleteAdapterContractReport,
    OpsS3DeleteAdapterContractService,
)
from app.domains.ops.schemas import (
    OpsAlertDestinationDryRunRequest,
    OpsAlertDestinationDryRunResponse,
    OpsAlertDestinationSafetyResponse,
    OpsAlertDeliveryAdapterContractResponse,
    OpsAlertDeliveryAdapterContractSafetyResponse,
    OpsAlertDeliveryFakeSendRequest,
    OpsAlertDeliveryPreviewRequest,
    OpsAlertDeliveryRealPreviewRequest,
    OpsAlertDeliveryRealSendRequest,
    OpsAlertDeliveryResponse,
    OpsAlertDeliverySafetyResponse,
    OpsIntegrationControlPlaneResponse,
    OpsIntegrationControlPlaneSafetyResponse,
    OpsProviderCancellationFakeRequest,
    OpsProviderCancellationPreviewRequest,
    OpsProviderCancellationResponse,
    OpsProviderCancellationSafetyResponse,
    OpsProviderCancellationSemanticsResponse,
    OpsProviderCancellationSemanticsSafetyResponse,
    OpsProviderCancellationSemanticsSourceResponse,
    OpsRecoveryActionExecuteRequest,
    OpsRecoveryActionExecuteResponse,
    OpsRecoveryActionPreviewRequest,
    OpsRecoveryActionPreviewResponse,
    OpsRecoveryActionRegistryResponse,
    OpsRecoveryActionSafetyResponse,
    OpsS3DeleteAdapterContractResponse,
    OpsS3DeleteAdapterContractSafetyResponse,
    OpsS3DeleteLocalStackProfileResponse,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/integration-capabilities", response_model=OpsIntegrationControlPlaneResponse)
def get_ops_integration_capabilities(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsIntegrationControlPlaneResponse:
    """读取真实集成控制面状态，不调用外部 provider 或执行任何动作。"""

    report = OpsIntegrationControlPlaneService(runtime.settings).build_report()
    return _build_integration_control_plane_response(report)


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


@router.post("/recovery-actions/execute", response_model=OpsRecoveryActionExecuteResponse)
def execute_ops_recovery_action(
    payload: OpsRecoveryActionExecuteRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> OpsRecoveryActionExecuteResponse:
    """执行已收口的 recovery action；MVP 仅支持 document_job.replay_execution。"""

    if payload.action_id != "document_job.replay_execution" or payload.target_type != "document_job":
        raise ApiError(status.HTTP_409_CONFLICT, "conflict", "当前 execute endpoint 仅支持 document_job.replay_execution。")
    service = _build_recovery_action_service(runtime)
    preview = service.preview_action(payload)
    if not preview.eligible:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "conflict",
            f"document_job replay 不满足执行条件: {', '.join(preview.missing_gates) or 'unknown'}",
        )
    result = runtime.document_job_recovery_service.execute_replay(
        payload.target_id,
        trace_id=trace_id,
        run_inline=False,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action=preview.audit_action or payload.action_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
        details=_build_recovery_action_execute_audit_details(result),
        trace_id=trace_id,
    )
    return OpsRecoveryActionExecuteResponse(
        generated_at=preview.generated_at,
        action=preview.action,
        target=preview.target,
        eligible=True,
        missing_gates=[],
        warnings=preview.warnings,
        executed=result.executed,
        queued_task_id=result.queued_task_id,
        replayable_callback_messages=result.replayable_callback_messages,
        ignored_callback_messages=result.ignored_callback_messages,
        recovery_events_written=result.recovery_events_written,
        audit_events_written=1,
        risk_flags=preview.risk_flags,
        audit_action=preview.audit_action,
        safety=OpsRecoveryActionSafetyResponse(
            read_only=False,
            execution_performed=True,
            metadata_mutated=result.recovery_events_written > 0 or result.ignored_callback_messages > 0,
            queue_mutated=result.queued_task_id is not None,
            provider_calls_executed=False,
            notification_delivery_executed=False,
            cleanup_executed=False,
            delete_executed=False,
            audit_events_written=True,
        ),
    )


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


@router.get("/alert-deliveries/adapter-contract", response_model=OpsAlertDeliveryAdapterContractResponse)
def get_ops_alert_delivery_adapter_contract(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsAlertDeliveryAdapterContractResponse:
    """读取真实 alert delivery adapter 合同和 fake parity，不发送通知。"""

    report = _build_alert_delivery_adapter_contract_service(runtime).build_report()
    return _build_alert_delivery_adapter_contract_response(report)


@router.post("/alert-deliveries/real-send/preview", response_model=OpsAlertDeliveryResponse)
def preview_ops_real_alert_delivery(
    payload: OpsAlertDeliveryRealPreviewRequest,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsAlertDeliveryResponse:
    """预览 Phase 7 Slack webhook pilot gates，不解析 secret 或发送通知。"""

    report = _build_real_alert_delivery_service(runtime).preview(
        alert_codes=payload.alert_codes,
        destination_ids=payload.destination_ids,
        dedupe_window_minutes=payload.dedupe_window_minutes,
    )
    return _build_alert_delivery_response(report, audit_events_written=False)


@router.get("/s3-deletions/adapter-contract", response_model=OpsS3DeleteAdapterContractResponse)
def get_ops_s3_delete_adapter_contract(
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsS3DeleteAdapterContractResponse:
    """读取 S3 delete LocalStack/fake parity 合同，不调用 S3 或执行删除。"""

    report = _build_s3_delete_adapter_contract_service(runtime).build_report()
    return _build_s3_delete_adapter_contract_response(report)


@router.post("/alert-deliveries/real-send", response_model=OpsAlertDeliveryResponse)
def real_send_ops_alert_delivery(
    payload: OpsAlertDeliveryRealSendRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_admin_user),
    trace_id: str = Depends(get_trace_id),
) -> OpsAlertDeliveryResponse:
    """执行 Phase 7 Slack webhook pilot；所有 gate 通过后才调用 provider。"""

    service = _build_real_alert_delivery_service(runtime)
    report = service.real_send(
        alert_codes=payload.alert_codes,
        destination_ids=payload.destination_ids,
        reason=payload.reason,
        confirmation=payload.confirmation,
        dedupe_window_minutes=payload.dedupe_window_minutes,
    )
    audit_written = report.totals.get("audit_events_written", 0) > 0
    if audit_written:
        runtime.audit_service.record(
            actor=_actor_from_user(user),
            action=REAL_ALERT_DELIVERY_AUDIT_ACTION,
            target_type="ops_alert_delivery",
            target_id=report.delivery_id,
            reason=service.audit_reason(human_reason=payload.reason, report=report),
            details=_build_real_alert_delivery_audit_details(
                report,
                audit_events_written=audit_written,
            ),
            trace_id=trace_id,
        )
    return _build_alert_delivery_response(report, audit_events_written=audit_written)


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


@router.get("/provider-cancellations/semantics-verification", response_model=OpsProviderCancellationSemanticsResponse)
def get_ops_provider_cancellation_semantics_verification(
    _runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> OpsProviderCancellationSemanticsResponse:
    """读取 MinerU provider cancellation 语义核查结论，不调用 provider。"""

    report = OpsProviderCancellationSemanticsService().build_report()
    return _build_provider_cancellation_semantics_response(report)


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
        document_job_max_retries=runtime.settings.p0_document_job_max_retries,
        document_job_recovery_service=runtime.document_job_recovery_service,
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


def _build_real_alert_delivery_service(runtime: AppRuntime) -> OpsRealAlertDeliveryService:
    """按当前 runtime 构建 Phase 7 Slack webhook pilot service。"""

    ops_alerts = runtime.health_service.build_ops_alerts_response()
    provider = runtime.alert_delivery_provider or SlackWebhookAlertDeliveryProvider()
    secret_resolver = runtime.secret_resolver or EnvironmentSecretResolver()
    return OpsRealAlertDeliveryService(
        settings=runtime.settings,
        destinations_json=runtime.settings.ops_alert_destinations_json,
        current_alerts=ops_alerts.alerts,
        audit_event_repository=runtime.audit_event_repository,
        provider=provider,
        secret_resolver=secret_resolver,
    )


def _build_alert_delivery_adapter_contract_service(runtime: AppRuntime) -> OpsAlertDeliveryAdapterContractService:
    """按当前 settings 构建只读 alert delivery adapter contract service。"""

    return OpsAlertDeliveryAdapterContractService(
        destinations_json=runtime.settings.ops_alert_destinations_json,
    )


def _build_s3_delete_adapter_contract_service(runtime: AppRuntime) -> OpsS3DeleteAdapterContractService:
    """按当前 settings 构建只读 S3 delete adapter contract service。"""

    return OpsS3DeleteAdapterContractService(runtime.settings)


def _build_provider_cancellation_service(runtime: AppRuntime) -> OpsProviderCancellationService:
    """按当前 metadata repositories 构建 provider fake cancellation service。"""

    return OpsProviderCancellationService(
        document_job_repository=runtime.document_job_repository,
        audit_event_repository=runtime.audit_event_repository,
    )


def _build_integration_control_plane_response(
    report: OpsIntegrationControlPlaneReport,
) -> OpsIntegrationControlPlaneResponse:
    """把 integration control plane report 映射为带安全声明的 API response。"""

    payload = report.to_dict()
    payload["safety"] = OpsIntegrationControlPlaneSafetyResponse(**payload["safety"])
    return OpsIntegrationControlPlaneResponse(**payload)


def _build_alert_destination_response(
    report: OpsAlertDestinationDryRunReport,
) -> OpsAlertDestinationDryRunResponse:
    """把 alert destination dry-run report 映射为带安全声明的 API response。"""

    payload = report.to_dict()
    payload["safety"] = OpsAlertDestinationSafetyResponse()
    return OpsAlertDestinationDryRunResponse(**payload)


def _build_alert_delivery_response(
    report: OpsAlertDeliveryReport | OpsRealAlertDeliveryReport,
    *,
    audit_events_written: bool,
) -> OpsAlertDeliveryResponse:
    """把 alert delivery report 映射为带安全声明的 API response。"""

    payload = report.to_dict()
    adapter_results = [
        item.get("adapter_result") or {}
        for item in payload.get("items", [])
        if isinstance(item, dict)
    ]
    payload["safety"] = OpsAlertDeliverySafetyResponse(
        audit_events_written=audit_events_written,
        provider_calls_executed=any(bool(item.get("provider_calls_executed")) for item in adapter_results),
        external_delivery_executed=any(bool(item.get("external_delivery_executed")) for item in adapter_results),
        secret_values_exposed=any(bool(item.get("secret_values_exposed")) for item in adapter_results),
    )
    return OpsAlertDeliveryResponse(**payload)


def _build_alert_delivery_adapter_contract_response(
    report: OpsAlertDeliveryAdapterContractReport,
) -> OpsAlertDeliveryAdapterContractResponse:
    """把 alert delivery adapter contract report 映射为 API response。"""

    payload = report.to_dict()
    payload["safety"] = OpsAlertDeliveryAdapterContractSafetyResponse(**payload["safety"])
    return OpsAlertDeliveryAdapterContractResponse(**payload)


def _build_s3_delete_adapter_contract_response(
    report: OpsS3DeleteAdapterContractReport,
) -> OpsS3DeleteAdapterContractResponse:
    """把 S3 delete adapter contract report 映射为 API response。"""

    payload = report.to_dict()
    payload["localstack_profile"] = OpsS3DeleteLocalStackProfileResponse(**payload["localstack_profile"])
    payload["safety"] = OpsS3DeleteAdapterContractSafetyResponse(**payload["safety"])
    return OpsS3DeleteAdapterContractResponse(**payload)


def _build_provider_cancellation_response(
    report: OpsProviderCancellationReport,
    *,
    audit_events_written: bool,
) -> OpsProviderCancellationResponse:
    """把 provider cancellation report 映射为带安全声明的 API response。"""

    payload = report.to_dict()
    payload["safety"] = OpsProviderCancellationSafetyResponse(audit_events_written=audit_events_written)
    return OpsProviderCancellationResponse(**payload)


def _build_recovery_action_execute_audit_details(result) -> AuditDetails:
    """生成 document_job replay execute 的 compact audit 证据，不包含 callback payload。"""

    callback_observation = result.preview.callback_observation
    return {
        "action_id": "document_job.replay_execution",
        "executed": result.executed,
        "queued_task_id": result.queued_task_id,
        "worker_backend": result.preview.worker_backend,
        "automatic_execution_enabled": result.preview.automatic_execution_enabled,
        "stale_job_detected": result.preview.stale_job_detected,
        "replayable_callback_messages": result.replayable_callback_messages,
        "ignored_callback_messages": result.ignored_callback_messages,
        "recovery_events_written": result.recovery_events_written,
        "callback_status_counts": dict(callback_observation.status_counts),
        "oldest_replayable_age_seconds": callback_observation.oldest_replayable_age_seconds,
        "safety": {
            "provider_calls_executed": False,
            "notification_delivery_executed": False,
            "cleanup_executed": False,
            "delete_executed": False,
            "audit_events_written": True,
        },
    }


def _build_provider_cancellation_semantics_response(
    report: OpsProviderCancellationSemanticsReport,
) -> OpsProviderCancellationSemanticsResponse:
    """把 provider cancellation 语义核查报告映射为 API response。"""

    payload = report.to_dict()
    payload["sources"] = [
        OpsProviderCancellationSemanticsSourceResponse(**source)
        for source in payload["sources"]
    ]
    payload["safety"] = OpsProviderCancellationSemanticsSafetyResponse(**payload["safety"])
    return OpsProviderCancellationSemanticsResponse(**payload)


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
                "adapter_result": item.adapter_result.to_dict() if item.adapter_result else None,
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


def _build_real_alert_delivery_audit_details(
    report: OpsRealAlertDeliveryReport,
    *,
    audit_events_written: bool,
) -> AuditDetails:
    """生成 Phase 7 real alert delivery 的结构化审计证据，不包含 secret 或 Slack 响应正文。"""

    item = report.items[0]
    adapter_result = item.adapter_result.to_dict()
    return {
        "delivery_id": report.delivery_id,
        "action_mode": report.action_mode,
        "channel": report.channel,
        "destination_id": item.destination_id,
        "target_label": item.target_label,
        "alert_code": item.alert_code,
        "outcome": item.outcome,
        "dedupe_key": item.dedupe_key,
        "idempotency_key": item.idempotency_key,
        "dedupe_window_minutes": report.dedupe_window_minutes,
        "missing_gates": list(item.missing_gates),
        "gate_snapshot": dict(report.gate_snapshot),
        "adapter_result": adapter_result,
        "rollback": dict(report.rollback),
        "safety": {
            "external_delivery_executed": bool(adapter_result["external_delivery_executed"]),
            "provider_calls_executed": bool(adapter_result["provider_calls_executed"]),
            "cleanup_executed": False,
            "delete_executed": False,
            "conversion_workflow_executed": False,
            "audit_events_written": audit_events_written,
            "secret_values_exposed": False,
            "payload_persisted": False,
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
