"""DOCX 文本与表格 HTML 共用的格式替换规则。"""

from __future__ import annotations

import re
import hashlib
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
    """按既有顺序和作用域执行 YAML 格式替换，支持不可变输入重放。"""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path
        self.rules: list[ReplacementRule] = []
        self.content_sha256: str | None = None
        self._load_rules()

    def freeze_rules(self) -> list[dict]:
        """仅保存执行所需白名单值；数组顺序就是已经生效的规则顺序。"""
        return [{"pattern": rule.pattern, "replacement": rule.replacement,
                 "flags": rule.regex.flags, "apply_scope": rule.apply_scope}
                for rule in self.rules if rule.enabled and rule.regex is not None]

    @classmethod
    def from_frozen_rules(cls, rules: list[dict]) -> "TerminologyReplacer":
        """历史证据只重放冻结规则，不读取当前文件或重新排序。"""
        replacer = cls()
        if not isinstance(rules, list):
            raise ValueError("图片格式规则快照无效")
        for data in rules:
            if (not isinstance(data, dict) or set(data) != {"pattern", "replacement", "flags", "apply_scope"}
                    or not isinstance(data["pattern"], str) or not isinstance(data["replacement"], str)
                    or type(data["flags"]) is not int or not isinstance(data["apply_scope"], str)):
                raise ValueError("图片格式规则快照无效")
            try:
                regex = re.compile(data["pattern"], data["flags"])
            except (re.error, ValueError) as exc:
                raise ValueError("图片格式规则无法重放") from exc
            replacer.rules.append(ReplacementRule(source="", pattern=data["pattern"],
                replacement=data["replacement"], apply_scope=data["apply_scope"], regex=regex))
        return replacer

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

        content = self.config_path.read_bytes()
        self.content_sha256 = hashlib.sha256(content).hexdigest()
        config = yaml.safe_load(content.decode("utf-8")) or {}
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
