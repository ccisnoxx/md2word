from __future__ import annotations

# app/domains/term_rules/service.py: 维护术语规则 live store、增量写接口和 conversion runtime YAML 导出。

import re
import uuid
from pathlib import Path
from typing import Any

from app.domains.term_rules.models import (
    RuleApplyScope,
    RuleMode,
    RuleRenderType,
    TermRuleCategoryRecord,
    TermRuleRecord,
    TermRuleSegmentRecord,
    TermRulesStore,
    utc_now,
)
from app.domains.term_rules.repository import TermRuleRepositoryProtocol
from app.domains.term_rules.yaml_codec import (
    CATEGORY_CODE_RE,
    TermRuleYamlCodec,
    build_rule_pattern,
    render_segments_html,
    render_segments_markdown,
)


class TermRuleService:
    def __init__(self, repository: TermRuleRepositoryProtocol, runtime_yaml_path: Path, bootstrap_yaml_path: Path):
        self.repository = repository
        self.runtime_yaml_path = runtime_yaml_path
        self.bootstrap_yaml_path = bootstrap_yaml_path
        self.yaml_codec = TermRuleYamlCodec()

    def list_categories_with_counts(self) -> list[tuple[TermRuleCategoryRecord, int, int]]:
        return self.repository.list_categories_with_counts()

    def query_rules_page(
        self,
        *,
        category_id: str | None,
        enabled: bool | None,
        q: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TermRuleRecord], int]:
        return self.repository.query_rules_page(
            category_id=category_id,
            enabled=enabled,
            q=q,
            page=page,
            page_size=page_size,
        )

    def get_rule(self, rule_id: str) -> TermRuleRecord:
        for rule in self.repository.load().rules:
            if rule.id == rule_id:
                return rule
        raise FileNotFoundError(f"规则不存在: {rule_id}")

    def create_category(
        self,
        *,
        category_id: str | None,
        code: str,
        name: str,
        priority: int,
        enabled: bool,
        description: str,
    ) -> TermRuleCategoryRecord:
        store = self.repository.load()
        normalized_id = self._normalize_optional_id(category_id) or uuid.uuid4().hex
        normalized_code = self._normalize_category_code(code)
        if any(item.id == normalized_id for item in store.categories):
            raise ValueError(f"分类 ID 已存在: {normalized_id}")
        if any(item.code == normalized_code for item in store.categories):
            raise ValueError(f"分类 code 已存在: {normalized_code}")
        category = TermRuleCategoryRecord(
            id=normalized_id,
            code=normalized_code,
            name=self._normalize_required_text(name, "name"),
            priority=priority,
            enabled=enabled,
            description=description.strip(),
        )
        self.repository.add_category(category)
        self.export_runtime_yaml()
        return category

    def update_category(self, category_id: str, fields: dict[str, Any]) -> TermRuleCategoryRecord:
        store = self.repository.load()
        category = self._find_category(store, category_id)
        updates: dict[str, Any] = {}
        if "code" in fields:
            next_code = self._normalize_category_code(fields["code"])
            if any(item.id != category.id and item.code == next_code for item in store.categories):
                raise ValueError(f"分类 code 已存在: {next_code}")
            updates["code"] = next_code
        if "name" in fields:
            updates["name"] = self._normalize_required_text(fields["name"], "name")
        if "priority" in fields:
            updates["priority"] = int(fields["priority"])
        if "enabled" in fields:
            updates["enabled"] = bool(fields["enabled"])
        if "description" in fields:
            updates["description"] = str(fields["description"] or "").strip()
        if updates:
            updates["updated_at"] = utc_now()
            category = category.model_copy(update=updates)
            self.repository.update_category(category)
            self.export_runtime_yaml()
        return category

    def delete_category(self, category_id: str) -> None:
        store = self.repository.load()
        category = self._find_category(store, category_id)
        if any(rule.category_id == category.id for rule in store.rules):
            raise ValueError(f"分类仍包含规则，不能删除: {category.id}")
        self.repository.delete_category(category.id)
        self.export_runtime_yaml()

    def create_rule(
        self,
        *,
        rule_id: str | None,
        category_id: str,
        source_term: str,
        apply_scope: str,
        case_sensitive: bool,
        enabled: bool,
        priority: int,
        segments: list[dict[str, Any]],
        custom_html: str | None,
        custom_markdown: str | None,
        notes: str,
    ) -> TermRuleRecord:
        store = self.repository.load()
        normalized_id = self._normalize_optional_id(rule_id) or uuid.uuid4().hex
        if any(item.id == normalized_id for item in store.rules):
            raise ValueError(f"规则 ID 已存在: {normalized_id}")
        category = self._find_category(store, category_id)
        normalized_source = self._normalize_source_term(source_term)
        self._ensure_unique_source_term(store, normalized_source, exclude_rule_id=None)
        rule = self._build_rule_record(
            rule_id=normalized_id,
            category_id=category.id,
            source_term=normalized_source,
            apply_scope=apply_scope,
            case_sensitive=case_sensitive,
            enabled=enabled,
            priority=priority,
            segments=segments,
            custom_html=custom_html,
            custom_markdown=custom_markdown,
            notes=notes,
        )
        self.repository.add_rule(rule)
        self.export_runtime_yaml()
        return rule

    def update_rule(self, rule_id: str, fields: dict[str, Any]) -> TermRuleRecord:
        store = self.repository.load()
        rule = self._find_rule(store, rule_id)
        category_id = rule.category_id
        if "category_id" in fields:
            category_id = self._find_category(store, str(fields["category_id"])).id
        source_term = rule.source_term
        if "source_term" in fields:
            source_term = self._normalize_source_term(str(fields["source_term"]))
            self._ensure_unique_source_term(store, source_term, exclude_rule_id=rule.id)
        segments = [
            {"segment_text": segment.segment_text, "render_type": segment.render_type.value}
            for segment in sorted(rule.segments, key=lambda item: item.seq)
        ]
        segments_changed = "segments" in fields
        if segments_changed:
            segments = fields["segments"]

        custom_html = rule.custom_html
        custom_markdown = rule.custom_markdown
        if "custom_html" in fields:
            custom_html = fields["custom_html"]
        elif segments_changed:
            custom_html = None
        if "custom_markdown" in fields:
            custom_markdown = fields["custom_markdown"]
        elif segments_changed:
            custom_markdown = None

        updated = self._build_rule_record(
            rule_id=rule.id,
            category_id=category_id,
            source_term=source_term,
            apply_scope=fields.get("apply_scope", rule.apply_scope.value),
            case_sensitive=fields.get("case_sensitive", rule.case_sensitive),
            enabled=fields.get("enabled", rule.enabled),
            priority=fields.get("priority", rule.priority),
            segments=segments,
            custom_html=custom_html,
            custom_markdown=custom_markdown,
            notes=fields.get("notes", rule.notes),
            created_at=rule.created_at,
        )
        updated = updated.model_copy(update={"updated_at": utc_now()})
        self.repository.update_rule(updated)
        self.export_runtime_yaml()
        return updated

    def delete_rule(self, rule_id: str) -> None:
        self.repository.delete_rule(rule_id)
        self.export_runtime_yaml()

    def export_runtime_yaml(self) -> Path:
        self.runtime_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_yaml_path.write_text(
            self.yaml_codec.dump_legacy_runtime_yaml(self.repository.load()),
            encoding="utf-8",
        )
        return self.runtime_yaml_path

    def export_store_yaml(self) -> str:
        return self.yaml_codec.dump_store(self.repository.load())

    def apply_import_store(self, store: TermRulesStore) -> TermRulesStore:
        self.repository.save(store)
        self.export_runtime_yaml()
        return store

    def bootstrap_from_seed_if_empty(self) -> tuple[TermRulesStore, bool, list[str]]:
        store = self.repository.load()
        imported = False
        warnings: list[str] = []
        if not store.categories and not store.rules:
            if not self.bootstrap_yaml_path.exists():
                raise FileNotFoundError(f"bootstrap 规则文件不存在: {self.bootstrap_yaml_path}")
            result = self.yaml_codec.validate_yaml_text(self.bootstrap_yaml_path.read_text(encoding="utf-8"))
            if result.errors or result.store is None:
                message = result.errors[0].message if result.errors else "bootstrap 规则导入失败"
                raise ValueError(message)
            store = self.repository.save(result.store)
            imported = True
            warnings = [item.message for item in result.warnings]
        self.export_runtime_yaml()
        return store, imported, warnings

    def simulate(self, text: str) -> dict[str, str]:
        categories = {item.id: item for item in self.repository.load().categories if item.enabled}
        rules = [
            rule
            for rule in self.repository.load().rules
            if rule.enabled and rule.category_id in categories
        ]
        markdown_result = text
        html_result = text
        for rule in sorted(rules, key=lambda item: (item.priority, -len(item.source_term), item.source_term)):
            pattern = build_rule_pattern(rule.source_term)
            flags = 0 if rule.case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
            if rule.apply_scope in {RuleApplyScope.MARKDOWN, RuleApplyScope.BOTH}:
                markdown_result = regex.sub(
                    rule.custom_markdown or render_segments_markdown(rule.segments),
                    markdown_result,
                )
            if rule.apply_scope in {RuleApplyScope.TABLE, RuleApplyScope.BOTH}:
                html_result = regex.sub(
                    rule.custom_html or render_segments_html(rule.segments),
                    html_result,
                )

        return {
            "original": text,
            "markdown_preview": markdown_result,
            "html_preview": html_result,
        }

    @staticmethod
    def _normalize_optional_id(raw_id: str | None) -> str | None:
        if raw_id is None:
            return None
        normalized = raw_id.strip()
        if not normalized:
            return None
        if not re.match(r"^[A-Za-z0-9_.-]{1,128}$", normalized):
            raise ValueError("id 只能包含大小写字母、数字、下划线、短横线和英文句点，长度不超过 128。")
        return normalized

    @staticmethod
    def _normalize_category_code(code: str) -> str:
        normalized = code.strip()
        if not CATEGORY_CODE_RE.match(normalized):
            raise ValueError(f"分类 code 必须是英文稳定标识: {normalized or '<empty>'}")
        return normalized

    @staticmethod
    def _normalize_required_text(value: str, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空")
        return normalized

    def _normalize_source_term(self, source_term: str) -> str:
        return self._normalize_required_text(source_term, "source_term")

    @staticmethod
    def _find_category(store: TermRulesStore, category_id: str) -> TermRuleCategoryRecord:
        for category in store.categories:
            if category.id == category_id:
                return category
        raise FileNotFoundError(f"分类不存在: {category_id}")

    @staticmethod
    def _find_rule(store: TermRulesStore, rule_id: str) -> TermRuleRecord:
        for rule in store.rules:
            if rule.id == rule_id:
                return rule
        raise FileNotFoundError(f"规则不存在: {rule_id}")

    @staticmethod
    def _ensure_unique_source_term(
        store: TermRulesStore,
        source_term: str,
        *,
        exclude_rule_id: str | None,
    ) -> None:
        for rule in store.rules:
            if rule.source_term == source_term and rule.id != exclude_rule_id:
                raise ValueError(f"规则 source_term 已存在: {source_term}")

    def _build_rule_record(
        self,
        *,
        rule_id: str,
        category_id: str,
        source_term: str,
        apply_scope: str,
        case_sensitive: bool,
        enabled: bool,
        priority: int,
        segments: list[dict[str, Any]],
        custom_html: str | None,
        custom_markdown: str | None,
        notes: str,
        created_at=None,
    ) -> TermRuleRecord:
        parsed_segments = self._build_segments(segments)
        try:
            parsed_apply_scope = RuleApplyScope(str(apply_scope).strip().lower())
        except ValueError as exc:
            raise ValueError(f"不支持的 apply_scope: {apply_scope}") from exc
        resolved_custom_html = custom_html if custom_html is not None else render_segments_html(parsed_segments)
        resolved_custom_markdown = custom_markdown if custom_markdown is not None else render_segments_markdown(parsed_segments)
        return TermRuleRecord(
            id=rule_id,
            category_id=category_id,
            source_term=source_term,
            rule_mode=RuleMode.SIMPLE if len(parsed_segments) <= 2 else RuleMode.ADVANCED,
            apply_scope=parsed_apply_scope,
            case_sensitive=case_sensitive,
            enabled=enabled,
            priority=int(priority),
            segments=parsed_segments,
            custom_html=resolved_custom_html,
            custom_markdown=resolved_custom_markdown,
            notes=str(notes or ""),
            **({"created_at": created_at} if created_at is not None else {}),
        )

    @staticmethod
    def _build_segments(raw_segments: list[dict[str, Any]]) -> list[TermRuleSegmentRecord]:
        if not raw_segments:
            raise ValueError("segments 必须是非空数组")
        segments: list[TermRuleSegmentRecord] = []
        for index, raw_segment in enumerate(raw_segments):
            segment_text = str(raw_segment.get("segment_text", "") or "")
            if not segment_text:
                raise ValueError("segment_text 不能为空")
            render_type_value = str(raw_segment.get("render_type", "") or "").strip().lower()
            try:
                render_type = RuleRenderType(render_type_value)
            except ValueError as exc:
                raise ValueError(f"不支持的 render_type: {render_type_value}") from exc
            segments.append(
                TermRuleSegmentRecord(
                    seq=index + 1,
                    segment_text=segment_text,
                    render_type=render_type,
                )
            )
        return segments
