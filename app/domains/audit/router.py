# File: app/domains/audit/router.py
# Purpose: Expose Admin-only read APIs for persisted audit events.
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_runtime, require_admin_user
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorRole, AuditEvent
from app.domains.audit.query import AuditEventQuery, AuditEventQueryService
from app.domains.audit.schemas import AuditEventListResponse, AuditEventResponse, AuditEventSort
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=AuditEventListResponse)
def list_audit_events(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    sort: AuditEventSort = "created_at_desc",
    actor_role: ActorRole | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_id: str | None = None,
    q: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    runtime: AppRuntime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_admin_user),
) -> AuditEventListResponse:
    """返回 Admin-only 审计事件分页列表，不写入新的审计事件。"""

    service = AuditEventQueryService(runtime.audit_event_repository)
    page_result = service.list_events(
        AuditEventQuery(
            page=page,
            page_size=page_size,
            sort=sort,
            actor_role=actor_role,
            action=_normalize_optional_text(action),
            target_type=_normalize_optional_text(target_type),
            target_id=_normalize_optional_text(target_id),
            actor_id=_normalize_optional_text(actor_id),
            q=q,
            created_from=created_from,
            created_to=created_to,
        )
    )
    return AuditEventListResponse(
        items=[_build_audit_event_response(event) for event in page_result.items],
        page=page_result.page,
        page_size=page_result.page_size,
        total=page_result.total,
    )


def _build_audit_event_response(event: AuditEvent) -> AuditEventResponse:
    """把领域审计事件映射为 API 响应模型。"""

    return AuditEventResponse(**event.model_dump(mode="python"))


def _normalize_optional_text(value: str | None) -> str | None:
    """清理精确匹配筛选字段，空字符串视为未传。"""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
