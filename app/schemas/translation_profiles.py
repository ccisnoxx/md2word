from __future__ import annotations

# app/schemas/translation_profiles.py: 定义 Translation Profile 版本管理 API 的 v1 请求/响应模型。

from datetime import datetime

from pydantic import BaseModel, Field


class TranslationProfileListItemResponse(BaseModel):
    id: str
    default_version: str | None = None
    version_count: int
    target_language: str
    domain: str
    prompt_version: str
    model: str | None = None
    max_pages_per_batch: int
    max_chars_per_batch: int


class TranslationProfileListResponse(BaseModel):
    items: list[TranslationProfileListItemResponse]


class TranslationProfileVersionResponse(BaseModel):
    translation_profile_id: str
    version: str
    status: str
    snapshot_hash: str | None = None
    is_default: bool = False
    target_language: str
    domain: str
    prompt_version: str
    model: str | None = None
    max_pages_per_batch: int
    max_chars_per_batch: int
    published_at: datetime | None = None


class TranslationProfileDetailResponse(BaseModel):
    id: str
    default_version: str | None = None
    versions: list[TranslationProfileVersionResponse]


class TranslationProfileDraftResponse(BaseModel):
    translation_profile_id: str
    base_version: str | None = None
    target_language: str
    domain: str
    prompt_version: str
    model: str | None = None
    max_pages_per_batch: int
    max_chars_per_batch: int
    snapshot_hash: str | None = None


class TranslationProfileDraftUpdateRequest(BaseModel):
    target_language: str = Field(default="zh-CN", min_length=1, max_length=32)
    domain: str = Field(default="electronics engineering technical document", min_length=1, max_length=200)
    prompt_version: str = Field(default="translation-minimal-v1", min_length=1, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    max_pages_per_batch: int = Field(default=20, ge=1, le=500)
    max_chars_per_batch: int = Field(default=60000, ge=1, le=500000)


class TranslationProfilePublishRequest(BaseModel):
    make_default: bool = True


class TranslationProfileRollbackRequest(BaseModel):
    version: str
