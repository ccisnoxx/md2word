# File: app/infrastructure/persistence/sqlite/cleanup_runs.py
# Purpose: Persist file-retention cleanup run history for the sqlite metadata backend.

from __future__ import annotations

import sqlite3

from app.domains.files.cleanup_history import FileRetentionCleanupRunHistoryRecord
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteRetentionCleanupRunHistoryRepository:
    """用 sqlite backend 读写 cleanup run history metadata。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def save_run(self, record: FileRetentionCleanupRunHistoryRecord) -> FileRetentionCleanupRunHistoryRecord:
        """创建或替换 cleanup run history 记录。"""

        with self.backend.connect() as connection:
            self._upsert_run(connection, record)
        return record

    def get_run(self, run_id: str) -> FileRetentionCleanupRunHistoryRecord | None:
        """按 run_id 读取 cleanup run history。"""

        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM file_retention_cleanup_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return FileRetentionCleanupRunHistoryRecord.model_validate_json(row["payload"])

    def list_runs(self) -> list[FileRetentionCleanupRunHistoryRecord]:
        """读取全部 cleanup run history。"""

        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM file_retention_cleanup_runs ORDER BY updated_at DESC, run_id DESC"
            ).fetchall()
        return [FileRetentionCleanupRunHistoryRecord.model_validate_json(row["payload"]) for row in rows]

    def _upsert_run(self, connection: sqlite3.Connection, record: FileRetentionCleanupRunHistoryRecord) -> None:
        """写入 cleanup run history JSON payload。"""

        connection.execute(
            """
            INSERT INTO file_retention_cleanup_runs (run_id, status, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                status = excluded.status,
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                record.run_id,
                record.status,
                self.backend.dump_payload(record),
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
