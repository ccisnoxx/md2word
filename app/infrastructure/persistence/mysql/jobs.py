from __future__ import annotations

# app/infrastructure/persistence/mysql/jobs.py: MySQL backend的任务事件仓储。

from app.domains.jobs.models import JobEvent
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlJobEventRepository:
    """用 MySQL backend 追加和读取 JobEvent。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def append_event(self, job_id: str, event: JobEvent) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO job_events (job_id, payload, created_at)
                    VALUES (%s, %s, %s)
                    """,
                    (job_id, self.backend.dump_payload(event), event.created_at.isoformat()),
                )

    def list_events(self, job_id: str) -> list[JobEvent]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM job_events WHERE job_id = %s ORDER BY id",
                    (job_id,),
                )
                rows = cursor.fetchall()
        return [JobEvent.model_validate_json(row["payload"]) for row in rows]
