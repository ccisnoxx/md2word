# File: app/domains/ops/schemas.py
# Purpose: Define Admin-only read-only recovery, integration, alert, provider, and S3 API contracts.

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


OpsRecoveryActionCategory = Literal[
    "recovery",
    "cancellation",
    "archive",
    "cleanup",
    "provider",
    "notification",
    "automation",
]
OpsRecoveryActionTargetType = Literal[
    "document_job",
    "provider_operation",
    "alert",
    "cleanup_run",
]
OpsAlertDeliveryChannel = Literal["local_outbox", "slack"]
OpsAlertDeliveryMode = Literal["dry_run", "fake_send", "real_send_preview", "real_send"]
OpsAlertDeliveryOutcome = Literal[
    "deliverable",
    "fake_delivered",
    "sent",
    "deduped",
    "blocked",
    "rate_limited",
    "skipped_not_active",
    "skipped_rate_limited",
    "failed",
    "timed_out",
]
OpsAlertDestinationChannel = Literal["slack", "email", "webhook"]
OpsAlertDestinationMode = Literal["config_dry_run"]
OpsAlertDestinationStatus = Literal[
    "config_valid",
    "dry_run_passed",
    "disabled",
    "missing_config",
    "blocked",
]
OpsProviderCancellationProvider = Literal["mineru"]
OpsProviderCancellationTargetType = Literal["document_job"]
OpsProviderCancellationMode = Literal["dry_run", "fake_cancel"]
OpsProviderCancellationOutcome = Literal["cancelable", "fake_canceled", "deduped", "ineligible", "failed"]
OpsIntegrationCapabilityId = Literal[
    "alert_delivery",
    "provider_cancellation",
    "s3_deletion",
    "cleanup_scheduler_execute",
    "quota_enforcement",
]
OpsIntegrationCapabilityStatus = Literal["blocked", "dry_run_only", "ready"]
OpsIntegrationOverallStatus = Literal["blocked", "partial", "ready"]


class OpsRecoveryActionRiskFlagsResponse(BaseModel):
    """描述动作执行时可能触达的副作用类别，preview 本身不会执行这些副作用。"""

    mutates_metadata: bool
    mutates_queue: bool
    calls_provider: bool
    sends_notification: bool
    deletes_data: bool


class OpsIntegrationCapabilityResponse(BaseModel):
    """返回单个真实集成能力的 enable、gate 和 readiness 状态。"""

    capability_id: OpsIntegrationCapabilityId
    label: str
    category: str
    status: OpsIntegrationCapabilityStatus
    real_execution_enabled: bool
    dry_run_only: bool
    kill_switch_active: bool
    configured: bool
    ready: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    required_gates: list[str] = Field(default_factory=list)
    safe_config: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class OpsIntegrationControlPlaneSafetyResponse(BaseModel):
    """声明 integration control plane 只读检查没有触发真实副作用。"""

    read_only: bool = True
    provider_calls_executed: bool = False
    external_delivery_executed: bool = False
    s3_delete_executed: bool = False
    cleanup_scheduler_executed: bool = False
    quota_enforcement_executed: bool = False
    cleanup_executed: bool = False
    delete_executed: bool = False
    conversion_workflow_executed: bool = False
    audit_events_written: bool = False
    secret_values_exposed: bool = False


class OpsIntegrationControlPlaneResponse(BaseModel):
    """返回真实集成控制面的只读状态汇总。"""

    generated_at: datetime
    action_mode: Literal["read_only"]
    overall_status: OpsIntegrationOverallStatus
    capabilities: list[OpsIntegrationCapabilityResponse]
    safety: OpsIntegrationControlPlaneSafetyResponse


