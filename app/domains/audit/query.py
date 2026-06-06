# File: app/domains/audit/query.py
# Purpose: Filter, sort, paginate, and encode persisted audit events for Admin queries and exports.
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO

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


@dataclass(frozen=True, slots=True)
class AuditEventExport:
    """保存一次受治理审计导出的 CSV 和计数信息。"""

    csv_text: str
    items: list[AuditEvent]
    matched_count: int
    exported_count: int
    max_rows: int
    truncated: bool
    columns: list[str]


AUDIT_EVENT_EXPORT_COLUMNS = [
    "created_at",
    "audit_id",
    "actor_role",
    "actor_id",
    "action",
    "target_type",
    "target_id",
    "reason",
    "trace_id",
]


class AuditEventQueryService:
    """基于现有 repository 合同提供审计事件只读查询能力。"""

    def __init__(self, repository: AuditEventRepositoryProtocol) -> None:
        self.repository = repository

    def list_events(self, query: AuditEventQuery) -> AuditEventPage:
        """按筛选条件读取审计事件，并返回稳定排序后的分页结果。"""

        events = self._filtered_sorted_events(query)
        total = len(events)
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        return AuditEventPage(
            items=events[start:end],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    def export_events(self, query: AuditEventQuery, *, max_rows: int) -> AuditEventExport:
        """按筛选条件生成受上限保护的 CSV 导出结果。"""

        events = self._filtered_sorted_events(query)
        exported_events = events[:max_rows]
        return AuditEventExport(
            csv_text=self._build_csv_text(exported_events),
            items=exported_events,
            matched_count=len(events),
            exported_count=len(exported_events),
            max_rows=max_rows,
            truncated=len(events) > max_rows,
            columns=list(AUDIT_EVENT_EXPORT_COLUMNS),
        )

    def _filtered_sorted_events(self, query: AuditEventQuery) -> list[AuditEvent]:
        """复用同一套筛选和排序逻辑，避免列表与导出行为分叉。"""

        events = [
            event
            for event in self.repository.list_audit_events()
            if self._matches_query(event, query)
        ]
        events.sort(
            key=lambda event: (self._comparable_datetime(event.created_at), event.audit_id),
            reverse=query.sort == "created_at_desc",
        )
        return events

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

    def _build_csv_text(self, events: list[AuditEvent]) -> str:
        """把审计事件编码为 CSV，交由 csv 模块处理逗号、引号和换行。"""

        output = StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(AUDIT_EVENT_EXPORT_COLUMNS)
        for event in events:
            writer.writerow(
                [
                    event.created_at.isoformat(),
                    event.audit_id,
                    event.actor_role,
                    event.actor_id or "",
                    event.action,
                    event.target_type,
                    event.target_id,
                    event.reason or "",
                    event.trace_id,
                ]
            )
        return output.getvalue()
