from __future__ import annotations

# app/composition/startup.py: API 在持久化和服务装配完成后执行启动初始化。

from app.composition.document_pipeline import DocumentPipeline
from app.composition.platform import PlatformServices
from app.composition.terminology import TerminologyServices
from app.core.config import Settings
from app.domains.term_rules.bootstrap import TermRuleBootstrapService


def run_startup_bootstrap(
    settings: Settings,
    platform: PlatformServices,
    pipeline: DocumentPipeline,
    terminology: TerminologyServices,
) -> None:
    platform.auth_service.bootstrap_repository_from_config_if_empty()
    platform.acceptance_run_service.bootstrap_default_runs_if_empty()
    pipeline.term_version_service.bootstrap_repository_from_csv_if_empty()
    if terminology.term_rule_set_version_service is not None:
        terminology.term_rule_set_version_service.bootstrap_seed_as_default_if_empty(settings.term_rules_seed_file)
    else:
        TermRuleBootstrapService(
            terminology.term_rule_repository,
            settings.term_rules_runtime_yaml_file,
            settings.term_rules_seed_file,
            repository_backend="file",
        ).bootstrap()
    if terminology.translation_profile_service is not None:
        terminology.translation_profile_service.bootstrap_default_profiles_if_missing()
    # MySQL 默认选择依赖已登记的目录与版本。
    pipeline.template_read_service.bootstrap_manifest_versions()
    pipeline.template_read_service.get_default_template_id()
