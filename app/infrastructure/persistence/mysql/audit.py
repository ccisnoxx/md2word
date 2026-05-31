from __future__ import annotations

# app/infrastructure/persistence/mysql/audit.py: MySQL backend 的审计事件 adapter。

from app.domains.audit.models import AuditEvent
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlAuditEventRepository:
    """用 MySQL backend 追加和读取跨资源 AuditEvent。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def append_audit_event(self, event: AuditEvent) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO audit_events (audit_id, payload, created_at)
                    VALUES (%s, %s, %s)
                    """,
                    (event.audit_id, self.backend.dump_payload(event), event.created_at.isoformat()),
                )

    def list_audit_events(self) -> list[AuditEvent]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM audit_events ORDER BY created_at, id")
                rows = cursor.fetchall()
        return [AuditEvent.model_validate_json(row["payload"]) for row in rows]
