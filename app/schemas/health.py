from __future__ import annotations

# app/schemas/health.py: 定义 health API 的 v1 响应模型。

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class HealthLiveResponse(BaseModel):
    status: str
    app_name: str


class HealthReadyResponse(BaseModel):
    status: str
    app_name: str
    jobs_dir: str
    dependency_checks: dict[str, Any]


class HealthMetricsResponse(BaseModel):
    status: str
    app_name: str
    generated_at: datetime
    metadata_store: str
    artifact_storage: str
    worker_mode: str
    stage_dispatcher: str
    jobs: dict[str, int]
    stage_messages: dict[str, int]
    resources: dict[str, int | str | None]
    audit_events: dict[str, int]
