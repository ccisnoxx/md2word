from __future__ import annotations

# app/infrastructure/persistence/sqlite/files.py: sqlite backend 的 job files 和 document files adapter。

import sqlite3
from typing import Any

from app.domains.jobs.models import JobFile
from app.domains.files.models import DocumentFileRecord
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteJobFileRepository:
    """用 sqlite backend 读写 JobFile artifact metadata。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def upsert_file(self, job_id: str, file: JobFile) -> None:
        with self.backend.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_files (job_id, file_type, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id, file_type) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (job_id, file.file_type, self.backend.dump_payload(file), file.created_at.isoformat()),
            )

    def list_files(self, job_id: str) -> list[JobFile]:
        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM job_files WHERE job_id = ? ORDER BY created_at, file_type",
                (job_id,),
            ).fetchall()
        return [JobFile.model_validate_json(row["payload"]) for row in rows]


class SqliteDocumentFileRepository:
    """用 sqlite backend 读写 document_files metadata。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def create_document_file(self, record: DocumentFileRecord) -> DocumentFileRecord:
        with self.backend.connect() as connection:
            self._upsert_document_file(connection, record)
        return record

    def _upsert_document_file(self, connection: sqlite3.Connection, record: DocumentFileRecord) -> None:
        connection.execute(
            """
            INSERT INTO document_files (file_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
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

    def get_document_file(self, file_id: str) -> DocumentFileRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_files WHERE file_id = ?",
                (file_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentFileRecord.model_validate_json(row["payload"])

    def list_document_files(self) -> list[DocumentFileRecord]:
        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM document_files ORDER BY created_at, file_id"
            ).fetchall()
        return [DocumentFileRecord.model_validate_json(row["payload"]) for row in rows]

    def update_document_file(self, file_id: str, **patch: Any) -> DocumentFileRecord:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_files WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            updated = DocumentFileRecord.model_validate_json(row["payload"]).model_copy(update=patch)
            self._upsert_document_file(connection, updated)
        return updated
