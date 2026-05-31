from __future__ import annotations

# app/domains/audit/models.py: 定义最小 actor 上下文和跨资源审计事件记录。

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


ActorRole = Literal["admin", "operator", "jobs", "anonymous"]
ActorSource = Literal["admin_token", "jobs_token", "jwt", "open"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActorContext(BaseModel):
    """一次请求解析出的操作者上下文，不包含 token 原文。"""

    actor_id: str | None = None
    actor_role: ActorRole
    source: ActorSource


class AuditEvent(BaseModel):
    """跨资源审计事件，记录成功执行的高风险动作。"""

    audit_id: str
    actor_id: str | None = None
    actor_role: ActorRole
    action: str
    target_type: str
    target_id: str
    reason: str | None = None
    trace_id: str
    created_at: datetime = Field(default_factory=utc_now)
