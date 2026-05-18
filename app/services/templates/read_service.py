from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.config import Settings
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

    def list_templates(self, *, url_for: Callable[..., str] | None) -> list[TemplateListItemResponse]:
        detail = self.get_template_detail(self.settings.default_template_id, url_for=url_for)
        return [detail.to_list_item()] if detail is not None else []

    def get_template_detail(
        self,
        template_id: str,
        *,
        url_for: Callable[..., str] | None,
    ) -> TemplateDetailResponse | None:
        if template_id != self.settings.default_template_id:
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
            path=self.settings.layout_config_path,
            label="页面布局 YAML",
            download_url=None,
        )
        subscript_asset = self._build_asset(
            path=self.settings.subscript_config_path,
            label="术语上下标 YAML",
            download_url=None,
        )

        name = template_path.stem if template_path is not None else self.settings.default_template_id
        return TemplateDetailResponse(
            id=self.settings.default_template_id,
            name=name,
            description="当前默认 DOCX 模板与绑定渲染配置。",
            is_default=True,
            downloadable=template_asset.exists,
            download_url=template_asset.download_url,
            template=template_asset,
            layout_config=layout_asset,
            subscript_config=subscript_asset,
        )

    def get_template_path(self, template_id: str) -> Path | None:
        if template_id != self.settings.default_template_id:
            return None
        return self.settings.default_template_path

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
