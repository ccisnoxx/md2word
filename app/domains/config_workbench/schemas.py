from __future__ import annotations

# File: app/domains/config_workbench/schemas.py
# Purpose: 定义配置工作台总览 API 的只读响应模型。

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ConfigWorkbenchStatus = Literal["ready", "warning", "blocked", "unavailable"]
ConfigWorkbenchSeverity = Literal["info", "warning", "critical"]
ConfigWorkbenchGroupId = Literal[
    "runtime_readiness",
    "templates",
    "term_rule_sets",
    "translation_profiles",
    "translation_term_sets",
]


class ConfigWorkbenchFinding(BaseModel):
    code: str
    severity: ConfigWorkbenchSeverity
    message: str
    route: str | None = None
    target_id: str | None = None


class ConfigWorkbenchGroup(BaseModel):
    id: ConfigWorkbenchGroupId
    label: str
    status: ConfigWorkbenchStatus
    route: str
    default_label: str | None = None
    draft_count: int | None = None
    pending_count: int | None = None
    warning_count: int = 0
    blocker_count: int = 0
    findings: list[ConfigWorkbenchFinding] = Field(default_factory=list)


class ConfigWorkbenchReleaseGate(BaseModel):
    p0_document_jobs_required: bool = False
    p0_document_jobs_ready: bool = True
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConfigWorkbenchSummaryResponse(BaseModel):
    generated_at: datetime
    overall_status: ConfigWorkbenchStatus
    release_gate: ConfigWorkbenchReleaseGate
    groups: list[ConfigWorkbenchGroup] = Field(default_factory=list)

