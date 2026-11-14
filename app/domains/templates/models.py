from __future__ import annotations

# app/domains/templates/models.py: 定义模板目录、内置清单与旧默认状态。

import re
from typing import Any

from pydantic import BaseModel, Field


def validate_template_id(value: str) -> str:
    """模板 ID 同时用作数据库键和受管目录的单个路径段。"""

    template_id = value.strip()
    if template_id in {".", ".."} or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", template_id) is None:
        raise ValueError("template_id 只能包含大小写字母、数字、下划线、短横线和英文句点，长度不超过 128，且不能为 . 或 ..。")
    return template_id


class TemplateMetadata(BaseModel):
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    layout_config_path: str | None = None
    render_policy: dict[str, Any] = Field(default_factory=dict)


class TemplateManifestItem(TemplateMetadata):
    is_default_seed: bool = False
    version: int = 1
    template_path: str
    disabled_versions: list[int] = Field(default_factory=list)


class TemplateCatalogItem(TemplateMetadata):
    """模板级目录元数据，版本身份和资产由资源版本记录持有。"""

    deleted: bool = False


class TemplatesManifest(BaseModel):
    templates: list[TemplateManifestItem] = Field(default_factory=list)


class TemplateState(BaseModel):
    default_template_id: str | None = None
