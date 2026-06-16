from __future__ import annotations

# app/infrastructure/persistence/mysql/files.py: MySQL backend 的 job files 和 document files adapter。

from typing import Any

from app.domains.jobs.models import JobFile
from app.domains.files.models import DocumentFileRecord
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlJobFileRepository:
    """用 MySQL backend 读写 JobFile artifact metadata。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def upsert_file(self, job_id: str, file: JobFile) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO job_files (job_id, file_type, payload, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        payload = VALUES(payload),
                        created_at = VALUES(created_at)
                    """,
                    (job_id, file.file_type, self.backend.dump_payload(file), file.created_at.isoformat()),
                )

    def list_files(self, job_id: str) -> list[JobFile]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM job_files WHERE job_id = %s ORDER BY created_at, file_type",
                    (job_id,),
                )
                rows = cursor.fetchall()
        return [JobFile.model_validate_json(row["payload"]) for row in rows]


class MysqlDocumentFileRepository:
    """用 MySQL backend 读写 document_files metadata。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def create_document_file(self, record: DocumentFileRecord) -> DocumentFileRecord:
        with self.backend.connect() as connection:
            self._upsert_document_file(connection, record)
        return record

    def _upsert_document_file(self, connection: Any, record: DocumentFileRecord) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_files (file_id, payload, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    payload = VALUES(payload),
                    created_at = VALUES(created_at),
                    updated_at = VALUES(updated_at)
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
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_files WHERE file_id = %s", (file_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return DocumentFileRecord.model_validate_json(row["payload"])

    def list_document_files(self) -> list[DocumentFileRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_files ORDER BY created_at, file_id")
                rows = cursor.fetchall()
        return [DocumentFileRecord.model_validate_json(row["payload"]) for row in rows]

    def update_document_file(self, file_id: str, **patch: Any) -> DocumentFileRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_files WHERE file_id = %s", (file_id,))
                row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            updated = DocumentFileRecord.model_validate_json(row["payload"]).model_copy(update=patch)
            self._upsert_document_file(connection, updated)
        return updated
