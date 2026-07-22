from __future__ import annotations

# app/domains/templates/schemas.py: 定义 templates API 的 v1 请求/响应模型。

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


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
    publish_reason: str
    verification_job_id: str
    verification_note: str

    @field_validator("publish_reason", "verification_job_id", "verification_note")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class TemplateVersionDefaultRequest(BaseModel):
    set_default_reason: str

    @field_validator("set_default_reason")
    @classmethod
    def validate_set_default_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("set_default_reason 不能为空")
        return normalized


class TemplateVersionResponse(BaseModel):
    template_id: str | None = None
    template_version_id: str | None = None
    version: int
    status: str = "published"
    is_current: bool
    is_default: bool = False
    snapshot_hash: str | None = None
    render_policy: dict[str, Any] = Field(default_factory=dict)
    verification_job_id: str | None = None
    verification_note: str | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    publish_reason: str | None = None
    published_by: str | None = None
    published_at: datetime | None = None
    template: TemplateAssetResponse
    layout_config: TemplateAssetResponse | None = None


class TemplateVersionListResponse(BaseModel):
    template_id: str
    items: list[TemplateVersionResponse]


class TemplateLayoutConfigResponse(BaseModel):
    template_id: str
    template_version_id: str | None = None
    version: int
    status: str
    is_default: bool = False
    active_template_version_id: str
    source_path: str | None = None
    config_sha256: str | None = None
    snapshot_hash: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    preview_samples: dict[str, Any] = Field(default_factory=dict)
    field_schema: dict[str, Any] = Field(default_factory=dict)


class TemplateLayoutConfigDraftRequest(BaseModel):
    base_template_version_id: str
    expected_config_sha256: str
    expected_active_template_version_id: str
    changes: dict[str, Any]
    change_note: str = Field(default="", max_length=500)


class TemplateDeleteResponse(BaseModel):
    id: str
    deleted: bool
