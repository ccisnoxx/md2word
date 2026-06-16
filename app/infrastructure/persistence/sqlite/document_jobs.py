from __future__ import annotations

# app/infrastructure/persistence/sqlite/document_jobs.py: sqlite backend 的 document_jobs adapter。

import sqlite3
from typing import Any

from app.domains.document_jobs.models import DocumentJobCallbackMessage, DocumentJobEventRecord, DocumentJobRecord
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

    def update_document_job_if_current(
        self,
        job_id: str,
        *,
        allowed_statuses: set[str],
        allowed_stages: set[str],
        expected_retry_count: int | None = None,
        **patch: Any,
    ) -> DocumentJobRecord | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"文档任务不存在: {job_id}")
            existing = DocumentJobRecord.model_validate_json(row["payload"])
            if existing.status in {"succeeded", "failed", "canceled"}:
                return None
            if existing.status not in allowed_statuses or existing.stage not in allowed_stages:
                return None
            if expected_retry_count is not None and existing.retry_count != expected_retry_count:
                return None
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


class SqliteDocumentJobCallbackMessageStore:
    """用 sqlite backend 读写 document_jobs callback message。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def put_or_get_callback_message(
        self,
        message: DocumentJobCallbackMessage,
    ) -> tuple[DocumentJobCallbackMessage, bool]:
        with self.backend.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO document_job_callback_messages
                    (message_id, job_id, status, dedupe_key, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.job_id,
                    message.status,
                    message.dedupe_key,
                    self.backend.dump_payload(message),
                    message.created_at.isoformat(),
                    message.updated_at.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT payload FROM document_job_callback_messages WHERE dedupe_key = ?",
                (message.dedupe_key,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"document job callback message 不存在: {message.id}")
        stored = DocumentJobCallbackMessage.model_validate_json(row["payload"])
        return stored, stored.id == message.id

    def get_callback_message(self, message_id: str) -> DocumentJobCallbackMessage | None:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_job_callback_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentJobCallbackMessage.model_validate_json(row["payload"])

    def list_callback_messages(
        self,
        job_id: str | None = None,
        *,
        statuses: set[str] | None = None,
        limit: int | None = None,
    ) -> list[DocumentJobCallbackMessage]:
        query = "SELECT payload FROM document_job_callback_messages WHERE 1 = 1"
        params: list[str | int] = []
        if job_id is not None:
            query += " AND job_id = ?"
            params.append(job_id)
        if statuses is not None:
            ordered_statuses = sorted(statuses)
            placeholders = ", ".join("?" for _ in ordered_statuses)
            query += f" AND status IN ({placeholders})"
            params.extend(ordered_statuses)
        query += " ORDER BY created_at, message_id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self.backend.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [DocumentJobCallbackMessage.model_validate_json(row["payload"]) for row in rows]

    def list_replayable_callback_messages(self, job_id: str | None = None) -> list[DocumentJobCallbackMessage]:
        return self.list_callback_messages(job_id, statuses={"pending", "running"})

    def mark_callback_message_running(
        self,
        message_id: str,
        *,
        attempts: int,
        lease_owner: str | None,
        leased_at: Any,
        lease_expires_at: Any,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage | None:
        return self._update_if_replayable(
            message_id,
            status="running",
            attempts=attempts,
            lease_owner=lease_owner,
            leased_at=leased_at,
            lease_expires_at=lease_expires_at,
            error_code=None,
            error_message=None,
            updated_at=updated_at,
        )

    def mark_callback_message_processed(self, message_id: str, *, updated_at: Any) -> DocumentJobCallbackMessage:
        return self._update_message(message_id, status="processed", updated_at=updated_at)

    def mark_callback_message_failed(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage:
        return self._update_message(
            message_id,
            status="failed",
            error_code=error_code,
            error_message=error_message,
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            updated_at=updated_at,
        )

    def mark_callback_message_ignored(
        self,
        message_id: str,
        *,
        error_code: str,
        error_message: str,
        updated_at: Any,
    ) -> DocumentJobCallbackMessage:
        return self._update_message(
            message_id,
            status="ignored",
            error_code=error_code,
            error_message=error_message,
            lease_owner=None,
            leased_at=None,
            lease_expires_at=None,
            updated_at=updated_at,
        )

    def count_callback_messages_by_status(self, job_id: str | None = None) -> dict[str, int]:
        counts = {"pending": 0, "running": 0, "processed": 0, "failed": 0, "ignored": 0}
        query = "SELECT status, COUNT(*) AS count FROM document_job_callback_messages"
        params: tuple[str, ...] = ()
        if job_id is not None:
            query += " WHERE job_id = ?"
            params = (job_id,)
        query += " GROUP BY status"
        with self.backend.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        for row in rows:
            counts[row["status"]] = row["count"]
        return counts

    def _update_if_replayable(self, message_id: str, **patch: Any) -> DocumentJobCallbackMessage | None:
        message = self.get_callback_message(message_id)
        if message is None:
            raise FileNotFoundError(f"document job callback message 不存在: {message_id}")
        if message.status not in {"pending", "running"}:
            return None
        return self._update_message(message_id, **patch)

    def _update_message(self, message_id: str, **patch: Any) -> DocumentJobCallbackMessage:
        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM document_job_callback_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"document job callback message 不存在: {message_id}")
            updated = DocumentJobCallbackMessage.model_validate_json(row["payload"]).model_copy(update=patch)
            connection.execute(
                """
                UPDATE document_job_callback_messages
                SET job_id = ?, status = ?, dedupe_key = ?, payload = ?, created_at = ?, updated_at = ?
                WHERE message_id = ?
                """,
                (
                    updated.job_id,
                    updated.status,
                    updated.dedupe_key,
                    self.backend.dump_payload(updated),
                    updated.created_at.isoformat(),
                    updated.updated_at.isoformat(),
                    message_id,
                ),
            )
        return updated
