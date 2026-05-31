from __future__ import annotations

# app/domains/audit/repository.py: 定义 audit domain 依赖的持久化端口。

from typing import Protocol

from app.domains.audit.models import AuditEvent


class AuditEventRepositoryProtocol(Protocol):
    """跨资源审计事件读写合同。"""

    def append_audit_event(self, event: AuditEvent) -> None: ...
    def list_audit_events(self) -> list[AuditEvent]: ...
