from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus
from app.domains.templates.catalog_migration import TemplateCatalogMigrationConflict
from app.domains.templates.models import TemplateCatalogItem
from app.domains.templates.package_validator import TemplatePackageValidationError
from app.domains.templates.repository import TemplateCatalogCommitUnknown
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.resources import MysqlResourceVersionRepository
from app.infrastructure.persistence.mysql.schema import MYSQL_SCHEMA_STATEMENTS, TEMPLATE_CATALOG_SCHEMA_STATEMENTS
from app.infrastructure.persistence.mysql.template_catalog import MysqlTemplateCatalogRepository


@unittest.skipUnless(os.environ.get("MD2WORD_TEST_MYSQL_PORT"), "需要显式指定隔离 MySQL 端口。")
class MysqlTemplateCatalogIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = "catalog_test_" + uuid4().hex
        config = MysqlPersistenceConfig(
            host="127.0.0.1",
            port=int(os.environ["MD2WORD_TEST_MYSQL_PORT"]),
            user=os.environ.get("MD2WORD_TEST_MYSQL_USER", "root"),
            password=os.environ["MD2WORD_TEST_MYSQL_PASSWORD"],
            database="mysql",
        )
        self.control = MysqlPersistenceBackend(config, initialize=False)
        with self.control.connect() as connection, connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{self.database}`")
        self.addCleanup(self.drop_schema)
        self.backend = MysqlPersistenceBackend(replace(config, database=self.database), initialize=False)
        self.catalog = MysqlTemplateCatalogRepository(self.backend)
        self.versions = MysqlResourceVersionRepository(self.backend)
        with self.backend.connect() as connection, connection.cursor() as cursor:
            for statement in MYSQL_SCHEMA_STATEMENTS:
                if "CREATE TABLE IF NOT EXISTS resource_" in statement:
                    cursor.execute(statement)

    def drop_schema(self) -> None:
        with self.control.connect() as connection, connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE `{self.database}`")

    def create_catalog_schema(self) -> None:
        with self.backend.connect() as connection, connection.cursor() as cursor:
            for statement in TEMPLATE_CATALOG_SCHEMA_STATEMENTS:
                cursor.execute(statement)

    @staticmethod
    def record(template_id: str, version: str = "1", *, published: bool = False) -> ResourceVersionRecord:
        return ResourceVersionRecord(
            resource_type="template",
            resource_id=template_id,
            version=version,
            status=ResourceVersionStatus.PUBLISHED if published else ResourceVersionStatus.DRAFT,
            snapshot_hash="sha256:" + "a" * 64,
            payload={"docx_path": f"var/config/templates/{template_id}/v{version}/test.docx"},
        )

    def test_concurrent_create_and_partial_transaction(self) -> None:
        self.create_catalog_schema()
        barrier = Barrier(2)

        def create(name: str) -> str:
            barrier.wait(timeout=10)
            try:
                self.catalog.create_template(TemplateCatalogItem(id="shared", name=name), self.record("shared"))
            except TemplatePackageValidationError:
                return "conflict"
            return name

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, ("甲", "乙")))
        self.assertEqual(results.count("conflict"), 1)
        self.assertIn(self.catalog.get_template("shared").name, results)
        self.assertEqual(len(self.versions.list_resource_versions("template", "shared")), 1)

        # 模拟原故障遗留草稿。首版冲突须回滚本事务刚插入的目录。
        orphan = self.record("orphan")
        self.versions.create_resource_version(orphan)
        with self.assertRaises(TemplatePackageValidationError):
            self.catalog.create_template(TemplateCatalogItem(id="orphan", name="残留"), orphan)
        self.assertIsNone(self.catalog.get_template("orphan"))
        self.assertEqual(self.versions.get_resource_version("template", "orphan", "1"), orphan)

    def test_commit_unknown_reconciles_on_independent_connection(self) -> None:
        self.create_catalog_schema()
        original_connect = self.backend._connect_factory

        class CommitReplyLost:
            def __init__(self) -> None:
                self.connection = original_connect()

            def commit(self) -> None:
                self.connection.commit()
                raise OSError("测试模拟提交应答丢失")

            def __getattr__(self, name: str):
                return getattr(self.connection, name)

        item = TemplateCatalogItem(id="committed", name="提交已生效")
        record = self.record(item.id)
        with patch.object(self.backend, "_connect_factory", CommitReplyLost):
            with self.assertRaises(TemplateCatalogCommitUnknown):
                self.catalog.create_template(item, record)
        self.assertEqual(self.catalog.get_template(item.id), item)
        self.assertEqual(self.versions.get_resource_version("template", item.id, "1"), record)

    def test_version_and_global_default_races(self) -> None:
        self.create_catalog_schema()
        for template_id in ("seed", "custom"):
            record = self.record(template_id, published=True)
            self.catalog.bootstrap_seed(TemplateCatalogItem(id=template_id, name=template_id), record)
        self.catalog.initialize_default_template("seed", "1")
        self.catalog.initialize_default_template("custom", "1")
        self.assertEqual(self.catalog.get_default_template_id(), "seed")

        def add(_: int) -> int:
            version = self.versions.allocate_next_version("template", "custom", 2)
            self.catalog.add_template_version(self.record("custom", str(version), published=True))
            return version

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(add, range(2))), [2, 3])

        def race(*operations) -> list[str]:
            barrier = Barrier(2)

            def run(operation) -> str:
                barrier.wait(timeout=10)
                try:
                    operation()
                except (FileNotFoundError, ValueError):
                    return "rejected"
                return "committed"

            with ThreadPoolExecutor(max_workers=2) as pool:
                return sorted(pool.map(run, operations))

        self.assertEqual(
            race(
                lambda: self.catalog.set_default_template_version(self.record("custom", "2", published=True)),
                lambda: self.catalog.disable_template_version("custom", "2"),
            ),
            ["committed", "rejected"],
        )
        published = self.versions.get_default_resource_version("template", "custom")
        self.assertEqual(published.status, ResourceVersionStatus.PUBLISHED)
        self.assertEqual(
            race(
                lambda: self.catalog.set_default_template("custom", published.version),
                lambda: self.catalog.update_template("custom", {"enabled": False}),
            ),
            ["committed", "rejected"],
        )
        self.assertTrue(self.catalog.get_template(self.catalog.get_default_template_id()).enabled)

    def test_migration_preflight_and_repeat_preserve_history(self) -> None:
        v1, v2 = (self.record("legacy", version, published=True) for version in ("1", "2"))
        for version in (v1, v2):
            self.versions.create_resource_version(version)
        self.versions.set_default_resource_version("template", "legacy", "1")
        original = self.catalog.read_legacy_migration_snapshot()
        self.assertEqual(original.templates, ())
        item = TemplateCatalogItem(id="legacy", name="导入")
        self.catalog.apply_legacy_migration(original, (item,), (("legacy", "2"),), "legacy")
        migrated = self.catalog.read_legacy_migration_snapshot()
        self.assertEqual(migrated.templates, (item,))
        self.assertEqual(migrated.default_template_id, "legacy")
        self.assertEqual(migrated.versions[0], v1)
        self.assertEqual(migrated.versions[1].snapshot_hash, v2.snapshot_hash)
        self.assertEqual(migrated.versions[1].payload, v2.payload)
        self.assertEqual(migrated.versions[1].status, ResourceVersionStatus.DISABLED)
        with self.assertRaises(TemplateCatalogMigrationConflict):
            self.catalog.apply_legacy_migration(original, (item,), (), None)
        self.catalog.apply_legacy_migration(migrated, (), (), None)
        self.assertEqual(self.catalog.read_legacy_migration_snapshot(), migrated)
