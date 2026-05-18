from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag


_RUNTIME_MODULE: Any | None = None


def bind_runtime(module: Any) -> None:
    global _RUNTIME_MODULE
    _RUNTIME_MODULE = module


def _runtime_value(name: str, default: Any) -> Any:
    if _RUNTIME_MODULE is None:
        return default
    return getattr(_RUNTIME_MODULE, name, default)


@dataclass(slots=True)
class ReplacementRule:
    source: str
    pattern: str
    replacement: str
    priority: int = 100
    apply_scope: str = "both"
    enabled: bool = True
    regex: re.Pattern[str] | None = field(default=None, repr=False, compare=False)


class TerminologyReplacer:
    def __init__(self, config_path: Path | None = None) -> None:
        finder = _runtime_value("find_subscript_config_path", lambda: None)
        self.config_path = config_path or finder()
        self.rules: list[ReplacementRule] = []
        self._load_rules()

    def replace_text(self, text: str) -> str:
        if not text or not self.rules:
            return text

        return self._replace_text_for_output_mode(text, "markdown")

    def replace_html(self, html: str | None) -> str | None:
        if not html or not self.rules:
            return html

        soup = BeautifulSoup(html, "html.parser")
        changed = False

        for text_node in list(soup.find_all(string=True)):
            if not self._is_replaceable_html_text_node(text_node):
                continue

            original_text = str(text_node)
            replaced_text = self._replace_text_for_output_mode(original_text, "table")
            if replaced_text == original_text:
                continue

            changed = True
            self._replace_text_node_with_fragment(text_node, replaced_text)

        return str(soup) if changed else html

    def _load_rules(self) -> None:
        if not self.config_path or not self.config_path.exists():
            return

        config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        rules_data = config.get("subscript_rules", {})
        if not isinstance(rules_data, dict):
            return

        case_sensitive = bool(config.get("case_sensitive", True))
        category_meta = config.get("categories", {})
        rules_meta = config.get("rules_meta", {})
        pattern_builder = _runtime_value("build_replacement_pattern", build_replacement_pattern)

        for category, items in rules_data.items():
            if not isinstance(items, dict):
                continue

            priority = 100
            if isinstance(category_meta, dict):
                priority = int(category_meta.get(category, {}).get("priority", 100))

            for source, replacement in items.items():
                source_text = str(source).strip()
                replacement_text = str(replacement).strip()
                if not source_text or not replacement_text:
                    continue

                meta = rules_meta.get(source_text, {}) if isinstance(rules_meta, dict) else {}
                enabled = bool(meta.get("enabled", True))
                if not enabled:
                    continue
                pattern = pattern_builder(source_text)
                regex_flags = 0 if bool(meta.get("case_sensitive", case_sensitive)) else re.IGNORECASE
                try:
                    compiled = re.compile(pattern, regex_flags)
                except re.error:
                    continue

                self.rules.append(
                    ReplacementRule(
                        source=source_text,
                        pattern=pattern,
                        replacement=replacement_text,
                        priority=int(meta.get("priority", priority)),
                        apply_scope=str(meta.get("apply_scope", "both") or "both").lower(),
                        enabled=enabled,
                        regex=compiled,
                    )
                )

        self.rules.sort(key=lambda rule: (rule.priority, -len(rule.source), rule.source))

    @staticmethod
    def _is_replaceable_html_text_node(text_node: NavigableString) -> bool:
        parent = text_node.parent
        if not isinstance(parent, Tag):
            return False
        if parent.name in {"script", "style", "sub", "sup"}:
            return False
        return bool(str(text_node).strip())

    @staticmethod
    def _replace_text_node_with_fragment(text_node: NavigableString, html_fragment: str) -> None:
        fragment = BeautifulSoup(html_fragment, "html.parser")
        contents = list(fragment.contents)
        if not contents:
            text_node.extract()
            return

        anchor = text_node
        for node in reversed(contents):
            anchor.insert_after(node)
        anchor.extract()

    def _replace_text_for_output_mode(self, text: str, output_mode: str) -> str:
        replaced = text
        for rule in self.rules:
            assert rule.regex is not None
            if not rule.enabled or not self._rule_applies_to_output_mode(rule, output_mode):
                continue
            replaced = rule.regex.sub(rule.replacement, replaced)
        return replaced

    @staticmethod
    def _rule_applies_to_output_mode(rule: ReplacementRule, output_mode: str) -> bool:
        if rule.apply_scope == "both":
            return True
        if output_mode == "markdown":
            return rule.apply_scope == "markdown"
        return rule.apply_scope == "table"


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
    render_config_cls: Any,
) -> Any:
    layout_config_path = find_layout_config_path_fn()
    layout = load_section_layout_fn(template_document, layout_config_path)
    terminology = terminology_factory(subscript_config)
    paragraph_styles = load_paragraph_styles_fn(layout_config_path)
    return render_config_cls(
        section_layout=layout,
        use_mineru_header_footer=use_mineru_header_footer,
        terminology=terminology if terminology.rules else None,
        paragraph_styles=paragraph_styles,
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

    return section_layout_cls(
        top_margin=resolve_margin("top_margin", base_layout.top_margin),
        bottom_margin=resolve_margin("bottom_margin", base_layout.bottom_margin),
        left_margin=resolve_margin("left_margin", base_layout.left_margin),
        right_margin=resolve_margin("right_margin", base_layout.right_margin),
        header_distance=resolve_margin("header_distance", base_layout.header_distance),
        footer_distance=resolve_margin("footer_distance", base_layout.footer_distance),
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


def build_replacement_pattern(source: str) -> str:
    if re.match(r"^[A-Za-z0-9_]+$", source):
        return rf"\b{re.escape(source)}\b"

    if re.search(r"[α-ωΑ-ΩθρμπσλδγβτφψχξζηεικνοωυΔΨ]", source):
        escaped = re.escape(source)
        return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"

    return re.escape(source)
