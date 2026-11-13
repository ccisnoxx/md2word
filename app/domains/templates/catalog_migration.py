from __future__ import annotations

from dataclasses import dataclass

from app.domains.resources.models import ResourceVersionRecord
from app.domains.templates.models import TemplateCatalogItem


@dataclass(frozen=True, slots=True)
class CatalogMigrationSnapshot:
    """在同一次只读事务中采集旧版本和目标目录。"""

    templates: tuple[TemplateCatalogItem, ...]
    versions: tuple[ResourceVersionRecord, ...]
    version_defaults: dict[str, str]
    default_template_id: str | None


class TemplateCatalogMigrationConflict(ValueError):
    """预检后模板数据发生变化，必须重新核对。"""
