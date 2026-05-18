from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

from app.core.config import Settings
from app.core.template_models import TemplateManifestItem, TemplateState, TemplatesManifest
from app.schemas.api_v1 import TemplateAssetResponse, TemplateDetailResponse, TemplateListItemResponse


@dataclass(frozen=True, slots=True)
class AssetSpec:
    key: str
    label: str
    path_getter: str


ASSET_SPECS: tuple[AssetSpec, ...] = (
    AssetSpec(key="template", label="Word 模板", path_getter="default_template_path"),
    AssetSpec(key="layout_config", label="页面布局 YAML", path_getter="layout_config_path"),
    AssetSpec(key="subscript_config", label="术语上下标 YAML", path_getter="subscript_config_path"),
)


class TemplateReadService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
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
            is_default=template.id == current_default_id,
            downloadable=template_asset.exists,
            download_url=template_asset.download_url,
            template=template_asset,
            layout_config=layout_asset,
            subscript_config=subscript_asset,
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
                        template_path=relative_template_path,
                        layout_config_path=self._to_repo_relative_path(layout_path) if layout_path is not None else None,
                    )
                )
            self._manifest_cache = TemplatesManifest(templates=templates)
            return self._manifest_cache

        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        self._manifest_cache = TemplatesManifest.model_validate(raw)
        return self._manifest_cache

    def _visible_templates(self) -> list[TemplateManifestItem]:
        return [item for item in self._load_manifest().templates if item.enabled]

    def _get_template_item(self, template_id: str) -> TemplateManifestItem | None:
        for item in self._load_manifest().templates:
            if item.id == template_id:
                return item
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
