from __future__ import annotations

# app/infrastructure/persistence/sqlite/jobs.py: sqlite backend的任务事件仓储。

from app.domains.jobs.models import JobEvent
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteJobEventRepository:
    """用 sqlite backend 追加和读取 JobEvent。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def append_event(self, job_id: str, event: JobEvent) -> None:
        with self.backend.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_events (job_id, payload, created_at)
                VALUES (?, ?, ?)
                """,
                (job_id, self.backend.dump_payload(event), event.created_at.isoformat()),
            )

    def list_events(self, job_id: str) -> list[JobEvent]:
        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM job_events WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return [JobEvent.model_validate_json(row["payload"]) for row in rows]
