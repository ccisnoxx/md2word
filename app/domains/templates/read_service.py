from __future__ import annotations

# app/domains/templates/read_service.py: 读取模板清单并映射为 templates API 响应模型。

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from app.domains.audit.models import ActorContext
from app.core.config import Settings
from app.domains.document_jobs.repository import DocumentJobRepositoryProtocol
from app.domains.resources.models import ResourceVersionRecord, utc_now
from app.domains.templates.models import TemplateManifestItem, TemplateState, TemplatesManifest
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


ASSET_SPECS: tuple[AssetSpec, ...] = (
    AssetSpec(key="template", label="Word 模板", path_getter="default_template_path"),
    AssetSpec(key="layout_config", label="页面布局 YAML", path_getter="layout_config_path"),
    AssetSpec(key="subscript_config", label="术语上下标 YAML", path_getter="subscript_config_path"),
)

TEMPLATE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
ALIGNMENT_VALUES = ("left", "center", "right", "justify")

LAYOUT_META_FIELD_SCHEMA: dict[str, dict[str, Any]] = {
    "schema_version": {"type": "text", "label": "schema_version", "readonly": True},
    "template_name": {"type": "text", "label": "配置名称", "readonly": True},
    "output_filename": {"type": "text", "label": "输出文件名", "readonly": True},
}

PARAGRAPH_STYLE_FIELDS: dict[str, dict[str, Any]] = {
    "font_name": {"type": "text", "label": "中文字体"},
    "western_font_name": {"type": "text", "label": "西文字体"},
    "complex_script_font_name": {"type": "text", "label": "复杂文种字体"},
    "font_size": {"type": "number", "label": "字号", "unit": "pt"},
    "bold": {"type": "boolean", "label": "加粗"},
    "color": {"type": "color", "label": "颜色"},
    "alignment": {"type": "alignment", "label": "对齐方式"},
    "space_before": {"type": "number", "label": "段前间距", "unit": "pt"},
    "space_after": {"type": "number", "label": "段后间距", "unit": "pt"},
    "line_spacing": {"type": "number", "label": "行距"},
    "first_line_indent_pt": {"type": "number", "label": "首行缩进", "unit": "pt"},
    "left_indent_pt": {"type": "number", "label": "左缩进", "unit": "pt"},
    "right_indent_pt": {"type": "number", "label": "右缩进", "unit": "pt"},
}
TEXT_STYLE_FIELDS: dict[str, dict[str, Any]] = {
    "font_name": PARAGRAPH_STYLE_FIELDS["font_name"],
    "western_font_name": PARAGRAPH_STYLE_FIELDS["western_font_name"],
    "complex_script_font_name": PARAGRAPH_STYLE_FIELDS["complex_script_font_name"],
    "font_size": PARAGRAPH_STYLE_FIELDS["font_size"],
    "bold": PARAGRAPH_STYLE_FIELDS["bold"],
    "alignment": PARAGRAPH_STYLE_FIELDS["alignment"],
    "space_after": PARAGRAPH_STYLE_FIELDS["space_after"],
}

