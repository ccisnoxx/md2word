from __future__ import annotations

# app/infrastructure/persistence/sqlite/files.py: sqlite backend 的 job files 和 document files adapter。

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.domains.jobs.models import JobFile
from app.domains.files.models import DocumentFileRecord
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend
from app.domains.files.result_registration import expired_file, materialized_file, patched_file


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
    """在同一文件序列化点维护候选身份、物化和不可逆生命周期。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    @contextmanager
    def _locked_file(self, file_id: str) -> Iterator[tuple[Any, DocumentFileRecord | None]]:
        with self.backend.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM document_files WHERE file_id = ?", (file_id,)).fetchone()
            yield connection, DocumentFileRecord.model_validate_json(row["payload"]) if row is not None else None

    def _write_file(self, connection: Any, record: DocumentFileRecord, *, create: bool = False) -> None:
        if create:
            query = "INSERT INTO document_files (file_id, payload, created_at, updated_at) VALUES (?, ?, ?, ?)"
            params = (record.id, self.backend.dump_payload(record), record.created_at.isoformat(), record.updated_at.isoformat())
        else:
            query = "UPDATE document_files SET payload = ?, created_at = ?, updated_at = ? WHERE file_id = ?"
            params = (self.backend.dump_payload(record), record.created_at.isoformat(), record.updated_at.isoformat(), record.id)
        connection.execute(query, params)

    def create_document_file(self, record: DocumentFileRecord) -> DocumentFileRecord:
        with self._locked_file(record.id) as (connection, existing):
            if existing is not None:
                if existing != record:
                    raise ValueError("文件 ID 已存在，不能覆盖生命周期或证据。")
                return existing
            self._write_file(connection, record, create=True)
            return record

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
        with self._locked_file(file_id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            updated = patched_file(existing, patch)
            self._write_file(connection, updated)
            return updated

    def materialize_prepared_result(self, descriptor: DocumentFileRecord) -> DocumentFileRecord:
        with self._locked_file(descriptor.id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"结果候选不存在: {descriptor.id}")
            updated = materialized_file(existing, descriptor)
            self._write_file(connection, updated)
            return updated

    def expire_document_file(self, file_id: str, *, now: datetime) -> DocumentFileRecord:
        with self._locked_file(file_id) as (connection, existing):
            if existing is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            updated = expired_file(existing, now=now)
            self._write_file(connection, updated)
            return updated