class OpsRecoveryActionResponse(BaseModel):
    """单个恢复动作的稳定 registry 条目。"""

    action_id: str
    label: str
    category: OpsRecoveryActionCategory
    target_type: OpsRecoveryActionTargetType
    available: bool
    requires_admin: bool
    requires_reason: bool
    requires_confirmation: bool
    dry_run_supported: bool
    mutates_metadata: bool
    mutates_queue: bool
    calls_provider: bool
    sends_notification: bool
    deletes_data: bool
    audit_action: str | None
    known_gaps: list[str] = Field(default_factory=list)
    suggested_route: str | None = None


class OpsRecoveryActionSafetyResponse(BaseModel):
    """声明 registry/preview 响应生成过程中没有执行任何恢复或外部副作用。"""

    read_only: bool = True
    execution_performed: bool = False
    metadata_mutated: bool = False
    queue_mutated: bool = False
    provider_calls_executed: bool = False
    notification_delivery_executed: bool = False
    cleanup_executed: bool = False
    delete_executed: bool = False
    audit_events_written: bool = False


class OpsRecoveryActionRegistryResponse(BaseModel):
    """返回当前 Ops recovery action registry 和只读安全声明。"""

    generated_at: datetime
    actions: list[OpsRecoveryActionResponse]
    safety: OpsRecoveryActionSafetyResponse


class OpsRecoveryActionPreviewRequest(BaseModel):
    """请求预览一个动作对一个精确目标的适用性。"""

    action_id: str
    target_type: OpsRecoveryActionTargetType
    target_id: str


class OpsRecoveryActionExecuteRequest(OpsRecoveryActionPreviewRequest):
    """请求执行已纳入后端执行合同的恢复动作。"""

    reason: str = Field(min_length=1, max_length=1000)


class OpsRecoveryActionTargetPreviewResponse(BaseModel):
    """返回目标是否存在和可安全展示的目标摘要。"""

    target_type: OpsRecoveryActionTargetType
    target_id: str
    exists: bool
    status: str | None = None
    stage: str | None = None
    summary: dict[str, str | int | bool | None] = Field(default_factory=dict)


class OpsRecoveryActionPreviewResponse(BaseModel):
    """返回单个动作的只读 eligibility preview。"""

    generated_at: datetime
    action: OpsRecoveryActionResponse
    target: OpsRecoveryActionTargetPreviewResponse
    eligible: bool
    missing_gates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    risk_flags: OpsRecoveryActionRiskFlagsResponse
    audit_action: str | None = None
    safety: OpsRecoveryActionSafetyResponse


class OpsRecoveryActionExecuteResponse(BaseModel):
    """返回恢复动作执行结果和安全声明。"""

    generated_at: datetime
    action: OpsRecoveryActionResponse
    target: OpsRecoveryActionTargetPreviewResponse
    eligible: bool
    missing_gates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    executed: bool
    queued_task_id: str | None = None
    replayable_callback_messages: int = 0
    ignored_callback_messages: int = 0
    recovery_events_written: int = 0
    audit_events_written: int = 0
    risk_flags: OpsRecoveryActionRiskFlagsResponse
    audit_action: str | None = None
    safety: OpsRecoveryActionSafetyResponse


class OpsAlertDeliveryPreviewRequest(BaseModel):
    """请求预览精确 Ops alert codes 的 fake outbox delivery。"""

    alert_codes: list[str] = Field(default_factory=list)
    channel: OpsAlertDeliveryChannel = "local_outbox"
    dedupe_window_minutes: int = Field(default=60, ge=1, le=1440)


class OpsAlertDeliveryFakeSendRequest(OpsAlertDeliveryPreviewRequest):
    """请求执行本地 fake outbox delivery，不发送外部通知。"""

    reason: str
    confirmation: str


class OpsAlertDeliveryRealPreviewRequest(BaseModel):
    """请求预览 Phase 7 Slack webhook pilot gates，不解析 secret 或外发。"""

    alert_codes: list[str] = Field(default_factory=list)
    destination_ids: list[str] = Field(default_factory=list)
    dedupe_window_minutes: int = Field(default=60, ge=1, le=1440)