LAYOUT_GROUP_FIELD_SCHEMA: dict[str, dict[str, dict[str, Any]]] = {
    "page_setup": {
        "page_width_cm": {"type": "number", "label": "页面宽度", "unit": "cm"},
        "page_height_cm": {"type": "number", "label": "页面高度", "unit": "cm"},
        "top_margin": {"type": "number", "label": "上边距", "unit": "cm"},
        "bottom_margin": {"type": "number", "label": "下边距", "unit": "cm"},
        "left_margin": {"type": "number", "label": "左边距", "unit": "cm"},
        "right_margin": {"type": "number", "label": "右边距", "unit": "cm"},
        "header_distance": {"type": "number", "label": "页眉距离", "unit": "cm"},
        "footer_distance": {"type": "number", "label": "页脚距离", "unit": "cm"},
    },
    "part_number": TEXT_STYLE_FIELDS,
    "category": TEXT_STYLE_FIELDS,
    "heading1": PARAGRAPH_STYLE_FIELDS,
    "heading2": PARAGRAPH_STYLE_FIELDS,
    "heading3": PARAGRAPH_STYLE_FIELDS,
    "toc_title": {
        key: value
        for key, value in PARAGRAPH_STYLE_FIELDS.items()
        if key not in {"first_line_indent_pt", "left_indent_pt", "right_indent_pt"}
    },
    "toc_level1": {
        key: value
        for key, value in PARAGRAPH_STYLE_FIELDS.items()
        if key not in {"first_line_indent_pt", "left_indent_pt", "right_indent_pt"}
    },
    "toc_level2": {
        key: value
        for key, value in PARAGRAPH_STYLE_FIELDS.items()
        if key not in {"first_line_indent_pt", "left_indent_pt", "right_indent_pt"}
    },
    "toc_level3": {
        key: value
        for key, value in PARAGRAPH_STYLE_FIELDS.items()
        if key not in {"first_line_indent_pt", "left_indent_pt", "right_indent_pt"}
    },
    "normal": PARAGRAPH_STYLE_FIELDS,
    "table_content": {
        key: value
        for key, value in PARAGRAPH_STYLE_FIELDS.items()
        if key not in {"bold"}
    },
    "table_style": {
        "style_name": {"type": "text", "label": "表格样式"},
        "header_fill": {"type": "color", "label": "表头底色"},
        "border_color": {"type": "color", "label": "边框颜色"},
    },
    "table_note": {
        **{key: value for key, value in PARAGRAPH_STYLE_FIELDS.items() if key != "bold"},
        "italic": {"type": "boolean", "label": "斜体"},
    },
    "caption": PARAGRAPH_STYLE_FIELDS,
    "long_table_caption": PARAGRAPH_STYLE_FIELDS,
    "header": {
        "enabled": {"type": "boolean", "label": "启用页眉覆盖"},
        "logo_path": {"type": "text", "label": "Logo 路径", "readonly": True},
        "logo_height_cm": {"type": "number", "label": "Logo 高度", "unit": "cm"},
        "title_text": {"type": "text", "label": "页眉标题"},
        "title_font_name": {"type": "text", "label": "页眉中文字体"},
        "title_western_font_name": {"type": "text", "label": "页眉西文字体"},
        "title_complex_script_font_name": {"type": "text", "label": "页眉复杂文种字体"},
        "title_font_size": {"type": "number", "label": "页眉字号", "unit": "pt"},
        "title_color": {"type": "color", "label": "页眉颜色"},
    },
    "footer": {
        "enabled": {"type": "boolean", "label": "启用页脚覆盖"},
        "show_page_number": {"type": "boolean", "label": "显示页码"},
        "font_name": {"type": "text", "label": "页脚中文字体"},
        "western_font_name": {"type": "text", "label": "页脚西文字体"},
        "complex_script_font_name": {"type": "text", "label": "页脚复杂文种字体"},
        "alignment": {"type": "alignment", "label": "页脚对齐"},
    },
}

