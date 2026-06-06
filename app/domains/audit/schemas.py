# File: app/domains/audit/schemas.py
# Purpose: Define audit event list and export API schemas for the Admin audit viewer.
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


class AuditEventExportManifest(BaseModel):
    """返回一次审计导出的治理清单。"""

    exported_at: datetime
    requested_by: str | None = None
    actor_role: ActorRole
    sort: AuditEventSort
    filters: dict[str, str] = Field(default_factory=dict)
    matched_count: int
    exported_count: int
    max_rows: int
    truncated: bool
    columns: list[str] = Field(default_factory=list)
    audit_id: str


class AuditEventExportResponse(BaseModel):
    """返回审计导出 CSV 和清单，不在服务端创建临时文件。"""

    manifest: AuditEventExportManifest
    csv_text: str
