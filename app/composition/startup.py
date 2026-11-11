from __future__ import annotations

# app/composition/startup.py: 进程启动时的幂等种子写入与登记，集中在全部服务构造完成之后执行。
#
# 顺序约束（见 .trellis/tasks/11-11-sr-3-composition-root/research/bootstrap-order.md）：
# 下列步骤各自只写自己的存储且"为空才写入"，构造函数不读取它们的产物，因此可以在构造之后统一执行；
# 步骤之间仍保持拆分前的相对顺序。

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
    # 先解析默认模板（缺失时失败），再幂等登记 bundled seed 版本。
    pipeline.template_read_service.get_default_template_id()
    pipeline.template_read_service.bootstrap_manifest_versions()
