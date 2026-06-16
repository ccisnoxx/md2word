from __future__ import annotations

# app/domains/templates/models.py: 定义模板 manifest 和运行时默认态的数据模型。

from typing import Any

from pydantic import BaseModel, Field


class TemplateManifestItem(BaseModel):
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    is_default_seed: bool = False
    version: int = 1
    template_path: str
    layout_config_path: str | None = None
    render_policy: dict[str, Any] = Field(default_factory=dict)
    disabled_versions: list[int] = Field(default_factory=list)


class TemplatesManifest(BaseModel):
    templates: list[TemplateManifestItem] = Field(default_factory=list)


class TemplateState(BaseModel):
    default_template_id: str | None = None
