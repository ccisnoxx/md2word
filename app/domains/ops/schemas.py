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
