from __future__ import annotations

# app/infrastructure/persistence/file/audit.py: file backend 的审计事件 adapter。

from app.domains.audit.models import AuditEvent
from app.domains.document_jobs.new_generation import decode_generation_requests
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileAuditEventRepository:
    """用 file backend 追加和读取跨资源 AuditEvent JSONL。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def append_audit_event(self, event: AuditEvent) -> None:
        self.backend.append_json_line(self.backend.audit_events_jsonl, event.model_dump_json())

    def list_audit_events(self) -> list[AuditEvent]:
        events = [AuditEvent.model_validate_json(line)
                  for line in self.backend.read_json_lines(self.backend.audit_events_jsonl)]
        events.extend(record.audit for record in self.backend.list_publication_records())
        for path in sorted(self.backend.document_jobs_dir.glob("*/job.json")):
            entries = decode_generation_requests(self.backend.read_json(path, {}))
            events.extend(entry.audit for entry in entries.values())
        # 成功事件内嵌于提交点；历史 JSONL 的同 ID 副本仅保留一次。
        unique = {event.audit_id: event for event in events}
        return sorted(unique.values(), key=lambda event: (event.created_at, event.audit_id))
