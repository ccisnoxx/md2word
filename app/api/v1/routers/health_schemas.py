# File: app/api/v1/routers/health_schemas.py
# Purpose: Define v1 response models for health and read-only operations alert APIs.

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthLiveResponse(BaseModel):
    status: str
    app_name: str


class HealthDeploymentInfo(BaseModel):
    """Non-sensitive deployment identity fields for release evidence."""

    environment: str
    public_deployment_mode: str
    version: str
    deployment_id: str | None = None
    started_at: datetime


class HealthReadyResponse(BaseModel):
    status: str
    app_name: str
    deployment: HealthDeploymentInfo
    jobs_dir: str
    dependency_checks: dict[str, Any]


class HealthMetricsResponse(BaseModel):
    status: str
    app_name: str
    generated_at: datetime
    deployment: HealthDeploymentInfo
    metadata_store: str
    artifact_storage: str
    worker_mode: str
    stage_dispatcher: str
    jobs: dict[str, int]
    document_jobs: dict[str, int] = Field(default_factory=dict)
    stage_messages: dict[str, int]
    document_job_callback_messages: dict[str, int] = Field(default_factory=dict)
    resources: dict[str, int | str | None]
    audit_events: dict[str, int]


HealthOpsStatus = Literal["ok", "watch", "needs_attention"]
HealthOpsAlertSeverity = Literal["info", "warning", "critical"]
HealthOpsAlertSource = Literal["readiness", "stage_spool", "jobs", "document_job_callbacks"]


class HealthOpsAlertSummary(BaseModel):
    """汇总只读运维告警判断所需的关键计数。"""

    readiness_blockers: int
    readiness_warnings: int
    stage_failed_messages: int
    stage_stale_running_messages: int
    stage_replayable_messages: int
    callback_failed_messages: int
    callback_replayable_messages: int
    callback_oldest_replayable_age_seconds: int
    failed_jobs: int
    running_jobs: int
    worker_mode: str
    stage_dispatcher: str
    stage_message_store: str
    artifact_storage: str


class HealthOpsAlertItem(BaseModel):
    """描述一个只读运维告警和建议入口。"""

    code: str
    severity: HealthOpsAlertSeverity
    source: HealthOpsAlertSource
    title: str
    description: str
    count: int = Field(ge=0)
    suggested_route: str | None = None
    suggested_action: str


class HealthOpsAlertSafety(BaseModel):
    """声明 ops-alerts 查询没有执行写入、恢复或外部调用。"""

    read_only: bool = True
    writes_performed: bool = False
    recovery_actions_executed: bool = False
    provider_calls_executed: bool = False
    notification_delivery_executed: bool = False
    audit_events_written: bool = False


class HealthOpsAlertsResponse(BaseModel):
    """返回 Admin-only 运维告警 readiness 合同。"""

    status: HealthOpsStatus
    app_name: str
    generated_at: datetime
    summary: HealthOpsAlertSummary
    alerts: list[HealthOpsAlertItem] = Field(default_factory=list)
    safety: HealthOpsAlertSafety = Field(default_factory=HealthOpsAlertSafety)