LAYOUT_FIELD_SCHEMA: dict[str, Any] = {
    "meta": LAYOUT_META_FIELD_SCHEMA,
    "groups": LAYOUT_GROUP_FIELD_SCHEMA,
}


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

    def get_template_detail(
        self,
        template_id: str,
        *,
        url_for: Callable[..., str] | None,
    ) -> TemplateDetailResponse | None:
        template = self._get_template_item(template_id)
        if template is None or not template.enabled:
            return None

        template_path = self.get_template_path(template_id)
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
            path=self._resolve_manifest_path(template.layout_config_path) if template.layout_config_path else None,
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
            version=template.version,
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
        stored_path = self._store_versioned_template_file(
            template_id=normalized_id,
            version=1,
            source_path=source_path,
            source_filename=source_filename,
        )
        manifest.templates.append(
            TemplateManifestItem(
                id=normalized_id,
                name=self._normalize_required_text(name, "name"),
                description=description.strip(),
                enabled=enabled,
                is_default_seed=False,
                version=1,
                template_path=self._to_repo_relative_path(stored_path),
                layout_config_path=normalized_layout_config_path,
                render_policy=normalized_render_policy,
            )
        )
        self._write_manifest(manifest)
        created_template = self._require_template_item(normalized_id)
        self._create_template_resource_draft(
            template=created_template,
            version=1,
            template_path=stored_path,
            layout_config_path=normalized_layout_config_path,
            render_policy=normalized_render_policy,
            require_service=False,
        )

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
        next_version = max(template.version + 1, 1)
        stored_path = self._store_versioned_template_file(
            template_id=template.id,
            version=next_version,
            source_path=source_path,
            source_filename=source_filename,
        )
        self._replace_template_item(
            template.model_copy(
                update={
                    "version": next_version,
                    "template_path": self._to_repo_relative_path(stored_path),
                }
            )
        )
        updated_template = self._require_template_item(template.id)
        self._create_template_resource_draft(
            template=updated_template,
            version=next_version,
            template_path=stored_path,
            layout_config_path=updated_template.layout_config_path,
            render_policy=updated_template.render_policy,
            require_service=False,
        )

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
        next_version = self._next_template_version(template)
        stored_path = self._store_versioned_template_file(
            template_id=template.id,
            version=next_version,
            source_path=source_path,
            source_filename=source_filename,
        )
        normalized_layout_config_path = (
            self._normalize_optional_text(layout_config_path)
            if layout_config_path is not None
            else template.layout_config_path
        )
        normalized_render_policy = render_policy if render_policy is not None else template.render_policy
        record = self._create_template_resource_draft(
            template=template,
            version=next_version,
            template_path=stored_path,
            layout_config_path=normalized_layout_config_path,
            render_policy=normalized_render_policy,
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
        normalized_verification_job_id = self._normalize_required_text(verification_job_id, "verification_job_id")
        normalized_verification_note = self._normalize_required_text(verification_note, "verification_note")
        normalized_publish_reason = self._normalize_required_text(publish_reason, "publish_reason")
        self._validate_verification_job(template.id, version, normalized_verification_job_id)
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
        service.repository.save_resource_version(
            draft_record.model_copy(
                update={
                    "payload": payload,
                    "snapshot_hash": self._snapshot_hash(payload),
                    "updated_at": now,
                }
            )
        )
        record = service.publish("template", template.id, str(version), make_default=make_default)
        if make_default:
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

    def _validate_verification_job(self, template_id: str, version: int, verification_job_id: str) -> None:
        """校验模板发布证据来自成功的同版本验证任务。"""

        if self.document_job_repository is None:
            raise RuntimeError("Template publish requires document_job_repository for verification.")
        job = self.document_job_repository.get_document_job(verification_job_id)
        if job is None:
            raise FileNotFoundError(f"验证任务不存在: {verification_job_id}")
        if job.status != "succeeded":
            raise ValueError("验证任务必须是 succeeded 状态。")
        expected_template_version_id = self.build_template_version_id(template_id, version)
        if job.template_version_id != expected_template_version_id:
            raise ValueError(
                "验证任务 template_version_id 与待发布版本不匹配: "
                f"expected={expected_template_version_id} actual={job.template_version_id}"
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
        """列出 API 管理目录下可见的模板文件版本。"""

        template = self._require_template_item(template_id)
        records_by_version = self._resource_records_by_version(template.id)
        default_version = self._resource_default_version(template.id)
        version_dir = self.settings.templates_storage_dir / template.id
        versions: list[TemplateVersionResponse] = []
        if version_dir.exists():
            for child in sorted(version_dir.iterdir(), key=lambda path: self._version_sort_key(path.name)):
                version = self._parse_version_dir_name(child.name)
                if version is None or not child.is_dir():
                    continue
                template_file = next((item for item in sorted(child.iterdir()) if item.is_file() and item.suffix.lower() == ".docx"), None)
                if template_file is None:
                    continue
                record = records_by_version.get(str(version))
                versions.append(
                    self._build_template_version_response(
                        template=template,
                        version=version,
                        template_path=template_file,
                        record=record,
                        default_version=default_version,
                    )
                )

        current_path = self.get_template_path(template.id)
        if current_path is not None and all(item.version != template.version for item in versions):
            record = records_by_version.get(str(template.version))
            versions.append(
                self._build_template_version_response(
                    template=template,
                    version=template.version,
                    template_path=current_path,
                    record=record,
                    default_version=default_version,
                )
            )
        return sorted(versions, key=lambda item: item.version, reverse=True)

    def get_template_layout_config(self, template_id: str) -> TemplateLayoutConfigResponse:
        """读取当前模板绑定的版式 YAML，并返回前端可渲染的字段合同。"""

        template = self._require_template_item(template_id)
        layout_path = self._template_version_layout_config_path(template, None)
        if layout_path is None or not layout_path.exists():
            raise FileNotFoundError(f"模板版式配置不存在: {template.id}")
        raw_config = self._load_supported_layout_config(layout_path)
        meta, config = self._split_layout_config(raw_config)
        return TemplateLayoutConfigResponse(
            template_id=template.id,
            template_version_id=self.build_template_version_id(template.id, template.version),
            version=template.version,
            source_path=self._to_repo_relative_path(layout_path),
            config_sha256=self._sha256_prefixed(layout_path),
            meta=meta,
            config=config,
            field_schema=LAYOUT_FIELD_SCHEMA,
        )

    def create_template_layout_config_version(
        self,
        template_id: str,
        *,
        config: dict[str, Any],
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TemplateVersionResponse:
        """把页面提交的版式配置保存为新的模板 draft version，不直接改仓库 YAML。"""

        self._require_resource_version_service()
        template = self._require_template_item(template_id)
        source_template_path = self.get_template_path(template.id)
        if source_template_path is None or not source_template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template.id}")
        source_layout_path = self._template_version_layout_config_path(template, None)
        if source_layout_path is None or not source_layout_path.exists():
            raise FileNotFoundError(f"模板版式配置不存在: {template.id}")
        source_meta, _source_config = self._split_layout_config(self._load_supported_layout_config(source_layout_path))
        validated_config = {
            **source_meta,
            **self._validate_layout_config(config),
        }
        next_version = self._next_template_version(template)
        template_path = self._copy_versioned_template_file(
            template_id=template.id,
            version=next_version,
            source_path=source_template_path,
            source_filename=source_template_path.name,
        )
        layout_path = self._write_versioned_layout_config(
            template_id=template.id,
            version=next_version,
            config=validated_config,
        )
        layout_config_path = self._to_repo_relative_path(layout_path)
        record = self._create_template_resource_draft(
            template=template,
            version=next_version,
            template_path=template_path,
            layout_config_path=layout_config_path,
            render_policy=template.render_policy,
            require_service=True,
        )
        self._record_audit(
            actor=actor,
            action="template.layout_config_version_create",
            target_id=f"{template.id}@{next_version}",
            trace_id=trace_id,
        )
        return self._build_template_version_response(
            template=template,
            version=next_version,
            template_path=template_path,
            record=record,
        )

    def get_template_path(self, template_id: str) -> Path | None:
        template = self._get_template_item(template_id)
        if template is None or not template.enabled:
            return None
        return self._resolve_manifest_path(template.template_path)

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
        path = self.get_template_path(resolved_id)
        if path is None or not path.exists():
            raise FileNotFoundError(f"模板文件不存在: {resolved_id}")
        return path

    def resolve_job_layout_config_path(self, template_id: str | None) -> Path | None:
        """返回 job 选中模板绑定的版式 YAML；模板未绑定时允许 conversion 使用默认配置。"""

        resolved_id = self.resolve_selected_template_id(template_id)
        template = self._get_template_item(resolved_id)
        if template is None or not template.layout_config_path:
            return None
        path = self._resolve_manifest_path(template.layout_config_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"模板版式配置不存在: {resolved_id}")
        return path

    def resolve_template_version(self, template_version_id: str | None) -> TemplateVersionSelection:
        """把任务入参解析到具体模板版本文件和配置包。"""

        template_id, version = self._parse_template_version_id(template_version_id)
        if template_id is None:
            template_id = self.get_default_template_id()
        template = self._require_template_item(template_id)
        if not template.enabled:
            raise FileNotFoundError(f"模板未启用: {template.id}")
        selected_version = version or template.version
        if selected_version in template.disabled_versions:
            raise FileNotFoundError(f"模板版本已禁用: {template.id}@{selected_version}")

        record = self._resource_records_by_version(template.id).get(str(selected_version))
        payload = record.payload if record is not None else None
        template_path = self._template_version_path(template, selected_version, payload)
        if template_path is None or not template_path.exists():
            raise FileNotFoundError(f"模板版本文件不存在: {template.id}@{selected_version}")
        layout_config_path = self._template_version_layout_config_path(template, payload)
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
        manifest_path = self.settings.templates_manifest_file
        if not manifest_path.exists():
            templates: list[TemplateManifestItem] = []
            default_template_path = self.settings.default_template_path
            if default_template_path is not None:
                relative_template_path = self._to_repo_relative_path(default_template_path)
                layout_path = self.settings.layout_config_path
                templates.append(
                    TemplateManifestItem(
                        id=self.settings.default_template_id,
                        name=default_template_path.stem,
                        description="当前默认 DOCX 模板与绑定渲染配置。",
                        enabled=True,
                        is_default_seed=True,
                        version=1,
                        template_path=relative_template_path,
                        layout_config_path=self._to_repo_relative_path(layout_path) if layout_path is not None else None,
                    )
                )
            self._manifest_cache = TemplatesManifest(templates=templates)
            return self._manifest_cache

        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        self._manifest_cache = TemplatesManifest.model_validate(raw)
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
        version_dir = self.settings.templates_storage_dir / template.id
        if version_dir.exists():
            for child in version_dir.iterdir():
                version = self._parse_version_dir_name(child.name)
                if version is not None:
                    existing_versions.append(version)
        return max(existing_versions) + 1

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
        )
        return service.create_or_update_draft(
            resource_type="template",
            resource_id=template.id,
            version=str(version),
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"template:{template.id}@{version}",
            payload=payload,
        )

    def _build_template_version_payload(
        self,
        *,
        template: TemplateManifestItem,
        version: int,
        template_path: Path,
        layout_config_path: str | None,
        render_policy: dict[str, Any],
    ) -> dict[str, Any]:
        layout_path = self._resolve_manifest_path(layout_config_path) if layout_config_path else None
        return {
            "template_id": template.id,
            "version": version,
            "name": template.name,
            "description": template.description,
            "docx_path": self._to_repo_relative_path(template_path),
            "docx_sha256": self._sha256_prefixed(template_path),
            "layout_config_path": layout_config_path,
            "layout_config_sha256": self._sha256_prefixed(layout_path) if layout_path is not None and layout_path.exists() else None,
            "render_policy": render_policy,
        }

    def _activate_template_version(
        self,
        template: TemplateManifestItem,
        version: int,
        payload: dict[str, Any] | None,
    ) -> None:
        path = self._template_version_path(template, version, payload)
        if path is None or not path.exists():
            raise FileNotFoundError(f"模板版本文件不存在: {template.id}@{version}")
        layout_config_path = self._payload_text(payload, "layout_config_path")
        render_policy = self._payload_dict(payload, "render_policy") or template.render_policy
        self._replace_template_item(
            template.model_copy(
                update={
                    "version": version,
                    "template_path": self._to_repo_relative_path(path),
                    "layout_config_path": layout_config_path,
                    "render_policy": render_policy,
                }
            )
        )
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
        layout_config_path = self._payload_text(payload, "layout_config_path")
        if layout_config_path is None:
            layout_config_path = template.layout_config_path
        render_policy = self._payload_dict(payload, "render_policy")
        if render_policy is None:
            render_policy = template.render_policy
        return TemplateVersionResponse(
            template_id=template.id,
            template_version_id=self.build_template_version_id(template.id, version),
            version=version,
            status=status,
            is_current=version == template.version,
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
                path=self._resolve_manifest_path(layout_config_path) if layout_config_path else None,
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

    def _template_version_layout_config_path(
        self,
        template: TemplateManifestItem,
        payload: dict[str, Any] | None,
    ) -> Path | None:
        payload_path = self._payload_text(payload, "layout_config_path")
        manifest_path = payload_path or template.layout_config_path
        return self._resolve_manifest_path(manifest_path) if manifest_path else None

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
            raise FileNotFoundError(f"模板上传文件不存在: {source_path}")
        safe_name = self._safe_template_filename(source_filename, template_id)
        destination_dir = self.settings.templates_storage_dir / template_id / f"v{version}"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / safe_name
        shutil.move(str(source_path), str(destination))
        return destination.resolve()

    def _copy_versioned_template_file(
        self,
        *,
        template_id: str,
        version: int,
        source_path: Path,
        source_filename: str,
    ) -> Path:
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(f"模板文件不存在: {source_path}")
        safe_name = self._safe_template_filename(source_filename, template_id)
        destination_dir = self.settings.templates_storage_dir / template_id / f"v{version}"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / safe_name
        shutil.copy2(str(source_path), str(destination))
        return destination.resolve()

    def _write_versioned_layout_config(
        self,
        *,
        template_id: str,
        version: int,
        config: dict[str, Any],
    ) -> Path:
        destination_dir = self.settings.templates_storage_dir / template_id / f"v{version}"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / "layout_config.yaml"
        temp_path = destination.with_suffix(destination.suffix + ".tmp")
        temp_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        temp_path.replace(destination)
        return destination.resolve()

    def _load_supported_layout_config(self, path: Path) -> dict[str, Any]:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("模板版式配置必须是 YAML object。")
        return {
            key: value
            for key, value in raw.items()
            if key != "sample_content"
        }

    def _split_layout_config(self, raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """把只读元信息和页面可编辑分组拆开，避免前端提交元字段。"""

        meta = {key: raw.get(key) for key in LAYOUT_META_FIELD_SCHEMA if key in raw}
        if "schema_version" not in meta:
            meta["schema_version"] = "template-config/v1"
        config = {
            key: dict(raw[key]) if isinstance(raw[key], dict) else raw[key]
            for key in LAYOUT_GROUP_FIELD_SCHEMA
            if key in raw
        }
        self._complete_layout_font_fields(config)
        return meta, config

    @staticmethod
    def _complete_layout_font_fields(config: dict[str, Any]) -> None:
        """补齐旧版字体字段供编辑和另存；显式空字符串保持模板继承语义。"""

        for group_name, group_schema in LAYOUT_GROUP_FIELD_SCHEMA.items():
            group_value = config.get(group_name)
            if (
                group_name != "footer"
                and "font_name" in group_schema
                and isinstance(group_value, dict)
                and "font_name" in group_value
            ):
                group_value.setdefault("western_font_name", group_value["font_name"])
                group_value.setdefault("complex_script_font_name", group_value["font_name"])

        header = config.get("header")
        if isinstance(header, dict) and "title_font_name" in header:
            header.setdefault("title_western_font_name", header["title_font_name"])
            header.setdefault("title_complex_script_font_name", header["title_font_name"])

        footer = config.get("footer")
        if isinstance(footer, dict):
            footer.setdefault("font_name", "")
            footer.setdefault("western_font_name", "")
            footer.setdefault("complex_script_font_name", "")

    def _validate_layout_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("config 必须是 object。")
        readonly_keys = sorted(set(raw) & set(LAYOUT_META_FIELD_SCHEMA))
        if readonly_keys:
            raise ValueError(f"模板配置元信息为只读字段，不允许提交: {', '.join(readonly_keys)}")
        allowed_top_level = set(LAYOUT_GROUP_FIELD_SCHEMA)
        unknown_keys = sorted(set(raw) - allowed_top_level)
        if "sample_content" in raw:
            unknown_keys.append("sample_content")
        if unknown_keys:
            raise ValueError(f"不支持的模板配置分组: {', '.join(dict.fromkeys(unknown_keys))}")
        missing_keys = [key for key in allowed_top_level if key not in raw]
        if missing_keys:
            raise ValueError(f"模板配置缺少分组: {', '.join(sorted(missing_keys))}")

        validated: dict[str, Any] = {}
        for group_name, group_schema in LAYOUT_GROUP_FIELD_SCHEMA.items():
            group_value = raw[group_name]
            if not isinstance(group_value, dict):
                raise ValueError(f"{group_name} 必须是 object。")
            unknown_fields = sorted(set(group_value) - set(group_schema))
            if unknown_fields:
                raise ValueError(f"{group_name} 包含不支持字段: {', '.join(unknown_fields)}")
            missing_fields = sorted(set(group_schema) - set(group_value))
            if missing_fields:
                raise ValueError(f"{group_name} 缺少字段: {', '.join(missing_fields)}")
            validated[group_name] = {
                field_name: self._validate_layout_value(
                    group_value[field_name],
                    field_schema=field_schema,
                    path=f"{group_name}.{field_name}",
                )
                for field_name, field_schema in group_schema.items()
            }
        return validated

    @staticmethod
    def _validate_layout_value(value: Any, *, field_schema: dict[str, Any], path: str) -> Any:
        field_type = field_schema["type"]
        if field_schema.get("readonly") and path != "header.logo_path":
            raise ValueError(f"{path} 是只读字段。")
        if field_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{path} 必须是 boolean。")
            return value
        if field_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{path} 必须是 number。")
            if value < 0 and not path.endswith("_indent_pt"):
                raise ValueError(f"{path} 不能小于 0。")
            return value
        if field_type == "alignment":
            if value not in ALIGNMENT_VALUES:
                raise ValueError(f"{path} 必须是 {'/'.join(ALIGNMENT_VALUES)}。")
            return value
        if field_type == "color":
            if not isinstance(value, str) or not HEX_COLOR_RE.match(value):
                raise ValueError(f"{path} 必须是 6 位 RGB 颜色。")
            return value
        if field_type == "text":
            if not isinstance(value, str):
                raise ValueError(f"{path} 必须是 string。")
            normalized = value.strip()
            if path == "header.logo_path":
                candidate = Path(normalized)
                if candidate.is_absolute() or ".." in candidate.parts:
                    raise ValueError("header.logo_path 只能是模板配置目录下的相对路径。")
            return normalized
        raise ValueError(f"{path} 字段类型不受支持: {field_type}")

    def _load_state(self) -> TemplateState:
        path = self.settings.template_state_file
        if not path.exists():
            return TemplateState()
        return TemplateState.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_state(self, state: TemplateState) -> None:
        path = self.settings.template_state_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

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

    @staticmethod
    def _snapshot_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
