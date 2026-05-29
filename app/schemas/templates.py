from __future__ import annotations

# app/schemas/templates.py: 定义 templates API 的 v1 请求/响应模型。

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TemplateAssetResponse(BaseModel):
    label: str
    exists: bool
    file_name: str | None = None
    size_bytes: int | None = None
    updated_at: datetime | None = None
    sha256: str | None = None
    download_url: str | None = None


class TemplateListItemResponse(BaseModel):
    id: str
    name: str
    description: str
    version: int
    is_default: bool
    downloadable: bool
    download_url: str | None = None
    template: TemplateAssetResponse
    layout_config: TemplateAssetResponse
    subscript_config: TemplateAssetResponse


class TemplateDetailResponse(TemplateListItemResponse):
    def to_list_item(self) -> "TemplateListItemResponse":
        return TemplateListItemResponse.model_validate(self.model_dump())


class TemplateListResponse(BaseModel):
    items: list[TemplateListItemResponse]


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    layout_config_path: str | None = None
    render_policy: dict[str, Any] | None = None


class TemplateVersionPublishRequest(BaseModel):
    make_default: bool = False


class TemplateVersionDefaultRequest(BaseModel):
    reason: str | None = None


class TemplateVersionResponse(BaseModel):
    template_id: str | None = None
    template_version_id: str | None = None
    version: int
    status: str = "published"
    is_current: bool
    is_default: bool = False
    snapshot_hash: str | None = None
    render_policy: dict[str, Any] = Field(default_factory=dict)
    template: TemplateAssetResponse
    layout_config: TemplateAssetResponse | None = None


class TemplateVersionListResponse(BaseModel):
    template_id: str
    items: list[TemplateVersionResponse]


class TemplateDeleteResponse(BaseModel):
    id: str
    deleted: bool
