"""把停写部署的旧模板目录和默认选择导入 MySQL。"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
import sys
from typing import Protocol

import yaml
from pymysql import MySQLError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import Settings
from app.domains.resources.integrity import content_sha256, resource_payload_sha256
from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus
from app.domains.templates.catalog_migration import CatalogMigrationSnapshot, TemplateCatalogMigrationConflict
from app.domains.templates.manifest import BundledTemplateSeed, resolve_bundled_template_seed
from app.domains.templates.models import (
    TemplateCatalogItem, TemplateManifestItem, TemplatesManifest, TemplateState, validate_template_id,
)
from app.domains.templates.package_validator import TemplatePackageValidationError, validate_template_package
from app.domains.templates.read_service import TemplateReadService
from app.domains.templates.repository import TemplateCatalogCommitUnknown
from app.infrastructure.persistence.mysql.backend import MysqlPersistenceBackend, MysqlPersistenceConfig
from app.infrastructure.persistence.mysql.template_catalog import MysqlTemplateCatalogRepository


class MigrationRepository(Protocol):
    def read_legacy_migration_snapshot(self) -> CatalogMigrationSnapshot: ...

    def apply_legacy_migration(
        self,
        expected: CatalogMigrationSnapshot,
        additions: tuple[TemplateCatalogItem, ...],
        disables: tuple[tuple[str, str], ...],
        default_template_id: str | None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class MigrationIssue:
    code: str
    template_id: str | None = None
    version: str | None = None


@dataclass(slots=True)
class MigrationPlan:
    additions: list[TemplateCatalogItem] = field(default_factory=list)
    disables: list[tuple[str, str]] = field(default_factory=list)
    default_template_id: str | None = None
    conflicts: list[MigrationIssue] = field(default_factory=list)
    retained_deleted: list[str] = field(default_factory=list)
    deferred_seed: list[str] = field(default_factory=list)
    orphan_versions: list[tuple[str, str]] = field(default_factory=list)
    orphan_files: list[str] = field(default_factory=list)
    historical_issues: list[MigrationIssue] = field(default_factory=list)
    asset_evidence: dict[str, str] = field(default_factory=dict)

    @property
    def pending(self) -> bool:
        return bool(self.additions or self.disables or self.default_template_id is not None)


class MigrationInputError(ValueError):
    """只提供固定错误码，避免回显文件路径或配置值。"""


def _read_legacy_inputs(
    manifest_path: Path, state_path: Path,
) -> tuple[TemplatesManifest, TemplateState, str, str | None]:
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = TemplatesManifest.model_validate(yaml.safe_load(manifest_bytes))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise MigrationInputError("legacy_manifest_unreadable_or_invalid") from exc
    try:
        state_bytes = state_path.read_bytes()
    except FileNotFoundError:
        return manifest, TemplateState(), content_sha256(manifest_bytes), None
    except OSError as exc:
        raise MigrationInputError("legacy_state_unreadable_or_invalid") from exc
    try:
        state = TemplateState.model_validate_json(state_bytes)
    except ValueError as exc:
        raise MigrationInputError("legacy_state_unreadable_or_invalid") from exc
    return manifest, state, content_sha256(manifest_bytes), content_sha256(state_bytes)


def _valid_template_id(value: str) -> bool:
    try:
        return validate_template_id(value) == value
    except ValueError:
        return False


def _canonical_version(value: str) -> bool:
    return re.fullmatch(r"[1-9][0-9]*", value) is not None


def _asset_path(settings: Settings, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise MigrationInputError("asset_path_invalid")
    try:
        path = (settings.root_dir / value).resolve()
        asset_roots = (
            settings.data_path,
            settings.templates_storage_dir.resolve(),
            (settings.root_dir / "resources").resolve(),
        )
        if any(path.is_relative_to(root) for root in asset_roots):
            return path
    except (OSError, RuntimeError, ValueError) as exc:
        raise MigrationInputError("asset_path_invalid") from exc
    raise MigrationInputError("asset_outside_runtime_roots")


def _inspect_record(
    settings: Settings,
    validator: TemplateReadService,
    record: ResourceVersionRecord,
) -> str | None:
    payload = record.payload or {}
    try:
        _asset_path(settings, payload.get("docx_path"))
        if payload.get("layout_config_path") is not None:
            _asset_path(settings, payload["layout_config_path"])
        validator.validate_registered_template_package(record)
    except MigrationInputError as exc:
        return str(exc)
    except TemplatePackageValidationError as exc:
        return exc.code
    return None


def _inspect_legacy_item(
    settings: Settings,
    item: TemplateManifestItem,
    records: dict[str, ResourceVersionRecord],
    record_issues: dict[tuple[str, str], str],
    plan: MigrationPlan,
    *,
    canonical_seed_path: Path | None,
) -> None:
    current = records.get(str(item.version))
    if current is None:
        plan.conflicts.append(MigrationIssue("legacy_version_not_registered", item.id, str(item.version)))
        return
    try:
        old_docx = _asset_path(settings, item.template_path)
        registered_docx = _asset_path(settings, (current.payload or {}).get("docx_path"))
        managed_version_dir = (settings.templates_storage_dir / item.id / f"v{item.version}").resolve()
        registered_seed_copy = (
            canonical_seed_path is not None
            and old_docx == canonical_seed_path
            and managed_version_dir in registered_docx.parents
            and content_sha256(old_docx.read_bytes()) == (current.payload or {}).get("docx_sha256")
        )
        if old_docx != registered_docx and not registered_seed_copy:
            raise MigrationInputError("legacy_docx_path_conflict")
        # 目录级版式供后续上传使用。旧默认版本的实际版式由资源记录校验。
        if item.layout_config_path is not None:
            legacy_layout = _asset_path(settings, item.layout_config_path)
            try:
                plan.asset_evidence[item.id] = content_sha256(legacy_layout.read_bytes())
            except OSError as exc:
                raise MigrationInputError("legacy_layout_config_unavailable") from exc
    except MigrationInputError as exc:
        plan.conflicts.append(MigrationIssue(str(exc), item.id, current.version))
    except OSError:
        plan.conflicts.append(MigrationIssue("legacy_docx_unavailable", item.id, current.version))

    issue = record_issues.get((item.id, current.version))
    if issue is not None:
        plan.conflicts.append(MigrationIssue(issue, item.id, current.version))


def _plan_disabled_versions(
    item: TemplateManifestItem,
    records: dict[str, ResourceVersionRecord],
    default_version: str | None,
    record_issues: dict[tuple[str, str], str],
    plan: MigrationPlan,
) -> None:
    for version in sorted(set(item.disabled_versions)):
        key = str(version)
        record = records.get(key)
        if record is None:
            plan.conflicts.append(MigrationIssue("legacy_disabled_version_not_registered", item.id, key))
        elif default_version == key:
            plan.conflicts.append(MigrationIssue("legacy_disabled_version_is_default", item.id, key))
        elif record.status in {ResourceVersionStatus.DISABLED, ResourceVersionStatus.SUPERSEDED}:
            continue
        elif (issue := record_issues.get((item.id, key))) is not None:
            plan.conflicts.append(MigrationIssue(issue, item.id, key))
        else:
            plan.disables.append((item.id, key))


def _plan_legacy_default(
    state: TemplateState,
    manifest: TemplatesManifest,
    snapshot: CatalogMigrationSnapshot,
    target: dict[str, TemplateCatalogItem],
    records: dict[str, dict[str, ResourceVersionRecord]],
    record_issues: dict[tuple[str, str], str],
    plan: MigrationPlan,
) -> None:
    old_default = state.default_template_id
    existing_default = snapshot.default_template_id
    if old_default is not None and not _valid_template_id(old_default):
        plan.conflicts.append(MigrationIssue("legacy_default_id_invalid"))
        return
    if existing_default is not None and old_default is not None and existing_default != old_default:
        plan.conflicts.append(MigrationIssue("global_default_conflict", old_default))
        return
    selected = existing_default if existing_default is not None else old_default
    if selected is None:
        visible = [
            item for item in manifest.templates if item.enabled
            and (item.id in plan.deferred_seed or (
                (candidate := target.get(item.id)) is not None and candidate.enabled and not candidate.deleted
            ))
        ]
        legacy_seed = next((item for item in visible if item.is_default_seed), None)
        selected = legacy_seed.id if legacy_seed is not None else (visible[0].id if visible else None)
    if selected is None:
        return
    if existing_default is None and selected in plan.deferred_seed:
        return
    item = target.get(selected)
    if item is None or item.deleted or not item.enabled:
        plan.conflicts.append(MigrationIssue("global_default_template_unavailable", selected))
        return
    version = snapshot.version_defaults.get(selected)
    record = records.get(selected, {}).get(version) if version is not None else None
    if version is not None and not _canonical_version(version):
        plan.conflicts.append(MigrationIssue("template_default_version_not_canonical", selected, version))
    elif record is None or record.status != ResourceVersionStatus.PUBLISHED:
        plan.conflicts.append(MigrationIssue("global_default_requires_published_version", selected, version))
    elif (issue := record_issues.get((selected, record.version))) is not None:
        plan.conflicts.append(MigrationIssue(issue, selected, record.version))
    elif existing_default is None:
        plan.default_template_id = selected


def _plan_deleted_seed(
    seed: BundledTemplateSeed,
    state: TemplateState,
    existing: dict[str, TemplateCatalogItem],
    records: dict[str, dict[str, ResourceVersionRecord]],
    seen: set[str],
    plan: MigrationPlan,
) -> None:
    seed_id = seed.item.id
    if seed_id.lower() in seen or not records.get(seed_id):
        return
    current = existing.get(seed_id)
    if current is not None and current.deleted:
        plan.retained_deleted.append(seed_id)
    elif current is not None or state.default_template_id in {None, seed_id}:
        plan.conflicts.append(MigrationIssue("bundled_seed_absence_conflict", seed_id))
    else:
        # 旧清单无条目、库仍有版本，且旧默认已明确改到另一模板，符合旧删除入口的保留语义。
        plan.additions.append(TemplateCatalogItem.model_validate(
            seed.item.model_dump() | {"enabled": False, "deleted": True}
        ))


def _find_orphan_files(settings: Settings, records: tuple[ResourceVersionRecord, ...]) -> list[str]:
    storage = settings.templates_storage_dir.resolve()
    known_assets: set[Path] = set()
    for record in records:
        for key in ("docx_path", "layout_config_path"):
            value = (record.payload or {}).get(key)
            if value:
                try:
                    known_assets.add(_asset_path(settings, value))
                except MigrationInputError:
                    continue
    return sorted(
        path.relative_to(storage).as_posix()
        for path in storage.rglob("*")
        if path.suffix.lower() in {".docx", ".yaml", ".yml"} and path.is_file()
        and path.resolve() not in known_assets
    )


def build_migration_plan(
    settings: Settings,
    manifest: TemplatesManifest,
    state: TemplateState,
    snapshot: CatalogMigrationSnapshot,
) -> MigrationPlan:
    """以清单证明目录归属，以 MySQL 记录和实物哈希证明版本身份。"""

    plan = MigrationPlan()
    existing = {item.id: item for item in snapshot.templates}
    seed = resolve_bundled_template_seed(settings.root_dir)
    records: dict[str, dict[str, ResourceVersionRecord]] = {}
    validator = TemplateReadService(settings)
    record_issues: dict[tuple[str, str], str] = {}
    for record in snapshot.versions:
        records.setdefault(record.resource_id, {})[record.version] = record
        if (issue := _inspect_record(settings, validator, record)) is not None:
            record_issues[(record.resource_id, record.version)] = issue

    known_ids = {value.lower(): value for value in (*existing, *records, *snapshot.version_defaults)}
    seen: set[str] = set()
    for item in manifest.templates:
        if not _valid_template_id(item.id) or item.version < 1 or not item.name.strip():
            plan.conflicts.append(MigrationIssue("legacy_template_invalid"))
            continue
        key = item.id.lower()
        if key in seen or known_ids.get(key, item.id) != item.id:
            plan.conflicts.append(MigrationIssue("legacy_template_id_conflict", item.id))
            continue
        seen.add(key)
        current_catalog = existing.get(item.id)
        if current_catalog is not None and current_catalog.deleted:
            plan.retained_deleted.append(item.id)
            continue
        version_records = records.get(item.id, {})
        version_default = snapshot.version_defaults.get(item.id)
        seed_version = item.id == seed.item.id and item.version == seed.item.version and item.is_default_seed
        if not version_records and current_catalog is None and version_default is None and item == seed.item:
            try:
                fingerprint = validate_template_package(
                    template_path=seed.template_path, layout_config_path=seed.layout_config_path,
                )
            except TemplatePackageValidationError as exc:
                plan.conflicts.append(MigrationIssue(exc.code, item.id, str(item.version)))
            else:
                plan.asset_evidence[item.id] = resource_payload_sha256(asdict(fingerprint))
                plan.deferred_seed.append(item.id)
            continue
        _inspect_legacy_item(
            settings, item, version_records, record_issues, plan,
            canonical_seed_path=seed.template_path if seed_version else None,
        )
        _plan_disabled_versions(item, version_records, version_default, record_issues, plan)
        if (
            version_default is None and item == seed.item
            and (record := version_records.get(str(item.version))) is not None
            and record.status == ResourceVersionStatus.PUBLISHED
            and (item.id, str(item.version)) not in plan.disables
            and (item.id, record.version) not in record_issues
        ):
            plan.deferred_seed.append(item.id)
        if version_default is not None:
            default_record = version_records.get(version_default)
            if not _canonical_version(version_default):
                plan.conflicts.append(MigrationIssue("template_default_version_not_canonical", item.id, version_default))
            elif default_record is None or default_record.status != ResourceVersionStatus.PUBLISHED:
                plan.conflicts.append(MigrationIssue("template_default_requires_published_version", item.id, version_default))
            elif (issue := record_issues.get((item.id, version_default))) is not None:
                plan.conflicts.append(MigrationIssue(issue, item.id, version_default))
        candidate = TemplateCatalogItem.model_validate(
            item.model_dump(exclude={"is_default_seed", "version", "template_path", "disabled_versions"})
        )
        if current_catalog is None:
            plan.additions.append(candidate)
        elif current_catalog != candidate:
            plan.conflicts.append(MigrationIssue("catalog_metadata_conflict", item.id))

    _plan_deleted_seed(seed, state, existing, records, seen, plan)
    target = existing | {item.id: item for item in plan.additions}
    bundled_record = records.get(seed.item.id, {}).get(str(seed.item.version))
    bundled_item = target.get(seed.item.id)
    if bundled_record is not None and (bundled_item is None or not bundled_item.deleted):
        try:
            validator.validate_bundled_seed_identity(bundled_record, seed)
        except ValueError:
            plan.conflicts.append(MigrationIssue("bundled_seed_identity_conflict", seed.item.id, bundled_record.version))
    _plan_legacy_default(state, manifest, snapshot, target, records, record_issues, plan)
    plan.conflicts = list(dict.fromkeys(plan.conflicts))
    plan.orphan_versions = sorted(
        (record.resource_id, record.version) for record in snapshot.versions
        if record.resource_id not in target and record.resource_id.lower() not in seen
    )
    plan.orphan_files = _find_orphan_files(settings, snapshot.versions)
    blocking_keys = {(issue.template_id, issue.version, issue.code) for issue in plan.conflicts}
    plan.historical_issues = [
        MigrationIssue(code, template_id, version)
        for (template_id, version), code in sorted(record_issues.items())
        if (template_id, version, code) not in blocking_keys
    ]
    return plan


def migrate_template_catalog(
    settings: Settings,
    repository: MigrationRepository,
    *,
    manifest_path: Path,
    state_path: Path,
    mode: str,
    expected_evidence: str | None = None,
) -> dict[str, object]:
    report: dict[str, object] = {"mode": mode, "applied": False, "exit_code": 1}
    if settings.jobs_repository_backend != "mysql":
        return report | {"error": "mysql_backend_required"}
    try:
        manifest, state, manifest_hash, state_hash = _read_legacy_inputs(manifest_path, state_path)
        snapshot = repository.read_legacy_migration_snapshot()
        plan = build_migration_plan(settings, manifest, state, snapshot)
        evidence = resource_payload_sha256({
            "database": [settings.jobs_mysql_host, settings.jobs_mysql_port, settings.jobs_mysql_database],
            "manifest_sha256": manifest_hash,
            "state_sha256": state_hash,
            "templates": [item.model_dump(mode="json") for item in sorted(snapshot.templates, key=lambda item: item.id)],
            "versions": [
                record.model_dump(mode="json")
                for record in sorted(snapshot.versions, key=lambda record: (record.resource_id, record.version))
            ],
            "version_defaults": snapshot.version_defaults,
            "default_template_id": snapshot.default_template_id,
            "plan": asdict(plan) | {"additions": [item.model_dump(mode="json") for item in plan.additions]},
        })
        report.update({
            "evidence": evidence,
            "pending": plan.pending,
            "additions": [item.id for item in plan.additions],
            "disables": plan.disables,
            "default_to_import": plan.default_template_id,
            "conflicts": [asdict(issue) for issue in plan.conflicts],
            "retained_deleted": plan.retained_deleted,
            "deferred_seed": plan.deferred_seed,
            "orphan_versions": plan.orphan_versions,
            "orphan_files": plan.orphan_files,
            "historical_issues": [asdict(issue) for issue in plan.historical_issues],
        })
        if plan.conflicts:
            return report
        if mode == "verify" and plan.pending:
            return report | {"error": "migration_not_applied"}
        if mode == "apply" and plan.pending:
            if expected_evidence != evidence:
                return report | {"error": "migration_evidence_changed"}
            repository.apply_legacy_migration(
                snapshot, tuple(plan.additions), tuple(plan.disables), plan.default_template_id,
            )
            report["applied"] = True
        return report | {"exit_code": 0}
    except MigrationInputError as exc:
        return report | {"error": str(exc)}
    except TemplateCatalogMigrationConflict:
        return report | {"error": "migration_evidence_changed"}
    except TemplateCatalogCommitUnknown:
        return report | {"error": "migration_commit_unknown_verify_before_retry"}
    except (OSError, ValueError, RuntimeError, MySQLError, KeyboardInterrupt):
        return report | {"error": "migration_input_or_storage_error"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", dest="mode", action="store_const", const="dry-run", help="只读预检（默认）")
    modes.add_argument("--apply", dest="mode", action="store_const", const="apply", help="应用已核对的导入计划")
    modes.add_argument("--verify", dest="mode", action="store_const", const="verify", help="只读核对是否还有待导入项")
    parser.set_defaults(mode="dry-run")
    parser.add_argument("--legacy-manifest", type=Path, required=True, help="停写后保留的旧模板清单")
    parser.add_argument("--legacy-state", type=Path, help="旧全局默认状态文件，缺省使用部署配置")
    parser.add_argument("--expected-evidence", help="只读预检报告的 evidence 值")
    args = parser.parse_args(argv)
    if args.mode == "apply" and not args.expected_evidence:
        parser.error("--apply 必须提供 --expected-evidence")
    try:
        settings = Settings()
        backend = MysqlPersistenceBackend(
            MysqlPersistenceConfig(
                host=settings.jobs_mysql_host,
                port=settings.jobs_mysql_port,
                user=settings.jobs_mysql_user,
                password=settings.jobs_mysql_password,
                database=settings.jobs_mysql_database,
                charset=settings.jobs_mysql_charset,
                connect_timeout_seconds=settings.jobs_mysql_connect_timeout_seconds,
            ),
            initialize=False,
        )
    except (OSError, ValueError, RuntimeError):
        print(json.dumps({"error": "migration_configuration_invalid", "exit_code": 1}))
        return 1
    report = migrate_template_catalog(
        settings,
        MysqlTemplateCatalogRepository(backend),
        manifest_path=args.legacy_manifest,
        state_path=args.legacy_state or settings.template_state_file,
        mode=args.mode,
        expected_evidence=args.expected_evidence,
    )
    print(json.dumps(report, ensure_ascii=False))
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
