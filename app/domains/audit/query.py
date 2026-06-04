# File: app/domains/audit/query.py
# Purpose: Filter, sort, and paginate persisted audit events for read-only UI queries.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domains.audit.models import ActorRole, AuditEvent
from app.domains.audit.repository import AuditEventRepositoryProtocol
from app.domains.audit.schemas import AuditEventSort


@dataclass(frozen=True, slots=True)
class AuditEventQuery:
    """封装审计事件查询筛选、排序和分页参数。"""

    page: int = 1
    page_size: int = 50
    sort: AuditEventSort = "created_at_desc"
    actor_role: ActorRole | None = None
    action: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    actor_id: str | None = None
    q: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuditEventPage:
    """保存一次审计事件分页查询的结果。"""

    items: list[AuditEvent]
    page: int
    page_size: int
    total: int


class AuditEventQueryService:
    """基于现有 repository 合同提供审计事件只读查询能力。"""

    def __init__(self, repository: AuditEventRepositoryProtocol) -> None:
        self.repository = repository

    def list_events(self, query: AuditEventQuery) -> AuditEventPage:
        """按筛选条件读取审计事件，并返回稳定排序后的分页结果。"""

        events = [
            event
            for event in self.repository.list_audit_events()
            if self._matches_query(event, query)
        ]
        events.sort(
            key=lambda event: (self._comparable_datetime(event.created_at), event.audit_id),
            reverse=query.sort == "created_at_desc",
        )
        total = len(events)
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        return AuditEventPage(
            items=events[start:end],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    def _matches_query(self, event: AuditEvent, query: AuditEventQuery) -> bool:
        """判断单条审计事件是否满足所有查询条件。"""

        if query.actor_role is not None and event.actor_role != query.actor_role:
            return False
        if query.action is not None and event.action != query.action:
            return False
        if query.target_type is not None and event.target_type != query.target_type:
            return False
        if query.target_id is not None and event.target_id != query.target_id:
            return False
        if query.actor_id is not None and event.actor_id != query.actor_id:
            return False

        created_at = self._comparable_datetime(event.created_at)
        if query.created_from is not None and created_at < self._comparable_datetime(query.created_from):
            return False
        if query.created_to is not None and created_at > self._comparable_datetime(query.created_to):
            return False

        normalized_query = self._normalize_optional_text(query.q)
        if normalized_query is not None and normalized_query not in self._search_blob(event):
            return False
        return True

    def _search_blob(self, event: AuditEvent) -> str:
        """把稳定审计字段拼成大小写无关搜索文本。"""

        values = [
            event.audit_id,
            event.actor_id,
            event.actor_role,
            event.action,
            event.target_type,
            event.target_id,
            event.reason,
            event.trace_id,
        ]
        return "\n".join(value for value in values if value is not None).lower()

    def _normalize_optional_text(self, value: str | None) -> str | None:
        """清理可选文本筛选条件，空字符串视为未传。"""

        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    def _comparable_datetime(self, value: datetime) -> datetime:
        """把 naive datetime 视为 UTC，避免比较时区不一致时报错。"""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