class OpsAlertDeliveryRealSendRequest(OpsAlertDeliveryRealPreviewRequest):
    """请求执行 Phase 7 Slack webhook pilot real-send。"""

    reason: str
    confirmation: str


class OpsAlertDeliverySafetyResponse(BaseModel):
    """声明 alert delivery 合同没有触发任何真实外部副作用。"""

    external_delivery_executed: bool = False
    provider_calls_executed: bool = False
    cleanup_executed: bool = False
    delete_executed: bool = False
    conversion_workflow_executed: bool = False
    audit_events_written: bool = False
    secret_values_exposed: bool = False


class OpsAlertDeliveryAdapterResultResponse(BaseModel):
    """返回 fake alert delivery adapter 与未来 real adapter 同形的结果证据。"""

    contract_version: str
    adapter_id: str
    adapter_mode: Literal["fake", "real"]
    channel: OpsAlertDeliveryChannel
    alert_code: str
    operation_id: str
    idempotency_key: str
    dedupe_key: str
    timeout_seconds: int
    outcome: OpsAlertDeliveryOutcome
    provider_request_id: str | None = None
    error_code: str | None = None
    retryable: bool = False
    provider_calls_executed: bool = False
    external_delivery_executed: bool = False
    payload_persisted: bool = False
    secret_values_exposed: bool = False


class OpsAlertDeliveryAdapterContractSafetyResponse(BaseModel):
    """声明 adapter contract 报告只读且不会触发真实通知或 secret 暴露。"""

    read_only: bool = True
    provider_calls_executed: bool = False
    external_delivery_executed: bool = False
    audit_events_written: bool = False
    cleanup_executed: bool = False
    delete_executed: bool = False
    conversion_workflow_executed: bool = False
    secret_values_exposed: bool = False


class OpsAlertDeliveryAdapterContractResponse(BaseModel):
    """返回真实 alert delivery adapter 合同和 fake parity 证据。"""

    generated_at: datetime
    action_mode: Literal["adapter_contract"]
    contract_version: str
    fake_adapter_id: str
    fake_adapter_mode: Literal["fake"]
    real_channels: list[OpsAlertDestinationChannel] = Field(default_factory=list)
    required_request_fields: list[str] = Field(default_factory=list)
    required_result_fields: list[str] = Field(default_factory=list)
    required_audit_fields: list[str] = Field(default_factory=list)
    required_safety_fields: list[str] = Field(default_factory=list)
    parity_checks: dict[str, bool] = Field(default_factory=dict)
    destination_count: int
    destination_channels: list[OpsAlertDestinationChannel] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    safety: OpsAlertDeliveryAdapterContractSafetyResponse


class OpsS3DeleteLocalStackProfileResponse(BaseModel):
    """返回未来 LocalStack S3 delete 合同测试需要保持的 harness 语义。"""

    harness: Literal["localstack"]
    endpoint_required: bool
    versioned_bucket_required: bool
    exact_bucket_key_required: bool
    version_id_supported: bool
    etag_precondition_supported: bool
    runtime_executed: bool
    provider_payload_persisted: bool
    secrets_required_for_contract_report: bool


class OpsS3DeleteAdapterContractSafetyResponse(BaseModel):
    """声明 S3 delete adapter contract 报告只读且没有触发删除或外部调用。"""

    read_only: bool = True
    provider_calls_executed: bool = False
    real_s3_delete_executed: bool = False
    localstack_calls_executed: bool = False
    cleanup_executed: bool = False
    scheduler_loop_executed: bool = False
    delete_executed: bool = False
    metadata_mutated: bool = False
    audit_events_written: bool = False
    conversion_workflow_executed: bool = False
    secret_values_exposed: bool = False


