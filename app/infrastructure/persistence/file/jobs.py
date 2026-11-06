from __future__ import annotations

# app/infrastructure/persistence/file/jobs.py: file backend的任务事件仓储。

from app.domains.jobs.models import JobEvent
from app.infrastructure.persistence.file.backend import FilePersistenceBackend


class FileJobEventRepository:
    """用 file backend 追加和读取 JobEvent JSONL。"""

    def __init__(self, backend: FilePersistenceBackend) -> None:
        self.backend = backend

    def append_event(self, job_id: str, event: JobEvent) -> None:
        self.backend.append_json_line(
            self.backend.job_paths(job_id).events_jsonl,
            event.model_dump_json(),
        )

    def list_events(self, job_id: str) -> list[JobEvent]:
        path = self.backend.job_paths(job_id).events_jsonl
        return [JobEvent.model_validate_json(line) for line in self.backend.read_json_lines(path)]
