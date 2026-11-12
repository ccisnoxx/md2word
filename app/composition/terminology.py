from __future__ import annotations

# app/composition/terminology.py: 装配术语规则、翻译术语集、提案、术语发布与翻译 profile 服务。

from dataclasses import dataclass

from app.composition.platform import PlatformServices
from app.core.config import Settings
from app.domains.term_rules.file_repository import FileTermRuleRepository
from app.domains.term_rules.import_validation import TermRuleImportValidationService
from app.domains.term_rules.proposals_service import TermRuleProposalService
from app.domains.term_rules.review_service import TermRuleReviewService
from app.domains.term_rules.service import TermRuleService
from app.domains.term_rules.sync_files import TermRuleFileSyncService
from app.domains.term_rules.versioning_service import TermRuleSetVersionService
from app.domains.terminology.service import TerminologyReleaseService
from app.domains.translation.profiles_service import TranslationProfileVersionService
from app.domains.translation.proposals_service import TranslationTermProposalService
from app.domains.translation.term_set_version_service import TranslationTermSetVersionService
from app.infrastructure.persistence import PersistenceAdapters


@dataclass(frozen=True)
class TerminologyServices:
    term_rule_repository: FileTermRuleRepository
    term_rule_service: TermRuleService
    term_rule_import_validation_service: TermRuleImportValidationService
    term_rule_file_sync_service: TermRuleFileSyncService
    term_rule_set_version_service: TermRuleSetVersionService | None
    term_rule_proposal_service: TermRuleProposalService | None
    term_rule_review_service: TermRuleReviewService | None
    translation_profile_service: TranslationProfileVersionService | None
    translation_term_set_version_service: TranslationTermSetVersionService | None
    translation_term_proposal_service: TranslationTermProposalService | None
    terminology_release_service: TerminologyReleaseService


def build_terminology_services(
    settings: Settings,
    adapters: PersistenceAdapters,
    platform: PlatformServices,
) -> TerminologyServices:
    """版本化服务只在对应仓储（及资源版本服务）可用时构造，否则为 None，与 legacy 文件模式兼容。"""

    resource_version_service = platform.resource_version_service
    audit_service = platform.audit_service
    term_rule_repository = FileTermRuleRepository(settings.term_rules_store_file)
    term_rule_service = TermRuleService(
        term_rule_repository,
        settings.term_rules_runtime_yaml_file,
        settings.term_rules_seed_file,
    )
    term_rule_set_version_service = (
        TermRuleSetVersionService(
            repository=term_rule_repository,
            runtime_yaml_path=settings.term_rules_runtime_yaml_file,
            resource_version_service=resource_version_service,
            audit_service=audit_service,
            asset_repository=adapters.term_rule_asset_repository,
        )
        if resource_version_service is not None
        else None
    )
    translation_term_set_version_service = (
        TranslationTermSetVersionService(adapters.translation_term_repository, audit_service)
        if adapters.translation_term_repository is not None
        else None
    )
    return TerminologyServices(
        term_rule_repository=term_rule_repository,
        term_rule_service=term_rule_service,
        term_rule_import_validation_service=TermRuleImportValidationService(),
        term_rule_file_sync_service=TermRuleFileSyncService(
            term_rule_repository,
            settings.term_rules_runtime_yaml_file,
            settings.term_rules_seed_file,
            repository_backend="file",
        ),
        term_rule_set_version_service=term_rule_set_version_service,
        term_rule_proposal_service=(
            TermRuleProposalService(
                repository=adapters.term_rule_proposal_repository,
                term_rule_service=term_rule_service,
                term_rule_set_version_service=term_rule_set_version_service,
                audit_service=audit_service,
            )
            if adapters.term_rule_proposal_repository is not None
            and term_rule_set_version_service is not None
            else None
        ),
        term_rule_review_service=(
            TermRuleReviewService(
                repository=adapters.term_rule_review_repository,
                term_rule_service=term_rule_service,
                term_rule_set_version_service=term_rule_set_version_service,
                audit_service=audit_service,
            )
            if adapters.term_rule_review_repository is not None
            and term_rule_set_version_service is not None
            else None
        ),
        translation_profile_service=(
            TranslationProfileVersionService(settings, resource_version_service, audit_service)
            if resource_version_service is not None
            else None
        ),
        translation_term_set_version_service=translation_term_set_version_service,
        translation_term_proposal_service=(
            TranslationTermProposalService(
                repository=adapters.translation_term_repository,
                term_set_version_service=translation_term_set_version_service,
                audit_service=audit_service,
            )
            if adapters.translation_term_repository is not None
            and translation_term_set_version_service is not None
            else None
        ),
        terminology_release_service=TerminologyReleaseService(
            adapters.terminology_release_repository,
            translation_term_repository=adapters.translation_term_repository,
            resource_version_service=resource_version_service,
        ),
    )