class OpsS3DeleteAdapterContractResponse(BaseModel):
    """返回 S3 delete adapter 合同、LocalStack profile 和 fake parity 证据。"""

    generated_at: datetime
    action_mode: Literal["adapter_contract"]
    contract_version: str
    fake_adapter_id: str
    fake_adapter_mode: Literal["fake"]
    fake_file_retention_contract_version: str
    localstack_profile: OpsS3DeleteLocalStackProfileResponse
    storage_config_summary: dict[str, str | bool] = Field(default_factory=dict)
    required_request_fields: list[str] = Field(default_factory=list)
    required_result_fields: list[str] = Field(default_factory=list)
    required_audit_fields: list[str] = Field(default_factory=list)
    required_safety_fields: list[str] = Field(default_factory=list)
    parity_checks: dict[str, bool] = Field(default_factory=dict)
    blocking_reasons: list[str] = Field(default_factory=list)
    safety: OpsS3DeleteAdapterContractSafetyResponse


class OpsAlertDeliveryItemResponse(BaseModel):
    """返回单个 alert code 的 delivery preview 或 fake-send 结果。"""

    alert_code: str
    destination_id: str | None = None
    target_label: str | None = None
    severity: str | None = None
    source: str | None = None
    title: str | None = None
    outcome: OpsAlertDeliveryOutcome
    dedupe_key: str | None = None
    idempotency_key: str | None = None
    missing_gates: list[str] = Field(default_factory=list)
    reason: str
    audit_event_written: bool = False
    adapter_result: OpsAlertDeliveryAdapterResultResponse | None = None


class OpsAlertDeliveryResponse(BaseModel):
    """返回 Ops alert fake delivery outbox 的批量结果。"""

    generated_at: datetime
    action_mode: OpsAlertDeliveryMode
    channel: OpsAlertDeliveryChannel
    confirmation_phrase: str
    dedupe_window_minutes: int
    requested_alert_codes: list[str] = Field(default_factory=list)
    requested_destination_ids: list[str] = Field(default_factory=list)
    delivery_id: str
    totals: dict[str, int] = Field(default_factory=dict)
    gate_snapshot: dict[str, str | int | bool | list[str] | None] = Field(default_factory=dict)
    rollback: dict[str, str | int | bool | None] = Field(default_factory=dict)
    items: list[OpsAlertDeliveryItemResponse] = Field(default_factory=list)
    safety: OpsAlertDeliverySafetyResponse


class OpsAlertDestinationDryRunRequest(BaseModel):
    """请求对 staged alert destinations 做只读配置 dry-run。"""

    alert_codes: list[str] = Field(default_factory=list)
    destination_ids: list[str] = Field(default_factory=list)


class OpsAlertDestinationSafetyResponse(BaseModel):
    """声明 alert destination dry-run 不触发通知或泄露 secret。"""

    read_only: bool = True
    external_delivery_executed: bool = False
    provider_calls_executed: bool = False
    cleanup_executed: bool = False
    delete_executed: bool = False
    conversion_workflow_executed: bool = False
    audit_events_written: bool = False
    secret_values_exposed: bool = False


class OpsAlertDestinationItemResponse(BaseModel):
    """返回单个 alert destination 的配置 dry-run 结果。"""

    destination_id: str
    channel: OpsAlertDestinationChannel
    enabled: bool
    secret_ref: str
    secret_ref_present: bool
    target_label: str
    allowlist: list[str] = Field(default_factory=list)
    rate_limit_per_hour: int
    dedupe_window_minutes: int
    status: OpsAlertDestinationStatus
    missing_gates: list[str] = Field(default_factory=list)
    matched_alert_codes: list[str] = Field(default_factory=list)
    blocked_alert_codes: list[str] = Field(default_factory=list)


class OpsAlertDestinationDryRunResponse(BaseModel):
    """返回 alert destination configuration dry-run 汇总。"""

    generated_at: datetime
    action_mode: OpsAlertDestinationMode
    requested_alert_codes: list[str] = Field(default_factory=list)
    requested_destination_ids: list[str] = Field(default_factory=list)
    configured_count: int
    selected_count: int
    config_errors: list[str] = Field(default_factory=list)
    destinations: list[OpsAlertDestinationItemResponse] = Field(default_factory=list)
    safety: OpsAlertDestinationSafetyResponse


