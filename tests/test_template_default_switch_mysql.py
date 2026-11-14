"""在隔离的 MySQL 8.4 随机库验证默认模板指针的实际竞争和回滚。"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

import pymysql
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_runtime, require_admin_actor
from app.api.errors import register_api_error_handlers
from app.core.errors import ApplicationError
from app.domains.audit.models import ActorContext
from app.domains.audit.service import AuditService
from app.domains.resources.service import ResourceVersionService
from app.domains.templates.read_service import TemplateReadService
from app.domains.templates.router import router
from app.infrastructure.persistence.mysql.audit import MysqlAuditEventRepository
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.resources import MysqlResourceVersionRepository
from app.infrastructure.persistence.mysql.schema import MYSQL_SCHEMA_STATEMENTS
from tests.test_document_job_list_query_v2_mysql import _connection_options
from tests.test_template_seed_history import _IsolatedSettings


class MysqlTemplateDefaultSwitchTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        options = _connection_options(os.environ)
        schema = f"md2word_template_switch_test_{uuid4().hex}"
        admin = pymysql.connect(**options, autocommit=True)
        cls.addClassCleanup(admin.close)
        with admin.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version, @@transaction_isolation AS isolation")
            facts = cursor.fetchone()
            if not facts["version"].startswith("8.4.") or facts["isolation"] != "REPEATABLE-READ":
                raise RuntimeError("专项验证要求 MySQL 8.4 和默认 REPEATABLE READ 隔离级别。")
            cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4")

        def drop_schema() -> None:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{schema}`")

        cls.addClassCleanup(drop_schema)
        config = MysqlPersistenceConfig(options["host"], options["port"], options["user"], options["password"], schema)
        cls.backend = MysqlPersistenceBackend(
            config, initialize=False,
            connect_factory=lambda: pymysql.connect(**options, database=schema, autocommit=False),
        )
        with cls.backend.connect() as connection, connection.cursor() as cursor:
            for table in ("resource_versions", "resource_default_versions", "resource_version_sequences", "audit_events"):
                ddl, = (sql for sql in MYSQL_SCHEMA_STATEMENTS if sql.strip().startswith(f"CREATE TABLE IF NOT EXISTS {table} ("))
                cursor.execute(ddl)

    def setUp(self) -> None:
        with self.backend.connect() as connection, connection.cursor() as cursor:
            for table in ("resource_versions", "resource_default_versions", "resource_version_sequences", "audit_events"):
                cursor.execute(f"DELETE FROM {table}")
        root = Path(self.enterContext(TemporaryDirectory())).resolve()
        manifest = root / "manifest.yaml"
        seed = root / "seed.docx"
        doc = Document()
        doc.add_paragraph("已登记的模板")
        doc.save(seed)
        manifest.write_text(
            "templates:\n  - id: default\n    name: 测试模板\n    version: 1\n"
            "    enabled: true\n    is_default_seed: true\n    template_path: seed.docx\n", encoding="utf-8",
        )
        settings = _IsolatedSettings(_env_file=None, fixture_root=root, data_dir=str(root / "data"),
                                     templates_manifest_path=str(manifest), templates_storage_path=str(root / "versions"))
        self.repository = MysqlResourceVersionRepository(self.backend)
        self.audit = MysqlAuditEventRepository(self.backend)
        self.reader = TemplateReadService(settings, ResourceVersionService(self.repository), AuditService(self.audit))
        self.reader.bootstrap_manifest_versions()
        seed_record = self.repository.get_resource_version("template", "default", "1")
        self.candidates = {}
        for version in (2, 3):
            upload = root / f"candidate-{version}.docx"
            upload.write_bytes(seed.read_bytes())
            draft = self.reader.create_template_version("default", source_path=upload, source_filename=upload.name)
            self.assertEqual(draft.version, version)
            self.candidates[version] = self.reader.resource_version_service.publish("template", "default", str(version))
        self.assertEqual(self._default(), seed_record)

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        register_api_error_handlers(app)
        app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(template_read_service=self.reader)
        app.dependency_overrides[require_admin_actor] = lambda: ActorContext(actor_role="admin", source="admin_token")
        self.app = app

    def _default(self):
        return self.repository.get_default_resource_version("template", "default")

    def _set_default(self, version: int):
        with TestClient(self.app, raise_server_exceptions=False) as client:
            return client.post(f"/api/v1/templates/default/versions/{version}/set-default",
                               json={"set_default_reason": f"选择版本 {version}"})

    def _trigger(self, statement: str) -> None:
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute(f"CREATE TRIGGER inject_switch_failure {statement}")

        def drop_trigger() -> None:
            with self.backend.connect() as connection, connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER inject_switch_failure")

        self.addCleanup(drop_trigger)

    def _race(self):
        barrier = Barrier(2)
        observe = self.repository.get_default_resource_pointer

        def observe_together(*args):
            result = observe(*args)
            barrier.wait(timeout=10)
            return result

        with patch.object(self.repository, "get_default_resource_pointer", side_effect=observe_together):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(self._set_default, (2, 3)))
        self.assertCountEqual([result.status_code for result in results], [200, 409], [r.text for r in results])
        winner = next(result for result in results if result.status_code == 200).json()
        loser = next(result for result in results if result.status_code == 409).json()
        self.assertTrue(winner["is_default"])
        self.assertTrue(winner["is_current"])
        self.assertEqual(loser["error"]["reason_code"], "template_default_conflict")
        self.assertEqual(self._default(), self.candidates[winner["version"]])
        self.assertEqual([(audit.target_id, audit.reason) for audit in self.audit.list_audit_events()],
                         [(winner["template_version_id"], f"选择版本 {winner['version']}")])

    def test_competing_updates_only_commit_one_switch(self):
        self._race()

    def test_competing_first_inserts_only_commit_one_switch(self):
        with self.backend.connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM resource_default_versions")
        self.assertIsNone(self._default())
        self._race()

    def test_readback_mismatch_rolls_back_pointer_and_audit(self):
        self._trigger("BEFORE UPDATE ON resource_default_versions FOR EACH ROW SET NEW.version = OLD.version")
        original = self.repository.get_default_resource_pointer("template", "default")
        response = self._set_default(2)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(self.repository.get_default_resource_pointer("template", "default"), original)
        self.assertEqual(self.audit.list_audit_events(), [])

    def test_audit_failure_rolls_back_pointer(self):
        self._trigger("BEFORE INSERT ON audit_events FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit test'")
        original = self.repository.get_default_resource_pointer("template", "default")
        response = self._set_default(2)
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(self.repository.get_default_resource_pointer("template", "default"), original)
        self.assertEqual(self.audit.list_audit_events(), [])

    def test_commit_response_loss_requires_readback(self):
        switch = self.repository.switch_default_resource_version
        connect = self.backend._connect_factory

        def connect_with_lost_commit_response():
            connection = connect()
            wrapped = Mock(wraps=connection)

            def commit_then_disconnect():
                connection.commit()
                raise pymysql.OperationalError(2013, "提交响应丢失")

            wrapped.commit.side_effect = commit_then_disconnect
            return wrapped

        def switch_with_fault(*args, **kwargs):
            with patch.object(self.backend, "_connect_factory", side_effect=connect_with_lost_commit_response):
                return switch(*args, **kwargs)

        with patch.object(self.repository, "switch_default_resource_version", side_effect=switch_with_fault):
            response = self._set_default(2)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["error"]["reason_code"], "template_default_commit_unknown")
        self.assertEqual(self._default(), self.candidates[2])
        self.assertEqual([audit.target_id for audit in self.audit.list_audit_events()], ["default@2"])

    def test_disable_after_switch_observation_rejects_switch(self):
        validated = Event()
        proceed = Event()
        validate = self.reader.validate_registered_template_package

        def pause_after_validation(record):
            validate(record)
            validated.set()
            self.assertTrue(proceed.wait(10))

        with patch.object(self.reader, "validate_registered_template_package", side_effect=pause_after_validation):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(self._set_default, 2)
                try:
                    self.assertTrue(validated.wait(10))
                    disabled = self.reader.disable_template_version("default", 2)
                    self.assertEqual(disabled.status, "disabled")
                finally:
                    proceed.set()
                result = pending.result(timeout=10)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(self._default().version, "1")
        self.assertEqual(self.audit.list_audit_events(), [])

    def test_changed_snapshot_after_validation_rejects_switch(self):
        validate = self.reader.validate_registered_template_package

        def change_record(record):
            validate(record)
            self.repository.save_resource_version(record.model_copy(update={"snapshot_hash": "sha256:" + "0" * 64}))

        with patch.object(self.reader, "validate_registered_template_package", side_effect=change_record):
            result = self._set_default(2)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(self._default().version, "1")
        self.assertEqual(self.audit.list_audit_events(), [])

    def test_switch_committing_first_prevents_disable(self):
        pointer_written = Event()
        disable_entered = Event()
        allow_commit = Event()
        readback = self.repository._get_default_resource_version
        disable = self.repository.disable_template_version_if_not_default

        def pause_after_write(*args):
            record = readback(*args)
            pointer_written.set()
            self.assertTrue(allow_commit.wait(10))
            return record

        def begin_disable(*args):
            disable_entered.set()
            return disable(*args)

        with (
            patch.object(self.repository, "_get_default_resource_version", side_effect=pause_after_write),
            patch.object(self.repository, "disable_template_version_if_not_default", side_effect=begin_disable),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            switching = pool.submit(self._set_default, 2)
            try:
                self.assertTrue(pointer_written.wait(10))
                disabling = pool.submit(self.reader.disable_template_version, "default", 2)
                self.assertTrue(disable_entered.wait(10))
            finally:
                allow_commit.set()
            response = switching.result(timeout=10)
            self.assertEqual(response.status_code, 200, response.text)
            with self.assertRaisesRegex((ValueError, ApplicationError), "默认资源版本"):
                disabling.result(timeout=10)
        self.assertEqual(self._default(), self.candidates[2])
