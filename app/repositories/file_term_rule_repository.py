from __future__ import annotations

import json
from pathlib import Path

from app.core.rule_models import TermRuleCategoryRecord, TermRuleRecord, TermRulesStore


class FileTermRuleRepository:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> TermRulesStore:
        if not self.store_path.exists():
            return TermRulesStore()
        return TermRulesStore.model_validate_json(self.store_path.read_text(encoding="utf-8"))

    def save(self, store: TermRulesStore) -> TermRulesStore:
        self.store_path.write_text(store.model_dump_json(indent=2), encoding="utf-8")
        return store

    def is_initialized(self) -> bool:
        if not self.store_path.exists():
            return False
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return bool(payload.get("categories") or payload.get("rules"))

    def list_categories_with_counts(self) -> list[tuple[TermRuleCategoryRecord, int, int]]:
        store = self.load()
        counts: dict[str, tuple[int, int]] = {}
        for rule in store.rules:
            total, enabled = counts.get(rule.category_id, (0, 0))
            counts[rule.category_id] = (total + 1, enabled + (1 if rule.enabled else 0))
        return [
            (category, counts.get(category.id, (0, 0))[0], counts.get(category.id, (0, 0))[1])
            for category in sorted(store.categories, key=lambda item: (item.priority, item.code))
        ]

    def query_rules_page(
        self,
        *,
        category_id: str | None,
        enabled: bool | None,
        q: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TermRuleRecord], int]:
        rules = sorted(self.load().rules, key=lambda item: (item.priority, item.source_term))
        needle = q.lower() if q else None
        filtered: list[TermRuleRecord] = []
        for rule in rules:
            if category_id and rule.category_id != category_id:
                continue
            if enabled is not None and rule.enabled != enabled:
                continue
            if needle and needle not in rule.source_term.lower():
                continue
            filtered.append(rule)
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        return filtered[start:end], total

    def add_category(self, category: TermRuleCategoryRecord) -> TermRuleCategoryRecord:
        store = self.load()
        store.categories.append(category)
        self.save(store)
        return category

    def update_category(self, category: TermRuleCategoryRecord) -> TermRuleCategoryRecord:
        store = self.load()
        for index, item in enumerate(store.categories):
            if item.id == category.id:
                store.categories[index] = category
                self.save(store)
                return category
        raise FileNotFoundError(f"分类不存在: {category.id}")

    def delete_category(self, category_id: str) -> None:
        store = self.load()
        original_length = len(store.categories)
        store.categories = [item for item in store.categories if item.id != category_id]
        if len(store.categories) == original_length:
            raise FileNotFoundError(f"分类不存在: {category_id}")
        self.save(store)

    def add_rule(self, rule: TermRuleRecord) -> TermRuleRecord:
        store = self.load()
        store.rules.append(rule)
        self.save(store)
        return rule

    def update_rule(self, rule: TermRuleRecord) -> TermRuleRecord:
        store = self.load()
        for index, item in enumerate(store.rules):
            if item.id == rule.id:
                store.rules[index] = rule
                self.save(store)
                return rule
        raise FileNotFoundError(f"规则不存在: {rule.id}")

    def delete_rule(self, rule_id: str) -> None:
        store = self.load()
        original_length = len(store.rules)
        store.rules = [item for item in store.rules if item.id != rule_id]
        if len(store.rules) == original_length:
            raise FileNotFoundError(f"规则不存在: {rule_id}")
        self.save(store)
