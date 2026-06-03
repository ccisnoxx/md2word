from __future__ import annotations

# app/services/renderer/template_config.py: 定义模板配置包 v1 的结构化配置模型。

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class TemplatePageSetupConfig(BaseModel):
    """模板页面设置；单位沿用配置文件中的 cm。"""

    model_config = ConfigDict(extra="ignore")

    top_margin: float | None = None
    bottom_margin: float | None = None
    left_margin: float | None = None
    right_margin: float | None = None
    header_distance: float | None = None
    footer_distance: float | None = None


class TemplateParagraphStyleConfig(BaseModel):
    """段落/标题/表格文字样式配置；字段名保持 YAML 稳定。"""

    model_config = ConfigDict(extra="ignore")

    font_name: str | None = None
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
    """页眉配置，Logo 路径相对模板配置文件所在目录解析。"""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    logo_path: str | None = None
    logo_height_cm: float | None = None
    title_text: str | None = None
    title_font_name: str | None = None
    title_font_size: float | None = None
    title_color: str | None = None


class TemplateFooterConfig(BaseModel):
    """页脚配置；P0 只支持静态居中页脚文本和模板已有页脚保留。"""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    show_page_number: bool = False
    alignment: Literal["left", "center", "right"] | None = "center"


class TemplateTableStyleConfig(BaseModel):
    """表格外观配置；P0 保持最小可编辑表格输出。"""

    model_config = ConfigDict(extra="ignore")

    style_name: str = "Table Grid"
    header_fill: str | None = "EEF3F8"
    border_color: str | None = "C7CDD4"


class TemplateConfigPackage(BaseModel):
    """模板配置包 v1；兼容既有 datasheet_template.yaml 的扁平样式键。"""

    model_config = ConfigDict(extra="ignore")

    schema_version: Literal["template-config/v1"] = "template-config/v1"
    template_name: str = ""
    output_filename: str | None = None
    page_setup: TemplatePageSetupConfig = Field(default_factory=TemplatePageSetupConfig)
    header: TemplateHeaderConfig = Field(default_factory=TemplateHeaderConfig)
    footer: TemplateFooterConfig = Field(default_factory=TemplateFooterConfig)
    table_style: TemplateTableStyleConfig = Field(default_factory=TemplateTableStyleConfig)
    part_number: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    category: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    heading1: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    heading2: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    heading3: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    normal: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    table_content: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    table_note: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)
    caption: TemplateParagraphStyleConfig = Field(default_factory=TemplateParagraphStyleConfig)

    @classmethod
    def load(cls, config_path: Path | None) -> "TemplateConfigPackage":
        """从 YAML 加载配置；缺失配置时返回 v1 默认值。"""

        if config_path is None or not config_path.exists():
            return cls()
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"模板配置必须是 YAML object: {config_path}")
        return cls.model_validate(raw)

    def heading_style_for_level(self, level: int | None) -> TemplateParagraphStyleConfig:
        normalized_level = max(1, min(int(level or 1), 3))
        if normalized_level == 1:
            return self.heading1
        if normalized_level == 2:
            return self.heading2
        return self.heading3

    def heading_word_style_name_for_level(self, level: int | None) -> str:
        normalized_level = max(1, min(int(level or 1), 3))
        configured = self.heading_style_for_level(normalized_level).word_style_name
        return configured or f"Heading {normalized_level}"
