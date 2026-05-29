from __future__ import annotations

# app/services/audit.py: 统一生成并持久化跨资源审计事件。

from uuid import uuid4

from app.core.audit_models import ActorContext, AuditEvent
from app.repositories.protocols import AuditEventRepositoryProtocol


class AuditService:
    """记录已通过权限并成功执行的业务审计事件。"""

    def __init__(self, repository: AuditEventRepositoryProtocol) -> None:
        self.repository = repository

    def record(
        self,
        *,
        actor: ActorContext,
        action: str,
        target_type: str,
        target_id: str,
        trace_id: str,
        reason: str | None = None,
    ) -> AuditEvent:
        normalized_reason = self._normalize_optional_text(reason)
        event = AuditEvent(
            audit_id=f"audit_{uuid4().hex[:12]}",
            actor_id=actor.actor_id,
            actor_role=actor.actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=normalized_reason,
            trace_id=trace_id,
        )
        self.repository.append_audit_event(event)
        return event

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
