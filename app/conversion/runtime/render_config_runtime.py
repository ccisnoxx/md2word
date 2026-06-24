from __future__ import annotations

# app/conversion/runtime/render_config_runtime.py: 加载 DOCX 渲染版式、段落样式、表格样式和术语配置。

from pathlib import Path
from typing import Any

import yaml

from app.conversion.docx_rules.terminology import (
    ReplacementRule,
    TerminologyReplacer as _SharedTerminologyReplacer,
    build_replacement_pattern,
)


_RUNTIME_MODULE: Any | None = None


def bind_runtime(module: Any) -> None:
    global _RUNTIME_MODULE
    _RUNTIME_MODULE = module


def _runtime_value(name: str, default: Any) -> Any:
    if _RUNTIME_MODULE is None:
        return default
    return getattr(_RUNTIME_MODULE, name, default)


def find_subscript_config_path(default_candidates: tuple[Path, ...]) -> Path | None:
    return _find_existing_path(default_candidates)


def find_layout_config_path(default_candidates: tuple[Path, ...]) -> Path | None:
    return _find_existing_path(default_candidates)


def _find_existing_path(candidates: tuple[Path, ...]) -> Path | None:
    for candidate in candidates:
        resolved = candidate if candidate.is_absolute() else candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def load_render_config(
    template_document: Any | None,
    subscript_config: Path | None,
    use_mineru_header_footer: bool,
    *,
    find_layout_config_path_fn: Any,
    load_section_layout_fn: Any,
    terminology_factory: Any,
    load_paragraph_styles_fn: Any,
    load_table_style_fn: Any,
    render_config_cls: Any,
) -> Any:
    layout_config_path = find_layout_config_path_fn()
    layout = load_section_layout_fn(template_document, layout_config_path)
    terminology = terminology_factory(subscript_config)
    paragraph_styles = load_paragraph_styles_fn(layout_config_path)
    table_style = load_table_style_fn(layout_config_path)
    return render_config_cls(
        section_layout=layout,
        use_mineru_header_footer=use_mineru_header_footer,
        terminology=terminology if terminology.rules else None,
        paragraph_styles=paragraph_styles,
        table_style=table_style,
    )


def load_section_layout(
    template_document: Any | None,
    config_path: Path | None,
    *,
    page_margin: Any,
    mm_fn: Any,
    section_layout_cls: Any,
) -> Any:
    base_layout = section_layout_cls(
        top_margin=page_margin,
        bottom_margin=page_margin,
        left_margin=page_margin,
        right_margin=page_margin,
        header_distance=mm_fn(8),
        footer_distance=mm_fn(8),
        page_width=mm_fn(210),
        page_height=mm_fn(297),
    )

    if template_document and template_document.sections:
        section = template_document.sections[0]
        base_layout = section_layout_cls(
            top_margin=section.top_margin,
            bottom_margin=section.bottom_margin,
            left_margin=section.left_margin,
            right_margin=section.right_margin,
            header_distance=section.header_distance,
            footer_distance=section.footer_distance,
            page_width=getattr(section, "page_width", None),
            page_height=getattr(section, "page_height", None),
        )

    if not config_path or not config_path.exists():
        return base_layout

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    page_setup = raw.get("page_setup")
    if not isinstance(page_setup, dict):
        return base_layout

    def resolve_margin(name: str, fallback: Any) -> Any:
        value = page_setup.get(name)
        if value is None:
            return fallback
        return mm_fn(float(value) * 10.0)

    def resolve_page_dimension(*names: str, fallback: Any) -> Any:
        for name in names:
            value = page_setup.get(name)
            if value is not None:
                return mm_fn(float(value) * 10.0)
        return fallback

    return section_layout_cls(
        top_margin=resolve_margin("top_margin", base_layout.top_margin),
        bottom_margin=resolve_margin("bottom_margin", base_layout.bottom_margin),
        left_margin=resolve_margin("left_margin", base_layout.left_margin),
        right_margin=resolve_margin("right_margin", base_layout.right_margin),
        header_distance=resolve_margin("header_distance", base_layout.header_distance),
        footer_distance=resolve_margin("footer_distance", base_layout.footer_distance),
        page_width=resolve_page_dimension("page_width_cm", "page_width", fallback=getattr(base_layout, "page_width", None)),
        page_height=resolve_page_dimension("page_height_cm", "page_height", fallback=getattr(base_layout, "page_height", None)),
    )


def load_paragraph_styles(
    config_path: Path | None,
    *,
    paragraph_style_config_cls: Any,
) -> dict[str, Any]:
    if not config_path or not config_path.exists():
        return {}

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    mapping = {
        "PartNumber": "part_number",
        "Category": "category",
        "Heading 1": "heading1",
        "Heading 2": "heading2",
        "Heading 3": "heading3",
        "TocTitle": "toc_title",
        "TocLevel1": "toc_level1",
        "TocLevel2": "toc_level2",
        "TocLevel3": "toc_level3",
        "Normal": "normal",
        "Caption": "caption",
        "LongTableCaption": "long_table_caption",
        "TableNote": "table_note",
        "TableContent": "table_content",
    }

    styles: dict[str, Any] = {}
    for style_name, yaml_key in mapping.items():
        value = raw.get(yaml_key)
        if not isinstance(value, dict):
            continue
        styles[style_name] = paragraph_style_config_cls(
            font_name=value.get("font_name"),
            font_size=float(value["font_size"]) if value.get("font_size") is not None else None,
            bold=value.get("bold"),
            italic=value.get("italic"),
            color=value.get("color"),
            alignment=value.get("alignment"),
            line_spacing=float(value["line_spacing"]) if value.get("line_spacing") is not None else None,
            space_before=float(value["space_before"]) if value.get("space_before") is not None else None,
            space_after=float(value["space_after"]) if value.get("space_after") is not None else None,
            first_line_indent_pt=float(value["first_line_indent_pt"]) if value.get("first_line_indent_pt") is not None else None,
            left_indent_pt=float(value["left_indent_pt"]) if value.get("left_indent_pt") is not None else None,
            right_indent_pt=float(value["right_indent_pt"]) if value.get("right_indent_pt") is not None else None,
        )

    return styles


def load_table_style(
    config_path: Path | None,
    *,
    table_style_config_cls: Any,
) -> Any:
    if not config_path or not config_path.exists():
        return table_style_config_cls()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    value = raw.get("table_style")
    if not isinstance(value, dict):
        return table_style_config_cls()

    return table_style_config_cls(
        header_bold=bool(value.get("header_bold", True)),
        header_fill=str(value.get("header_fill", "") or "").strip().lstrip("#").upper(),
        border_color=str(value.get("border_color", "C7CDD4") or "C7CDD4").strip().lstrip("#").upper(),
    )


class TerminologyReplacer(_SharedTerminologyReplacer):
    """Runtime-compatible wrapper around the shared terminology replacer."""

    def __init__(self, config_path: Path | None = None) -> None:
        finder = _runtime_value("find_subscript_config_path", lambda: None)
        super().__init__(config_path or finder())
