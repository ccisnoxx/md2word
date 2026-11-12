from __future__ import annotations

# app/domains/templates/read_service.py: 读取模板清单并映射为 templates API 响应模型。

import hashlib
import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import yaml
from pydantic import ValidationError

from app.domains.audit.models import ActorContext
from app.core.config import Settings
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.resources.integrity import content_sha256, resource_payload_sha256
from app.domains.resources.models import ResolvedResourceVersion, ResourceVersionRecord, ResourceVersionStatus, utc_now
from app.domains.templates.layout_config_schema import (
    apply_layout_changes,
    editor_field_schema,
    load_layout_config_yaml,
    split_layout_config,
    validate_layout_config,
)
from app.domains.templates.manifest import load_template_manifest
from app.domains.templates.models import TemplateManifestItem, TemplateState, TemplatesManifest
from app.domains.templates.package_validator import (
    TemplatePackageFingerprint,
    TemplatePackageValidationError,
    read_template_resource,
    validate_template_package,
    validate_template_package_content,
)
from app.domains.templates.schemas import (
    TemplateAssetResponse,
    TemplateDetailResponse,
    TemplateLayoutConfigResponse,
    TemplateListItemResponse,
    TemplateVersionResponse,
)


@dataclass(frozen=True, slots=True)
class AssetSpec:
    key: str
    label: str
    path_getter: str


@dataclass(frozen=True, slots=True)
class TemplateVersionSelection:
    """Worker 渲染时使用的模板版本解析结果。"""

    template_id: str
    version: int
    template_version_id: str
    template_path: Path
    layout_config_path: Path | None
    render_policy: dict[str, Any]


class TemplateLayoutConfigConflict(RuntimeError):
    """样式编辑基线或默认版本已经变化。"""

    def __init__(
        self,
        message: str,
        *,
        active_template_version_id: str,
        config_sha256: str | None,
    ) -> None:
        super().__init__(message)
        self.active_template_version_id = active_template_version_id
        self.config_sha256 = config_sha256


ASSET_SPECS: tuple[AssetSpec, ...] = (
    AssetSpec(key="template", label="Word 模板", path_getter="default_template_path"),
    AssetSpec(key="layout_config", label="页面布局 YAML", path_getter="layout_config_path"),
    AssetSpec(key="subscript_config", label="术语上下标 YAML", path_getter="subscript_config_path"),
)

TEMPLATE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
SYSTEM_LOGGER = logging.getLogger("system")


