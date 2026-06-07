# File: app/domains/audit/service.py
# Purpose: Generate and persist cross-resource audit events with optional structured evidence.
from __future__ import annotations

import math
from uuid import uuid4

from app.domains.audit.models import ActorContext, AuditDetails, AuditDetailsValue, AuditEvent
from app.domains.audit.repository import AuditEventRepositoryProtocol


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
        details: AuditDetails | None = None,
    ) -> AuditEvent:
        """记录一条审计事件，保留 human reason 并可附加安全结构化 details。"""

        normalized_reason = self._normalize_optional_text(reason)
        normalized_details = self._normalize_details(details)
        event = AuditEvent(
            audit_id=f"audit_{uuid4().hex[:12]}",
            actor_id=actor.actor_id,
            actor_role=actor.actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=normalized_reason,
            details=normalized_details,
            trace_id=trace_id,
        )
        self.repository.append_audit_event(event)
        return event

    def _normalize_optional_text(self, value: str | None) -> str | None:
        """清理可选文本，空白字符串统一为 None。"""

        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _normalize_details(self, details: AuditDetails | None) -> AuditDetails | None:
        """清理结构化 details，空对象统一为 None。"""

        if not details:
            return None
        normalized: AuditDetails = {}
        for key, value in details.items():
            normalized_key = key.strip()
            if not normalized_key:
                continue
            normalized[normalized_key] = self._normalize_detail_value(value)
        return normalized or None

    def _normalize_detail_value(self, value: AuditDetailsValue) -> AuditDetailsValue:
        """递归保留 JSON-safe details 值，避免任意对象静默写入审计。"""

        if value is None or isinstance(value, str | int | bool):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise TypeError("audit details float value must be finite")
            return value
        if isinstance(value, list):
            return [self._normalize_detail_value(item) for item in value]
        if isinstance(value, dict):
            normalized: dict[str, AuditDetailsValue] = {}
            for key, nested_value in value.items():
                normalized_key = str(key).strip()
                if normalized_key:
                    normalized[normalized_key] = self._normalize_detail_value(nested_value)
            return normalized
        raise TypeError(f"audit details value must be JSON-safe, got {type(value).__name__}")
