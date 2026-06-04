# File: app/domains/audit/schemas.py
# Purpose: Define audit event list API schemas for the Admin audit viewer.
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domains.audit.models import ActorRole


AuditEventSort = Literal["created_at_desc", "created_at_asc"]


class AuditEventResponse(BaseModel):
    """返回单条审计事件的只读元数据。"""

    audit_id: str
    actor_id: str | None = None
    actor_role: ActorRole
    action: str
    target_type: str
    target_id: str
    reason: str | None = None
    trace_id: str
    created_at: datetime


class AuditEventListResponse(BaseModel):
    """返回审计事件分页列表。"""

    items: list[AuditEventResponse] = Field(default_factory=list)
    page: int
    page_size: int
    total: int
