from __future__ import annotations

# app/infrastructure/persistence/sqlite/jobs.py: sqlite backend 的 job 主记录和事件 adapter。

import sqlite3
from typing import Any

from app.domains.jobs.models import JobEvent, JobRecord, sync_source_pdf_compatibility_fields
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteJobSnapshotRepository:
    """用 sqlite backend 读写 JobRecord 主记录。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def create_job(self, job: JobRecord) -> None:
        storage_job = sync_source_pdf_compatibility_fields(job)
        with self.backend.connect() as connection:
            self._upsert_job(connection, storage_job)

    def _upsert_job(self, connection: sqlite3.Connection, job: JobRecord) -> None:
        connection.execute(
            """
            INSERT INTO jobs (job_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                job.id,
                self.backend.dump_payload(job),
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
            ),
        )

    def get_job(self, job_id: str) -> JobRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return JobRecord.model_validate_json(row["payload"])

    def list_jobs(self) -> list[JobRecord]:
        with self.backend.connect() as connection:
            rows = connection.execute("SELECT payload FROM jobs ORDER BY created_at, job_id").fetchall()
        return [JobRecord.model_validate_json(row["payload"]) for row in rows]

    def update_job(self, job_id: str, **patch: Any) -> JobRecord:
        with self.backend.connect() as connection:
            row = connection.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(f"任务不存在: {job_id}")
            existing = JobRecord.model_validate_json(row["payload"])
            updated = sync_source_pdf_compatibility_fields(existing.model_copy(update=patch))
            self._upsert_job(connection, updated)
        return updated


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
