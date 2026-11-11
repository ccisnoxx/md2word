# B05 第 1 步实施证据

基线 HEAD：`79f20cef9ca0bb1a59af635e2408e130c4935e2d`。实施前产品文件干净，仅主会话创建的本任务目录未跟踪。

## 检查命令与实际结果

工作目录始终为 `${TASK_WORKTREE_ROOT}/b05-1-formal-deps`。全部 Python 命令使用 `PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python`；涉及临时文件的测试及最终 AST 检查另设 `TMPDIR="$PWD/.trellis/tasks/11-06-b05-1-formal-deps/tmp"`。测试后该目录为空，已用 `rmdir` 清理。

基线命令：

```sh
TMPDIR="$PWD/.trellis/tasks/11-06-b05-1-formal-deps/tmp" PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python -m unittest -v \
  tests.test_translation_profile_prompts.TranslationProfilePromptTests.test_bootstrap_seeds_four_profiles_without_overwriting_defaults \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_when_default_translation_mode_requires_missing_client \
  tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_main_calls_formal_conversion_adapter \
  tests.test_conversion_sandbox_dev_tools.OfficialConversionRuntimeBindingTests.test_runtime_facade_load_pages_binds_model_classes
```

结果：4/4 通过，0 失败，`baseline-tests.log` 保存原始输出。

最终定向命令：

```sh
TMPDIR="$PWD/.trellis/tasks/11-06-b05-1-formal-deps/tmp" PYTHONDONTWRITEBYTECODE=1 ${PROJECT_ROOT}/.venv/bin/python -m unittest -v \
  tests.test_formal_conversion_configuration \
  tests.test_translation_profile_prompts.TranslationProfilePromptTests.test_bootstrap_seeds_four_profiles_without_overwriting_defaults \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_when_default_translation_mode_requires_missing_client \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_marks_translation_unavailable_when_provider_disabled \
  tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_main_calls_formal_conversion_adapter \
  tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_build_conversion_kwargs_uses_official_runtime_contract \
  tests.test_conversion_sandbox_dev_tools.LocalMinerUDebugConfigTests.test_main_calls_formal_conversion_adapter_from_config \
  tests.test_conversion_sandbox_dev_tools.OfficialConversionRuntimeBindingTests.test_runtime_facade_load_pages_binds_model_classes \
  tests.test_local_mineru_quality_matrix.LocalMinerUQualityMatrixTests.test_en2zh_without_key_or_response_is_reported_as_blocker \
  tests.test_local_mineru_quality_matrix.LocalMinerUQualityMatrixTests.test_ru2zh_without_key_or_response_is_reported_as_blocker \
  tests.test_llm_client_characterization.LLMClientCharacterizationTests.test_build_client_requires_sdk \
  tests.test_llm_client_characterization.LLMClientCharacterizationTests.test_build_client_requires_api_key \
  tests.test_translation_runtime_characterization.TranslationRuntimeCharacterizationTests.test_request_payload_keeps_llm_items_minimal
```

结果：20/20 通过，0 失败，`targeted-tests.log` 保存原始输出。其中 7 个新用例锁定默认值、环境空值优先级、整型默认/下限/非法输入、dotenv 解析、旧配置与生成沙箱配置的对象同一性、SDK 导入异常分流、模型回退、三 CLI 默认值及 key/SDK 四种健康组合。SDK 探测测试使用独立模块对象，不 reload 或污染共享模块。

两个测试批次均出现既有 Starlette HTTP 常量及 TestClient/httpx 弃用警告。没有基线失败，也未修历史测试。

附加静态检查：

- Python `ast.parse`：六个消费者前后导入对比见 `import-comparison.json`，复用主会话的 `import-baseline.json`。基线 8 条直接导入和 1 条生成配置导入；迁移后目标 legacy 导入为 0。迁移生成文本也作为独立 Python AST 检查。
- `ast.dump(ast.parse(git show HEAD:app/conversion/runtime_config.py))` 与新 `app/core/conversion_config.py` 的 AST 完全相等。新旧文件所在目录深度相同，`ROOT_DIR` 不变。
- 对迁移符号的定义搜索确认：`AppConfig/load_app_config/APP_CONFIG` 只归正式配置；`DEFAULT_MODEL/OpenAI` 探测只归 `app/clients/openai_sdk.py`；三个翻译常量只归 `modes.py`。正式 Provider 的原有延迟 SDK 导入路径不在迁移范围且未修改。
- `git diff --check`：通过。
- `git diff --exit-code -- app/conversion/docx_rules app/conversion/runtime/table_html_parser.py app/domains/jobs app/domains/translation/provider.py docs/implementation/codex-task-manifest.yaml`：通过，受保护路径与 Provider 不变。

## 六个消费者的归属变化

| 消费者 | 原导入 | 新归属 |
| --- | --- | --- |
| profiles_service | llm_client、translation_runtime | openai_sdk.DEFAULT_MODEL、modes 三常量 |
| health_service | llm_client | openai_sdk.OpenAI |
| run_local_mineru_conversion | llm_client、translation_runtime、runtime_config | openai_sdk.DEFAULT_MODEL、core.conversion_config.APP_CONFIG |
| run_local_mineru_debug_config | llm_client、runtime_config | openai_sdk.DEFAULT_MODEL、core.conversion_config.APP_CONFIG |
| run_local_mineru_quality_matrix | llm_client、runtime_config | openai_sdk.DEFAULT_MODEL、core.conversion_config.APP_CONFIG |
| migrate_md2word_main_sandbox 生成配置 | runtime_config | core.conversion_config.APP_CONFIG/ROOT_DIR |

## 剩余正式 runtime 导入

扫描 `app/` 与 `scripts/`，排除 legacy 所在 `app/conversion/` 后，仅以下四处保留 `app.conversion.runtime.table_html_parser` 共享能力（完整记录见 `remaining-runtime-imports.json`）：

- `app/services/document_ir/artifact_validator.py:26`
- `app/services/document_ir/logical_table_group.py:15`
- `app/services/renderer/evidence.py:12`
- `app/services/renderer/table_renderer.py:24`

未移动或删除 docx_rules、parser、jobs 共享能力，旧转换入口保留。没有真实 Provider/MinerU/数据库调用，没有全仓或在线测试，没有 commit/push/发布。新增与修改注释/docstring 使用中文；CLI 帮助文案和未改逻辑中的历史文本保持原样，确保行为逐字不变。

## 最终独立复核与收尾

Trellis check 子代理只读复核未发现本次引入的可操作缺陷；已阅读原始测试日志，复用 4/4 基线与 20/20 定向结果，未重复运行。主会话再次检查最终 diff、受保护路径、新增 Python 文件语法及临时目录清理，均通过。未运行独立 lint/type-check；不能用 diff 检查代替其结果。

AC-1 至 AC-5 均有本地证据支持；此处是实现者报告，不代表 Claude 已验收。按授权不提交、不推送、不归档、不写会话日志；任务目录保留供后续审阅。
