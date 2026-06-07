# File: app/domains/audit/router.py
# Purpose: Expose Admin-only list and governed export APIs for persisted audit events.
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_runtime, get_trace_id, require_admin_user
from app.core.runtime import AppRuntime
from app.domains.audit.models import ActorContext, ActorRole, AuditEvent
from app.domains.audit.query import AuditEventQuery, AuditEventQueryService
from app.domains.audit.schemas import (
    AuditEventExportManifest,
    AuditEventExportResponse,
    AuditEventListResponse,
    AuditEventResponse,
    AuditEventSort,
)
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
        _build_audit_event_query(
            page=page,
            page_size=page_size,
            sort=sort,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            actor_id=actor_id,
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


@router.get("/export", response_model=AuditEventExportResponse)
def export_audit_events(
    sort: AuditEventSort = "created_at_desc",
    actor_role: ActorRole | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_id: str | None = None,
    q: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    max_rows: Annotated[int, Query(ge=1, le=10000)] = 1000,
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
    user: AuthenticatedUser = Depends(require_admin_user),
) -> AuditEventExportResponse:
    """导出当前筛选条件下的审计事件 CSV，并记录导出审计事件。"""

    query = _build_audit_event_query(
        page=1,
        page_size=max_rows,
        sort=sort,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        q=q,
        created_from=created_from,
        created_to=created_to,
    )
    export = AuditEventQueryService(runtime.audit_event_repository).export_events(
        query,
        max_rows=max_rows,
    )
    filter_summary = _build_export_filter_summary(
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        q=q,
        created_from=created_from,
        created_to=created_to,
    )
    audit_event = runtime.audit_service.record(
        actor=ActorContext(actor_id=user.id, actor_role="admin", source="jwt"),
        action="audit_events.export",
        target_type="audit_events",
        target_id="filtered_export",
        trace_id=trace_id,
        reason=(
            f"exported={export.exported_count} matched={export.matched_count} "
            f"truncated={str(export.truncated).lower()} max_rows={max_rows}"
        ),
        details={
            "matched_count": export.matched_count,
            "exported_count": export.exported_count,
            "max_rows": export.max_rows,
            "truncated": export.truncated,
            "sort": sort,
            "filters": filter_summary,
            "columns": export.columns,
        },
    )
    return AuditEventExportResponse(
        manifest=AuditEventExportManifest(
            exported_at=audit_event.created_at,
            requested_by=user.id,
            actor_role="admin",
            sort=sort,
            filters=filter_summary,
            matched_count=export.matched_count,
            exported_count=export.exported_count,
            max_rows=export.max_rows,
            truncated=export.truncated,
            columns=export.columns,
            audit_id=audit_event.audit_id,
        ),
        csv_text=export.csv_text,
    )


def _build_audit_event_response(event: AuditEvent) -> AuditEventResponse:
    """把领域审计事件映射为 API 响应模型。"""

    return AuditEventResponse(**event.model_dump(mode="python"))


def _build_audit_event_query(
    *,
    page: int,
    page_size: int,
    sort: AuditEventSort,
    actor_role: ActorRole | None,
    action: str | None,
    target_type: str | None,
    target_id: str | None,
    actor_id: str | None,
    q: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
) -> AuditEventQuery:
    """统一构建列表与导出使用的查询对象。"""

    return AuditEventQuery(
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


def _build_export_filter_summary(
    *,
    actor_role: ActorRole | None,
    action: str | None,
    target_type: str | None,
    target_id: str | None,
    actor_id: str | None,
    q: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
) -> dict[str, str]:
    """生成导出清单中的筛选摘要，只保留实际生效的筛选字段。"""

    filters: dict[str, str] = {}
    if actor_role is not None:
        filters["actor_role"] = actor_role
    for key, value in (
        ("action", action),
        ("target_type", target_type),
        ("target_id", target_id),
        ("actor_id", actor_id),
        ("q", q),
    ):
        normalized = _normalize_optional_text(value)
        if normalized is not None:
            filters[key] = normalized
    if created_from is not None:
        filters["created_from"] = created_from.isoformat()
    if created_to is not None:
        filters["created_to"] = created_to.isoformat()
    return filters


def _normalize_optional_text(value: str | None) -> str | None:
    """清理精确匹配筛选字段，空字符串视为未传。"""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