class OpsProviderCancellationPreviewRequest(BaseModel):
    """请求预览一个精确目标的 provider fake cancellation eligibility。"""

    target_type: OpsProviderCancellationTargetType
    target_id: str
    provider: OpsProviderCancellationProvider = "mineru"
    dedupe_window_minutes: int = Field(default=60, ge=1, le=1440)


class OpsProviderCancellationFakeRequest(OpsProviderCancellationPreviewRequest):
    """请求执行 provider fake cancellation，不调用真实 provider。"""

    reason: str
    confirmation: str


class OpsProviderCancellationSemanticsSourceResponse(BaseModel):
    """返回 provider cancellation 语义核查的公开来源摘要。"""

    label: str
    url: str
    source_type: Literal["primary_docs"]
    finding: str


class OpsProviderCancellationSemanticsSafetyResponse(BaseModel):
    """声明 provider cancellation 语义核查不触发 provider 或本地副作用。"""

    read_only: bool = True
    real_provider_cancel_executed: bool = False
    provider_calls_executed: bool = False
    local_job_mutated: bool = False
    queue_mutated: bool = False
    cleanup_executed: bool = False
    delete_executed: bool = False
    conversion_workflow_executed: bool = False
    audit_events_written: bool = False
    secret_values_exposed: bool = False


class OpsProviderCancellationSemanticsResponse(BaseModel):
    """返回 MinerU provider cancellation 语义核查结论和阻断理由。"""

    generated_at: datetime
    action_mode: Literal["semantics_verification"]
    provider: OpsProviderCancellationProvider
    verification_status: str
    checked_on: str
    decision: str
    public_docs_support_real_cancel: bool
    real_provider_cancel_allowed: bool
    supported_provider_operations: list[str] = Field(default_factory=list)
    documented_task_statuses: list[str] = Field(default_factory=list)
    unsupported_operations: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    sources: list[OpsProviderCancellationSemanticsSourceResponse] = Field(default_factory=list)
    safety: OpsProviderCancellationSemanticsSafetyResponse


class OpsProviderCancellationTargetResponse(BaseModel):
    """返回 provider cancellation 精确目标的安全摘要。"""

    target_type: OpsProviderCancellationTargetType
    target_id: str
    exists: bool
    status: str | None = None
    stage: str | None = None
    summary: dict[str, str | int | bool | None] = Field(default_factory=dict)


class OpsProviderOperationResponse(BaseModel):
    """返回可安全展示的 provider operation 摘要。"""

    provider: OpsProviderCancellationProvider
    operation_id: str | None = None
    data_id: str | None = None
    operation_type: str = "batch_extract"


class OpsProviderCancellationSafetyResponse(BaseModel):
    """声明 provider cancellation fake contract 没有真实外部副作用。"""

    real_provider_cancel_executed: bool = False
    provider_calls_executed: bool = False
    local_job_mutated: bool = False
    queue_mutated: bool = False
    cleanup_executed: bool = False
    delete_executed: bool = False
    conversion_workflow_executed: bool = False
    audit_events_written: bool = False


class OpsProviderCancellationResponse(BaseModel):
    """返回 provider cancellation preview 或 fake execution 结果。"""

    generated_at: datetime
    action_mode: OpsProviderCancellationMode
    provider: OpsProviderCancellationProvider
    confirmation_phrase: str
    dedupe_window_minutes: int
    target: OpsProviderCancellationTargetResponse
    provider_operation: OpsProviderOperationResponse
    eligible: bool
    missing_gates: list[str] = Field(default_factory=list)
    outcome: OpsProviderCancellationOutcome
    dedupe_key: str | None = None
    audit_event_written: bool = False
    safety: OpsProviderCancellationSafetyResponse
