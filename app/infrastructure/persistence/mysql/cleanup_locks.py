# File: app/infrastructure/persistence/mysql/cleanup_locks.py
# Purpose: Persist file-retention cleanup locks for the MySQL metadata backend.

from __future__ import annotations

from typing import Any

from app.domains.files.cleanup_lock import FileRetentionCleanupLockRecord
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlRetentionCleanupLockRepository:
    """用 MySQL backend 读写 cleanup lock metadata。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def save_lock(self, record: FileRetentionCleanupLockRecord) -> FileRetentionCleanupLockRecord:
        """创建或替换 cleanup lock 记录。"""

        with self.backend.connect() as connection:
            self._upsert_lock(connection, record)
        return record

    def get_lock(self, lock_name: str) -> FileRetentionCleanupLockRecord | None:
        """按 lock_name 读取 cleanup lock。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM file_retention_cleanup_locks WHERE lock_name = %s", (lock_name,))
                row = cursor.fetchone()
        if row is None:
            return None
        return FileRetentionCleanupLockRecord.model_validate_json(row["payload"])

    def _upsert_lock(self, connection: Any, record: FileRetentionCleanupLockRecord) -> None:
        """写入 cleanup lock JSON payload。"""

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO file_retention_cleanup_locks
                    (lock_name, status, owner_id, fencing_token, expires_at, payload, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    owner_id = VALUES(owner_id),
                    fencing_token = VALUES(fencing_token),
                    expires_at = VALUES(expires_at),
                    payload = VALUES(payload),
                    updated_at = VALUES(updated_at)
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
