# File: app/infrastructure/persistence/mysql/retention_policies.py
# Purpose: Persist document_files retention policies for the MySQL metadata backend.

from __future__ import annotations

from typing import Any

from app.domains.files.retention_policy import FileRetentionPolicyRecord
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlRetentionPolicyRepository:
    """用 MySQL backend 读写 document_files retention policy metadata。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def create_policy(self, record: FileRetentionPolicyRecord) -> FileRetentionPolicyRecord:
        """创建或替换策略记录。"""

        with self.backend.connect() as connection:
            self._upsert_policy(connection, record)
        return record

    def get_policy(self, policy_id: str) -> FileRetentionPolicyRecord | None:
        """按 policy_id 读取策略记录。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM file_retention_policies WHERE policy_id = %s", (policy_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return FileRetentionPolicyRecord.model_validate_json(row["payload"])

    def list_policies(self) -> list[FileRetentionPolicyRecord]:
        """读取全部策略记录。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM file_retention_policies ORDER BY created_at, policy_id")
                rows = cursor.fetchall()
        return [FileRetentionPolicyRecord.model_validate_json(row["payload"]) for row in rows]

    def update_policy(self, policy_id: str, **patch: Any) -> FileRetentionPolicyRecord:
        """更新策略记录；不存在时抛出 FileNotFoundError。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM file_retention_policies WHERE policy_id = %s", (policy_id,))
                row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"保留策略不存在: {policy_id}")
            updated = FileRetentionPolicyRecord(
                **FileRetentionPolicyRecord.model_validate_json(row["payload"]).model_copy(update=patch).model_dump(
                    mode="python"
                )
            )
            self._upsert_policy(connection, updated)
        return updated

    def _upsert_policy(self, connection: Any, record: FileRetentionPolicyRecord) -> None:
        """写入策略 JSON payload。"""

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO file_retention_policies (policy_id, payload, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    payload = VALUES(payload),
                    created_at = VALUES(created_at),
                    updated_at = VALUES(updated_at)
                """,
                (
                    record.policy_id,
                    self.backend.dump_payload(record),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
