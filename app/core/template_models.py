from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateManifestItem(BaseModel):
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    is_default_seed: bool = False
    template_path: str
    layout_config_path: str | None = None


class TemplatesManifest(BaseModel):
    templates: list[TemplateManifestItem] = Field(default_factory=list)


class TemplateState(BaseModel):
    default_template_id: str | None = None
