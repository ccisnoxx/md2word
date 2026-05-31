from __future__ import annotations

# app/infrastructure/persistence/file/audit.py: file backend 的审计事件 adapter。

from app.domains.audit.models import AuditEvent
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileAuditEventRepository:
    """用 file backend 追加和读取跨资源 AuditEvent JSONL。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def append_audit_event(self, event: AuditEvent) -> None:
        self.backend.append_json_line(self.backend.audit_events_jsonl, event.model_dump_json())

    def list_audit_events(self) -> list[AuditEvent]:
        return [
            AuditEvent.model_validate_json(line)
            for line in self.backend.read_json_lines(self.backend.audit_events_jsonl)
        ]