class TemplateReadService:
    def __init__(
        self,
        settings: Settings,
        resource_version_service: Any | None = None,
        audit_service: Any | None = None,
        document_job_repository: DocumentJobRepositoryProtocol | None = None,
    ) -> None:
        self.settings = settings
        self.resource_version_service = resource_version_service
        self.audit_service = audit_service
        self.document_job_repository = document_job_repository
        self._manifest_cache: TemplatesManifest | None = None

    def list_templates(self, *, url_for: Callable[..., str] | None) -> list[TemplateListItemResponse]:
        return [self.get_template_detail(item.id, url_for=url_for).to_list_item() for item in self._visible_templates()]

    def bootstrap_manifest_versions(self) -> None:
        """完整预检待登记资源，再登记缺失 seed 或建立缺省默认指针。"""

        service = self.resource_version_service
        if service is None:
            return
        prepared: list[tuple[ResourceVersionRecord, bool]] = []
        bundled_templates_dir = (self.settings.root_dir / "resources" / "templates").resolve()
        for template in self._visible_templates():
            version = str(template.version)
            record = service.repository.get_resource_version("template", template.id, version)
            template_path = self._resolve_manifest_path(template.template_path)
            layout_path = self._resolve_manifest_path(template.layout_config_path) if template.layout_config_path else None
            if not template_path.exists() or (layout_path is not None and not layout_path.exists()):
                raise FileNotFoundError(f"模板 seed 资源不存在: {template.id}@{version}")
            if record is None:
                fingerprint = validate_template_package(template_path=template_path, layout_config_path=layout_path)
                payload = self._build_template_version_payload(
                    template=template,
                    version=template.version,
                    template_path=template_path,
                    layout_config_path=template.layout_config_path,
                    render_policy=template.render_policy,
                    fingerprint=fingerprint,
                )
                now = utc_now()
                prepared.append((ResourceVersionRecord(
                    resource_type="template",
                    resource_id=template.id,
                    version=version,
                    status=ResourceVersionStatus.PUBLISHED,
                    snapshot_hash=resource_payload_sha256(payload),
                    payload_ref=f"template:{template.id}@{version}",
                    payload=payload,
                    created_at=now,
                    updated_at=now,
                ), True))
                continue

            resolved_template_path = template_path.resolve()
            managed_version_dir = (self.settings.templates_storage_dir / template.id / f"v{version}").resolve()
            is_bundled_seed = (
                template.is_default_seed
                and resolved_template_path.is_relative_to(bundled_templates_dir)
                # 上传目录即使位于 bundled 根目录内，其中的 draft 也不是 seed。
                and not resolved_template_path.is_relative_to(managed_version_dir)
            )
            if is_bundled_seed:
                self._check_bundled_seed_identity(record, resolved_template_path, managed_version_dir)
            if record.status == ResourceVersionStatus.PUBLISHED and (
                is_bundled_seed or service.repository.get_default_resource_version("template", template.id) is None
            ):
                self._validate_registered_template_package(record)
            prepared.append((record, False))

        for record, create in prepared:
            if create:
                record = service.repository.create_resource_version(record)
            if (
                record.status == ResourceVersionStatus.PUBLISHED
                and service.repository.get_default_resource_version("template", record.resource_id) is None
            ):
                service.repository.set_default_resource_version("template", record.resource_id, record.version)

    def _check_bundled_seed_identity(
        self, record: ResourceVersionRecord, seed_path: Path, managed_version_dir: Path,
    ) -> None:
        """校验已有 seed 身份，允许同内容的受管副本及 manifest 元数据变化。"""

        payload = record.payload or {}
        registered_docx_path = self._payload_text(payload, "docx_path")
        registered_path = self._resolve_manifest_path(registered_docx_path).resolve() if registered_docx_path else None
        if (
            record.status == ResourceVersionStatus.DRAFT
            or payload.get("template_id") != record.resource_id
            or str(payload.get("version")) != record.version
            or payload.get("docx_sha256") != content_sha256(read_template_resource(seed_path, kind="docx"))
            or registered_path is None
            or not (registered_path == seed_path or managed_version_dir in registered_path.parents)
            or record.snapshot_hash != resource_payload_sha256(payload)
        ):
            raise ValueError(f"模板 seed 版本与已登记资源冲突: {record.resource_id}@{record.version}")

    def get_template_detail(
        self,
        template_id: str,
        *,
        url_for: Callable[..., str] | None,
    ) -> TemplateDetailResponse | None:
        template = self._get_template_item(template_id)
        if template is None or not template.enabled:
            return None

        active_version = self._resource_default_version(template.id) or template.version
        active_record = self._resource_records_by_version(template.id).get(str(active_version))
        active_payload = active_record.payload if active_record is not None else None
        template_path = self._template_version_path(template, active_version, active_payload)
        template_asset = self._build_asset(
            path=template_path,
            label="Word 模板",
            download_url=(
                str(url_for("download_template", template_id=template_id))
                if url_for is not None and template_path is not None and template_path.exists()
                else None
            ),
        )
        layout_asset = self._build_asset(
            path=self._template_version_layout_config_path(template, active_payload),
            label="页面布局 YAML",
            download_url=None,
        )
        subscript_asset = self._build_asset(
            path=self.settings.subscript_config_path,
            label="术语上下标 YAML",
            download_url=None,
        )

        current_default_id = self.get_default_template_id()
        name = template.name
        return TemplateDetailResponse(
            id=template.id,
            name=name,
            description=template.description,
            version=active_version,
            is_default=template.id == current_default_id,
            downloadable=template_asset.exists,
            download_url=template_asset.download_url,
            template=template_asset,
            layout_config=layout_asset,
            subscript_config=subscript_asset,
        )

    def create_template(
        self,
        *,
        template_id: str,
        name: str,
        description: str,
        source_path: Path,
        source_filename: str,
        layout_config_path: str | None,
        render_policy: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> None:
        """新增模板记录并把第一个 DOCX 文件保存为 version 1。"""

        normalized_id = self._validate_template_id(template_id)
        if self._get_template_item(normalized_id) is not None:
            raise ValueError(f"模板已存在: {normalized_id}")

        manifest = self._load_manifest()
        normalized_layout_config_path = self._normalize_optional_text(layout_config_path)
        normalized_render_policy = render_policy or {}
        normalized_name = self._normalize_required_text(name, "name")
        fingerprint = self._preflight_template_package(source_path, normalized_layout_config_path)
        stored_path = self._store_versioned_template_file(
            template_id=normalized_id,
            version=1,
            source_path=source_path,
            source_filename=source_filename,
        )
        created_template = TemplateManifestItem(
            id=normalized_id,
            name=normalized_name,
            description=description.strip(),
            enabled=enabled,
            is_default_seed=False,
            version=1,
            template_path=self._to_repo_relative_path(stored_path),
            layout_config_path=normalized_layout_config_path,
            render_policy=normalized_render_policy,
        )
        self._create_template_resource_draft(
            template=created_template,
            version=1,
            template_path=stored_path,
            layout_config_path=normalized_layout_config_path,
            render_policy=normalized_render_policy,
            fingerprint=fingerprint,
            require_service=False,
        )
        manifest.templates.append(created_template)
        self._write_manifest(manifest)

    def update_template_metadata(
        self,
        template_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        layout_config_path: str | None = None,
        render_policy: dict[str, Any] | None = None,
    ) -> None:
        """更新模板 manifest 元数据，不改已登记的 DOCX 版本。"""

        template = self._require_template_item(template_id)
        if enabled is False and self.get_default_template_id() == template.id:
            raise ValueError(f"当前默认模板不能停用: {template.id}")
        updates: dict = {}
        if name is not None:
            updates["name"] = self._normalize_required_text(name, "name")
        if description is not None:
            updates["description"] = description.strip()
        if enabled is not None:
            updates["enabled"] = enabled
        if layout_config_path is not None:
            updates["layout_config_path"] = self._normalize_optional_text(layout_config_path)
        if render_policy is not None:
            updates["render_policy"] = render_policy
        if not updates:
            return
        self._replace_template_item(template.model_copy(update=updates))

    def replace_template_file(
        self,
        template_id: str,
        *,
        source_path: Path,
        source_filename: str,
    ) -> None:
        """替换模板 DOCX 文件并递增 manifest 中的当前版本号。"""

        template = self._require_template_item(template_id)
        fingerprint = self._preflight_template_package(source_path, template.layout_config_path)
        next_version = self._next_template_version(template)
        stored_path = self._store_versioned_template_file(
            template_id=template.id,
            version=next_version,
            source_path=source_path,
            source_filename=source_filename,
        )
        updated_template = template.model_copy(
            update={
                "version": next_version,
                "template_path": self._to_repo_relative_path(stored_path),
            }
        )
        self._create_template_resource_draft(
            template=updated_template,
            version=next_version,
            template_path=stored_path,
            layout_config_path=updated_template.layout_config_path,
            render_policy=updated_template.render_policy,
            fingerprint=fingerprint,
            require_service=False,
        )
        self._replace_template_item(updated_template)

    def create_template_version(
        self,
        template_id: str,
        *,
        source_path: Path,
        source_filename: str,
        layout_config_path: str | None = None,
        render_policy: dict[str, Any] | None = None,
    ) -> TemplateVersionResponse:
        """为模板创建下一版 draft；发布状态由 ResourceVersionService 统一管理。"""

        self._require_resource_version_service()
        template = self._require_template_item(template_id)
        normalized_layout_config_path = (
            self._normalize_optional_text(layout_config_path)
            if layout_config_path is not None
            else template.layout_config_path
        )
        normalized_render_policy = render_policy if render_policy is not None else template.render_policy
        fingerprint = self._preflight_template_package(source_path, normalized_layout_config_path)
        next_version = self._next_template_version(template)
        stored_path = self._store_versioned_template_file(
            template_id=template.id,
            version=next_version,
            source_path=source_path,
            source_filename=source_filename,
        )
        record = self._create_template_resource_draft(
            template=template,
            version=next_version,
            template_path=stored_path,
            layout_config_path=normalized_layout_config_path,
            render_policy=normalized_render_policy,
            fingerprint=fingerprint,
            require_service=True,
        )
        return self._build_template_version_response(
            template=template,
            version=next_version,
            template_path=stored_path,
            record=record,
        )

    def publish_template_version(
        self,
        template_id: str,
        version: int,
        *,
        make_default: bool,
        publish_reason: str,
        verification_job_id: str,
        verification_note: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TemplateVersionResponse:
        """发布 draft 模板版本；可选同步切为默认版本。"""

        template = self._require_template_item(template_id)
        service = self._require_resource_version_service()
        draft_record = service.repository.get_resource_version("template", template.id, str(version))
        if draft_record is None:
            raise FileNotFoundError(f"模板版本不存在: {template.id}@{version}")
        if draft_record.status != ResourceVersionStatus.DRAFT:
            raise ValueError("只有 draft 资源版本可以发布。")
        normalized_verification_job_id = self._normalize_required_text(verification_job_id, "verification_job_id")
        normalized_verification_note = self._normalize_required_text(verification_note, "verification_note")
        normalized_publish_reason = self._normalize_required_text(publish_reason, "publish_reason")
        self._validate_verification_job(draft_record, normalized_verification_job_id)
        self._validate_registered_template_package(draft_record)
        now = utc_now()
        payload = {
            **(draft_record.payload or {}),
            "verification_job_id": normalized_verification_job_id,
            "verification_note": normalized_verification_note,
            "verified_by": actor.actor_id if actor is not None else None,
            "verified_at": now.isoformat(),
            "publish_reason": normalized_publish_reason,
            "published_by": actor.actor_id if actor is not None else None,
            "published_at": now.isoformat(),
        }
        record = service.repository.update_resource_version_if_current(
            draft_record.model_copy(
                update={
                    "status": ResourceVersionStatus.PUBLISHED,
                    "payload": payload,
                    "snapshot_hash": resource_payload_sha256(payload),
                    "updated_at": now,
                }
            ),
            expected_snapshot_hash=draft_record.snapshot_hash,
            expected_status=ResourceVersionStatus.DRAFT,
        )
        if record is None:
            raise TemplatePackageValidationError(
                "模板草稿在发布前已变化。",
                path="template_version",
                code="template_draft_conflict",
            )
        if make_default:
            service.repository.set_default_resource_version("template", template.id, str(version))
            self._activate_template_version(template, version, record.payload)
        self._record_audit(
            actor=actor,
            action="template.publish",
            target_id=f"{template.id}@{version}",
            trace_id=trace_id,
            reason=normalized_publish_reason,
        )
        refreshed_template = self._require_template_item(template.id)
        return self._build_template_version_response(
            template=refreshed_template,
            version=version,
            template_path=self._template_version_path(refreshed_template, version, record.payload),
            record=record,
        )

    def _validate_verification_job(self, draft: ResourceVersionRecord, verification_job_id: str) -> None:
        """校验模板发布证据来自成功的同版本验证任务。"""

        if self.document_job_repository is None:
            raise RuntimeError("模板发布需要任务仓储校验验证任务。")
        job = self.document_job_repository.get_document_job(verification_job_id)
        if job is None:
            raise FileNotFoundError(f"验证任务不存在: {verification_job_id}")
        if job.status != "succeeded":
            raise ValueError("验证任务必须是 succeeded 状态。")
        expected_template_version_id = f"{draft.resource_id}@{draft.version}"
        if job.template_version_id != expected_template_version_id:
            raise ValueError(
                "验证任务 template_version_id 与待发布版本不匹配: "
                f"expected={expected_template_version_id} actual={job.template_version_id}"
            )
        resources = job.request_snapshot.get("resources")
        if resources is None:
            return
        try:
            bound = ResolvedResourceVersion.model_validate(resources["template"])
        except (ValidationError, KeyError, TypeError):
            bound = None
        if bound is None or (
            bound.resource_type, bound.resource_id, bound.version, bound.status, bound.snapshot_hash
        ) != ("template", draft.resource_id, draft.version, "draft", draft.snapshot_hash):
            raise TemplatePackageValidationError(
                "验证任务绑定的模板草稿与待发布资源不一致。",
                path="verification_job_id",
                code="template_verification_resource_mismatch",
            )

    def set_default_template_version(
        self,
        template_id: str,
        version: int,
        *,
        set_default_reason: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TemplateVersionResponse:
        """把默认模板指针切到指定已发布版本，并同步当前转换兼容态。"""

        template = self._require_template_item(template_id)
        service = self._require_resource_version_service()
        service.set_default("template", template.id, str(version))
        record = service.repository.get_resource_version("template", template.id, str(version))
        if record is None:
            raise FileNotFoundError(f"模板版本不存在: {template.id}@{version}")
        self._activate_template_version(template, version, record.payload)
        self._record_audit(
            actor=actor,
            action="template.set_default",
            target_id=f"{template.id}@{version}",
            trace_id=trace_id,
            reason=set_default_reason,
        )
        refreshed_template = self._require_template_item(template.id)
        return self._build_template_version_response(
            template=refreshed_template,
            version=version,
            template_path=self._template_version_path(refreshed_template, version, record.payload),
            record=record,
        )

    def disable_template_version(
        self,
        template_id: str,
        version: int,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TemplateVersionResponse:
        """禁用非默认模板版本，历史 DOCX 文件保留用于人工恢复。"""

        template = self._require_template_item(template_id)
        service = self._require_resource_version_service()
        record = service.disable("template", template.id, str(version))
        if version not in template.disabled_versions:
            self._replace_template_item(
                template.model_copy(update={"disabled_versions": [*template.disabled_versions, version]})
            )
            template = self._require_template_item(template.id)
        self._record_audit(
            actor=actor,
            action="template.disable",
            target_id=f"{template.id}@{version}",
            trace_id=trace_id,
        )
        return self._build_template_version_response(
            template=template,
            version=version,
            template_path=self._template_version_path(template, version, record.payload),
            record=record,
        )

    def delete_template(self, template_id: str) -> None:
        """从 manifest 删除模板记录；历史版本文件保留用于人工恢复。"""

        template = self._require_template_item(template_id)
        if self.get_default_template_id() == template.id:
            raise ValueError(f"当前默认模板不能删除: {template.id}")

        manifest = self._load_manifest()
        manifest.templates = [item for item in manifest.templates if item.id != template.id]
        self._write_manifest(manifest)

    def list_template_versions(self, template_id: str) -> list[TemplateVersionResponse]:
        """合并受管目录、manifest 和持久化快照中的模板版本。"""

        template = self._require_template_item(template_id)
        records_by_version: dict[int, ResourceVersionRecord] = {}
        for raw_version, record in self._resource_records_by_version(template.id).items():
            try:
                version = int(raw_version)
            except ValueError:
                continue
            # 规范 key 优先；没有规范 key 时保留仓储顺序中的首条等价记录。
            if version not in records_by_version or raw_version == str(version):
                records_by_version[version] = record
        default_version = self._resource_default_version(template.id)
        version_dir = self.settings.templates_storage_dir / template.id
        versions: list[TemplateVersionResponse] = []
        listed_versions: set[int] = set()
        if version_dir.exists():
            for child in sorted(version_dir.iterdir(), key=lambda path: self._version_sort_key(path.name)):
                version = self._parse_version_dir_name(child.name)
                if version is None or version in listed_versions or not child.is_dir():
                    continue
                record = records_by_version.get(version)
                # 已登记版本以 payload 为准，目录残留文件不能遮蔽原文件或其缺失状态。
                template_file = (
                    self._template_version_path(template, version, record.payload)
                    if record is not None
                    else next((item for item in sorted(child.iterdir()) if item.is_file() and item.suffix.lower() == ".docx"), None)
                )
                if template_file is None and record is None:
                    continue
                versions.append(
                    self._build_template_version_response(
                        template=template,
                        version=version,
                        template_path=template_file,
                        record=record,
                        default_version=default_version,
                    )
                )
                listed_versions.add(version)

        current_record = records_by_version.get(template.version)
        current_path = self._template_version_path(
            template,
            template.version,
            current_record.payload if current_record is not None else None,
        )
        if current_path is not None and template.version not in listed_versions:
            versions.append(
                self._build_template_version_response(
                    template=template,
                    version=template.version,
                    template_path=current_path,
                    record=current_record,
                    default_version=default_version,
                )
            )
            listed_versions.add(template.version)

        # 新 seed 不再引用的历史版本仍由其持久化快照拥有。
        for version, record in records_by_version.items():
            if version in listed_versions:
                continue
            versions.append(
                self._build_template_version_response(
                    template=template,
                    version=version,
                    template_path=self._template_version_path(template, version, record.payload),
                    record=record,
                    default_version=default_version,
                )
            )
            listed_versions.add(version)
        return sorted(versions, key=lambda item: item.version, reverse=True)

    def get_template_layout_config(self, template_id: str, *, version: int | None = None) -> TemplateLayoutConfigResponse:
        """读取默认或指定模板版本的完整样式值与编辑合同。"""

        template = self._require_template_item(template_id)
        active_version = self._active_template_version(template)
        selected_version = version or active_version
        record = self._resource_records_by_version(template.id).get(str(selected_version))
        if selected_version != template.version and record is None:
            raise FileNotFoundError(f"模板版本不存在: {template.id}@{selected_version}")
        payload = record.payload if record is not None else None
        layout_path = self._template_version_layout_config_path(template, payload)
        if layout_path is None or not layout_path.exists():
            raise FileNotFoundError(f"模板版式配置不存在: {template.id}@{selected_version}")
        expected_hash = self._payload_text(payload, "layout_config_sha256")
        actual_hash = self._sha256_prefixed(layout_path)
        if expected_hash is not None and expected_hash != actual_hash:
            raise ValueError(f"模板版式配置 hash 不匹配: {template.id}@{selected_version}")
        raw_config = self._load_supported_layout_config(layout_path)
        meta, config, preview_samples = split_layout_config(raw_config)
        return TemplateLayoutConfigResponse(
            template_id=template.id,
            template_version_id=self.build_template_version_id(template.id, selected_version),
            version=selected_version,
            status=record.status.value if record is not None else "published",
            is_default=selected_version == active_version,
            active_template_version_id=self.build_template_version_id(template.id, active_version),
            source_path=self._public_repo_relative_path(layout_path),
            config_sha256=actual_hash,
            snapshot_hash=record.snapshot_hash if record is not None else None,
            meta=meta,
            config=config,
            preview_samples=preview_samples,
            field_schema=editor_field_schema(),
        )

    def create_template_layout_config_version(
        self,
        template_id: str,
        *,
        base_template_version_id: str,
        expected_config_sha256: str,
        expected_active_template_version_id: str,
        changes: dict[str, Any],
        change_note: str = "",
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TemplateVersionResponse:
        """把页面提交的版式配置保存为新的模板 draft version，不直接改仓库 YAML。"""

        self._require_resource_version_service()
        template = self._require_template_item(template_id)
        base_template_id, base_version = self._parse_template_version_id(base_template_version_id)
        if base_template_id != template.id or base_version is None:
            raise ValueError("base_template_version_id 必须匹配当前模板并包含明确版本。")
        active_version = self._active_template_version(template)
        active_template_version_id = self.build_template_version_id(template.id, active_version)
        if expected_active_template_version_id != active_template_version_id:
            active_record = self._resource_records_by_version(template.id).get(str(active_version))
            active_layout_path = self._template_version_layout_config_path(
                template,
                active_record.payload if active_record is not None else None,
            )
            raise TemplateLayoutConfigConflict(
                f"模板默认版本已变化: expected={expected_active_template_version_id} actual={active_template_version_id}",
                active_template_version_id=active_template_version_id,
                config_sha256=(
                    self._sha256_prefixed(active_layout_path)
                    if active_layout_path is not None and active_layout_path.is_file()
                    else None
                ),
            )
        base_record = self._resource_records_by_version(template.id).get(str(base_version))
        if base_version != template.version and base_record is None:
            raise FileNotFoundError(f"模板版本不存在: {template.id}@{base_version}")
        base_payload = base_record.payload if base_record is not None else None
        source_template_path = self._template_version_path(template, base_version, base_payload)
        if source_template_path is None or not source_template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template.id}@{base_version}")
        source_layout_path = self._template_version_layout_config_path(template, base_payload)
        if source_layout_path is None or not source_layout_path.exists():
            raise FileNotFoundError(f"模板版式配置不存在: {template.id}@{base_version}")
        source_layout_content = read_template_resource(source_layout_path, kind="layout_config")
        actual_hash = content_sha256(source_layout_content)
        if expected_config_sha256 != actual_hash:
            raise TemplateLayoutConfigConflict(
                f"模板样式配置已变化: expected={expected_config_sha256} actual={actual_hash}",
                active_template_version_id=active_template_version_id,
                config_sha256=actual_hash,
            )
        expected_base_layout_hash = self._payload_text(base_payload, "layout_config_sha256")
        if expected_base_layout_hash is not None:
            self._require_resource_hash(actual_hash, expected_base_layout_hash, kind="layout_config")
        validated_config = apply_layout_changes(load_layout_config_yaml(source_layout_content), changes)
        layout_content = yaml.safe_dump(validated_config, allow_unicode=True, sort_keys=False).encode("utf-8")
        template_content = read_template_resource(source_template_path, kind="docx")
        expected_base_docx_hash = self._payload_text(base_payload, "docx_sha256")
        if expected_base_docx_hash is not None:
            self._require_resource_hash(content_sha256(template_content), expected_base_docx_hash, kind="docx")
        fingerprint = validate_template_package_content(
            template_content=template_content,
            layout_config_content=layout_content,
        )
        next_version = self._next_template_version(template)
        template_path, layout_path = self._stage_template_layout_version(
            template_id=template.id,
            version=next_version,
            source_filename=source_template_path.name,
            template_content=template_content,
            layout_content=layout_content,
        )
        layout_config_path = self._to_repo_relative_path(layout_path)
        record = self._create_template_resource_draft(
            template=template,
            version=next_version,
            template_path=template_path,
            layout_config_path=layout_config_path,
            render_policy=template.render_policy,
            fingerprint=fingerprint,
            require_service=True,
        )
        self._record_audit(
            actor=actor,
            action="template.layout_config_version_create",
            target_id=f"{template.id}@{next_version}",
            trace_id=trace_id,
            reason=self._normalize_optional_text(change_note),
        )
        return self._build_template_version_response(
            template=template,
            version=next_version,
            template_path=template_path,
            record=record,
        )

    def get_template_path(self, template_id: str) -> Path | None:
        """返回 manifest seed 文件；版本解析不得把它当作运行时默认指针。"""

        template = self._get_template_item(template_id)
        if template is None or not template.enabled:
            return None
        return self._resolve_manifest_path(template.template_path)

    def get_active_template_path(self, template_id: str) -> Path | None:
        """返回数据库默认指针对应的模板文件。"""

        template = self._get_template_item(template_id)
        if template is None or not template.enabled:
            return None
        active_version = self._active_template_version(template)
        record = self._resource_records_by_version(template.id).get(str(active_version))
        return self._template_version_path(template, active_version, record.payload if record is not None else None)

    def get_default_template_id(self) -> str:
        state = self._load_state()
        default_id = state.default_template_id
        if default_id and self._template_is_available(default_id):
            return default_id

        manifest_default = next((item.id for item in self._visible_templates() if item.is_default_seed and self._template_is_available(item.id)), None)
        if manifest_default is not None:
            self._write_state(TemplateState(default_template_id=manifest_default))
            return manifest_default

        first_visible = next((item.id for item in self._visible_templates() if self._template_is_available(item.id)), self.settings.default_template_id)
        self._write_state(TemplateState(default_template_id=first_visible))
        return first_visible

    def resolve_selected_template_id(self, template_id: str | None) -> str:
        if template_id is None:
            return self.get_default_template_id()
        if not self._template_is_available(template_id):
            raise ValueError(f"模板不存在或未启用: {template_id}")
        return template_id

    def set_default_template(self, template_id: str) -> None:
        if not self._template_is_available(template_id):
            raise FileNotFoundError(f"模板不存在或未启用: {template_id}")
        self._write_state(TemplateState(default_template_id=template_id))

    def resolve_job_template_path(self, template_id: str | None) -> Path:
        resolved_id = self.resolve_selected_template_id(template_id)
        path = self.get_active_template_path(resolved_id)
        if path is None or not path.exists():
            raise FileNotFoundError(f"模板文件不存在: {resolved_id}")
        return path

    def resolve_job_layout_config_path(self, template_id: str | None) -> Path | None:
        """返回 job 选中模板绑定的版式 YAML；模板未绑定时允许 conversion 使用默认配置。"""

        resolved_id = self.resolve_selected_template_id(template_id)
        template = self._get_template_item(resolved_id)
        if template is None:
            return None
        active_version = self._active_template_version(template)
        record = self._resource_records_by_version(template.id).get(str(active_version))
        path = self._template_version_layout_config_path(template, record.payload if record is not None else None)
        if path is None:
            return None
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"模板版式配置不存在: {resolved_id}")
        return path

    def resolve_template_render_state(
        self, template_id: str, version: int | None,
    ) -> tuple[TemplateManifestItem, int]:
        """检查渲染准入状态；显式版本不读取默认指针或资源实物。"""

        template = self._require_template_item(template_id)
        if not template.enabled:
            raise FileNotFoundError(f"模板未启用: {template.id}")
        selected_version = self._active_template_version(template) if version is None else version
        if selected_version in template.disabled_versions:
            raise FileNotFoundError(f"模板版本已禁用: {template.id}@{selected_version}")
        return template, selected_version

    def resolve_template_version(
        self,
        template_version_id: str | None,
        *,
        allow_draft: bool = False,
    ) -> TemplateVersionSelection:
        """按调用意图解析 published 生产版本或 admin 验证 draft。"""

        template_id, version = self._parse_template_version_id(template_version_id)
        if template_id is None:
            template_id = self.get_default_template_id()
        template, selected_version = self.resolve_template_render_state(template_id, version or None)

        record = self._resource_records_by_version(template.id).get(str(selected_version))
        if self.resource_version_service is not None and record is None:
            raise FileNotFoundError(f"模板版本记录不存在: {template.id}@{selected_version}")
        if record is not None:
            if record.status == ResourceVersionStatus.DRAFT and not allow_draft:
                raise ValueError(f"普通任务不能使用 draft 模板版本: {template.id}@{selected_version}")
            if record.status not in {ResourceVersionStatus.PUBLISHED, ResourceVersionStatus.DRAFT}:
                raise ValueError(f"模板版本状态不可用于生成: {template.id}@{selected_version} status={record.status.value}")
        payload = record.payload if record is not None else None
        template_path = self._template_version_path(template, selected_version, payload)
        if template_path is None or not template_path.exists():
            raise FileNotFoundError(f"模板版本文件不存在: {template.id}@{selected_version}")
        layout_config_path = self._template_version_layout_config_path(template, payload)
        if layout_config_path is not None:
            if not layout_config_path.exists() or not layout_config_path.is_file():
                raise FileNotFoundError(f"模板版式配置不存在: {template.id}@{selected_version}")
            expected_hash = self._payload_text(payload, "layout_config_sha256")
            if expected_hash is not None and expected_hash != self._sha256_prefixed(layout_config_path):
                raise ValueError(f"模板版式配置 hash 不匹配: {template.id}@{selected_version}")
        render_policy = self._payload_dict(payload, "render_policy") or template.render_policy
        return TemplateVersionSelection(
            template_id=template.id,
            version=selected_version,
            template_version_id=self.build_template_version_id(template.id, selected_version),
            template_path=template_path,
            layout_config_path=layout_config_path,
            render_policy=render_policy,
        )

    @staticmethod
    def build_template_version_id(template_id: str, version: int) -> str:
        return f"{template_id}@{version}"

    def _load_manifest(self) -> TemplatesManifest:
        if self._manifest_cache is not None:
            return self._manifest_cache
        try:
            self._manifest_cache = load_template_manifest(self.settings.templates_manifest_file)
        except FileNotFoundError:
            seed = self.settings.bundled_template_seed
            templates: list[TemplateManifestItem] = []
            if seed is not None and seed.template_path.is_file():
                item = seed.item
                if item.id != self.settings.default_template_id:
                    # 自定义默认 ID 在无部署清单时仍沿用历史合成版本。
                    item = item.model_copy(update={"id": self.settings.default_template_id, "version": 1})
                templates.append(item)
            self._manifest_cache = TemplatesManifest(templates=templates)
        return self._manifest_cache

    def _record_audit(
        self,
        *,
        actor: ActorContext | None,
        action: str,
        target_id: str,
        trace_id: str | None,
        reason: str | None = None,
    ) -> None:
        if actor is None or self.audit_service is None:
            return
        self.audit_service.record(
            actor=actor,
            action=action,
            target_type="template",
            target_id=target_id,
            trace_id=trace_id or "",
            reason=reason,
        )

    def _write_manifest(self, manifest: TemplatesManifest) -> None:
        path = self.settings.templates_manifest_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(manifest.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self._manifest_cache = manifest

    def _visible_templates(self) -> list[TemplateManifestItem]:
        return [item for item in self._load_manifest().templates if item.enabled]

    def _get_template_item(self, template_id: str) -> TemplateManifestItem | None:
        for item in self._load_manifest().templates:
            if item.id == template_id:
                return item
        return None

    def _require_template_item(self, template_id: str) -> TemplateManifestItem:
        normalized_id = self._validate_template_id(template_id)
        item = self._get_template_item(normalized_id)
        if item is None:
            raise FileNotFoundError(f"模板不存在: {normalized_id}")
        return item

    def _replace_template_item(self, updated_template: TemplateManifestItem) -> None:
        manifest = self._load_manifest()
        for index, item in enumerate(manifest.templates):
            if item.id == updated_template.id:
                manifest.templates[index] = updated_template
                self._write_manifest(manifest)
                return
        raise FileNotFoundError(f"模板不存在: {updated_template.id}")

    def _next_template_version(self, template: TemplateManifestItem) -> int:
        existing_versions = [template.version]
        for raw_version in self._resource_records_by_version(template.id):
            try:
                existing_versions.append(int(raw_version))
            except ValueError:
                continue
        version_dir = self.settings.templates_storage_dir / template.id
        if version_dir.exists():
            for child in version_dir.iterdir():
                version = self._parse_version_dir_name(child.name)
                if version is not None:
                    existing_versions.append(version)
        minimum_next = max(existing_versions) + 1
        if self.resource_version_service is None:
            return minimum_next
        return self._require_resource_version_service().allocate_next_version(
            "template",
            template.id,
            minimum_next,
        )

    def _require_resource_version_service(self) -> Any:
        if self.resource_version_service is None:
            raise RuntimeError("模板版本发布需要 JOBS_REPOSITORY_BACKEND=mysql。")
        return self.resource_version_service

    def _create_template_resource_draft(
        self,
        *,
        template: TemplateManifestItem,
        version: int,
        template_path: Path,
        layout_config_path: str | None,
        render_policy: dict[str, Any],
        fingerprint: TemplatePackageFingerprint,
        require_service: bool,
    ) -> ResourceVersionRecord | None:
        service = self.resource_version_service
        if service is None:
            if require_service:
                raise RuntimeError("模板版本发布需要 JOBS_REPOSITORY_BACKEND=mysql。")
            return None
        payload = self._build_template_version_payload(
            template=template,
            version=version,
            template_path=template_path,
            layout_config_path=layout_config_path,
            render_policy=render_policy,
            fingerprint=fingerprint,
        )
        try:
            return service.create_draft(
                resource_type="template",
                resource_id=template.id,
                version=str(version),
                snapshot_hash=resource_payload_sha256(payload),
                payload_ref=f"template:{template.id}@{version}",
                payload=payload,
            )
        except Exception:
            self._cleanup_staged_path(template_path.parent, template.id, version)
            raise

    def _build_template_version_payload(
        self,
        *,
        template: TemplateManifestItem,
        version: int,
        template_path: Path,
        layout_config_path: str | None,
        render_policy: dict[str, Any],
        fingerprint: TemplatePackageFingerprint,
    ) -> dict[str, Any]:
        return {
            "template_id": template.id,
            "version": version,
            "name": template.name,
            "description": template.description,
            "docx_path": self._to_repo_relative_path(template_path),
            "docx_sha256": fingerprint.docx_sha256,
            "layout_config_path": layout_config_path,
            "layout_config_sha256": fingerprint.layout_config_sha256,
            "render_policy": render_policy,
        }

    def _preflight_template_package(
        self, template_path: Path, layout_config_path: str | None,
    ) -> TemplatePackageFingerprint:
        try:
            layout_path = self._resolve_manifest_path(layout_config_path) if layout_config_path else None
        except (OSError, RuntimeError):
            raise TemplatePackageValidationError(
                "模板版式资源路径不可解析。",
                path="layout_config",
                code="template_layout_config_unavailable",
            ) from None
        return validate_template_package(
            template_path=template_path,
            layout_config_path=layout_path,
        )

    def _validate_registered_template_package(self, record: ResourceVersionRecord) -> None:
        payload = record.payload or {}
        docx_path = self._payload_text(payload, "docx_path")
        layout_path = payload.get("layout_config_path")
        if (
            docx_path is None
            or (layout_path is not None and (not isinstance(layout_path, str) or not layout_path))
            or payload.get("template_id") != record.resource_id
            or str(payload.get("version")) != record.version
            or resource_payload_sha256(payload) != record.snapshot_hash
        ):
            raise TemplatePackageValidationError(
                "模板资源版本记录不完整或身份不一致。",
                path="template_version",
                code="template_resource_payload_invalid",
            )
        fingerprint = self._preflight_template_package(self._resolve_manifest_path(docx_path), layout_path)
        self._require_resource_hash(fingerprint.docx_sha256, payload.get("docx_sha256"), kind="docx")
        self._require_resource_hash(
            fingerprint.layout_config_sha256, payload.get("layout_config_sha256"), kind="layout_config",
        )

    @staticmethod
    def _require_resource_hash(actual: str | None, expected: Any, *, kind: str) -> None:
        if actual != expected:
            raise TemplatePackageValidationError(
                "模板资源字节与版本记录不一致。", path=kind, code=f"template_{kind}_hash_mismatch",
            )

    def _activate_template_version(
        self,
        template: TemplateManifestItem,
        version: int,
        payload: dict[str, Any] | None,
    ) -> None:
        path = self._template_version_path(template, version, payload)
        if path is None or not path.exists():
            raise FileNotFoundError(f"模板版本文件不存在: {template.id}@{version}")
        layout_path = self._template_version_layout_config_path(template, payload)
        if layout_path is not None and not layout_path.exists():
            raise FileNotFoundError(f"模板版式配置不存在: {template.id}@{version}")
        self._write_state(TemplateState(default_template_id=template.id))

    def _build_template_version_response(
        self,
        *,
        template: TemplateManifestItem,
        version: int,
        template_path: Path | None,
        record: ResourceVersionRecord | None,
        default_version: int | None = None,
    ) -> TemplateVersionResponse:
        payload = record.payload if record is not None else None
        status = record.status.value if record is not None else self._manifest_version_status(template, version)
        resolved_default_version = default_version if default_version is not None else self._resource_default_version(template.id)
        is_default = (
            resolved_default_version == version
            if resolved_default_version is not None
            else template.id == self.get_default_template_id() and version == template.version
        )
        render_policy = self._payload_dict(payload, "render_policy")
        if render_policy is None:
            render_policy = template.render_policy
        return TemplateVersionResponse(
            template_id=template.id,
            template_version_id=self.build_template_version_id(template.id, version),
            version=version,
            status=status,
            is_current=version == (self._resource_default_version(template.id) or template.version),
            is_default=is_default,
            snapshot_hash=record.snapshot_hash if record is not None else None,
            render_policy=render_policy,
            verification_job_id=self._payload_text(payload, "verification_job_id"),
            verification_note=self._payload_text(payload, "verification_note"),
            verified_by=self._payload_text(payload, "verified_by"),
            verified_at=self._payload_datetime(payload, "verified_at"),
            publish_reason=self._payload_text(payload, "publish_reason"),
            published_by=self._payload_text(payload, "published_by"),
            published_at=self._payload_datetime(payload, "published_at"),
            template=self._build_asset(path=template_path, label="Word 模板", download_url=None),
            layout_config=self._build_asset(
                path=self._template_version_layout_config_path(template, payload),
                label="页面布局 YAML",
                download_url=None,
            ),
        )

    def _manifest_version_status(self, template: TemplateManifestItem, version: int) -> str:
        return "disabled" if version in template.disabled_versions else "published"

    def _resource_records_by_version(self, template_id: str) -> dict[str, ResourceVersionRecord]:
        service = self.resource_version_service
        if service is None:
            return {}
        return {
            record.version: record
            for record in service.repository.list_resource_versions("template", template_id)
        }

    def _resource_default_version(self, template_id: str) -> int | None:
        service = self.resource_version_service
        if service is None:
            return None
        record = service.repository.get_default_resource_version("template", template_id)
        if record is None:
            return None
        try:
            return int(record.version)
        except ValueError:
            return None

    def _active_template_version(self, template: TemplateManifestItem) -> int:
        """在版本治理启用时只接受数据库中的 published 默认指针。"""

        service = self.resource_version_service
        if service is None:
            return template.version
        record = service.repository.get_default_resource_version("template", template.id)
        if record is None:
            raise FileNotFoundError(f"模板默认版本不存在: {template.id}")
        if record.status != ResourceVersionStatus.PUBLISHED:
            raise ValueError(f"模板默认版本必须是 published: {template.id}@{record.version}")
        try:
            return int(record.version)
        except ValueError as exc:
            raise ValueError(f"模板默认版本号必须是整数: {template.id}@{record.version}") from exc

    def _template_version_layout_config_path(
        self,
        template: TemplateManifestItem,
        payload: dict[str, Any] | None,
    ) -> Path | None:
        """显式空值表示版本未绑定 YAML，旧记录缺少字段时仍可使用 manifest。"""

        if payload is not None and "layout_config_path" in payload and payload["layout_config_path"] is None:
            return None
        payload_path = self._payload_text(payload, "layout_config_path")
        layout_path = payload_path or template.layout_config_path
        return self._resolve_manifest_path(layout_path) if layout_path else None

    def _parse_template_version_id(self, template_version_id: str | None) -> tuple[str | None, int | None]:
        normalized = self._normalize_optional_text(template_version_id)
        if normalized is None:
            return None, None
        template_id, separator, raw_version = normalized.partition("@")
        if not separator:
            return self._validate_template_id(template_id), None
        template_id = self._validate_template_id(template_id)
        try:
            version = int(raw_version)
        except ValueError as exc:
            raise ValueError("template_version_id 必须使用 template_id@version 格式。") from exc
        if version < 1:
            raise ValueError("template_version_id 版本号必须大于 0。")
        return template_id, version

    def _template_version_path(
        self,
        template: TemplateManifestItem,
        version: int,
        payload: dict[str, Any] | None,
    ) -> Path | None:
        payload_path = self._payload_text(payload, "docx_path")
        if payload_path:
            return self._resolve_manifest_path(payload_path)
        if version == template.version:
            return self.get_template_path(template.id)
        version_dir = self.settings.templates_storage_dir / template.id / f"v{version}"
        if not version_dir.exists():
            return None
        return next((item for item in sorted(version_dir.iterdir()) if item.is_file() and item.suffix.lower() == ".docx"), None)

    @staticmethod
    def _payload_text(payload: dict[str, Any] | None, key: str) -> str | None:
        value = payload.get(key) if payload is not None else None
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _payload_dict(payload: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
        value = payload.get(key) if payload is not None else None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _payload_datetime(payload: dict[str, Any] | None, key: str) -> datetime | None:
        value = payload.get(key) if payload is not None else None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value)
        return None

    def _template_is_enabled(self, template_id: str) -> bool:
        item = self._get_template_item(template_id)
        return item is not None and item.enabled

    def _template_is_available(self, template_id: str) -> bool:
        item = self._get_template_item(template_id)
        if item is None or not item.enabled:
            return False
        path = self._resolve_manifest_path(item.template_path)
        return path.exists() and path.is_file()

    def _store_versioned_template_file(
        self,
        *,
        template_id: str,
        version: int,
        source_path: Path,
        source_filename: str,
    ) -> Path:
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError("模板上传文件不存在。")
        safe_name = self._safe_template_filename(source_filename, template_id)
        destination_dir = self.settings.templates_storage_dir / template_id / f"v{version}"
        try:
            destination_dir.mkdir(parents=True)
        except FileExistsError:
            raise TemplatePackageValidationError(
                "模板版本目录已存在。", path="template_version", code="template_version_conflict",
            ) from None
        destination = destination_dir / safe_name
        try:
            shutil.move(str(source_path), str(destination))
        except OSError:
            self._cleanup_staged_path(destination_dir, template_id, version)
            raise
        return destination.resolve()

    def _stage_template_layout_version(
        self,
        *,
        template_id: str,
        version: int,
        source_filename: str,
        template_content: bytes,
        layout_content: bytes,
    ) -> tuple[Path, Path]:
        """一次性提交已通过预检的候选文件，使 Worker 只能看到完整版本。"""

        safe_name = self._safe_template_filename(source_filename, template_id)
        template_root = self.settings.templates_storage_dir / template_id
        template_root.mkdir(parents=True, exist_ok=True)
        destination_dir = template_root / f"v{version}"
        if destination_dir.exists():
            raise FileExistsError(f"模板版本目录已存在: {template_id}@{version}")
        staging_dir = template_root / f".v{version}.{uuid4().hex}.tmp"
        staging_dir.mkdir()
        staged_template = staging_dir / safe_name
        staged_layout = staging_dir / "layout_config.yaml"
        installed = False
        try:
            for path, content in ((staged_template, template_content), (staged_layout, layout_content)):
                with path.open("wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            staging_dir.replace(destination_dir)
            installed = True
            directory_fd = os.open(template_root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            self._cleanup_staged_path(destination_dir if installed else staging_dir, template_id, version)
            raise
        return (destination_dir / safe_name).resolve(), (destination_dir / "layout_config.yaml").resolve()

    @staticmethod
    def _cleanup_staged_path(path: Path, template_id: str, version: int) -> None:
        """清理本次失败写入并记录无法自动修复的孤儿目录。"""

        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            return
        except OSError as error:
            SYSTEM_LOGGER.warning(
                "[template_id=%s version=%s error_type=%s status=cleanup_failed] 模板版本失败目录清理失败",
                template_id,
                version,
                type(error).__name__,
            )

    def _load_supported_layout_config(self, path: Path) -> dict[str, Any]:
        raw = load_layout_config_yaml(path.read_bytes())
        validate_layout_config(raw)
        return raw

    def _load_state(self) -> TemplateState:
        path = self.settings.template_state_file
        if not path.exists():
            return TemplateState()
        return TemplateState.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_state(self, state: TemplateState) -> None:
        path = self.settings.template_state_file
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + f".{uuid4().hex}.tmp")
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                handle.write(state.model_dump_json(indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _resolve_manifest_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return (self.settings.root_dir / path).resolve()

    def _to_repo_relative_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.settings.root_dir))
        except ValueError:
            return str(path.resolve())

    def _public_repo_relative_path(self, path: Path) -> str | None:
        """只向管理 API 暴露仓库内相对路径，避免泄露服务器绝对路径。"""

        try:
            return str(path.resolve().relative_to(self.settings.root_dir))
        except ValueError:
            return None

    @staticmethod
    def _validate_template_id(template_id: str) -> str:
        normalized = template_id.strip()
        if not TEMPLATE_ID_RE.match(normalized):
            raise ValueError("template_id 只能包含大小写字母、数字、下划线、短横线和英文句点，长度不超过 128。")
        return normalized

    @staticmethod
    def _normalize_required_text(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _safe_template_filename(source_filename: str, template_id: str) -> str:
        filename = Path(source_filename or f"{template_id}.docx").name
        if not filename.lower().endswith(".docx"):
            raise ValueError("模板文件必须是 .docx 格式。")
        return filename

    @staticmethod
    def _parse_version_dir_name(name: str) -> int | None:
        if not name.startswith("v"):
            return None
        try:
            return int(name[1:])
        except ValueError:
            return None

    def _version_sort_key(self, name: str) -> int:
        return self._parse_version_dir_name(name) or 0

    def _build_asset(
        self,
        *,
        path: Path | None,
        label: str,
        download_url: str | None,
    ) -> TemplateAssetResponse:
        if path is None or not path.exists():
            return TemplateAssetResponse(
                label=label,
                exists=False,
                file_name=path.name if path is not None else None,
                size_bytes=None,
                updated_at=None,
                sha256=None,
                download_url=download_url,
            )

        stat = path.stat()
        return TemplateAssetResponse(
            label=label,
            exists=True,
            file_name=path.name,
            size_bytes=stat.st_size,
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            sha256=self._sha256(path),
            download_url=download_url,
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _sha256_prefixed(self, path: Path) -> str:
        return f"sha256:{self._sha256(path)}"
