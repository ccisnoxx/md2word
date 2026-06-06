# File: app/domains/ops/schemas.py
# Purpose: Define Admin-only read-only recovery action registry and preview API contracts.

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
    "legacy_job",
    "provider_operation",
    "alert",
    "cleanup_run",
]
OpsAlertDeliveryChannel = Literal["local_outbox"]
OpsAlertDeliveryMode = Literal["dry_run", "fake_send"]
OpsAlertDeliveryOutcome = Literal[
    "deliverable",
    "fake_delivered",
    "deduped",
    "skipped_not_active",
    "skipped_rate_limited",
    "failed",
]
OpsProviderCancellationProvider = Literal["mineru"]
OpsProviderCancellationTargetType = Literal["document_job", "legacy_job"]
OpsProviderCancellationMode = Literal["dry_run", "fake_cancel"]
OpsProviderCancellationOutcome = Literal["cancelable", "fake_canceled", "deduped", "ineligible", "failed"]


class OpsRecoveryActionRiskFlagsResponse(BaseModel):
    """描述动作执行时可能触达的副作用类别，preview 本身不会执行这些副作用。"""

    mutates_metadata: bool
    mutates_queue: bool
    calls_provider: bool
    sends_notification: bool
    deletes_data: bool


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


class OpsAlertDeliveryPreviewRequest(BaseModel):
    """请求预览精确 Ops alert codes 的 fake outbox delivery。"""

    alert_codes: list[str] = Field(default_factory=list)
    channel: OpsAlertDeliveryChannel = "local_outbox"
    dedupe_window_minutes: int = Field(default=60, ge=1, le=1440)


class OpsAlertDeliveryFakeSendRequest(OpsAlertDeliveryPreviewRequest):
    """请求执行本地 fake outbox delivery，不发送外部通知。"""

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


class OpsAlertDeliveryItemResponse(BaseModel):
    """返回单个 alert code 的 delivery preview 或 fake-send 结果。"""

    alert_code: str
    severity: str | None = None
    source: str | None = None
    title: str | None = None
    outcome: OpsAlertDeliveryOutcome
    dedupe_key: str | None = None
    reason: str
    audit_event_written: bool = False


class OpsAlertDeliveryResponse(BaseModel):
    """返回 Ops alert fake delivery outbox 的批量结果。"""

    generated_at: datetime
    action_mode: OpsAlertDeliveryMode
    channel: OpsAlertDeliveryChannel
    confirmation_phrase: str
    dedupe_window_minutes: int
    requested_alert_codes: list[str] = Field(default_factory=list)
    delivery_id: str
    totals: dict[str, int] = Field(default_factory=dict)
    items: list[OpsAlertDeliveryItemResponse] = Field(default_factory=list)
    safety: OpsAlertDeliverySafetyResponse


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
