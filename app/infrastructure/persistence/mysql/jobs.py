from __future__ import annotations

# app/infrastructure/persistence/mysql/jobs.py: MySQL backend 的 job 主记录和事件 adapter。

from typing import Any

from app.domains.jobs.models import JobEvent, JobRecord, sync_source_pdf_compatibility_fields
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlJobSnapshotRepository:
    """用 MySQL backend 读写 JobRecord 主记录。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def create_job(self, job: JobRecord) -> None:
        storage_job = sync_source_pdf_compatibility_fields(job)
        with self.backend.connect() as connection:
            self._upsert_job(connection, storage_job)

    def _upsert_job(self, connection: Any, job: JobRecord) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO jobs (job_id, payload, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    payload = VALUES(payload),
                    created_at = VALUES(created_at),
                    updated_at = VALUES(updated_at)
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
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return JobRecord.model_validate_json(row["payload"])

    def list_jobs(self) -> list[JobRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs ORDER BY created_at, job_id")
                rows = cursor.fetchall()
        return [JobRecord.model_validate_json(row["payload"]) for row in rows]

    def update_job(self, job_id: str, **patch: Any) -> JobRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"任务不存在: {job_id}")
            existing = JobRecord.model_validate_json(row["payload"])
            updated = sync_source_pdf_compatibility_fields(existing.model_copy(update=patch))
            self._upsert_job(connection, updated)
        return updated


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
