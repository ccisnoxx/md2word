from __future__ import annotations

# app/infrastructure/persistence/mysql/resources.py: MySQL backend 的资源版本 adapter。

import json
from typing import Any

from app.domains.audit.models import AuditEvent
from app.domains.resources.models import (
    ResourceDefaultPointer,
    ResourceType,
    ResourceVersionRecord,
    ResourceVersionStatus,
    disable_nondefault_resource_version,
    utc_now,
)
from app.domains.resources.repository import ResourceDefaultCommitUnknownError
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, pymysql


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
        expected_status: ResourceVersionStatus | None = None,
    ) -> ResourceVersionRecord | None:
        """按旧状态和指纹原子更新资源版本，条件不再成立时返回 None。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE resource_versions
                    SET snapshot_hash = %s,
                        payload_ref = %s,
                        payload = %s,
                        updated_at = %s,
                        status = %s
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
                        record.status.value,
                        record.resource_type,
                        record.resource_id,
                        record.version,
                        (expected_status if expected_status is not None else record.status).value,
                        expected_snapshot_hash,
                    ),
                )
                updated = cursor.rowcount == 1
        return record if updated else None

    def create_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord:
        """只插入新资源版本，数据库主键冲突必须向上游暴露。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                insert_resource_version(cursor, record)
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
                return self._get_resource_version(cursor, resource_type, resource_id, version)

    def _get_resource_version(
        self,
        cursor: Any,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
        *,
        for_update: bool = False,
    ) -> ResourceVersionRecord | None:
        sql = """
            SELECT resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, created_at, updated_at
            FROM resource_versions
            WHERE resource_type = %s AND resource_id = %s AND version = %s
        """
        cursor.execute(sql + (" FOR UPDATE" if for_update else ""), (resource_type, resource_id, version))
        row = cursor.fetchone()
        return load_resource_version(row) if row is not None else None

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
        return [load_resource_version(row) for row in rows]

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
                return self._get_default_resource_version(cursor, resource_type, resource_id)

    def _get_default_resource_version(
        self, cursor: Any, resource_type: ResourceType, resource_id: str,
    ) -> ResourceVersionRecord | None:
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
        return load_resource_version(row) if row is not None else None

    def get_default_resource_pointer(self, resource_type: ResourceType, resource_id: str) -> ResourceDefaultPointer | None:
        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                return self._get_default_resource_pointer(cursor, resource_type, resource_id)

    @staticmethod
    def _get_default_resource_pointer(
        cursor: Any, resource_type: ResourceType, resource_id: str, *, for_update: bool = False,
    ) -> ResourceDefaultPointer | None:
        sql = """
            SELECT version, updated_at FROM resource_default_versions
            WHERE resource_type = %s AND resource_id = %s
        """
        cursor.execute(sql + (" FOR UPDATE" if for_update else ""), (resource_type, resource_id))
        row = cursor.fetchone()
        return ResourceDefaultPointer(row["version"], row["updated_at"]) if row is not None else None

    def switch_default_resource_version(
        self,
        record: ResourceVersionRecord,
        *,
        expected_pointer: ResourceDefaultPointer | None,
        audit_event: AuditEvent | None = None,
    ) -> ResourceVersionRecord | None:
        """比较已验证目标和旧指针，读回确认后原子提交指针与审计。"""

        commit_ready = False
        try:
            with self.backend.connect() as connection:
                with connection.cursor() as cursor:
                    confirmed = self.switch_default_with_cursor(
                        cursor, record, expected_pointer=expected_pointer, audit_event=audit_event,
                    )
                # 连接上下文退出时提交，连接中断后无法通过回滚结果判定是否已提交。
                commit_ready = confirmed is not None
        except Exception as exc:
            if commit_ready:
                raise ResourceDefaultCommitUnknownError("默认模板版本切换结果暂不可确认，请重新读取默认版本。") from exc
            raise
        return confirmed

    def switch_default_with_cursor(
        self,
        cursor: Any,
        record: ResourceVersionRecord,
        *,
        expected_pointer: ResourceDefaultPointer | None,
        audit_event: AuditEvent | None,
    ) -> ResourceVersionRecord | None:
        """在调用方的事务内完成条件切换、读回与审计。"""

        resource_type, resource_id, version = record.resource_type, record.resource_id, record.version
        target = self._get_resource_version(cursor, resource_type, resource_id, version, for_update=True)
        if (target is None or target.status != ResourceVersionStatus.PUBLISHED
                or target.snapshot_hash != record.snapshot_hash):
            return None
        if expected_pointer is None:
            # 空指针由主键裁决，避免两个锁定读同时拿到间隙锁。
            if not self._insert_default_resource_pointer(cursor, resource_type, resource_id, version):
                return None
        else:
            pointer = self._get_default_resource_pointer(cursor, resource_type, resource_id, for_update=True)
            if pointer != expected_pointer:
                return None
            if expected_pointer.version != version:
                cursor.execute(
                    """
                    UPDATE resource_default_versions
                    SET version = %s, updated_at = %s
                    WHERE resource_type = %s AND resource_id = %s
                    """,
                    (version, utc_now().isoformat(), resource_type, resource_id),
                )
        confirmed = self._get_default_resource_version(cursor, resource_type, resource_id)
        if (confirmed is None or confirmed.version != version
                or confirmed.status != ResourceVersionStatus.PUBLISHED
                or confirmed.snapshot_hash != record.snapshot_hash):
            raise RuntimeError("默认资源版本指针读回确认失败。")
        if audit_event is not None:
            cursor.execute(
                "INSERT INTO audit_events (audit_id, payload, created_at) VALUES (%s, %s, %s)",
                (audit_event.audit_id, self.backend.dump_payload(audit_event), audit_event.created_at.isoformat()),
            )
        return confirmed

    @staticmethod
    def _insert_default_resource_pointer(
        cursor: Any, resource_type: ResourceType, resource_id: str, version: str,
    ) -> bool:
        try:
            cursor.execute(
                """
                INSERT INTO resource_default_versions (resource_type, resource_id, version, updated_at)
                VALUES (%s, %s, %s, %s)
                """,
                (resource_type, resource_id, version, utc_now().isoformat()),
            )
        except Exception as exc:
            if (pymysql is not None and isinstance(exc, pymysql.err.IntegrityError)
                    and exc.args[:1] == (pymysql.constants.ER.DUP_ENTRY,)):
                return False
            raise
        return True

    def disable_template_version_if_not_default(self, template_id: str, version: str) -> ResourceVersionRecord:
        """与显式切换争用同一目标行，禁止把已切为默认的版本禁用。"""

        with self.backend.connect() as connection:
            with connection.cursor() as cursor:
                record = self._get_resource_version(cursor, "template", template_id, version, for_update=True)
                if record is None:
                    raise FileNotFoundError(f"资源版本不存在: template/{template_id}@{version}")
                # 获得目标锁后才建立一致读快照，能看到持有同一锁的切换已提交的指针。
                pointer = self._get_default_resource_pointer(cursor, "template", template_id)
                disabled = disable_nondefault_resource_version(
                    record, default_version=pointer.version if pointer is not None else None,
                )
                if disabled is not record:
                    cursor.execute(
                        """
                        UPDATE resource_versions
                        SET status = %s, updated_at = %s
                        WHERE resource_type = %s AND resource_id = %s AND version = %s
                        """,
                        (disabled.status.value, disabled.updated_at.isoformat(), "template", template_id, version),
                    )
        return disabled


def insert_resource_version(cursor: Any, record: ResourceVersionRecord) -> None:
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


def load_resource_version(row: dict[str, Any]) -> ResourceVersionRecord:
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
