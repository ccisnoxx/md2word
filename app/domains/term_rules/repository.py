from __future__ import annotations

# app/domains/term_rules/repository.py: 定义 term_rules domain 依赖的持久化端口。

from typing import Protocol

from app.domains.term_rules.models import (
    TermRuleCategoryRecord,
    TermRuleProposalRecord,
    TermRuleProposalStatus,
    TermRuleRecord,
    TermRulesStore,
)


class TermRuleRepositoryProtocol(Protocol):
    """术语规则 runtime store 的读写合同。"""

    def load(self) -> TermRulesStore: ...
    def save(self, store: TermRulesStore) -> TermRulesStore: ...
    def is_initialized(self) -> bool: ...
    def list_categories_with_counts(self) -> list[tuple[TermRuleCategoryRecord, int, int]]: ...
    def query_rules_page(
        self,
        *,
        category_id: str | None,
        enabled: bool | None,
        q: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[TermRuleRecord], int]: ...
    def add_category(self, category: TermRuleCategoryRecord) -> TermRuleCategoryRecord: ...
    def update_category(self, category: TermRuleCategoryRecord) -> TermRuleCategoryRecord: ...
    def delete_category(self, category_id: str) -> None: ...
    def add_rule(self, rule: TermRuleRecord) -> TermRuleRecord: ...
    def update_rule(self, rule: TermRuleRecord) -> TermRuleRecord: ...
    def delete_rule(self, rule_id: str) -> None: ...


class TermRuleProposalRepositoryProtocol(Protocol):
    """术语建议审核流的持久化合同。"""

    def save_proposal(self, proposal: TermRuleProposalRecord) -> TermRuleProposalRecord: ...
    def get_proposal(self, proposal_id: str) -> TermRuleProposalRecord | None: ...
    def list_proposals(
        self,
        *,
        status: TermRuleProposalStatus | None = None,
        created_by: str | None = None,
    ) -> list[TermRuleProposalRecord]: ...


class TermRuleAssetRepositoryProtocol(Protocol):
    """术语规则版本的 SQL 明细投影持久化合同。"""

    def replace_version(self, term_rule_set_id: str, version: str, store: TermRulesStore) -> None: ...
