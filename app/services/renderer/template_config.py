"""向现有 renderer 导出模板配置领域合同。"""

from app.domains.templates.layout_config_schema import (
    TemplateConfigPackage,
    TemplateFooterConfig,
    TemplateHeaderConfig,
    TemplatePageSetupConfig,
    TemplateParagraphStyleConfig,
    TemplateTableContentStyleConfig,
    TemplateTableStyleConfig,
)

__all__ = [
    "TemplateConfigPackage",
    "TemplateFooterConfig",
    "TemplateHeaderConfig",
    "TemplatePageSetupConfig",
    "TemplateParagraphStyleConfig",
    "TemplateTableContentStyleConfig",
    "TemplateTableStyleConfig",
]
