from __future__ import annotations

# app/domains/resources/models.py: 定义模板、术语和翻译配置共用的资源版本记录。

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ResourceType = Literal["template", "term_rule_set", "translation_profile"]


class ResourceVersionStatus(str, Enum):
    """资源版本生命周期状态。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"
    SUPERSEDED = "superseded"


class ResourceVersionRecord(BaseModel):
    """持久化的资源版本快照；发布后由 service 保证不可原地修改。"""

    resource_type: ResourceType
    resource_id: str
    version: str
    status: ResourceVersionStatus = ResourceVersionStatus.DRAFT
    snapshot_hash: str
    payload_ref: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("snapshot_hash")
    @classmethod
    def validate_snapshot_hash(cls, value: str) -> str:
        if not value.startswith("sha256:"):
            raise ValueError("snapshot_hash 必须使用 sha256:<hex> 格式。")
        digest = value.removeprefix("sha256:")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            raise ValueError("snapshot_hash 必须包含 64 位十六进制 sha256。")
        return value


class ResolvedResourceVersion(BaseModel):
    """job 创建快照可消费的已发布资源版本。"""

    resource_type: ResourceType
    resource_id: str
    version: str
    status: Literal["published"] = "published"
    snapshot_hash: str
    payload_ref: str | None = None
