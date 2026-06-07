# File: app/infrastructure/persistence/mysql/cleanup_runs.py
# Purpose: Persist file-retention cleanup run history for the MySQL metadata backend.

from __future__ import annotations

from typing import Any

from app.domains.files.cleanup_history import FileRetentionCleanupRunHistoryRecord
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlRetentionCleanupRunHistoryRepository:
    """用 MySQL backend 读写 cleanup run history metadata。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def save_run(self, record: FileRetentionCleanupRunHistoryRecord) -> FileRetentionCleanupRunHistoryRecord:
        """创建或替换 cleanup run history 记录。"""

        with self.backend.connect() as connection:
            self._upsert_run(connection, record)
        return record

    def get_run(self, run_id: str) -> FileRetentionCleanupRunHistoryRecord | None:
        """按 run_id 读取 cleanup run history。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM file_retention_cleanup_runs WHERE run_id = %s", (run_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return FileRetentionCleanupRunHistoryRecord.model_validate_json(row["payload"])

    def list_runs(self) -> list[FileRetentionCleanupRunHistoryRecord]:
        """读取全部 cleanup run history。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM file_retention_cleanup_runs ORDER BY updated_at DESC, run_id DESC")
                rows = cursor.fetchall()
        return [FileRetentionCleanupRunHistoryRecord.model_validate_json(row["payload"]) for row in rows]

    def _upsert_run(self, connection: Any, record: FileRetentionCleanupRunHistoryRecord) -> None:
        """写入 cleanup run history JSON payload。"""

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO file_retention_cleanup_runs (run_id, status, payload, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    payload = VALUES(payload),
                    created_at = VALUES(created_at),
                    updated_at = VALUES(updated_at)
                """,
                (
                    record.run_id,
                    record.status,
                    self.backend.dump_payload(record),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
