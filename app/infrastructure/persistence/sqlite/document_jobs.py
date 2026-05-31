from __future__ import annotations

# app/infrastructure/persistence/sqlite/document_jobs.py: sqlite backend 的 document_jobs adapter。

import sqlite3
from typing import Any

from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteDocumentJobRepository:
    """用 sqlite backend 读写 DocumentJobRecord 主记录。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def create_document_job(self, record: DocumentJobRecord) -> DocumentJobRecord:
        with self.backend.connect() as connection:
            self._upsert_document_job(connection, record)
        return record

    def _upsert_document_job(self, connection: sqlite3.Connection, record: DocumentJobRecord) -> None:
        connection.execute(
            """
            INSERT INTO document_jobs (job_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                record.id,
                self.backend.dump_payload(record),
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )

    def get_document_job(self, job_id: str) -> DocumentJobRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentJobRecord.model_validate_json(row["payload"])

    def list_document_jobs(self) -> list[DocumentJobRecord]:
        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM document_jobs ORDER BY created_at, job_id"
            ).fetchall()
        return [DocumentJobRecord.model_validate_json(row["payload"]) for row in rows]

    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            existing = DocumentJobRecord.model_validate_json(row["payload"])
            updated = DocumentJobRecord.model_validate(existing.model_copy(update=patch).model_dump(mode="python"))
            self._upsert_document_job(connection, updated)
        return updated


class SqliteDocumentJobEventRepository:
    """用 sqlite backend 追加和读取 document job 事件。

    当前 sqlite 存储沿用既有 `job_events` 表，保持历史 payload shape 不变。
    """

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def append_document_job_event(self, job_id: str, event: DocumentJobEventRecord) -> None:
        with self.backend.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_events (job_id, payload, created_at)
                VALUES (?, ?, ?)
                """,
                (job_id, self.backend.dump_payload(event), event.created_at.isoformat()),
            )

    def list_document_job_events(self, job_id: str) -> list[DocumentJobEventRecord]:
        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM job_events WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return [DocumentJobEventRecord.model_validate_json(row["payload"]) for row in rows]
