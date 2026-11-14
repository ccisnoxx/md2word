from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import yaml
from docx import Document

from app.core.config import Settings
from app.domains.resources.integrity import content_sha256, resource_payload_sha256
from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus
from app.domains.templates.catalog_migration import CatalogMigrationSnapshot, TemplateCatalogMigrationConflict
from app.domains.templates.manifest import resolve_bundled_template_seed
from app.domains.templates.models import TemplateCatalogItem
from app.domains.templates.repository import TemplateCatalogCommitUnknown
from scripts.ops.migrate_template_catalog import migrate_template_catalog


class MemoryMigrationRepository:
    def __init__(self, snapshot: CatalogMigrationSnapshot) -> None:
        self.snapshot = snapshot
        self.writes = 0
        self.fail_after_write = False

    def read_legacy_migration_snapshot(self) -> CatalogMigrationSnapshot:
        return self.snapshot

    def apply_legacy_migration(self, expected, additions, disables, default_template_id) -> None:
        if expected != self.snapshot:
            raise TemplateCatalogMigrationConflict()
        disabled = set(disables)
        self.snapshot = replace(
            self.snapshot,
            templates=(*self.snapshot.templates, *additions),
            versions=tuple(
                record.model_copy(update={"status": ResourceVersionStatus.DISABLED})
                if (record.resource_id, record.version) in disabled else record
                for record in self.snapshot.versions
            ),
            default_template_id=default_template_id or self.snapshot.default_template_id,
        )
        self.writes += 1
        if self.fail_after_write:
            raise TemplateCatalogCommitUnknown()


class TemplateCatalogMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.settings = Settings(
            _env_file=None,
            data_dir=str(self.root),
            templates_storage_path=str(self.root / "templates"),
            jobs_repository_backend="mysql",
        )
        self.manifest = self.root / "legacy.yaml"
        self.state = self.root / "legacy.json"
        self.version1 = self.make_version("custom", 1, ResourceVersionStatus.PUBLISHED)
        self.version2 = self.make_version("custom", 2, ResourceVersionStatus.DRAFT)
        self.orphan = self.make_version("orphan", 1, ResourceVersionStatus.DRAFT)
        self.repo = MemoryMigrationRepository(CatalogMigrationSnapshot(
            (), (self.version1, self.version2, self.orphan), {"custom": "1"}, None,
        ))
        self.item = {
            "id": "custom",
            "name": "旧版模板",
            "description": "保留说明",
            "enabled": True,
            "version": 2,
            "template_path": self.version2.payload["docx_path"],
            "disabled_versions": [2],
        }
        self.state.write_text(json.dumps({"default_template_id": "custom"}))
        self.write_manifest(self.item)

    def make_version(
        self, template_id: str, version: int, status: ResourceVersionStatus,
    ) -> ResourceVersionRecord:
        path = self.settings.templates_storage_dir / template_id / f"v{version}" / "template.docx"
        path.parent.mkdir(parents=True)
        document = Document()
        document.add_paragraph(f"{template_id}@{version}")
        document.save(path)
        payload = {
            "template_id": template_id,
            "version": version,
            "docx_path": str(path),
            "docx_sha256": content_sha256(path.read_bytes()),
            "layout_config_path": None,
            "layout_config_sha256": None,
        }
        return ResourceVersionRecord(
            resource_type="template", resource_id=template_id, version=str(version),
            status=status, payload=payload, snapshot_hash=resource_payload_sha256(payload),
        )

    def write_manifest(self, *items: dict) -> None:
        self.manifest.write_text(yaml.safe_dump({"templates": list(items)}, allow_unicode=True))

    def run_migration(self, mode: str = "dry-run", evidence: str | None = None) -> dict:
        return migrate_template_catalog(
            self.settings, self.repo, manifest_path=self.manifest, state_path=self.state,
            mode=mode, expected_evidence=evidence,
        )

    def test_import_preserves_registered_identity_and_exposes_unowned_assets(self) -> None:
        unowned = self.settings.templates_storage_dir / "custom" / "v2" / "extra.docx"
        unowned.write_bytes(b"unowned")
        missing = self.make_version("custom", 3, ResourceVersionStatus.SUPERSEDED)
        Path(missing.payload["docx_path"]).unlink()
        self.repo.snapshot = replace(self.repo.snapshot, versions=(*self.repo.snapshot.versions, missing))
        input_bytes = (self.manifest.read_bytes(), self.state.read_bytes())

        before = self.run_migration()
        self.assertEqual(self.repo.writes, 0)
        self.assertEqual(before["exit_code"], 0)
        self.assertEqual(before["additions"], ["custom"])
        self.assertEqual(before["disables"], [("custom", "2")])
        self.assertEqual(before["orphan_versions"], [("orphan", "1")])
        self.assertEqual(before["orphan_files"], ["custom/v2/extra.docx"])
        self.assertEqual(before["historical_issues"], [
            {"code": "template_docx_unavailable", "template_id": "custom", "version": "3"},
        ])
        self.assertEqual(self.run_migration("verify")["error"], "migration_not_applied")

        applied = self.run_migration("apply", before["evidence"])
        self.assertTrue(applied["applied"])
        self.assertEqual(self.repo.snapshot.templates[0].description, "保留说明")
        self.assertEqual(self.repo.snapshot.default_template_id, "custom")
        self.assertEqual(self.repo.snapshot.version_defaults, {"custom": "1"})
        self.assertEqual(self.repo.snapshot.versions[0], self.version1)
        self.assertEqual(self.repo.snapshot.versions[1].payload, self.version2.payload)
        self.assertEqual(self.repo.snapshot.versions[1].snapshot_hash, self.version2.snapshot_hash)
        self.assertEqual(self.repo.snapshot.versions[1].status, ResourceVersionStatus.DISABLED)
        self.assertEqual(self.repo.snapshot.versions[2:], (self.orphan, missing))
        self.assertTrue(unowned.is_file())
        self.assertEqual((self.manifest.read_bytes(), self.state.read_bytes()), input_bytes)

        self.assertEqual(self.run_migration("verify")["exit_code"], 0)
        self.assertFalse(self.run_migration("apply", before["evidence"])["applied"])
        self.assertEqual(self.repo.writes, 1)

    def test_default_conflict_and_missing_current_version_block_apply(self) -> None:
        self.item["version"] = 4
        self.write_manifest(self.item)
        self.repo.snapshot = replace(self.repo.snapshot, default_template_id="other")
        plan = self.run_migration()
        codes = {issue["code"] for issue in plan["conflicts"]}
        self.assertIn("legacy_version_not_registered", codes)
        self.assertIn("global_default_conflict", codes)
        self.assertEqual(self.run_migration("apply", plan["evidence"])["exit_code"], 1)
        self.assertEqual(self.repo.writes, 0)

    def test_hash_or_default_disable_conflict_blocks_apply(self) -> None:
        self.item["disabled_versions"] = [1]
        self.write_manifest(self.item)
        path = Path(self.version2.payload["docx_path"])
        document = Document(path)
        document.add_paragraph("变化")
        document.save(path)
        plan = self.run_migration()
        self.assertEqual(
            {issue["code"] for issue in plan["conflicts"]},
            {"template_docx_hash_mismatch", "legacy_disabled_version_is_default"},
        )
        self.assertEqual(self.run_migration("apply", plan["evidence"])["exit_code"], 1)
        self.assertEqual(self.repo.writes, 0)

    def test_concurrent_catalog_change_invalidates_evidence(self) -> None:
        before = self.run_migration()
        self.repo.snapshot = replace(self.repo.snapshot, versions=(self.version1, self.version2))
        result = self.run_migration("apply", before["evidence"])
        self.assertEqual(result["error"], "migration_evidence_changed")
        self.assertEqual(self.repo.writes, 0)

    def test_legacy_layout_bytes_are_part_of_evidence(self) -> None:
        layout = self.root / "legacy-layout.yaml"
        layout.write_text("first: 1")
        self.item["layout_config_path"] = str(layout)
        self.write_manifest(self.item)
        before = self.run_migration()
        self.assertEqual(before["exit_code"], 0)
        layout.write_text("first: 2")
        result = self.run_migration("apply", before["evidence"])
        self.assertEqual(result["error"], "migration_evidence_changed")
        self.assertEqual(self.repo.writes, 0)

    def test_existing_deleted_template_is_never_restored(self) -> None:
        self.state.unlink()
        deleted = TemplateCatalogItem(id="custom", name="已删除", enabled=False, deleted=True)
        self.repo.snapshot = replace(self.repo.snapshot, templates=(deleted,))
        report = self.run_migration()
        self.assertEqual(report["retained_deleted"], ["custom"])
        self.assertFalse(report["pending"])
        self.assertEqual(self.run_migration("apply", report["evidence"])["exit_code"], 0)
        self.assertEqual(self.repo.snapshot.templates, (deleted,))
        self.assertEqual(self.repo.writes, 0)

    def test_absent_state_uses_eligible_legacy_default(self) -> None:
        self.state.unlink()
        report = self.run_migration()
        self.assertEqual(report["default_to_import"], "custom")
        self.assertTrue(self.run_migration("apply", report["evidence"])["applied"])
        self.assertEqual(self.repo.snapshot.default_template_id, "custom")

    def test_absent_state_does_not_make_draft_the_default(self) -> None:
        self.state.unlink()
        self.item["disabled_versions"] = []
        self.write_manifest(self.item)
        self.repo.snapshot = replace(self.repo.snapshot, version_defaults={})
        report = self.run_migration()
        self.assertIn(
            {"code": "global_default_requires_published_version", "template_id": "custom", "version": None},
            report["conflicts"],
        )
        self.assertFalse(self.run_migration("apply", report["evidence"])["applied"])
        self.assertEqual(self.repo.writes, 0)

    def test_existing_metadata_does_not_get_overwritten(self) -> None:
        updated = TemplateCatalogItem(id="custom", name="新名称")
        self.repo.snapshot = replace(self.repo.snapshot, templates=(updated,))
        report = self.run_migration()
        self.assertIn({"code": "catalog_metadata_conflict", "template_id": "custom", "version": None},
                      report["conflicts"])
        self.assertEqual(self.run_migration("apply", report["evidence"])["exit_code"], 1)
        self.assertEqual(self.repo.snapshot.templates, (updated,))

    def test_explicit_bundled_default_can_be_registered_at_startup(self) -> None:
        seed = resolve_bundled_template_seed(self.settings.root_dir)
        self.write_manifest(seed.item.model_dump(mode="json"))
        self.state.write_text(json.dumps({"default_template_id": seed.item.id}))
        self.repo.snapshot = CatalogMigrationSnapshot((), (), {}, None)
        report = self.run_migration()
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["deferred_seed"], [seed.item.id])
        self.assertFalse(report["pending"])

    def test_bundled_seed_identity_conflict_detected_even_if_legacy_manifest_omits_it(self) -> None:
        seed = resolve_bundled_template_seed(self.settings.root_dir)
        self.state.unlink()
        replacement = self.make_version(seed.item.id, seed.item.version, ResourceVersionStatus.DRAFT)
        self.repo.snapshot = replace(self.repo.snapshot, versions=(*self.repo.snapshot.versions, replacement))
        report = self.run_migration()
        self.assertIn(
            {"code": "bundled_seed_identity_conflict", "template_id": seed.item.id, "version": replacement.version},
            report["conflicts"],
        )
        self.assertEqual(self.run_migration("apply", report["evidence"])["exit_code"], 1)
        self.assertEqual(self.repo.writes, 0)

    def test_bundled_seed_removed_in_legacy_directory_remains_deleted(self) -> None:
        seed = resolve_bundled_template_seed(self.settings.root_dir)
        payload = {
            "template_id": seed.item.id,
            "version": seed.item.version,
            "docx_path": seed.item.template_path,
            "docx_sha256": content_sha256(seed.template_path.read_bytes()),
            "layout_config_path": seed.item.layout_config_path,
            "layout_config_sha256": content_sha256(seed.layout_config_path.read_bytes()),
        }
        prior_seed = ResourceVersionRecord(
            resource_type="template", resource_id=seed.item.id, version=str(seed.item.version),
            status=ResourceVersionStatus.PUBLISHED, payload=payload, snapshot_hash=resource_payload_sha256(payload),
        )
        self.repo.snapshot = replace(self.repo.snapshot, versions=(*self.repo.snapshot.versions, prior_seed))
        self.state.unlink()
        report = self.run_migration()
        self.assertIn(
            {"code": "bundled_seed_absence_conflict", "template_id": seed.item.id, "version": None},
            report["conflicts"],
        )
        self.state.write_text(json.dumps({"default_template_id": "custom"}))
        report = self.run_migration()
        self.assertEqual(report["exit_code"], 0)
        self.assertTrue(self.run_migration("apply", report["evidence"])["applied"])
        tombstone = next(item for item in self.repo.snapshot.templates if item.id == seed.item.id)
        self.assertTrue(tombstone.deleted)
        self.assertFalse(tombstone.enabled)
        self.assertEqual(self.repo.snapshot.default_template_id, "custom")
        self.assertEqual(self.repo.snapshot.versions[-1], prior_seed)
        self.assertEqual(self.run_migration("verify")["retained_deleted"], [seed.item.id])
        self.assertEqual(self.repo.writes, 1)

    def test_tombstoned_bundled_template_skips_seed_validation(self) -> None:
        seed = resolve_bundled_template_seed(self.settings.root_dir)
        replacement = self.make_version(seed.item.id, seed.item.version, ResourceVersionStatus.DRAFT)
        self.repo.snapshot = replace(
            self.repo.snapshot,
            versions=(*self.repo.snapshot.versions, replacement),
            templates=(TemplateCatalogItem(id=seed.item.id, name=seed.item.name, enabled=False, deleted=True),),
        )
        report = self.run_migration()
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["retained_deleted"], [seed.item.id])
        self.assertTrue(self.run_migration("apply", report["evidence"])["applied"])
        self.assertEqual(self.run_migration("verify")["exit_code"], 0)
        self.assertEqual(self.repo.snapshot.versions[-1], replacement)

    def test_noncanonical_version_pointer_rejected(self) -> None:
        self.repo.snapshot = replace(self.repo.snapshot, version_defaults={"custom": "01"})
        report = self.run_migration()
        self.assertIn(
            {"code": "template_default_version_not_canonical", "template_id": "custom", "version": "01"},
            report["conflicts"],
        )
        self.assertEqual(self.run_migration("apply", report["evidence"])["exit_code"], 1)
        self.assertEqual(self.repo.writes, 0)

    def test_uncertain_commit_is_reported_and_verify_can_observe_it(self) -> None:
        before = self.run_migration()
        self.repo.fail_after_write = True
        result = self.run_migration("apply", before["evidence"])
        self.assertEqual(result["error"], "migration_commit_unknown_verify_before_retry")
        self.assertEqual(result["exit_code"], 1)
        self.assertFalse(result["applied"])
        self.assertEqual(self.run_migration("verify")["exit_code"], 0)
        self.assertEqual(self.repo.writes, 1)


if __name__ == "__main__":
    unittest.main()
