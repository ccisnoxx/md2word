from __future__ import annotations

import re
from pathlib import Path

from app.core.rule_models import RuleApplyScope, TermRuleCategoryRecord, TermRuleRecord, TermRulesStore
from app.repositories.protocols import TermRuleRepositoryProtocol
from app.services.term_rules.yaml_codec import (
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
