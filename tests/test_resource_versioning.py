from __future__ import annotations

# tests/test_resource_versioning.py: 校验通用资源版本状态机和 MySQL metadata 持久化。

from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from app.core.config import Settings
from app.domains.resources.models import ResourceType, ResourceVersionRecord, ResourceVersionStatus
from app.infrastructure.persistence import build_mysql_persistence_adapters
from app.main import build_runtime
from app.domains.resources.service import ResourceVersionService
from tests.test_database_job_repository import _FakeMysqlDatabase, _mysql_config


HASH_V1 = "sha256:" + "1" * 64
HASH_V2 = "sha256:" + "2" * 64


class _MemoryResourceVersionRepository:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str], ResourceVersionRecord] = {}
        self.defaults: dict[tuple[str, str], str] = {}

    def save_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord:
        self.records[(record.resource_type, record.resource_id, record.version)] = record
        return record

    def get_resource_version(
        self,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
    ) -> ResourceVersionRecord | None:
        return self.records.get((resource_type, resource_id, version))

    def list_resource_versions(self, resource_type: ResourceType, resource_id: str) -> list[ResourceVersionRecord]:
        return [
            record
            for key, record in sorted(self.records.items())
            if key[0] == resource_type and key[1] == resource_id
        ]

    def set_default_resource_version(self, resource_type: ResourceType, resource_id: str, version: str) -> None:
        self.defaults[(resource_type, resource_id)] = version

    def get_default_resource_version(self, resource_type: ResourceType, resource_id: str) -> ResourceVersionRecord | None:
        version = self.defaults.get((resource_type, resource_id))
        if version is None:
            return None
        return self.get_resource_version(resource_type, resource_id, version)


class ResourceVersionServiceTests(TestCase):
    def setUp(self) -> None:
        self.repository = _MemoryResourceVersionRepository()
        self.service = ResourceVersionService(self.repository)

    def test_publish_make_default_and_resolve(self):
        self.service.create_or_update_draft(
            resource_type="template",
            resource_id="datasheet-default",
            version="1.0.0",
            snapshot_hash=HASH_V1,
            payload_ref="artifact:docx-1",
            payload={"name": "Default"},
        )

        published = self.service.publish("template", "datasheet-default", "1.0.0", make_default=True)
        resolved = self.service.resolve_default("template", "datasheet-default")

        self.assertEqual(published.status, ResourceVersionStatus.PUBLISHED)
        self.assertEqual(resolved.version, "1.0.0")
        self.assertEqual(resolved.status, "published")
        self.assertEqual(resolved.snapshot_hash, HASH_V1)

    def test_published_version_cannot_be_modified_through_draft_path(self):
        self.service.create_or_update_draft(
            resource_type="term_rule_set",
            resource_id="electronics-default",
            version="2026.05.28-1",
            snapshot_hash=HASH_V1,
        )
        self.service.publish("term_rule_set", "electronics-default", "2026.05.28-1")

        with self.assertRaises(ValueError):
            self.service.create_or_update_draft(
                resource_type="term_rule_set",
                resource_id="electronics-default",
                version="2026.05.28-1",
                snapshot_hash=HASH_V2,
            )

        stored = self.repository.get_resource_version("term_rule_set", "electronics-default", "2026.05.28-1")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.snapshot_hash, HASH_V1)

    def test_default_pointer_only_accepts_published_versions(self):
        self.service.create_or_update_draft(
            resource_type="translation_profile",
            resource_id="direct-default",
            version="1.0.0",
            snapshot_hash=HASH_V1,
        )

        with self.assertRaises(ValueError):
            self.service.set_default("translation_profile", "direct-default", "1.0.0")

        self.assertIsNone(self.repository.get_default_resource_version("translation_profile", "direct-default"))

    def test_default_version_must_be_switched_before_disable_or_supersede(self):
        for version, snapshot_hash in (("1.0.0", HASH_V1), ("1.1.0", HASH_V2)):
            self.service.create_or_update_draft(
                resource_type="template",
                resource_id="datasheet-default",
                version=version,
                snapshot_hash=snapshot_hash,
            )
            self.service.publish("template", "datasheet-default", version, make_default=version == "1.0.0")

        with self.assertRaises(ValueError):
            self.service.disable("template", "datasheet-default", "1.0.0")
        with self.assertRaises(ValueError):
            self.service.mark_superseded("template", "datasheet-default", "1.0.0")

        self.service.set_default("template", "datasheet-default", "1.1.0")
        disabled = self.service.disable("template", "datasheet-default", "1.0.0")

        self.assertEqual(disabled.status, ResourceVersionStatus.DISABLED)

    def test_rollback_switches_default_pointer_without_changing_versions(self):
        for version, snapshot_hash in (("1.0.0", HASH_V1), ("1.1.0", HASH_V2)):
            self.service.create_or_update_draft(
                resource_type="template",
                resource_id="datasheet-default",
                version=version,
                snapshot_hash=snapshot_hash,
                payload={"version": version},
            )
            self.service.publish("template", "datasheet-default", version, make_default=version == "1.1.0")

        resolved = self.service.rollback_default("template", "datasheet-default", "1.0.0")
        old_version = self.repository.get_resource_version("template", "datasheet-default", "1.0.0")

        self.assertEqual(resolved.version, "1.0.0")
        self.assertEqual(old_version.payload, {"version": "1.0.0"})
        self.assertEqual(old_version.status, ResourceVersionStatus.PUBLISHED)


class MysqlResourceVersionRepositoryTests(TestCase):
    def test_mysql_repository_persists_resource_versions_and_default_pointer(self):
        fake_mysql = _FakeMysqlDatabase()
        repository = build_mysql_persistence_adapters(
            _mysql_config(),
            connect_factory=fake_mysql.connect,
        ).resource_version_repository
        service = ResourceVersionService(repository)

        service.create_or_update_draft(
            resource_type="template",
            resource_id="datasheet-default",
            version="1.0.0",
            snapshot_hash=HASH_V1,
            payload_ref="artifact:docx-1",
            payload={"layout": "default"},
        )
        service.publish("template", "datasheet-default", "1.0.0", make_default=True)

        resolved = service.resolve_default("template", "datasheet-default")
        versions = repository.list_resource_versions("template", "datasheet-default")

        self.assertEqual(resolved.version, "1.0.0")
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].payload, {"layout": "default"})

    def test_mysql_runtime_exposes_resource_version_service(self):
        fake_mysql = _FakeMysqlDatabase()

        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                _env_file=None,
                data_dir=str(temp_dir),
                jobs_repository_backend="mysql",
            )
            with patch(
                "app.main.build_persistence_adapters",
                lambda _settings: build_mysql_persistence_adapters(
                    _mysql_config(),
                    connect_factory=fake_mysql.connect,
                ),
            ):
                runtime = build_runtime(settings)

        self.assertIsNotNone(runtime.resource_version_service)
