"""Word 模板样式配置 v1 的唯一结构、编辑元数据和校验合同。"""

from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


SUPPORTED_SCHEMA_VERSION = "template-config/v1"
ALIGNMENT_VALUES = ("left", "center", "right", "justify")


class TemplateLayoutValidationError(ValueError):
    """携带字段路径和稳定错误码的模板样式校验错误。"""

    def __init__(self, message: str, *, path: str, code: str = "invalid") -> None:
        super().__init__(message)
        self.path = path
        self.code = code


class TemplatePageSetupConfig(BaseModel):
    """页面尺寸与边距，单位沿用 YAML 中的 cm。"""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    page_width_cm: float | None = None
    page_height_cm: float | None = None
    top_margin: float | None = None
    bottom_margin: float | None = None
    left_margin: float | None = None
    right_margin: float | None = None
    header_distance: float | None = None
    footer_distance: float | None = None


class TemplateParagraphStyleConfig(BaseModel):
    """段落、标题和表格文字共享的运行时字段。"""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    font_name: str | None = None
    western_font_name: str | None = None
    complex_script_font_name: str | None = None
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    color: str | None = None
    alignment: Literal["left", "center", "right", "justify"] | None = None
    line_spacing: float | None = None
    space_before: float | None = None
    space_after: float | None = None
    first_line_indent_pt: float | None = None
    left_indent_pt: float | None = None
    right_indent_pt: float | None = None
    word_style_name: str | None = None


class TemplateHeaderConfig(BaseModel):
    """页眉覆盖配置；Logo 路径不属于页面可编辑字段。"""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    enabled: bool = False
    logo_path: str | None = None
    logo_height_cm: float | None = None
    title_text: str | None = None
    title_font_name: str | None = None
    title_western_font_name: str | None = None
    title_complex_script_font_name: str | None = None
    title_font_size: float | None = None
    title_color: str | None = None


class TemplateFooterConfig(BaseModel):
    """页脚覆盖、页码和模板既有文字的字体配置。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    enabled: bool = False
    left_text: str = ""
    right_text: str = ""
    show_page_number: bool = False
    font_name: str | None = None
    western_font_name: str | None = None
    complex_script_font_name: str | None = None
    alignment: Literal["left", "center", "right"] | None = "center"


class TemplateTableStyleConfig(BaseModel):
    """表格边框、表头和 Word 表格样式配置。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    style_name: str = "Table Grid"
    header_bold: bool = True
    header_fill: str | None = "EEF3F8"
    border_color: str | None = "C7CDD4"


