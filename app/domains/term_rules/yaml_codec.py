from __future__ import annotations

# app/domains/term_rules/yaml_codec.py: 解析、校验并导出 term_rules YAML 格式。

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.domains.term_rules.models import (
    RuleApplyScope,
    RuleMode,
    RuleRenderType,
    TermRuleCategoryRecord,
    TermRuleRecord,
    TermRuleSegmentRecord,
    TermRuleScopeType,
    TermRulesStore,
    normalize_term_key,
)


CURRENT_SCHEMA_VERSION = 2
CATEGORY_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class CodecIssue:
    code: str
    message: str
    path: str | None = None


@dataclass
class CodecValidationResult:
    errors: list[CodecIssue] = field(default_factory=list)
    warnings: list[CodecIssue] = field(default_factory=list)
    store: TermRulesStore | None = None


def render_segments_html(segments: list[TermRuleSegmentRecord]) -> str:
    output: list[str] = []
    for segment in sorted(segments, key=lambda item: item.seq):
        if segment.render_type == RuleRenderType.SUBSCRIPT:
            output.append(f"<sub>{segment.segment_text}</sub>")
        elif segment.render_type == RuleRenderType.SUPERSCRIPT:
            output.append(f"<sup>{segment.segment_text}</sup>")
        else:
            output.append(segment.segment_text)
    return "".join(output)


def html_subsup_to_pandoc(text: str) -> str:
    converted = re.sub(
        r"<sub>(.*?)</sub>",
        lambda match: f"~{match.group(1)}~",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    converted = re.sub(
        r"<sup>(.*?)</sup>",
        lambda match: f"^{match.group(1)}^",
        converted,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return converted


def render_segments_markdown(segments: list[TermRuleSegmentRecord]) -> str:
    return html_subsup_to_pandoc(render_segments_html(segments))


def build_rule_pattern(source: str) -> str:
    if re.match(r"^[A-Za-z0-9_]+$", source):
        return rf"\b{re.escape(source)}\b"

    if re.search(r"[α-ωΑ-ΩθρμπσλδγβτφψχξζηεικνοωυΔΨ]", source):
        escaped = re.escape(source)
        return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"

    return re.escape(source)


class TermRuleYamlCodec:
    def validate_yaml_text(self, yaml_text: str) -> CodecValidationResult:
        try:
            raw = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError:
            return CodecValidationResult(
                errors=[CodecIssue(code="invalid_yaml", message="YAML 语法无效", path=None)]
            )

        if not isinstance(raw, dict):
            return CodecValidationResult(
                errors=[CodecIssue(code="invalid_top_level", message="YAML 顶层必须是对象", path=None)]
            )

        return self._validate_v2(raw)

    def parse_yaml_text(self, yaml_text: str) -> TermRulesStore:
        result = self.validate_yaml_text(yaml_text)
        if result.errors or result.store is None:
            message = result.errors[0].message if result.errors else "导入结果为空"
            raise ValueError(message)
        return result.store

    def parse_yaml_file(self, yaml_path: Path) -> TermRulesStore:
        if not yaml_path.exists():
            return TermRulesStore()
        return self.parse_yaml_text(yaml_path.read_text(encoding="utf-8"))

    def dump_store(self, store: TermRulesStore) -> str:
        categories_by_id = {item.id: item for item in store.categories}
        categories_section: dict[str, dict[str, Any]] = {}
        rules_section: list[dict[str, Any]] = []

        for category in sorted(store.categories, key=lambda item: (item.priority, item.code)):
            categories_section[category.code] = {
                "name": category.name,
                "priority": category.priority,
                "enabled": category.enabled,
                "description": category.description,
            }

        for rule in sorted(store.rules, key=lambda item: (item.priority, item.scope_type.value, item.scope_id or "", -len(item.source_term), item.source_term)):
            category = categories_by_id.get(rule.category_id)
            if category is None:
                continue
            rules_section.append(
                {
                    "source_term": rule.source_term,
                    "normalized_term": rule.normalized_term,
                    "scope_type": rule.scope_type.value,
                    "scope_id": rule.scope_id,
                    "current_version": rule.current_version,
                    "active": rule.active,
                    "category": category.code,
                    "segments": [
                        {
                            "segment_text": segment.segment_text,
                            "render_type": segment.render_type.value,
                        }
                        for segment in sorted(rule.segments, key=lambda item: item.seq)
                    ],
                    "apply_scope": rule.apply_scope.value,
                    "case_sensitive": rule.case_sensitive,
                    "enabled": rule.enabled,
                    "priority": rule.priority,
                    "notes": rule.notes,
                }
            )

        yaml_data = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "categories": categories_section,
            "rules": rules_section,
        }
        return yaml.safe_dump(yaml_data, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def dump_legacy_runtime_yaml(self, store: TermRulesStore, *, department_id: str | None = None) -> str:
        categories_by_id = {item.id: item for item in store.categories}
        categories_section: dict[str, dict[str, Any]] = {}
        subscript_rules: dict[str, dict[str, str]] = {}
        rules_meta: dict[str, dict[str, Any]] = {}

        for category in sorted(store.categories, key=lambda item: (item.priority, item.code)):
            categories_section[category.code] = {
                "name": category.name,
                "priority": category.priority,
                "enabled": category.enabled,
                "description": category.description,
            }
            subscript_rules[category.code] = {}

        for rule in self._effective_runtime_rules(store, department_id=department_id):
            category = categories_by_id.get(rule.category_id)
            if category is None:
                continue
            subscript_rules.setdefault(category.code, {})[rule.source_term] = rule.custom_html or render_segments_html(rule.segments)
            rules_meta[rule.source_term] = {
                "apply_scope": rule.apply_scope.value,
                "case_sensitive": rule.case_sensitive,
                "enabled": rule.enabled,
                "priority": rule.priority,
            }

        payload = {
            "case_sensitive": True,
            "categories": categories_section,
            "subscript_rules": subscript_rules,
            "rules_meta": rules_meta,
        }
        return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def _validate_v2(self, raw: dict[str, Any]) -> CodecValidationResult:
        errors: list[CodecIssue] = []
        warnings: list[CodecIssue] = []
        categories_raw = raw.get("categories", {}) or {}
        rules_raw = raw.get("rules", []) or []
        schema_version = raw.get("schema_version")

        if schema_version is not None and schema_version != CURRENT_SCHEMA_VERSION:
            errors.append(
                CodecIssue(
                    code="unknown_schema_version",
                    message=f"不支持的 schema_version: {schema_version}",
                    path="schema_version",
                )
            )

        if not isinstance(categories_raw, dict):
            errors.append(CodecIssue(code="invalid_categories", message="categories 必须是对象", path="categories"))
            categories_raw = {}

        if not isinstance(rules_raw, list):
            errors.append(CodecIssue(code="invalid_rules", message="rules 必须是数组", path="rules"))
            rules_raw = []

        categories: list[TermRuleCategoryRecord] = []
        category_ids: dict[str, str] = {}
        for code, meta in categories_raw.items():
            code_text = str(code).strip()
            if not code_text:
                errors.append(CodecIssue(code="invalid_category_code", message="分类 code 不能为空", path="categories"))
                continue
            if not CATEGORY_CODE_RE.match(code_text):
                errors.append(
                    CodecIssue(
                        code="invalid_category_code_format",
                        message=f"分类 code 必须是英文稳定标识: {code_text}",
                        path=f"categories.{code_text}",
                    )
                )
                continue
            meta_dict = meta if isinstance(meta, dict) else {}
            category_id = uuid.uuid4().hex
            category_ids[code_text] = category_id
            categories.append(
                TermRuleCategoryRecord(
                    id=category_id,
                    code=code_text,
                    name=str(meta_dict.get("name", "") or code_text),
                    priority=self._to_int(meta_dict.get("priority"), 100),
                    enabled=self._to_bool(meta_dict.get("enabled"), True),
                    description=str(meta_dict.get("description", "") or ""),
                )
            )

        rules: list[TermRuleRecord] = []
        seen_terms: set[tuple[str, str, str]] = set()
        for index, item in enumerate(rules_raw):
            path_prefix = f"rules.{index}"
            if not isinstance(item, dict):
                errors.append(CodecIssue(code="invalid_rule", message="rules 项必须是对象", path=path_prefix))
                continue

            source_term = str(item.get("source_term", "") or "").strip()
            if not source_term:
                errors.append(CodecIssue(code="missing_source_term", message="source_term 不能为空", path=f"{path_prefix}.source_term"))
                continue
            scope_type_value = str(item.get("scope_type", TermRuleScopeType.GLOBAL.value) or TermRuleScopeType.GLOBAL.value).strip()
            try:
                scope_type = TermRuleScopeType(scope_type_value)
            except ValueError:
                errors.append(
                    CodecIssue(
                        code="invalid_scope_type",
                        message=f"不支持的 scope_type: {scope_type_value}",
                        path=f"{path_prefix}.scope_type",
                    )
                )
                continue
            scope_id = None if scope_type == TermRuleScopeType.GLOBAL else str(item.get("scope_id", "") or "").strip()
            if scope_type == TermRuleScopeType.DEPARTMENT and not scope_id:
                errors.append(
                    CodecIssue(
                        code="missing_scope_id",
                        message="department scope 规则必须提供 scope_id",
                        path=f"{path_prefix}.scope_id",
                    )
                )
                continue
            normalized_term = normalize_term_key(str(item.get("normalized_term") or source_term))
            active = self._to_bool(item.get("active"), True)
            identity_key = (scope_type.value, scope_id or "", normalized_term)
            if active and identity_key in seen_terms:
                warnings.append(
                    CodecIssue(
                        code="duplicate_source_term",
                        message=f"发现同 scope 重复 source_term，后续项将被跳过: {source_term}",
                        path=f"{path_prefix}.source_term",
                    )
                )
                continue
            if active:
                seen_terms.add(identity_key)

            category_code = str(item.get("category", "") or "").strip()
            category_id = category_ids.get(category_code)
            if category_id is None:
                errors.append(
                    CodecIssue(
                        code="unknown_category",
                        message=f"规则引用了不存在的分类: {category_code or '<empty>'}",
                        path=f"{path_prefix}.category",
                    )
                )
                continue

            segments_raw = item.get("segments")
            if not isinstance(segments_raw, list) or not segments_raw:
                errors.append(
                    CodecIssue(code="invalid_segments", message="segments 必须是非空数组", path=f"{path_prefix}.segments")
                )
                continue

            segments: list[TermRuleSegmentRecord] = []
            for segment_index, segment_raw in enumerate(segments_raw):
                segment_path = f"{path_prefix}.segments.{segment_index}"
                if not isinstance(segment_raw, dict):
                    errors.append(
                        CodecIssue(code="invalid_segment", message="segment 必须是对象", path=segment_path)
                    )
                    continue
                segment_text = str(segment_raw.get("segment_text", "") or "")
                if not segment_text:
                    errors.append(
                        CodecIssue(code="missing_segment_text", message="segment_text 不能为空", path=f"{segment_path}.segment_text")
                    )
                    continue
                render_type_value = str(segment_raw.get("render_type", "") or "").strip().lower()
                try:
                    render_type = RuleRenderType(render_type_value)
                except ValueError:
                    errors.append(
                        CodecIssue(
                            code="invalid_render_type",
                            message=f"不支持的 render_type: {render_type_value}",
                            path=f"{segment_path}.render_type",
                        )
                    )
                    continue
                segments.append(
                    TermRuleSegmentRecord(
                        seq=segment_index + 1,
                        segment_text=segment_text,
                        render_type=render_type,
                    )
                )

            if not segments:
                continue

            apply_scope_value = str(item.get("apply_scope", RuleApplyScope.BOTH.value) or RuleApplyScope.BOTH.value).strip().lower()
            try:
                apply_scope = RuleApplyScope(apply_scope_value)
            except ValueError:
                errors.append(
                    CodecIssue(
                        code="invalid_apply_scope",
                        message=f"不支持的 apply_scope: {apply_scope_value}",
                        path=f"{path_prefix}.apply_scope",
                    )
                )
                continue

            case_sensitive = self._to_bool(item.get("case_sensitive"), True)
            enabled = self._to_bool(item.get("enabled"), True)
            current_version = self._to_int(item.get("current_version"), 1)
            category_priority = next((category.priority for category in categories if category.id == category_id), 100)
            priority = self._to_int(item.get("priority"), category_priority)
            notes = str(item.get("notes", "") or "")
            rule_mode = RuleMode.SIMPLE if len(segments) <= 2 else RuleMode.ADVANCED

            rules.append(
                TermRuleRecord(
                    id=uuid.uuid4().hex,
                    category_id=category_id,
                    source_term=source_term,
                    normalized_term=normalized_term,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    current_version=current_version,
                    active=active,
                    rule_mode=rule_mode,
                    apply_scope=apply_scope,
                    case_sensitive=case_sensitive,
                    enabled=enabled,
                    priority=priority,
                    segments=segments,
                    custom_html=render_segments_html(segments),
                    custom_markdown=render_segments_markdown(segments),
                    notes=notes,
                )
            )

        store = TermRulesStore(categories=categories, rules=rules)
        return CodecValidationResult(errors=errors, warnings=warnings, store=store if not errors else None)

    @staticmethod
    def _effective_runtime_rules(store: TermRulesStore, *, department_id: str | None) -> list[TermRuleRecord]:
        effective: dict[str, TermRuleRecord] = {}
        for rule in store.rules:
            if not rule.active:
                continue
            if rule.scope_type == TermRuleScopeType.GLOBAL:
                effective[rule.normalized_term or normalize_term_key(rule.source_term)] = rule
        normalized_department = str(department_id or "").strip()
        if normalized_department:
            for rule in store.rules:
                if not rule.active:
                    continue
                if rule.scope_type == TermRuleScopeType.DEPARTMENT and rule.scope_id == normalized_department:
                    effective[rule.normalized_term or normalize_term_key(rule.source_term)] = rule
        return sorted(effective.values(), key=lambda item: (item.priority, -len(item.source_term), item.source_term))

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)
