from __future__ import annotations

# app/infrastructure/persistence/mysql/document_jobs.py: MySQL backend 的 document_jobs adapter。

from typing import Any

from app.domains.document_jobs.models import DocumentJobEventRecord, DocumentJobRecord
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlDocumentJobRepository:
    """用 MySQL backend 读写 DocumentJobRecord 主记录。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def create_document_job(self, record: DocumentJobRecord) -> DocumentJobRecord:
        with self.backend.connect() as connection:
            self._upsert_document_job(connection, record)
        return record

    def _upsert_document_job(self, connection: Any, record: DocumentJobRecord) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_jobs (job_id, payload, created_at, updated_at)
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

    def get_document_job(self, job_id: str) -> DocumentJobRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return DocumentJobRecord.model_validate_json(row["payload"])

    def list_document_jobs(self) -> list[DocumentJobRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_jobs ORDER BY created_at, job_id")
                rows = cursor.fetchall()
        return [DocumentJobRecord.model_validate_json(row["payload"]) for row in rows]

    def update_document_job(self, job_id: str, **patch: Any) -> DocumentJobRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM document_jobs WHERE job_id = %s", (job_id,))
                row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            existing = DocumentJobRecord.model_validate_json(row["payload"])
            updated = DocumentJobRecord.model_validate(existing.model_copy(update=patch).model_dump(mode="python"))
            self._upsert_document_job(connection, updated)
        return updated


class MysqlDocumentJobEventRepository:
    """用 MySQL backend 追加和读取 document job 事件。

    当前 MySQL 存储沿用既有 `job_events` 表，保持历史 payload shape 不变。
    """

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def append_document_job_event(self, job_id: str, event: DocumentJobEventRecord) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO job_events (job_id, payload, created_at)
                    VALUES (%s, %s, %s)
                    """,
                    (job_id, self.backend.dump_payload(event), event.created_at.isoformat()),
                )

    def list_document_job_events(self, job_id: str) -> list[DocumentJobEventRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM job_events WHERE job_id = %s ORDER BY id",
                    (job_id,),
                )
                rows = cursor.fetchall()
        return [DocumentJobEventRecord.model_validate_json(row["payload"]) for row in rows]
