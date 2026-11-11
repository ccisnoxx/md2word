# 实施与验证

1. 已授权先写简短计划后直接实施；基线 79f20cef，初始工作区干净。
2. 读取 backend directory-structure/error-handling/quality-guidelines/logging-guidelines 与复用指南，检查实际定义、消费者、测试。
3. 先记录 AST 基线和必须测试基线，再迁移 owner 与导入，补必要定向默认值/SDK 回归。
4. 在根目录使用 PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python -m unittest，临时文件仅使用本任务内临时路径且清理。
5. 必须执行 tests.test_translation_profile_prompts.TranslationProfilePromptTests.test_bootstrap_seeds_four_profiles_without_overwriting_defaults、tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_when_default_translation_mode_requires_missing_client、tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_main_calls_formal_conversion_adapter、tests.test_conversion_sandbox_dev_tools.OfficialConversionRuntimeBindingTests.test_runtime_facade_load_pages_binds_model_classes；补充直接相关现有测试。基线失败单列，不修历史问题。
6. AST 对比、唯一 owner、默认值和健康/CLI 合同验证；检查最终 diff 与保护路径。独立 Trellis check 复核，复用成功结果。无需改 Spec；新归属记录在本任务设计。禁止提交和归档。
