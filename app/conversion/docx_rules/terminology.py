"""DOCX 文本与表格 HTML 共用的格式替换规则。"""

from __future__ import annotations

import re
import hashlib
from html import escape
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

    def replace_text(self, text: str, *, _native_literal: bool = False) -> str:
        if not text or not self.rules:
            return escape(text, quote=False) if _native_literal else text
        return self._replace_text_for_output_mode(text, "markdown", _native_literal=_native_literal)

    def replace_html(self, html: str | None) -> str | None:
        if not html or not self.rules:
            return html

        soup = BeautifulSoup(html, "html.parser")
        changed = False
        for rule in self.rules:
            if not rule.enabled or not self._rule_applies_to_output_mode(rule, "table"):
                continue
            assert rule.regex is not None
            for text_node in list(soup.find_all(string=True)):
                if self._is_replaceable_html_text_node(text_node):
                    changed = self._replace_html_matches(text_node, rule) or changed
            # 合并替换片段与原尾部的相邻纯文字，让下一优先级规则保持连续匹配；真实标签边界仍保留。
            soup.smooth()

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
    def _replace_html_matches(text_node: NavigableString, rule: ReplacementRule) -> bool:
        """只解析配置的替换片段，未匹配文字以原始文本节点插回。"""
        assert rule.regex is not None
        text = str(text_node)
        matches = list(rule.regex.finditer(text))
        if not matches:
            return False
        contents: list[Tag | NavigableString] = []
        cursor = 0
        changed = False
        for match in matches:
            if match.start() > cursor:
                contents.append(NavigableString(text[cursor:match.start()]))
            replacement = match.expand(rule.replacement)
            if replacement == match.group():
                contents.append(NavigableString(match.group()))
            else:
                fragment = BeautifulSoup(replacement, "html.parser")
                contents.extend(fragment.contents)
                changed = True
            cursor = match.end()
        if not changed:
            return False
        if cursor < len(text):
            contents.append(NavigableString(text[cursor:]))
        text_node.replace_with(*contents)
        return True

    def _replace_text_for_output_mode(self, text: str, output_mode: str, *, _native_literal: bool = False) -> str:
        replaced = text
        # native 叶已完成 HTML 解码；仅规则真正新增的片段可再次解释成标签。
        literal = bytearray(b"\1") * len(text) if _native_literal else None
        for rule in self.rules:
            assert rule.regex is not None
            if not rule.enabled or not self._rule_applies_to_output_mode(rule, output_mode):
                continue
            if literal is None:
                replaced = rule.regex.sub(rule.replacement, replaced)
                continue
            chunks, origins = [], bytearray()
            cursor = 0
            # 对完整当前文字匹配，保留 replace_text 原有作用域、顺序与跨替换尾部级联。
            for match in rule.regex.finditer(replaced):
                chunks.append(replaced[cursor:match.start()])
                origins.extend(literal[cursor:match.start()])
                replacement = match.expand(rule.replacement)
                chunks.append(replacement)
                origins.extend(literal[match.start():match.end()] if replacement == match.group()
                               else bytearray(len(replacement)))
                cursor = match.end()
            chunks.append(replaced[cursor:])
            origins.extend(literal[cursor:])
            replaced, literal = "".join(chunks), origins
        if literal is None:
            return replaced
        chunks = []
        start = 0
        for end in range(1, len(replaced) + 1):
            if end == len(replaced) or literal[end] != literal[start]:
                value = replaced[start:end]
                chunks.append(escape(value, quote=False) if literal[start] else value)
                start = end
        return "".join(chunks)

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
