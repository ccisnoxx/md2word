# File: app/infrastructure/persistence/sqlite/retention_policies.py
# Purpose: Persist document_files retention policies for the sqlite metadata backend.

from __future__ import annotations

import sqlite3
from typing import Any

from app.domains.files.retention_policy import FileRetentionPolicyRecord
from app.infrastructure.persistence.sqlite.backend import SqlitePersistenceBackend


class SqliteRetentionPolicyRepository:
    """用 sqlite backend 读写 document_files retention policy metadata。"""

    def __init__(self, backend: SqlitePersistenceBackend) -> None:
        self.backend = backend

    def create_policy(self, record: FileRetentionPolicyRecord) -> FileRetentionPolicyRecord:
        """创建或替换策略记录。"""

        with self.backend.connect() as connection:
            self._upsert_policy(connection, record)
        return record

    def get_policy(self, policy_id: str) -> FileRetentionPolicyRecord | None:
        """按 policy_id 读取策略记录。"""

        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM file_retention_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
        if row is None:
            return None
        return FileRetentionPolicyRecord.model_validate_json(row["payload"])

    def list_policies(self) -> list[FileRetentionPolicyRecord]:
        """读取全部策略记录。"""

        with self.backend.connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM file_retention_policies ORDER BY created_at, policy_id"
            ).fetchall()
        return [FileRetentionPolicyRecord.model_validate_json(row["payload"]) for row in rows]

    def update_policy(self, policy_id: str, **patch: Any) -> FileRetentionPolicyRecord:
        """更新策略记录；不存在时抛出 FileNotFoundError。"""

        with self.backend.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM file_retention_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(f"保留策略不存在: {policy_id}")
            updated = FileRetentionPolicyRecord(
                **FileRetentionPolicyRecord.model_validate_json(row["payload"]).model_copy(update=patch).model_dump(
                    mode="python"
                )
            )
            self._upsert_policy(connection, updated)
        return updated

    def _upsert_policy(self, connection: sqlite3.Connection, record: FileRetentionPolicyRecord) -> None:
        """写入策略 JSON payload。"""

        connection.execute(
            """
            INSERT INTO file_retention_policies (policy_id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(policy_id) DO UPDATE SET
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                record.policy_id,
                self.backend.dump_payload(record),
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
