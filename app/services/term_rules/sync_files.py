from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.repositories.protocols import TermRuleRepositoryProtocol
from app.services.term_rules.yaml_codec import TermRuleYamlCodec


@dataclass(frozen=True)
class TermRuleFileSyncResult:
    repository_backend: str
    category_count: int
    rule_count: int
    bootstrap_seed_path: Path
    runtime_yaml_path: Path
    warnings: list[str] = field(default_factory=list)


class TermRuleFileSyncService:
    def __init__(
        self,
        repository: TermRuleRepositoryProtocol,
        runtime_yaml_path: Path,
        bootstrap_seed_path: Path,
        *,
        repository_backend: str,
    ) -> None:
        self.repository = repository
        self.runtime_yaml_path = runtime_yaml_path
        self.bootstrap_seed_path = bootstrap_seed_path
        self.repository_backend = repository_backend
        self.yaml_codec = TermRuleYamlCodec()

    def sync_files(self) -> TermRuleFileSyncResult:
        store = self.repository.load()
        v2_yaml_text = self.yaml_codec.dump_store(store)
        runtime_yaml_text = self.yaml_codec.dump_legacy_runtime_yaml(store)
        self.bootstrap_seed_path.parent.mkdir(parents=True, exist_ok=True)
        self.bootstrap_seed_path.write_text(v2_yaml_text, encoding="utf-8")
        self.runtime_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_yaml_path.write_text(runtime_yaml_text, encoding="utf-8")
        return TermRuleFileSyncResult(
            repository_backend=self.repository_backend,
            category_count=len(store.categories),
            rule_count=len(store.rules),
            bootstrap_seed_path=self.bootstrap_seed_path,
            runtime_yaml_path=self.runtime_yaml_path,
            warnings=[],
        )
