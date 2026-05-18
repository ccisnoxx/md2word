from __future__ import annotations

from dataclasses import dataclass

from app.core.rule_models import TermRuleImportValidationFinding, TermRuleImportValidationReport, TermRuleImportValidationSummary, TermRulesStore
from app.services.term_rules.yaml_codec import TermRuleYamlCodec


@dataclass(frozen=True)
class TermRuleImportValidationResult:
    valid: bool
    summary: TermRuleImportValidationSummary
    errors: list[TermRuleImportValidationFinding]
    warnings: list[TermRuleImportValidationFinding]
    parsed_store: TermRulesStore | None = None


class TermRuleImportValidationService:
    def __init__(self) -> None:
        self.yaml_codec = TermRuleYamlCodec()

    def validate_yaml_text(self, yaml_text: str) -> TermRuleImportValidationResult:
        result = self.yaml_codec.validate_yaml_text(yaml_text)
        parsed_store = result.store
        summary = TermRuleImportValidationSummary(
            category_count=len(parsed_store.categories) if parsed_store else 0,
            rule_count=len(parsed_store.rules) if parsed_store else 0,
            error_count=len(result.errors),
            warning_count=len(result.warnings),
        )
        return TermRuleImportValidationResult(
            valid=not result.errors,
            summary=summary,
            errors=[TermRuleImportValidationFinding(code=item.code, message=item.message, path=item.path) for item in result.errors],
            warnings=[TermRuleImportValidationFinding(code=item.code, message=item.message, path=item.path) for item in result.warnings],
            parsed_store=parsed_store,
        )

    @staticmethod
    def to_report(result: TermRuleImportValidationResult) -> TermRuleImportValidationReport:
        return TermRuleImportValidationReport(
            valid=result.valid,
            summary=result.summary,
            errors=result.errors,
            warnings=result.warnings,
        )
