from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.domains.audit.models import AuditEvent
from app.domains.resources.models import ResourceDefaultPointer, ResourceVersionRecord, ResourceVersionStatus, utc_now
from app.domains.templates.catalog_migration import CatalogMigrationSnapshot, TemplateCatalogMigrationConflict
from app.domains.templates.models import TemplateCatalogItem
from app.domains.templates.package_validator import TemplatePackageValidationError
from app.domains.templates.repository import TemplateCatalogCommitUnknown
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, pymysql
from app.infrastructure.persistence.mysql.resources import (
    MysqlResourceVersionRepository,
    insert_resource_version,
    load_resource_version,
)
from app.infrastructure.persistence.mysql.schema import TEMPLATE_CATALOG_SCHEMA_STATEMENTS


class MysqlTemplateCatalogRepository:
    """持久化目录及模板专用的跨表事务。"""

    def __init__(self, backend: MysqlPersistenceBackend) -> None:
        self.backend = backend
        self._versions = MysqlResourceVersionRepository(backend)

    @contextmanager
    def _write(self) -> Iterator[Any]:
        # 事务内失败可以回滚；事务结束时断连则不能推定 COMMIT 未生效。
        writing_complete = False
        try:
            with self.backend.connect() as connection, connection.cursor() as cursor:
                yield cursor
                writing_complete = True
        except Exception as exc:
            if writing_complete:
                raise TemplateCatalogCommitUnknown() from exc
            raise

    def get_template(self, template_id: str) -> TemplateCatalogItem | None:
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT template_id, enabled, deleted, payload FROM template_catalog WHERE template_id = %s",
                (template_id,),
            )
            row = cursor.fetchone()
        return self._catalog_item(row) if row is not None else None

    def list_enabled_templates(self) -> list[TemplateCatalogItem]:
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT template_id, enabled, deleted, payload FROM template_catalog "
                "WHERE enabled = 1 AND deleted = 0 ORDER BY template_id"
            )
            return [self._catalog_item(row) for row in cursor.fetchall()]

    def get_default_template_id(self) -> str | None:
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT template_id FROM template_catalog_defaults WHERE singleton_id = 1")
            row = cursor.fetchone()
        return row["template_id"] if row is not None else None

    def create_template(self, item: TemplateCatalogItem, first_version: ResourceVersionRecord) -> None:
        with self._write() as cursor:
            try:
                self._insert_item(cursor, item)
                insert_resource_version(cursor, first_version)
            except Exception as exc:
                if not self._is_duplicate_key(exc):
                    raise
                raise self._version_conflict("模板 ID 或初始版本已登记。") from exc

    def update_template(self, template_id: str, updates: dict[str, Any]) -> None:
        with self._write() as cursor:
            global_default = self._lock_global_default(cursor) if updates.get("enabled") is False else None
            current = self._require_item(cursor, template_id)
            if current.id == global_default:
                raise ValueError(f"当前默认模板不能停用: {current.id}")
            updated = current.model_copy(update=updates)
            cursor.execute(
                "UPDATE template_catalog SET enabled = %s, payload = %s WHERE template_id = %s",
                (updated.enabled, self._catalog_payload(updated), updated.id),
            )

    def delete_template(self, template_id: str) -> None:
        with self._write() as cursor:
            global_default = self._lock_global_default(cursor)
            item = self._require_item(cursor, template_id)
            if item.id == global_default:
                raise ValueError(f"当前默认模板不能删除: {item.id}")
            cursor.execute(
                "UPDATE template_catalog SET enabled = 0, deleted = 1 WHERE template_id = %s",
                (item.id,),
            )

    def set_default_template(self, template_id: str, expected_version: str) -> None:
        with self._write() as cursor:
            self._lock_global_default(cursor)
            self._set_global_default(cursor, template_id, expected_version)

    def initialize_default_template(self, template_id: str, expected_version: str) -> None:
        with self._write() as cursor:
            if self._lock_global_default(cursor) is None:
                self._set_global_default(cursor, template_id, expected_version)

    def add_template_version(self, record: ResourceVersionRecord) -> None:
        with self._write() as cursor:
            self._require_item(cursor, record.resource_id)
            try:
                insert_resource_version(cursor, record)
            except Exception as exc:
                if not self._is_duplicate_key(exc):
                    raise
                raise self._version_conflict("模板版本已登记。") from exc

    def publish_template_version(
        self,
        record: ResourceVersionRecord,
        *,
        expected_snapshot_hash: str,
        make_default: bool,
    ) -> ResourceVersionRecord | None:
        with self._write() as cursor:
            self._require_item(cursor, record.resource_id)
            current = self._get_version(cursor, record.resource_id, record.version)
            if (
                current is None
                or current.status != ResourceVersionStatus.DRAFT
                or current.snapshot_hash != expected_snapshot_hash
            ):
                return None
            cursor.execute(
                "UPDATE resource_versions SET status = %s, snapshot_hash = %s, payload = %s, updated_at = %s "
                "WHERE resource_type = 'template' AND resource_id = %s AND version = %s",
                (
                    record.status.value,
                    record.snapshot_hash,
                    self._version_payload(record),
                    record.updated_at.isoformat(),
                    record.resource_id,
                    record.version,
                ),
            )
            if make_default:
                self._write_version_default(cursor, record)
            return record

    def set_default_template_version(
        self,
        record: ResourceVersionRecord,
        *,
        expected_pointer: ResourceDefaultPointer | None,
        audit_event: AuditEvent | None = None,
    ) -> ResourceVersionRecord | None:
        """先锁定目录，再在同一事务内切换并审计该模板的默认版本。"""

        with self._write() as cursor:
            self._require_item(cursor, record.resource_id)
            return self._versions.switch_default_with_cursor(
                cursor, record, expected_pointer=expected_pointer, audit_event=audit_event,
            )

    def disable_template_version(self, template_id: str, version: str) -> ResourceVersionRecord:
        with self._write() as cursor:
            item = self._require_item(cursor, template_id)
            record = self._get_version(cursor, item.id, version)
            if record is None:
                raise FileNotFoundError(f"模板版本不存在: {item.id}@{version}")
            if self._get_version_default(cursor, item.id) == record.version:
                raise ValueError("默认资源版本不能直接禁用，请先切换默认指针。")
            if record.status == ResourceVersionStatus.DISABLED:
                return record
            if record.status == ResourceVersionStatus.SUPERSEDED:
                raise ValueError("superseded 资源版本不能再切换为 disabled。")
            updated_at = utc_now()
            cursor.execute(
                "UPDATE resource_versions SET status = %s, updated_at = %s "
                "WHERE resource_type = 'template' AND resource_id = %s AND version = %s",
                (ResourceVersionStatus.DISABLED.value, updated_at.isoformat(), item.id, record.version),
            )
            return record.model_copy(update={"status": ResourceVersionStatus.DISABLED, "updated_at": updated_at})

    def bootstrap_seed(self, item: TemplateCatalogItem, record: ResourceVersionRecord) -> None:
        with self._write() as cursor:
            # 唯一键在启动竞争时为同一模板取得排他锁，保留旧目录元数据。
            self._insert_item(cursor, item, keep_existing=True)
            try:
                self._require_item(cursor, item.id)
            except FileNotFoundError:
                # 目录墓碑保留旧模板的删除决定。
                return
            current = self._get_version(cursor, item.id, record.version)
            if current is None:
                insert_resource_version(cursor, record)
                current = record
            elif current.resource_id != item.id or current.snapshot_hash != record.snapshot_hash:
                raise ValueError(f"模板 seed 版本身份在登记期间发生变化: {item.id}@{record.version}")
            if current.status == ResourceVersionStatus.PUBLISHED and self._get_version_default(cursor, item.id) is None:
                self._write_version_default(cursor, current)

    def read_legacy_migration_snapshot(self) -> CatalogMigrationSnapshot:
        """只读取现有表，兼容还没有目录结构的旧库。"""
        with self.backend.connect() as connection, connection.cursor() as cursor:
            return self._read_migration_snapshot(cursor)

    def apply_legacy_migration(
        self,
        expected: CatalogMigrationSnapshot,
        additions: tuple[TemplateCatalogItem, ...],
        disables: tuple[tuple[str, str], ...],
        default_template_id: str | None,
    ) -> None:
        # DDL 有隐式提交。先幂等建立两张新表，业务变更在随后的独立事务提交。
        with self.backend.connect() as connection, connection.cursor() as cursor:
            for statement in TEMPLATE_CATALOG_SCHEMA_STATEMENTS:
                cursor.execute(statement)
        with self._write() as cursor:
            self._lock_global_default(cursor)
            if self._read_migration_snapshot(cursor) != expected:
                raise TemplateCatalogMigrationConflict("模板数据已变化，请重新执行迁移预检。")
            for item in additions:
                self._insert_item(cursor, item)
            for template_id, version in disables:
                cursor.execute(
                    "UPDATE resource_versions SET status = %s, updated_at = %s "
                    "WHERE resource_type = %s AND resource_id = %s AND version = %s "
                    "AND status IN (%s, %s)",
                    (
                        ResourceVersionStatus.DISABLED.value, utc_now().isoformat(), "template", template_id, version,
                        ResourceVersionStatus.PUBLISHED.value, ResourceVersionStatus.DRAFT.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise TemplateCatalogMigrationConflict("待禁用版本状态已变化，请重新执行迁移预检。")
            if default_template_id is not None:
                version = expected.version_defaults[default_template_id]
                self._set_global_default(cursor, default_template_id, version)

    @classmethod
    def _read_migration_snapshot(cls, cursor: Any) -> CatalogMigrationSnapshot:
        cursor.execute(
            "SELECT TABLE_NAME AS table_name FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (%s, %s)",
            ("template_catalog", "template_catalog_defaults"),
        )
        tables = {row["table_name"] for row in cursor.fetchall()}
        templates = ()
        if "template_catalog" in tables:
            cursor.execute("SELECT template_id, enabled, deleted, payload FROM template_catalog ORDER BY template_id")
            templates = tuple(cls._catalog_item(row) for row in cursor.fetchall())
        default_template_id = None
        if "template_catalog_defaults" in tables:
            cursor.execute("SELECT template_id FROM template_catalog_defaults WHERE singleton_id = 1")
            row = cursor.fetchone()
            if row is not None:
                default_template_id = row["template_id"]
        cursor.execute(
            "SELECT resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, "
            "created_at, updated_at FROM resource_versions WHERE resource_type = %s ORDER BY resource_id, version",
            ("template",),
        )
        versions = tuple(load_resource_version(row) for row in cursor.fetchall())
        cursor.execute("SELECT resource_id, version FROM resource_default_versions WHERE resource_type = %s", ("template",))
        return CatalogMigrationSnapshot(
            templates=templates,
            versions=versions,
            version_defaults={row["resource_id"]: row["version"] for row in cursor.fetchall()},
            default_template_id=default_template_id,
        )

    def _set_global_default(self, cursor: Any, template_id: str, expected_version: str) -> None:
        # 全局指针先加锁，再锁模板行。版本操作仅锁模板行和它的版本记录。
        item = self._require_item(cursor, template_id)
        if not item.enabled:
            raise FileNotFoundError(f"模板不存在或未启用: {template_id}")
        version = self._get_version_default(cursor, item.id)
        if version != expected_version:
            raise self._version_conflict("模板默认版本在设置全局默认前已变化。")
        record = self._get_version(cursor, item.id, version)
        if record is None or record.status != ResourceVersionStatus.PUBLISHED:
            raise self._version_conflict("全局默认模板须具有已发布的默认版本。")
        cursor.execute("UPDATE template_catalog_defaults SET template_id = %s WHERE singleton_id = 1", (item.id,))

    @staticmethod
    def _lock_global_default(cursor: Any) -> str | None:
        cursor.execute(
            "INSERT INTO template_catalog_defaults (singleton_id, template_id) VALUES (1, NULL) "
            "ON DUPLICATE KEY UPDATE singleton_id = singleton_id"
        )
        cursor.execute("SELECT template_id FROM template_catalog_defaults WHERE singleton_id = 1 FOR UPDATE")
        return cursor.fetchone()["template_id"]

    @classmethod
    def _require_item(cls, cursor: Any, template_id: str) -> TemplateCatalogItem:
        cursor.execute(
            "SELECT template_id, enabled, deleted, payload FROM template_catalog WHERE template_id = %s FOR UPDATE",
            (template_id,),
        )
        row = cursor.fetchone()
        if row is None or row["deleted"]:
            raise FileNotFoundError(f"模板不存在: {template_id}")
        return cls._catalog_item(row)

    @classmethod
    def _insert_item(cls, cursor: Any, item: TemplateCatalogItem, *, keep_existing: bool = False) -> None:
        sql = "INSERT INTO template_catalog (template_id, enabled, deleted, payload) VALUES (%s, %s, %s, %s)"
        if keep_existing:
            sql += " ON DUPLICATE KEY UPDATE template_id = template_id"
        cursor.execute(sql, (item.id, item.enabled, item.deleted, cls._catalog_payload(item)))

    @staticmethod
    def _catalog_item(row: dict[str, Any]) -> TemplateCatalogItem:
        return TemplateCatalogItem.model_validate({
            **json.loads(row["payload"]),
            "id": row["template_id"],
            "enabled": bool(row["enabled"]),
            "deleted": bool(row["deleted"]),
        })

    @staticmethod
    def _catalog_payload(item: TemplateCatalogItem) -> str:
        return item.model_dump_json(exclude={"id", "enabled", "deleted"})

    @staticmethod
    def _version_payload(record: ResourceVersionRecord) -> str | None:
        return json.dumps(record.payload, ensure_ascii=False) if record.payload is not None else None

    @staticmethod
    def _get_version(cursor: Any, template_id: str, version: str) -> ResourceVersionRecord | None:
        cursor.execute(
            "SELECT resource_type, resource_id, version, status, snapshot_hash, payload_ref, payload, "
            "created_at, updated_at FROM resource_versions "
            "WHERE resource_type = %s AND resource_id = %s AND version = %s FOR UPDATE",
            ("template", template_id, version),
        )
        row = cursor.fetchone()
        return load_resource_version(row) if row is not None else None

    @staticmethod
    def _get_version_default(cursor: Any, template_id: str) -> str | None:
        # 同一模板目录行锁覆盖指针的读写，包括默认行尚未建立时。
        cursor.execute(
            "SELECT version FROM resource_default_versions WHERE resource_type = %s AND resource_id = %s",
            ("template", template_id),
        )
        row = cursor.fetchone()
        return row["version"] if row is not None else None

    @staticmethod
    def _write_version_default(cursor: Any, record: ResourceVersionRecord) -> None:
        cursor.execute(
            "INSERT INTO resource_default_versions (resource_type, resource_id, version, updated_at) "
            "VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
            "version = VALUES(version), updated_at = VALUES(updated_at)",
            ("template", record.resource_id, record.version, utc_now().isoformat()),
        )

    @staticmethod
    def _is_duplicate_key(exc: Exception) -> bool:
        return pymysql is not None and isinstance(exc, pymysql.err.IntegrityError) and exc.args[0] == 1062

    @staticmethod
    def _version_conflict(message: str) -> TemplatePackageValidationError:
        return TemplatePackageValidationError(message, path="template_version", code="template_version_conflict")
