"""Shared terminology replacement rules for DOCX text and table HTML."""

from __future__ import annotations

# File: app/conversion/docx_rules/terminology.py
# Purpose: Apply runtime subscript/terminology YAML consistently across renderers.

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag


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
    """Apply legacy runtime YAML terminology rules to plain text and HTML."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path
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
                pattern = build_replacement_pattern(source_text)
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


def build_replacement_pattern(source: str) -> str:
    if re.match(r"^[A-Za-z0-9_]+$", source):
        return rf"\b{re.escape(source)}\b"

    if re.search(r"[α-ωΑ-ΩθρμπσλδγβτφψχξζηεικνοωυΔΨ]", source):
        escaped = re.escape(source)
        return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"

    return re.escape(source)
