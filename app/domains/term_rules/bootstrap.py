from __future__ import annotations

# app/domains/term_rules/bootstrap.py: 从 seed 初始化 term_rules runtime store。

from dataclasses import dataclass
from pathlib import Path

from app.domains.term_rules.repository import TermRuleRepositoryProtocol
from app.domains.term_rules.service import TermRuleService


@dataclass(frozen=True)
class TermRuleBootstrapResult:
    repository_backend: str
    imported: bool
    category_count: int
    rule_count: int
    runtime_yaml_path: Path
    bootstrap_yaml_path: Path
    warnings: list[str]


class TermRuleBootstrapService:
    def __init__(
        self,
        repository: TermRuleRepositoryProtocol,
        runtime_yaml_path: Path,
        bootstrap_yaml_path: Path,
        *,
        repository_backend: str,
    ) -> None:
        self.repository_backend = repository_backend
        self.term_rule_service = TermRuleService(repository, runtime_yaml_path, bootstrap_yaml_path)
        self.runtime_yaml_path = runtime_yaml_path
        self.bootstrap_yaml_path = bootstrap_yaml_path

    def bootstrap(self) -> TermRuleBootstrapResult:
        store, imported, warnings = self.term_rule_service.bootstrap_from_seed_if_empty()
        return TermRuleBootstrapResult(
            repository_backend=self.repository_backend,
            imported=imported,
            category_count=len(store.categories),
            rule_count=len(store.rules),
            runtime_yaml_path=self.runtime_yaml_path,
            bootstrap_yaml_path=self.bootstrap_yaml_path,
            warnings=warnings,
        )
