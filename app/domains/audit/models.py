# File: app/domains/audit/models.py
# Purpose: Define actor context and structured cross-resource audit event records.
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field, JsonValue


ActorRole = Literal["admin", "operator", "jobs", "anonymous"]
ActorSource = Literal["admin_token", "jobs_token", "jwt", "open"]
AuditDetailsValue: TypeAlias = JsonValue
AuditDetails: TypeAlias = dict[str, JsonValue]


def utc_now() -> datetime:
    """返回 UTC 当前时间，作为审计事件默认时间源。"""

    return datetime.now(timezone.utc)


class ActorContext(BaseModel):
    """一次请求解析出的操作者上下文，不包含 token 原文。"""

    actor_id: str | None = None
    actor_role: ActorRole
    source: ActorSource


class AuditEvent(BaseModel):
    """跨资源审计事件，记录成功执行的高风险动作和可选结构化证据。"""

    audit_id: str
    actor_id: str | None = None
    actor_role: ActorRole
    action: str
    target_type: str
    target_id: str
    reason: str | None = None
    details: AuditDetails | None = None
    trace_id: str
    created_at: datetime = Field(default_factory=utc_now)
