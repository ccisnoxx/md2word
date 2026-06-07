# File: app/infrastructure/persistence/sqlite/cleanup_locks.py
# Purpose: Persist file-retention cleanup locks for the sqlite metadata backend.

from __future__ import annotations

import sqlite3

from app.domains.files.cleanup_lock import FileRetentionCleanupLockRecord
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteRetentionCleanupLockRepository:
    """用 sqlite backend 读写 cleanup lock metadata。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def save_lock(self, record: FileRetentionCleanupLockRecord) -> FileRetentionCleanupLockRecord:
        """创建或替换 cleanup lock 记录。"""

        with self.backend.connect() as connection:
            self._upsert_lock(connection, record)
        return record

    def get_lock(self, lock_name: str) -> FileRetentionCleanupLockRecord | None:
        """按 lock_name 读取 cleanup lock。"""

        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM file_retention_cleanup_locks WHERE lock_name = ?",
                (lock_name,),
            ).fetchone()
        if row is None:
            return None
        return FileRetentionCleanupLockRecord.model_validate_json(row["payload"])

    def _upsert_lock(self, connection: sqlite3.Connection, record: FileRetentionCleanupLockRecord) -> None:
        """写入 cleanup lock JSON payload。"""

        connection.execute(
            """
            INSERT INTO file_retention_cleanup_locks
                (lock_name, status, owner_id, fencing_token, expires_at, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lock_name) DO UPDATE SET
                status = excluded.status,
                owner_id = excluded.owner_id,
                fencing_token = excluded.fencing_token,
                expires_at = excluded.expires_at,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                record.lock_name,
                record.status,
                record.owner_id,
                record.fencing_token,
                record.expires_at.isoformat(),
                self.backend.dump_payload(record),
                record.heartbeat_at.isoformat(),
            ),
        )
