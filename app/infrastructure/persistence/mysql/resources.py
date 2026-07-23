from __future__ import annotations

# app/infrastructure/persistence/mysql/resources.py: MySQL backend 的资源版本 adapter。

import json
from typing import Any

from app.domains.resources.models import ResourceType, ResourceVersionRecord, utc_now
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend


class MysqlResourceVersionRepository:
    """用 MySQL backend 读写模板、术语和翻译配置资源版本。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend

    def save_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO resource_versions
                        (resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        snapshot_hash = VALUES(snapshot_hash),
                        payload_ref = VALUES(payload_ref),
                        payload = VALUES(payload),
                        created_at = VALUES(created_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        record.resource_type,
                        record.resource_id,
                        record.version,
                        record.status.value,
                        record.snapshot_hash,
                        record.payload_ref,
                        json.dumps(record.payload, ensure_ascii=False) if record.payload is not None else None,
                        record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                    ),
                )
        return record

    def update_resource_version_if_current(
        self,
        record: ResourceVersionRecord,
        *,
        expected_snapshot_hash: str,
    ) -> ResourceVersionRecord | None:
        """以 snapshot_hash 为条件原子更新草稿，过期写入返回 None。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE resource_versions
                    SET snapshot_hash = %s,
                        payload_ref = %s,
                        payload = %s,
                        updated_at = %s
                    WHERE resource_type = %s
                      AND resource_id = %s
                      AND version = %s
                      AND status = %s
                      AND snapshot_hash = %s
                    """,
                    (
                        record.snapshot_hash,
                        record.payload_ref,
                        json.dumps(record.payload, ensure_ascii=False)
                        if record.payload is not None
                        else None,
                        record.updated_at.isoformat(),
                        record.resource_type,
                        record.resource_id,
                        record.version,
                        record.status.value,
                        expected_snapshot_hash,
                    ),
                )
                updated = cursor.rowcount == 1
        return record if updated else None

    def create_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord:
        """只插入新资源版本，数据库主键冲突必须向上游暴露。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO resource_versions
                        (resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.resource_type,
                        record.resource_id,
                        record.version,
                        record.status.value,
                        record.snapshot_hash,
                        record.payload_ref,
                        json.dumps(record.payload, ensure_ascii=False) if record.payload is not None else None,
                        record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                    ),
                )
        return record

    def allocate_next_version(self, resource_type: ResourceType, resource_id: str, minimum_next: int) -> int:
        """在同一事务内锁定并递增资源整数版本序列。"""

        now = utc_now().isoformat()
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO resource_version_sequences (resource_type, resource_id, next_version, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        next_version = GREATEST(next_version, VALUES(next_version)),
                        updated_at = VALUES(updated_at)
                    """,
                    (resource_type, resource_id, minimum_next, now),
                )
                cursor.execute(
                    """
                    SELECT next_version
                    FROM resource_version_sequences
                    WHERE resource_type = %s AND resource_id = %s
                    FOR UPDATE
                    """,
                    (resource_type, resource_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("资源版本序列初始化失败。")
                allocated = int(row["next_version"])
                cursor.execute(
                    """
                    UPDATE resource_version_sequences
                    SET next_version = %s, updated_at = %s
                    WHERE resource_type = %s AND resource_id = %s
                    """,
                    (allocated + 1, now, resource_type, resource_id),
                )
        return allocated

    def get_resource_version(
        self,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
    ) -> ResourceVersionRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at
                    FROM resource_versions
                    WHERE resource_type = %s AND resource_id = %s AND version = %s
                    """,
                    (resource_type, resource_id, version),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return self._load_resource_version(row)

    def list_resource_versions(self, resource_type: ResourceType, resource_id: str) -> list[ResourceVersionRecord]:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at
                    FROM resource_versions
                    WHERE resource_type = %s AND resource_id = %s
                    ORDER BY created_at, version
                    """,
                    (resource_type, resource_id),
                )
                rows = cursor.fetchall()
        return [self._load_resource_version(row) for row in rows]

    def set_default_resource_version(self, resource_type: ResourceType, resource_id: str, version: str) -> None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO resource_default_versions (resource_type, resource_id, version, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        version = VALUES(version),
                        updated_at = VALUES(updated_at)
                    """,
                    (resource_type, resource_id, version, utc_now().isoformat()),
                )

    def get_default_resource_version(self, resource_type: ResourceType, resource_id: str) -> ResourceVersionRecord | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT rv.resource_type, rv.resource_id, rv.version, rv.status, rv.snapshot_hash,
                           rv.payload_ref, rv.payload, rv.created_at, rv.updated_at
                    FROM resource_default_versions rdv
                    JOIN resource_versions rv
                      ON rv.resource_type = rdv.resource_type
                     AND rv.resource_id = rdv.resource_id
                     AND rv.version = rdv.version
                    WHERE rdv.resource_type = %s AND rdv.resource_id = %s
                    """,
                    (resource_type, resource_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return self._load_resource_version(row)

    def _load_resource_version(self, row: dict[str, Any]) -> ResourceVersionRecord:
        payload = json.loads(row["payload"]) if row["payload"] is not None else None
        return ResourceVersionRecord(
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            version=row["version"],
            status=row["status"],
            snapshot_hash=row["snapshot_hash"],
            payload_ref=row["payload_ref"],
            payload=payload,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