class TemplateSampleContent(BaseModel):
    """只读预览样例，不参与真实任务内容生成。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    part_number: str | None = None
    category: str | None = None
    heading1_text: str | None = None
    heading2_text: str | None = None
    heading3_text: str | None = None
    normal_text: str | None = None
    table_note_text: str | None = None
    caption_text: str | None = None


class TemplateConfigPackage(BaseModel):
    """模板配置包 v1；编辑、保存和 Word renderer 共同消费。"""

    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    schema_version: Literal["template-config/v1"] = SUPPORTED_SCHEMA_VERSION
    template_name: str = ""
    output_filename: str | None = None
    page_setup: TemplatePageSetupConfig = Field(default_factory=TemplatePageSetupConfig)
    part_number: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    category: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    heading1: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    heading2: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    heading3: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    toc_title: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    toc_level1: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    toc_level2: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    toc_level3: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    normal: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    table_content: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    table_style: TemplateTableStyleConfig = Field(default_factory=TemplateTableStyleConfig)
    table_note: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    caption: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    long_table_caption: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    header: TemplateHeaderConfig = Field(default_factory=TemplateHeaderConfig)
    footer: TemplateFooterConfig = Field(default_factory=TemplateFooterConfig)
    sample_content: TemplateSampleContent | None = None
    language_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    terminology: Any | None = Field(default=None, exclude=True)

    @classmethod
    def load(cls, config_path: Path | None) -> "TemplateConfigPackage":
        """加载渲染配置；显式文件缺失或字段非法时直接失败。"""

        if config_path is None:
            return cls()
        if not config_path.exists() or not config_path.is_file():
            raise FileNotFoundError(f"模板配置文件不存在: {config_path}")
        raw = _read_yaml_object(config_path)
        if raw.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(f"schema_version 必须是 {SUPPORTED_SCHEMA_VERSION}。")
        try:
            package = cls.model_validate(_normalize_legacy_font_fields(raw))
        except ValidationError as exc:
            first = exc.errors(include_url=False)[0]
            path = ".".join(str(item) for item in first["loc"])
            raise ValueError(f"{path}: {first['msg']}") from exc
        _validate_package_values(package)
        _validate_page_body(package.page_setup)
        return package

    def heading_style_for_level(self, level: int | None) -> TemplateParagraphStyleConfig:
        normalized_level = max(1, min(int(level or 1), 3))
        return (self.heading1, self.heading2, self.heading3)[normalized_level - 1]

    def heading_word_style_name_for_level(self, level: int | None) -> str:
        normalized_level = max(1, min(int(level or 1), 3))
        return self.heading_style_for_level(normalized_level).word_style_name or f"Heading {normalized_level}"

    def toc_style_for_level(self, level: int | None) -> TemplateParagraphStyleConfig:
        normalized_level = max(1, min(int(level or 1), 3))
        return (self.toc_level1, self.toc_level2, self.toc_level3)[normalized_level - 1]

    def for_document_language(self, document_language: str | None) -> "TemplateConfigPackage":
        """在单次渲染中应用显式语言 override。"""

        language = (document_language or "").strip().lower()
        if not language or not self.language_overrides:
            return self
        candidates = [language]
        if "-" in language:
            candidates.append(language.split("-", 1)[0])
        if "_" in language:
            candidates.append(language.split("_", 1)[0])
        selected = next((self.language_overrides[key] for key in candidates if key in self.language_overrides), None)
        if not selected:
            return self
        raw = self.model_dump(mode="python", exclude={"terminology"})
        return self.__class__.model_validate(_deep_merge_dicts(raw, selected))


def _field(
    field_type: str,
    label: str,
    *,
    unit: str | None = None,
    readonly: bool = False,
    minimum: float | None = None,
    maximum: float | None = None,
    step: float | None = None,
    options: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": field_type, "label": label, "readonly": readonly}
    for key, value in (("unit", unit), ("min", minimum), ("max", maximum), ("step", step)):
        if value is not None:
            schema[key] = value
    if options is not None:
        schema["options"] = list(options)
    return schema


META_FIELD_SCHEMA = {
    "schema_version": _field("text", "schema_version", readonly=True),
    "template_name": _field("text", "配置名称", readonly=True),
    "output_filename": _field("text", "输出文件名", readonly=True),
}

PARAGRAPH_FIELDS = {
    "font_name": _field("text", "中文字体"),
    "western_font_name": _field("text", "西文字体"),
    "complex_script_font_name": _field("text", "复杂文种字体"),
    "font_size": _field("number", "字号", unit="pt", minimum=1, maximum=200, step=0.5),
    "bold": _field("boolean", "加粗"),
    "color": _field("color", "颜色"),
    "alignment": _field("alignment", "对齐方式", options=ALIGNMENT_VALUES),
    "space_before": _field("number", "段前间距", unit="pt", minimum=0, maximum=500, step=0.5),
    "space_after": _field("number", "段后间距", unit="pt", minimum=0, maximum=500, step=0.5),
    "line_spacing": _field("number", "行距", minimum=0.5, maximum=5, step=0.05),
    "first_line_indent_pt": _field("number", "首行缩进", unit="pt", minimum=-500, maximum=500, step=0.5),
    "left_indent_pt": _field("number", "左缩进", unit="pt", minimum=-500, maximum=500, step=0.5),
    "right_indent_pt": _field("number", "右缩进", unit="pt", minimum=-500, maximum=500, step=0.5),
}

TEXT_STYLE_FIELDS = {
    key: PARAGRAPH_FIELDS[key]
    for key in (
        "font_name",
        "western_font_name",
        "complex_script_font_name",
        "font_size",
        "bold",
        "alignment",
        "space_after",
    )
}
TOC_FIELDS = {key: value for key, value in PARAGRAPH_FIELDS.items() if not key.endswith("_indent_pt")}

GROUP_FIELD_SCHEMA: dict[str, dict[str, dict[str, Any]]] = {
    "page_setup": {
        "page_width_cm": _field("number", "页面宽度", unit="cm", readonly=True, minimum=1, maximum=100),
        "page_height_cm": _field("number", "页面高度", unit="cm", readonly=True, minimum=1, maximum=100),
        "top_margin": _field("number", "上边距", unit="cm", minimum=0, maximum=10, step=0.1),
        "bottom_margin": _field("number", "下边距", unit="cm", minimum=0, maximum=10, step=0.1),
        "left_margin": _field("number", "左边距", unit="cm", minimum=0, maximum=10, step=0.1),
        "right_margin": _field("number", "右边距", unit="cm", minimum=0, maximum=10, step=0.1),
        "header_distance": _field("number", "页眉距离", unit="cm", minimum=0, maximum=10, step=0.1),
        "footer_distance": _field("number", "页脚距离", unit="cm", minimum=0, maximum=10, step=0.1),
    },
    "part_number": TEXT_STYLE_FIELDS,
    "category": TEXT_STYLE_FIELDS,
    "heading1": PARAGRAPH_FIELDS,
    "heading2": PARAGRAPH_FIELDS,
    "heading3": PARAGRAPH_FIELDS,
    "toc_title": TOC_FIELDS,
    "toc_level1": TOC_FIELDS,
    "toc_level2": TOC_FIELDS,
    "toc_level3": TOC_FIELDS,
    "normal": PARAGRAPH_FIELDS,
    "table_content": {key: value for key, value in PARAGRAPH_FIELDS.items() if key != "bold"},
    "table_style": {
        "style_name": _field("text", "表格样式"),
        "header_fill": _field("color", "表头底色"),
        "border_color": _field("color", "边框颜色"),
    },
    "table_note": {
        **{key: value for key, value in PARAGRAPH_FIELDS.items() if key != "bold"},
        "italic": _field("boolean", "斜体"),
    },
    "caption": PARAGRAPH_FIELDS,
    "long_table_caption": PARAGRAPH_FIELDS,
    "header": {
        "enabled": _field("boolean", "启用页眉覆盖"),
        "logo_path": _field("text", "Logo 路径", readonly=True),
        "logo_height_cm": _field("number", "Logo 高度", unit="cm", minimum=0.1, maximum=10, step=0.1),
        "title_text": _field("text", "页眉标题"),
        "title_font_name": _field("text", "页眉中文字体"),
        "title_western_font_name": _field("text", "页眉西文字体"),
        "title_complex_script_font_name": _field("text", "页眉复杂文种字体"),
        "title_font_size": _field("number", "页眉字号", unit="pt", minimum=1, maximum=200, step=0.5),
        "title_color": _field("color", "页眉颜色"),
    },
    "footer": {
        "enabled": _field("boolean", "启用页脚覆盖"),
        "left_text": _field("text", "页脚左侧文字"),
        "right_text": _field("text", "页脚右侧文字"),
        "show_page_number": _field("boolean", "显示页码"),
        "font_name": _field("text", "页脚中文字体"),
        "western_font_name": _field("text", "页脚西文字体"),
        "complex_script_font_name": _field("text", "页脚复杂文种字体"),
        "alignment": _field("alignment", "页脚对齐", options=("left", "center", "right")),
    },
}

GROUP_META = {
    "page_setup": ("页面设置", "页面", "控制 A4 页边距和页眉页脚距离。"),
    "part_number": ("首页型号行", "首页", "控制首页器件型号行。"),
    "category": ("首页品类行", "首页", "控制首页器件品类行。"),
    "heading1": ("一级标题", "标题", "控制一级章节标题。"),
    "heading2": ("二级标题", "标题", "控制二级章节标题。"),
    "heading3": ("三级标题", "标题", "控制三级章节标题。"),
    "toc_title": ("目录标题", "目录", "控制目录标题。"),
    "toc_level1": ("目录一级项", "目录", "控制目录一级条目。"),
    "toc_level2": ("目录二级项", "目录", "控制目录二级条目。"),
    "toc_level3": ("目录三级项", "目录", "控制目录三级条目。"),
    "normal": ("正文", "正文", "控制普通正文段落。"),
    "table_content": ("表格正文", "表格与图注", "控制表格单元格文字。"),
    "table_style": ("表格样式", "表格与图注", "控制表格样式、表头底色和边框。"),
    "table_note": ("表格注释", "表格与图注", "控制表格下方注释。"),
    "caption": ("图注 / 表题", "表格与图注", "控制图片标题和表格标题。"),
    "long_table_caption": ("续表标题", "表格与图注", "控制拆分续表标题。"),
    "header": ("页眉", "页眉页脚", "控制渲染器页眉覆盖。"),
    "footer": ("页脚", "页眉页脚", "控制渲染器页脚覆盖和页码。"),
}

CATEGORY_ORDER = ("页面", "首页", "标题", "目录", "正文", "表格与图注", "页眉页脚")


def editor_field_schema() -> dict[str, Any]:
    """返回前端可直接渲染且顺序稳定的编辑合同。"""

    categories = [
        {
            "key": f"category_{index + 1}",
            "label": category,
            "order": index,
            "groups": [group for group, meta in GROUP_META.items() if meta[1] == category],
        }
        for index, category in enumerate(CATEGORY_ORDER)
    ]
    group_meta = {
        group: {
            "label": meta[0],
            "category": meta[1],
            "description": meta[2],
            "order": index,
        }
        for index, (group, meta) in enumerate(GROUP_META.items())
    }
    return {
        "schema_version": "template-layout-editor/v1",
        "meta": deepcopy(META_FIELD_SCHEMA),
        "categories": categories,
        "group_meta": group_meta,
        "groups": deepcopy(GROUP_FIELD_SCHEMA),
    }


def validate_layout_config(raw: dict[str, Any]) -> TemplateConfigPackage:
    """严格校验完整配置，拒绝未知字段和缺失的一级样式分组。"""

    if raw.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise TemplateLayoutValidationError(
            f"schema_version 必须是 {SUPPORTED_SCHEMA_VERSION}。",
            path="schema_version",
            code="unsupported_schema_version",
        )
    missing_groups = [group for group in GROUP_FIELD_SCHEMA if group not in raw]
    if missing_groups:
        raise TemplateLayoutValidationError(
            f"模板配置缺少分组: {', '.join(missing_groups)}",
            path=missing_groups[0],
            code="missing_group",
        )
    normalized_raw = _normalize_legacy_font_fields(raw)
    try:
        package = TemplateConfigPackage.model_validate(normalized_raw)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        path = ".".join(str(item) for item in first["loc"])
        raise TemplateLayoutValidationError(
            f"{path}: {first['msg']}",
            path=path,
            code="schema_validation_failed",
        ) from exc
    _validate_package_values(package)
    _validate_page_body(package.page_setup)
    return package


def split_layout_config(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """拆分只读元信息、完整样式值和只读预览样例。"""

    package = validate_layout_config(raw)
    normalized = package.model_dump(mode="python", exclude={"terminology", "language_overrides"}, exclude_none=True)
    meta = {key: normalized[key] for key in META_FIELD_SCHEMA if key in normalized}
    config = {group: normalized[group] for group in GROUP_FIELD_SCHEMA}
    preview_samples = normalized.get("sample_content", {})
    return meta, config, preview_samples


def apply_layout_changes(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """把白名单叶子变更合并到 exact base，并重新校验完整配置。"""

    validate_layout_config(base)
    if not isinstance(changes, dict) or not changes:
        raise TemplateLayoutValidationError(
            "changes 至少需要包含一个样式字段。",
            path="changes",
            code="empty_changes",
        )
    merged = deepcopy(base)
    changed_count = 0
    for group_name, group_changes in changes.items():
        group_schema = GROUP_FIELD_SCHEMA.get(group_name)
        if group_schema is None:
            raise TemplateLayoutValidationError(
                f"不支持的模板配置分组: {group_name}",
                path=group_name,
                code="unknown_group",
            )
        if not isinstance(group_changes, dict) or not group_changes:
            raise TemplateLayoutValidationError(
                f"{group_name} 必须包含至少一个字段。",
                path=group_name,
                code="empty_group_changes",
            )
        for field_name, value in group_changes.items():
            field_schema = group_schema.get(field_name)
            path = f"{group_name}.{field_name}"
            if field_schema is None:
                raise TemplateLayoutValidationError(
                    f"{group_name} 包含不支持字段: {field_name}",
                    path=path,
                    code="unknown_field",
                )
            if field_schema.get("readonly"):
                raise TemplateLayoutValidationError(
                    f"{path} 是只读字段。",
                    path=path,
                    code="readonly_field",
                )
            merged[group_name][field_name] = _validate_editor_value(value, field_schema, path)
            changed_count += 1
    if changed_count == 0:
        raise TemplateLayoutValidationError(
            "changes 至少需要包含一个样式字段。",
            path="changes",
            code="empty_changes",
        )
    package = validate_layout_config(merged)
    return package.model_dump(mode="python", exclude={"terminology"}, exclude_none=True)


def _validate_editor_value(value: Any, schema: dict[str, Any], path: str) -> Any:
    field_type = schema["type"]
    if field_type == "boolean":
        if not isinstance(value, bool):
            raise TemplateLayoutValidationError(f"{path} 必须是 boolean。", path=path, code="invalid_type")
        return value
    if field_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise TemplateLayoutValidationError(f"{path} 必须是有限 number。", path=path, code="invalid_number")
        if "min" in schema and value < schema["min"]:
            raise TemplateLayoutValidationError(f"{path} 不能小于 {schema['min']}。", path=path, code="below_minimum")
        if "max" in schema and value > schema["max"]:
            raise TemplateLayoutValidationError(f"{path} 不能大于 {schema['max']}。", path=path, code="above_maximum")
        return value
    if field_type in {"alignment", "enum"}:
        if value not in schema.get("options", []):
            raise TemplateLayoutValidationError(f"{path} 不是受支持的选项。", path=path, code="invalid_option")
        return value
    if field_type == "color":
        if value is None:
            return None
        if not isinstance(value, str):
            raise TemplateLayoutValidationError(f"{path} 必须是 6 位 RGB 颜色。", path=path, code="invalid_color")
        raw_color = value.strip()
        if not raw_color:
            return ""
        normalized = raw_color[1:] if raw_color.startswith("#") else raw_color
        if len(normalized) != 6 or any(char not in "0123456789abcdefABCDEF" for char in normalized):
            raise TemplateLayoutValidationError(f"{path} 必须是 6 位 RGB 颜色。", path=path, code="invalid_color")
        return f"#{normalized.upper()}"
    if field_type == "text":
        if not isinstance(value, str):
            raise TemplateLayoutValidationError(f"{path} 必须是 string。", path=path, code="invalid_type")
        normalized = value.strip()
        max_length = 500 if path == "header.title_text" else 128
        primary_font = path == "header.title_font_name" or (
            path.endswith(".font_name")
            and not path.endswith((".western_font_name", ".complex_script_font_name"))
            and path != "footer.font_name"
        )
        if primary_font or path == "table_style.style_name":
            if not normalized:
                raise TemplateLayoutValidationError(f"{path} 不能为空。", path=path, code="blank_value")
        if len(normalized) > max_length:
            raise TemplateLayoutValidationError(f"{path} 长度不能超过 {max_length}。", path=path, code="too_long")
        return normalized
    raise TemplateLayoutValidationError(
        f"{path} 字段类型不受支持: {field_type}",
        path=path,
        code="unsupported_field_type",
    )


def _validate_package_values(package: TemplateConfigPackage) -> None:
    """用编辑合同中的同一范围规则校验 renderer 和管理 API 的完整值。"""

    normalized = package.model_dump(mode="python", exclude={"terminology"}, exclude_none=True)
    for group_name, group_schema in GROUP_FIELD_SCHEMA.items():
        group_value = normalized[group_name]
        for field_name, field_schema in group_schema.items():
            if field_name in group_value:
                _validate_editor_value(group_value[field_name], field_schema, f"{group_name}.{field_name}")
    logo_path = package.header.logo_path
    if logo_path is not None:
        logo_candidate = Path(logo_path)
        if logo_candidate.is_absolute() or ".." in logo_candidate.parts:
            raise TemplateLayoutValidationError(
                "header.logo_path 只能是模板配置目录下的相对路径。",
                path="header.logo_path",
                code="invalid_relative_path",
            )


def _validate_page_body(setup: TemplatePageSetupConfig) -> None:
    width = setup.page_width_cm
    height = setup.page_height_cm
    if width is not None and setup.left_margin is not None and setup.right_margin is not None:
        if setup.left_margin + setup.right_margin >= width:
            raise TemplateLayoutValidationError(
                "page_setup 左右边距必须小于页面宽度。",
                path="page_setup",
                code="invalid_page_body",
            )
    if height is not None and setup.top_margin is not None and setup.bottom_margin is not None:
        if setup.top_margin + setup.bottom_margin >= height:
            raise TemplateLayoutValidationError(
                "page_setup 上下边距必须小于页面高度。",
                path="page_setup",
                code="invalid_page_body",
            )


def _normalize_legacy_font_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """在严格校验前补齐旧配置缺失的字体槽位，显式空值保持不变。"""

    normalized = deepcopy(raw)
    for group_name, group_schema in GROUP_FIELD_SCHEMA.items():
        group = normalized.get(group_name)
        if group_name == "footer" or "font_name" not in group_schema or not isinstance(group, dict):
            continue
        if "font_name" in group:
            group.setdefault("western_font_name", group["font_name"])
            group.setdefault("complex_script_font_name", group["font_name"])

    header = normalized.get("header")
    if isinstance(header, dict) and "title_font_name" in header:
        header.setdefault("title_western_font_name", header["title_font_name"])
        header.setdefault("title_complex_script_font_name", header["title_font_name"])

    footer = normalized.get("footer")
    if isinstance(footer, dict):
        footer.setdefault("font_name", "")
        footer.setdefault("western_font_name", "")
        footer.setdefault("complex_script_font_name", "")
    return normalized


def _read_yaml_object(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"模板配置必须是 YAML object: {path}")
    return raw


def _deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged
