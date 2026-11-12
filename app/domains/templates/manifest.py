"""模板清单解析与仓库内置默认资源的唯一入口。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.domains.templates.models import TemplateManifestItem, TemplatesManifest


BUNDLED_TEMPLATE_MANIFEST = "resources/template_configs/templates_manifest.yaml"


@dataclass(frozen=True, slots=True)
class BundledTemplateSeed:
    """同一清单条目声明的版本及 DOCX、YAML 路径。"""

    item: TemplateManifestItem
    template_path: Path
    layout_config_path: Path


def load_template_manifest(path: Path) -> TemplatesManifest:
    """读取已配置的模板清单，外部错误只包含固定文案。"""

    try:
        content = path.read_bytes()
    except FileNotFoundError:
        raise FileNotFoundError("模板清单不存在。") from None
    except OSError:
        raise ValueError("模板清单无法读取。") from None
    try:
        raw = yaml.safe_load(content)
        return TemplatesManifest.model_validate({} if raw is None else raw)
    except (yaml.YAMLError, UnicodeError, ValidationError):
        raise ValueError("模板清单格式无效。") from None


def resolve_bundled_template_seed(root_dir: Path) -> BundledTemplateSeed:
    """从仓库清单选择唯一启用的默认 seed，调用方按用途核对文件实物。"""

    manifest = load_template_manifest(root_dir / BUNDLED_TEMPLATE_MANIFEST)
    seeds = [item for item in manifest.templates if item.enabled and item.is_default_seed]
    if len(seeds) != 1:
        raise ValueError("仓库模板清单必须标记唯一启用的默认 seed。")
    item = seeds[0]
    layout_path = item.layout_config_path
    if item.version < 1 or not item.template_path.strip() or not layout_path or not layout_path.strip():
        raise ValueError("内置默认模板必须绑定有效版本及 DOCX、YAML 路径。")
    try:
        return BundledTemplateSeed(
            item=item,
            template_path=(root_dir / item.template_path).resolve(),
            layout_config_path=(root_dir / layout_path).resolve(),
        )
    except (OSError, RuntimeError):
        raise ValueError("内置默认模板资源路径无法解析。") from None
