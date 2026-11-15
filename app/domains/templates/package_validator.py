"""模板 DOCX、版式配置与实际 Word 样式的联合预检。"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from struct import error as StructError
from typing import Literal

from docx import Document
from docx.document import Document as WordDocument
from docx.enum.style import WD_STYLE_TYPE
from docx.image.exceptions import InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError
from docx.image.image import Image
from docx.opc.exceptions import OpcError
from docx.oxml.exceptions import InvalidXmlError
from docx.section import Section
from docx.shared import Cm
from lxml import etree

from app.domains.resources.integrity import content_sha256
from app.domains.templates.layout_config_schema import (
    TemplateConfigPackage,
    TemplateLayoutValidationError,
    TemplatePageSetupConfig,
    TemplateParagraphStyleConfig,
)
from app.services.ooxml_package import DocxPackageError, inspect_docx_package


class TemplatePackageValidationError(TemplateLayoutValidationError):
    """跨管理入口共用的预检失败，路径仅为逻辑字段。"""

    def __init__(self, message: str, *, path: str, code: str) -> None:
        super().__init__(f"{path}: {message}", path=path, code=code)


@dataclass(frozen=True, slots=True)
class TemplatePackageFingerprint:
    """预检实际读取的 DOCX 和 YAML 字节身份。"""

    docx_sha256: str
    layout_config_sha256: str | None


LogoPolicy = Literal["allow", "inactive_only", "forbid"]


def bundled_seed_logo_policy(template_id: str, version: int) -> LogoPolicy:
    """内置版本 1 和 2 的原始 YAML 保留关闭状态的 Logo 路径。"""

    return "inactive_only" if template_id == "default" and version in {1, 2} else "forbid"


def external_logo_field(package: TemplateConfigPackage, *, active_only: bool) -> str | None:
    """定位基础配置或任一种语言配置的外部页眉图像路径。"""

    if package.header.logo_path and (package.header.enabled or not active_only):
        return "header.logo_path"
    for override in package.language_overrides.values():
        try:
            variant = package.with_language_override(override)
        except TemplateLayoutValidationError as exc:
            raise TemplatePackageValidationError(
                "语言覆盖未通过校验。", path=f"language_overrides.{exc.path}", code=exc.code,
            ) from None
        if variant.header.logo_path and (variant.header.enabled or not active_only):
            return "language_overrides.header.logo_path"
    return None


def require_template_yaml_binding(payload: dict) -> None:
    """区分无版式的历史版本与不完整的登记绑定。"""

    path = payload.get("layout_config_path")
    digest = payload.get("layout_config_sha256")
    if path is None and digest is None:
        raise TemplatePackageValidationError(
            "此模板版本未绑定版式 YAML，仅供历史恢复和内部下载。",
            path="layout_config", code="legacy_internal_only",
        )
    if not isinstance(path, str) or not path.strip() or not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise TemplatePackageValidationError(
            "模板资源版本未完整登记版式 YAML。",
            path="layout_config", code="template_resource_payload_invalid",
        )


def validate_template_package(
    *, template_path: Path, layout_config_path: Path | None,
    require_layout: bool = False, logo_policy: LogoPolicy = "allow",
) -> TemplatePackageFingerprint:
    """从文件读取模板包并返回通过预检的字节指纹。"""

    return validate_template_package_content(
        template_content=read_template_resource(template_path, kind="docx"),
        layout_config_content=(
            read_template_resource(layout_config_path, kind="layout_config") if layout_config_path is not None else None
        ),
        layout_config_directory=layout_config_path.parent if layout_config_path is not None else None,
        require_layout=require_layout,
        logo_policy=logo_policy,
    )


def read_template_resource(path: Path, *, kind: str) -> bytes:
    """只向调用端返回固定资源错误，避免回显文件系统路径。"""

    try:
        return path.resolve().read_bytes()
    except (OSError, RuntimeError):
        raise TemplatePackageValidationError(
            "模板资源不存在或不可读取。", path=kind, code=f"template_{kind}_unavailable",
        ) from None


def validate_template_package_content(
    *, template_content: bytes, layout_config_content: bytes | None, layout_config_directory: Path | None = None,
    require_layout: bool = False, logo_policy: LogoPolicy = "allow",
) -> TemplatePackageFingerprint:
    """文件预检与写入前的候选字节共用相同检查。"""

    if require_layout and layout_config_content is None:
        raise TemplatePackageValidationError(
            "模板版本必须绑定版式 YAML。", path="layout_config", code="template_layout_config_required",
        )
    try:
        inspection = inspect_docx_package(template_content, verify_all_parts=True)
    except DocxPackageError as exc:
        raise TemplatePackageValidationError("模板 DOCX 结构无效。", path=exc.path, code=exc.code) from None
    if inspection.issues:
        issue = inspection.issues[0]
        raise TemplatePackageValidationError("模板 DOCX 部件或关系无效。", path=issue.path, code=issue.code)
    try:
        document = Document(io.BytesIO(template_content))
        _validate_configurations(document, layout_config_content, layout_config_directory, logo_policy=logo_policy)
    except TemplatePackageValidationError:
        raise
    except (OpcError, InvalidXmlError, etree.XMLSyntaxError, AttributeError, KeyError, ValueError, RecursionError):
        raise TemplatePackageValidationError(
            "无法读取模板 DOCX 的 Word 部件。", path="docx", code="docx_package_invalid",
        ) from None
    return TemplatePackageFingerprint(
        docx_sha256=content_sha256(template_content),
        layout_config_sha256=content_sha256(layout_config_content) if layout_config_content is not None else None,
    )


def _validate_configurations(
    document: WordDocument, content: bytes | None, directory: Path | None,
    *, logo_policy: LogoPolicy,
) -> None:
    try:
        package = TemplateConfigPackage.load_content(content) if content is not None else TemplateConfigPackage()
    except TemplateLayoutValidationError as exc:
        raise TemplatePackageValidationError("版式配置未通过校验。", path=exc.path, code=exc.code) from None

    validate_template_logo(package, logo_policy=logo_policy)
    table_styles = {style.name for style in document.styles if style.type == WD_STYLE_TYPE.TABLE}
    paragraph_styles = {style.name for style in document.styles if style.type == WD_STYLE_TYPE.PARAGRAPH}
    # Renderer 清理模板正文后，以最后一节为新正文的初始节。
    section = document.sections[-1]
    _validate_configuration(package, section, table_styles, paragraph_styles, directory)
    for override in package.language_overrides.values():
        try:
            variant = package.with_language_override(override)
            _validate_configuration(variant, section, table_styles, paragraph_styles, directory)
        except TemplateLayoutValidationError as exc:
            raise TemplatePackageValidationError(
                "语言覆盖未通过校验。", path=f"language_overrides.{exc.path}", code=exc.code,
            ) from None


def validate_template_logo(package: TemplateConfigPackage, *, logo_policy: LogoPolicy) -> None:
    """正式发布禁止声明路径，历史准入只拒绝会消费外部图像的配置。"""

    if logo_policy == "allow":
        return
    field = external_logo_field(package, active_only=logo_policy == "inactive_only")
    if field is not None:
        reason = "template_external_logo_forbidden" if logo_policy == "forbid" else "legacy_internal_only"
        raise TemplatePackageValidationError(
            "正式页眉的 Logo 须由 DOCX 模板提供。", path=field, code=reason,
        )


def _validate_configuration(
    package: TemplateConfigPackage,
    section: Section,
    table_styles: set[str],
    paragraph_styles: set[str],
    directory: Path | None,
) -> None:
    _validate_effective_page_body(package.page_setup, section)
    if package.table_style.style_name not in table_styles:
        raise TemplatePackageValidationError(
            "模板文档中不存在指定的 Word 表格样式。",
            path="table_style.style_name",
            code="unknown_word_style",
        )
    for group in TemplateConfigPackage.model_fields:
        style = getattr(package, group)
        if (
            isinstance(style, TemplateParagraphStyleConfig)
            and style.word_style_name
            and style.word_style_name not in paragraph_styles
        ):
            raise TemplatePackageValidationError(
                "模板文档中不存在指定的 Word 段落样式。",
                path=f"{group}.word_style_name",
                code="unknown_word_style",
            )
    if package.header.enabled and package.header.logo_path and directory is not None:
        _validate_override_logo(directory, package.header.logo_path)


def _validate_effective_page_body(setup: TemplatePageSetupConfig, section: Section) -> None:
    horizontal = sum(
        Cm(getattr(setup, name)) if getattr(setup, name) is not None else getattr(section, name) or 0
        for name in ("left_margin", "right_margin")
    ) + (section.gutter or 0)
    vertical = sum(
        Cm(getattr(setup, name)) if getattr(setup, name) is not None else getattr(section, name) or 0
        for name in ("top_margin", "bottom_margin")
    )
    # 旧 IR 可继承模板纸张，正式版式路径按 YAML 或 A4 排出纵向和横向。
    default_width, default_height = Cm(21), Cm(29.7)
    configured_width = Cm(setup.page_width_cm) if setup.page_width_cm is not None else None
    configured_height = Cm(setup.page_height_cm) if setup.page_height_cm is not None else None
    inherited_width = configured_width if configured_width is not None else section.page_width
    inherited_height = configured_height if configured_height is not None else section.page_height
    short_side = min(configured_width or default_width, configured_height or default_height)
    if (
        inherited_width is not None and inherited_width <= horizontal
        or inherited_height is not None and inherited_height <= vertical
        or short_side <= max(horizontal, vertical)
    ):
        raise TemplatePackageValidationError(
            "应用配置与模板边距后，正文区域宽度或高度不为正。",
            path="page_setup",
            code="invalid_page_body",
        )


def _validate_override_logo(directory: Path, name: str) -> None:
    try:
        root = directory.resolve()
        asset = (root / name).resolve()
        if not asset.is_relative_to(root):
            raise TemplatePackageValidationError(
                "页眉覆盖的图像路径超出配置目录。",
                path="header.logo_path",
                code="invalid_relative_path",
            )
        content = asset.read_bytes()
    except FileNotFoundError:
        # 历史模板允许配置中保留未分发的可选覆盖图像，仍可渲染标题。
        return
    except (OSError, RuntimeError):
        raise TemplatePackageValidationError(
            "页眉覆盖的图像不可读取。", path="header.logo_path", code="invalid_override_logo",
        ) from None
    try:
        image = Image.from_blob(content)
        if min(image.px_width, image.px_height, image.horz_dpi, image.vert_dpi) <= 0:
            raise InvalidImageStreamError
    except (InvalidImageStreamError, UnexpectedEndOfFileError, UnrecognizedImageError, StructError, ValueError):
        raise TemplatePackageValidationError(
            "页眉覆盖的图像无法用于 Word 渲染。", path="header.logo_path", code="invalid_override_logo",
        ) from None
