"""用独立文件快照验证模板 seed 身份与历史列表合同，不连接应用或数据库。"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any
from unittest import TestCase

import yaml
from docx import Document
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings
from app.domains.resources.models import ResourceType, ResourceVersionRecord, ResourceVersionStatus
from app.domains.resources.service import ResourceVersionService
from app.domains.templates.read_service import TemplateReadService
from app.domains.templates.schemas import TemplateAssetResponse


def _snapshot_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class _IsolatedSettings(Settings):
    """让真实路径派生规则只访问临时根目录，并隔离项目环境配置。"""

    model_config = SettingsConfigDict(env_file=None, env_prefix="MD2WORD_TEMPLATE_SEED_HISTORY_TEST_")
    fixture_root: Path

    @property
    def root_dir(self) -> Path:
        return self.fixture_root


class _MemoryResourceVersionRepository:
    """只实现本模块使用的仓储端口；复制记录，保留 create-only 和独立默认指针。"""

    def __init__(self) -> None:
        self.records: dict[tuple[ResourceType, str, str], ResourceVersionRecord] = {}
        self.defaults: dict[tuple[ResourceType, str], str] = {}
        self.writes: list[tuple[str, ResourceType, str, str]] = []

    def create_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord:
        key = (record.resource_type, record.resource_id, record.version)
        if key in self.records:
            raise ValueError(f"资源版本已存在: {record.resource_type}/{record.resource_id}@{record.version}")
        self.records[key] = record.model_copy(deep=True)
        self.writes.append(("create", *key))
        return record.model_copy(deep=True)

    def save_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord:
        key = (record.resource_type, record.resource_id, record.version)
        self.records[key] = record.model_copy(deep=True)
        self.writes.append(("save", *key))
        return record.model_copy(deep=True)

    def get_resource_version(
        self,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
    ) -> ResourceVersionRecord | None:
        record = self.records.get((resource_type, resource_id, version))
        return record.model_copy(deep=True) if record is not None else None

    def list_resource_versions(self, resource_type: ResourceType, resource_id: str) -> list[ResourceVersionRecord]:
        return [
            record.model_copy(deep=True)
            for (kind, identifier, _), record in self.records.items()
            if (kind, identifier) == (resource_type, resource_id)
        ]

    def set_default_resource_version(self, resource_type: ResourceType, resource_id: str, version: str) -> None:
        self.defaults[(resource_type, resource_id)] = version
        self.writes.append(("default", resource_type, resource_id, version))

    def get_default_resource_version(self, resource_type: ResourceType, resource_id: str) -> ResourceVersionRecord | None:
        version = self.defaults.get((resource_type, resource_id))
        return self.get_resource_version(resource_type, resource_id, version) if version is not None else None


class TemplateSeedHistoryTests(TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="md2word-template-seed-history-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.settings = _IsolatedSettings(
            _env_file=None,
            fixture_root=self.root,
            data_dir=str(self.root / "runtime"),
            templates_manifest_path=str(self.root / "manifest.yaml"),
            templates_storage_path=str(self.root / "managed"),
            template_state_path=str(self.root / "template-state.json"),
            default_template_id="default",
        )
        self.seed_path = self._docx("resources/templates/default/seed.docx", "当前内置模板")
        self.layout_path = self._yaml("resources/template_configs/seed.yaml", "宋体")
        self.manifest_item = {
            "id": "default",
            "name": "内置模板",
            "description": "原始说明",
            "enabled": True,
            "is_default_seed": True,
            "version": 2,
            "template_path": self._relative(self.seed_path),
            "layout_config_path": self._relative(self.layout_path),
            "render_policy": {"preserve_source_columns": True},
        }
        self._write_manifest()
        self._reset_services()

    def _reset_services(self) -> None:
        self.repository = _MemoryResourceVersionRepository()
        self.resources = ResourceVersionService(self.repository)
        self.reader = TemplateReadService(self.settings, self.resources)

    def _relative(self, path: Path) -> str:
        return str(path.relative_to(self.root))

    def _docx(self, relative_path: str, text: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        document = Document()
        document.add_paragraph(text)
        document.save(path)
        return path

    def _yaml(self, relative_path: str, font_name: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump({"schema_version": "template-config/v1", "normal": {"font_name": font_name}}, allow_unicode=True),
            encoding="utf-8",
        )
        return path

    def _write_manifest(self) -> None:
        self.settings.templates_manifest_file.write_text(
            yaml.safe_dump({"templates": [self.manifest_item]}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _payload(
        self,
        version: int | str,
        docx_path: Path,
        *,
        layout_path: Path | None = None,
        **updates: Any,
    ) -> dict[str, Any]:
        layout_path = layout_path if layout_path is not None else self.layout_path
        return {
            "template_id": "default",
            "version": version,
            "name": "内置模板",
            "description": "原始说明",
            "docx_path": self._relative(docx_path),
            "docx_sha256": "sha256:" + hashlib.sha256(docx_path.read_bytes()).hexdigest(),
            "layout_config_path": self._relative(layout_path),
            "layout_config_sha256": "sha256:" + hashlib.sha256(layout_path.read_bytes()).hexdigest(),
            "render_policy": {"preserve_source_columns": True},
            **updates,
        }

    def _register(
        self,
        version: int | str,
        payload: dict[str, Any],
        *,
        status: ResourceVersionStatus = ResourceVersionStatus.PUBLISHED,
        snapshot_hash: str | None = None,
    ) -> ResourceVersionRecord:
        return self.repository.create_resource_version(
            ResourceVersionRecord(
                resource_type="template",
                resource_id="default",
                version=str(version),
                status=status,
                snapshot_hash=snapshot_hash if snapshot_hash is not None else _snapshot_hash(payload),
                payload_ref=f"template:default@{version}",
                payload=payload,
            )
        )

    def _repository_snapshot(self) -> tuple[dict, dict, list]:
        return (
            {key: record.model_dump(mode="json") for key, record in self.repository.records.items()},
            self.repository.defaults.copy(),
            self.repository.writes.copy(),
        )

    def _assert_asset(self, asset: TemplateAssetResponse, path: Path) -> None:
        self.assertTrue(asset.exists)
        self.assertEqual(asset.file_name, path.name)
        self.assertEqual(asset.sha256, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_empty_bootstrap_creates_seed_once_and_initializes_default(self) -> None:
        self.reader.bootstrap_manifest_versions()

        record = self.repository.get_resource_version("template", "default", "2")
        self.assertIsNotNone(record)
        self.assertEqual(record.status, ResourceVersionStatus.PUBLISHED)
        self.assertEqual(record.payload, self._payload(2, self.seed_path))
        self.assertEqual(record.snapshot_hash, _snapshot_hash(record.payload))
        self.assertEqual(self.repository.defaults, {("template", "default"): "2"})
        self.assertEqual(self.repository.writes, [("create", "template", "default", "2"), ("default", "template", "default", "2")])
        before = self._repository_snapshot()

        self.reader.bootstrap_manifest_versions()

        self.assertEqual(self._repository_snapshot(), before)

    def test_new_seed_preserves_existing_old_default(self) -> None:
        old_path = self._docx("history/original.docx", "旧默认模板")
        old_record = self._register(1, self._payload(1, old_path))
        self.resources.set_default("template", "default", "1")

        self.reader.bootstrap_manifest_versions()

        self.assertEqual(self.repository.get_resource_version("template", "default", "1"), old_record)
        self.assertEqual(self.repository.get_default_resource_version("template", "default").version, "1")
        self.assertEqual(self.repository.get_resource_version("template", "default", "2").status, ResourceVersionStatus.PUBLISHED)
        before = self._repository_snapshot()
        self.reader.bootstrap_manifest_versions()
        self.assertEqual(self._repository_snapshot(), before)

    def test_bundled_identity_and_payload_conflicts_fail_without_writes(self) -> None:
        cases = ("docx_path", "docx_sha256", "docx_bytes", "template_id", "version", "snapshot_hash", "draft")
        old_path = self._docx("history/old-default.docx", "保留默认")
        other_path = self._docx("history/different.docx", "不同文件")
        for case in cases:
            with self.subTest(case=case):
                self._reset_services()
                self._register(1, self._payload(1, old_path))
                self.resources.set_default("template", "default", "1")
                payload = self._payload(2, self.seed_path)
                if case == "docx_path":
                    payload["docx_path"] = self._relative(other_path)
                elif case == "docx_sha256":
                    payload["docx_sha256"] = "sha256:" + "0" * 64
                elif case == "template_id":
                    payload["template_id"] = "other"
                elif case == "version":
                    payload["version"] = 99
                self._register(
                    2,
                    payload,
                    status=ResourceVersionStatus.DRAFT if case == "draft" else ResourceVersionStatus.PUBLISHED,
                    snapshot_hash="sha256:" + "0" * 64 if case == "snapshot_hash" else None,
                )
                if case == "docx_bytes":
                    self._docx(self._relative(self.seed_path), "同路径文件内容已改变")
                before = self._repository_snapshot()

                with self.assertRaisesRegex(ValueError, "default@2"):
                    self.reader.bootstrap_manifest_versions()

                self.assertEqual(self._repository_snapshot(), before)

    def test_metadata_and_publication_fields_do_not_replace_old_snapshot(self) -> None:
        payload = self._payload(
            2,
            self.seed_path,
            verification_job_id="verified-job",
            verification_note="已核验",
            verified_by="reviewer",
            verified_at="2026-10-31T08:00:00+00:00",
            publish_reason="验证后发布",
            published_by="publisher",
            published_at="2026-10-31T09:00:00+00:00",
        )
        self._register(2, payload)
        self.resources.set_default("template", "default", "2")
        updated_layout = self._yaml("metadata/updated-layout.yaml", "黑体")
        before = self._repository_snapshot()
        self.reader.update_template_metadata(
            "default",
            name="新的显示名称",
            description="新的描述",
            layout_config_path=self._relative(updated_layout),
            render_policy={"preserve_source_columns": False},
        )

        TemplateReadService(self.settings, self.resources).bootstrap_manifest_versions()

        self.assertEqual(self._repository_snapshot(), before)

    def test_closed_bundled_seeds_stay_closed_without_taking_default(self) -> None:
        old_path = self._docx("history/closed-default.docx", "继续使用旧默认")
        for status in (ResourceVersionStatus.DISABLED, ResourceVersionStatus.SUPERSEDED):
            for has_default in (False, True):
                with self.subTest(status=status, has_default=has_default):
                    self._reset_services()
                    if has_default:
                        self._register(1, self._payload(1, old_path))
                        self.resources.set_default("template", "default", "1")
                    self._register(2, self._payload(2, self.seed_path))
                    if status == ResourceVersionStatus.DISABLED:
                        self.resources.disable("template", "default", "2")
                    else:
                        self.resources.mark_superseded("template", "default", "2")
                    before = self._repository_snapshot()

                    self.reader.bootstrap_manifest_versions()

                    self.assertEqual(self._repository_snapshot(), before)

    def test_custom_upload_draft_is_not_published_by_bootstrap(self) -> None:
        self.reader.bootstrap_manifest_versions()
        upload = self._docx("uploads/custom.docx", "自定义上传")
        self.reader.create_template(
            template_id="custom",
            name="上传模板",
            description="自定义",
            source_path=upload,
            source_filename="custom.docx",
            layout_config_path=self._relative(self.layout_path),
        )
        before = self._repository_snapshot()

        self.reader.bootstrap_manifest_versions()

        self.assertEqual(self._repository_snapshot(), before)
        self.assertEqual(self.repository.get_resource_version("template", "custom", "1").status, ResourceVersionStatus.DRAFT)
        self.assertIsNone(self.repository.get_default_resource_version("template", "custom"))

    def test_seed_flag_is_required_even_for_file_inside_bundled_root(self) -> None:
        self.manifest_item["is_default_seed"] = False
        self._write_manifest()
        self._reset_services()
        self._register(2, self._payload(2, self.seed_path), status=ResourceVersionStatus.DRAFT)
        before = self._repository_snapshot()

        self.reader.bootstrap_manifest_versions()

        self.assertEqual(self._repository_snapshot(), before)
        self.assertIsNone(self.repository.get_default_resource_version("template", "default"))

    def test_default_replacement_draft_is_excluded_from_bundled_seed_check(self) -> None:
        for storage_path in (self.root / "managed", self.root / "resources/templates/uploads"):
            with self.subTest(storage_path=storage_path):
                self.settings = self.settings.model_copy(update={"templates_storage_path": str(storage_path)})
                self._write_manifest()
                self._reset_services()
                self.reader.bootstrap_manifest_versions()
                replacement = self._docx("uploads/replacement.docx", "替换内置模板")
                self.reader.replace_template_file("default", source_path=replacement, source_filename="replacement.docx")
                before = self._repository_snapshot()

                TemplateReadService(self.settings, self.resources).bootstrap_manifest_versions()

                self.assertEqual(self._repository_snapshot(), before)
                self.assertEqual(self.repository.get_resource_version("template", "default", "3").status, ResourceVersionStatus.DRAFT)
                self.assertEqual(self.repository.get_default_resource_version("template", "default").version, "2")

    def test_bundled_classification_uses_resolved_path(self) -> None:
        outside = self._docx("uploads/external.docx", "bundled 根目录外文件")
        linked_path = self.root / "resources/templates/default/external-link.docx"
        linked_path.symlink_to(outside)
        self.manifest_item["template_path"] = self._relative(linked_path)
        self._write_manifest()
        self._reset_services()
        self._register(2, self._payload(2, outside), status=ResourceVersionStatus.DRAFT)
        before = self._repository_snapshot()

        self.reader.bootstrap_manifest_versions()

        self.assertEqual(self._repository_snapshot(), before)

    def test_payload_only_history_retains_assets_status_and_publication_fields(self) -> None:
        old_path = self._docx("history/old.docx", "历史模板")
        old_layout = self._yaml("history/old-layout.yaml", "仿宋")
        metadata = {
            "render_policy": {"preserve_source_columns": False},
            "verification_job_id": "history-job",
            "verification_note": "历史验证记录",
            "verified_by": "history-reviewer",
            "verified_at": "2026-10-30T08:00:00+00:00",
            "publish_reason": "历史发布原因",
            "published_by": "history-publisher",
            "published_at": "2026-10-30T09:00:00+00:00",
        }
        old_record = self._register(1, self._payload(1, old_path, layout_path=old_layout, **metadata))
        self.resources.set_default("template", "default", "1")
        for version, status in ((3, ResourceVersionStatus.DRAFT), (4, ResourceVersionStatus.DISABLED), (5, ResourceVersionStatus.SUPERSEDED)):
            self._register(version, self._payload(version, old_path, layout_path=old_layout), status=status)
        self.reader.bootstrap_manifest_versions()
        before = self._repository_snapshot()

        versions = self.reader.list_template_versions("default")

        self.assertEqual([item.version for item in versions], [5, 4, 3, 2, 1])
        self.assertEqual([item.status for item in versions], ["superseded", "disabled", "draft", "published", "published"])
        history = versions[-1]
        self.assertEqual(history.template_version_id, "default@1")
        self.assertTrue(history.is_default)
        self.assertTrue(history.is_current)
        self.assertTrue(all(not item.is_default and not item.is_current for item in versions[:-1]))
        self.assertEqual(history.snapshot_hash, old_record.snapshot_hash)
        self._assert_asset(history.template, old_path)
        self._assert_asset(history.layout_config, old_layout)
        for key, value in metadata.items():
            actual = getattr(history, key)
            self.assertEqual(actual.isoformat() if key.endswith("_at") else actual, value)
        self.assertEqual(self._repository_snapshot(), before)

    def test_registered_paths_win_over_candidates_and_missing_assets_stay_missing(self) -> None:
        for source in ("managed", "manifest", "payload_only"):
            with self.subTest(source=source):
                self.settings = self.settings.model_copy(update={"templates_storage_path": str(self.root / source / "managed")})
                self._reset_services()
                version = 2 if source == "manifest" else 1
                target = self._docx(f"history/{source}-target.docx", f"快照目标 {source}")
                candidate = self.seed_path
                if source == "managed":
                    candidate = self._docx(f"{source}/managed/default/v1/a-residual.docx", "目录残留")
                    target = self._docx(f"{source}/managed/default/v1/z-target.docx", "目录内快照目标")
                self._register(version, self._payload(version, target))
                before = self._repository_snapshot()

                listed = {item.version: item for item in self.reader.list_template_versions("default")}

                self._assert_asset(listed[version].template, target)
                target.unlink()
                listed_missing = {item.version: item for item in self.reader.list_template_versions("default")}
                self.assertFalse(listed_missing[version].template.exists)
                self.assertEqual(listed_missing[version].template.file_name, target.name)
                self.assertIsNone(listed_missing[version].template.sha256)
                self.assertTrue(candidate.exists())
                self.assertEqual(self._repository_snapshot(), before)

    def test_integer_alias_records_own_overlapping_paths_and_missing_assets(self) -> None:
        for source in ("managed", "manifest", "payload_only"):
            for has_later_alias in (False, True):
                with self.subTest(source=source, has_later_alias=has_later_alias):
                    case = f"{source}-{has_later_alias}"
                    self.settings = self.settings.model_copy(update={"templates_storage_path": str(self.root / case / "managed")})
                    self._reset_services()
                    version = 2 if source == "manifest" else 1
                    target = self._docx(f"history/{case}-old.docx", "别名记录拥有的历史文件")
                    old_layout = self._yaml(f"history/{case}-layout.yaml", "仿宋")
                    candidate = self.seed_path
                    if source == "managed":
                        candidate = self._docx(f"{case}/managed/default/v1/a-residual.docx", "不能顶替快照的目录残留")
                    metadata = {
                        "render_policy": {"preserve_source_columns": False},
                        "verification_job_id": "alias-history-job",
                        "verification_note": "别名版本验证记录",
                        "verified_by": "alias-reviewer",
                        "verified_at": "2026-10-30T08:00:00+00:00",
                        "publish_reason": "别名版本发布原因",
                        "published_by": "alias-publisher",
                        "published_at": "2026-10-30T09:00:00+00:00",
                    }
                    first_key = f"00{version}" if has_later_alias else f"0{version}"
                    record = self._register(
                        first_key,
                        self._payload(version, target, layout_path=old_layout, **metadata),
                        status=ResourceVersionStatus.DISABLED,
                    )
                    if has_later_alias:
                        later_path = self._docx(f"history/{case}-later.docx", "后来的等价别名")
                        self._register(f"0{version}", self._payload(version, later_path), status=ResourceVersionStatus.DRAFT)
                    before = self._repository_snapshot()

                    for missing in (False, True):
                        if missing:
                            target.unlink()
                        versions = self.reader.list_template_versions("default")
                        selected = [item for item in versions if item.version == version]

                        self.assertEqual(len(selected), 1)
                        item = selected[0]
                        self.assertEqual(item.status, "disabled")
                        self.assertEqual(item.snapshot_hash, record.snapshot_hash)
                        self._assert_asset(item.layout_config, old_layout)
                        for key, value in metadata.items():
                            actual = getattr(item, key)
                            self.assertEqual(actual.isoformat() if key.endswith("_at") else actual, value)
                        if missing:
                            self.assertFalse(item.template.exists)
                            self.assertEqual(item.template.file_name, target.name)
                            self.assertIsNone(item.template.sha256)
                        else:
                            self._assert_asset(item.template, target)
                        self.assertTrue(candidate.exists())
                        self.assertEqual(self._repository_snapshot(), before)

    def test_integer_versions_are_deduplicated_and_non_integer_keys_are_ignored(self) -> None:
        old_path = self._docx("history/deduplicated.docx", "规范版本拥有的文件")
        alias_path = self._docx("history/alias.docx", "别名版本拥有的不同文件")
        self._docx("managed/default/v1/a.docx", "目录版本一")
        self._docx("managed/default/v01/a.docx", "目录版本一别名")
        self._docx("managed/default/v2/a.docx", "目录当前版本")
        self._register(1, self._payload(1, old_path))
        self._register(2, self._payload(2, self.seed_path))
        self._register(
            "03",
            self._payload(3, alias_path, render_policy={"preserve_source_columns": False}, publish_reason="别名发布原因"),
            status=ResourceVersionStatus.DRAFT,
        )
        canonical = self._register(3, self._payload(3, old_path, publish_reason="规范版本发布原因"))
        for version in ("legacy-v4", "2.5"):
            self._register(version, self._payload(version, alias_path))
        self.resources.set_default("template", "default", "3")
        before = self._repository_snapshot()

        versions = self.reader.list_template_versions("default")

        self.assertEqual([item.version for item in versions], [3, 2, 1])
        self._assert_asset(versions[0].template, old_path)
        self.assertEqual(versions[0].status, "published")
        self.assertEqual(versions[0].snapshot_hash, canonical.snapshot_hash)
        self.assertEqual(versions[0].render_policy, {"preserve_source_columns": True})
        self.assertEqual(versions[0].publish_reason, "规范版本发布原因")
        self._assert_asset(versions[1].template, self.seed_path)
        self.assertTrue(versions[0].is_default)
        self.assertEqual(self._repository_snapshot(), before)

    def test_without_version_service_keeps_legacy_directory_and_default_view(self) -> None:
        old_path = self._docx("managed/default/v1/legacy.docx", "legacy 历史")
        current_path = self._docx("managed/default/v2/legacy-current.docx", "legacy 当前目录文件")
        self.manifest_item["disabled_versions"] = [1]
        self._write_manifest()
        legacy = TemplateReadService(self.settings)
        self.assertFalse(self.settings.template_state_file.exists())
        before = self._repository_snapshot()

        legacy.bootstrap_manifest_versions()
        versions = legacy.list_template_versions("default")

        self.assertEqual([item.version for item in versions], [2, 1])
        self.assertEqual([item.status for item in versions], ["published", "disabled"])
        self.assertTrue(versions[0].is_current)
        self.assertTrue(versions[0].is_default)
        self.assertFalse(versions[1].is_default)
        self._assert_asset(versions[0].template, current_path)
        self._assert_asset(versions[1].template, old_path)
        self.assertTrue(all(item.snapshot_hash is None for item in versions))
        self.assertEqual(json.loads(self.settings.template_state_file.read_text(encoding="utf-8")), {"default_template_id": "default"})
        self.assertEqual(self._repository_snapshot(), before)
