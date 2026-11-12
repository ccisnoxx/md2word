# 实施与验证记录

基线 `30081252df51acdc3205809fe51f8b7df315a2e6`。命令在任务工作树以项目 Python 3.11 执行。

## PR 1 · 默认模板基线与任务资源

### TPL-BASE-001

- 新增独立 OOXML 特征测试，使用 manifest 解析实际默认模板。输出包含纵向单栏、连续双栏、连续恢复单栏、横向和恢复纵向五个 Section。
- 核对默认覆盖开关、首页与奇偶页设置、各节装饰继承，以及 relationship 关联 Logo 的 SHA-256。
- 在运行时代码尚未修改时，`python -m unittest tests.test_template_package_contract` 通过 2 项。基线阶段 `python -m unittest tests.test_template_seed_history tests.test_document_ir_word_renderer_layout` 通过 78 项。
- LibreOffice 26.2.4.2 以隔离配置将基线 DOCX 转为 3 页 PDF。该产物用作实施后的同输入对照。

### TPL-RSC-001

- 以版本及 canonical payload SHA-256 验证绑定，原子物化并回读任务 DOCX、YAML 和规则副本。Renderer 消费同一组认证字节，发布证明复用本次实际输入，普通重试与术语重绑沿用已有合同。
- `python -m unittest tests.test_job_render_resources tests.test_worker_failure_policy tests.test_document_job_list_query_v2_service.DocumentJobListV2PublicationTests tests.test_document_ir_word_renderer_layout tests.test_template_package_contract tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_resource_selection_requires_admin_and_rebinds_term_assets` 通过 84 项，其中新增资源测试 13 项。
- 在未修改的 main 重现了两个旧断言失败：历史 direct 任务详情投影 `test_historical_direct_read_clone_and_default_retry_keep_lazy_snapshot`，以及验证任务 fixture 占用 bundled `default@2` 的 `test_only_admin_can_create_validation_job_with_draft_template_version`。后者直接覆盖本次 draft 授权，纳入 TPL-VAL-001 的定向夹具修正。
- `python -m unittest tests.test_document_job_execution_stages` 在候选和未改 main 均运行 21 项，同为 6 项失败、5 项错误，涉及既有空 MinerU 夹具、旧加载器签名和证据调用次数。该历史维护不计入本次通过项。
- 独立复核发现任务模板双重解析及术语重绑丢失部门。创建、克隆和重绑已复用选定版本，重绑保留原部门。定向命令 `python -m unittest tests.test_document_job_modes.DocumentJobModesTests.test_create_and_clone_snapshot_bind_selected_custom_default_template tests.test_document_job_modes.DocumentJobModesTests.test_template_default_change_after_selection_does_not_rebind_new_job tests.test_document_job_modes.DocumentJobModesTests.test_explicit_rule_retry_keeps_old_template_and_bound_department tests.test_document_job_modes.DocumentJobModesTests.test_direct_symbol_rules_stay_available_for_create_retry_and_clone tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_resource_selection_requires_admin_and_rebinds_term_assets` 通过 5 项。补充历史仅记录模板 ID 的子用例后，对应 retry 测试再次通过。

## PR 2 · 模板装饰符合性

- 新增共享 OPC 部件读取与 `template-conformance/v1`，按各节实际生效的关系检查页眉、页脚、媒体和模板设置。修复多节自定义模板清空正文时丢失末节继承引用的问题。
- `python -m unittest tests.test_template_conformance tests.test_template_package_contract tests.test_document_ir_word_renderer_layout` 通过 72 项。
- 默认模板用同一份混合 Section IR 生成的前后产物，对比 19 个 ZIP 成员 SHA-256 全部一致。

## PR 3 · DOCX 与 YAML 联合预检

- 创建、替换、版式草稿、发布和 bootstrap 共用模板包预检，复用实际 Word 样式与语言配置校验。发布重新核对已登记指纹及已保存的验证任务绑定。
- 预检失败保留默认指针，测试覆盖无残留草稿目录或资源记录，以及 bootstrap 不写半批数据。既有 draft 授权测试采用真实模板与未占用版本，保留角色断言。
- 定向组合覆盖 `tests.test_template_package_validator`、`tests.test_template_seed_history`、`tests.test_template_layout_config_schema`、`tests.test_document_ir_word_renderer_layout`、`tests.test_template_conformance`、`tests.test_render_config_characterization` 和 5 项模板管理 API 回归，合计 116 项通过。

  ```bash
  python -m unittest \
    tests.test_template_package_validator tests.test_template_seed_history \
    tests.test_template_layout_config_schema tests.test_document_ir_word_renderer_layout \
    tests.test_template_conformance tests.test_render_config_characterization \
    tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_templates_crud_replace_and_versions_preserve_uploaded_file \
    tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_profile_versioning_publishes_defaults_and_disables_versions \
    tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_admin_creates_draft_version_without_mutating_source_yaml \
    tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_database_failure_removes_staged_version_directory \
    tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_only_admin_can_create_validation_job_with_draft_template_version
  ```

- 补充无 YAML 的版本仍能按持久化绑定激活后，`python -m unittest tests.test_template_package_validator tests.test_template_seed_history` 通过 29 项。
- 独立复核发现同号覆盖与发布竞争。旧替换入口复用版本分配器，上传目录和草稿记录仅创建。发布按 DRAFT 状态及预检时的快照 SHA-256 原子写入状态和审核信息。定向命令 `python -m unittest tests.test_template_seed_history tests.test_resource_versioning tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_file_replacement_preserves_version_published_outside_manifest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_profile_versioning_publishes_defaults_and_disables_versions tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_database_failure_removes_staged_version_directory` 通过 38 项，使用 fake MySQL。

## PR 4 · YAML 字段消费

- 169 个可编辑叶子逐项做独立 OOXML 单字段变异，17 个配置叶子和 3 个元数据字段维持只读合同。首页型号和品类保留历史读取与预览，编辑器标为只读。
- 窄表应用配置的正文对齐及段前段后间距，表头居中、宽表压缩保持原有行为。默认配置下相同窄表、宽表样本的 19 个 ZIP 成员与 main 逐字节一致。
- `python -m unittest tests.test_template_config_consumption` 通过 5 项，含字段变异矩阵及 HTML 表格回归。

## PR 5 · 质量证据与发布检查

- 新证据绑定生成实物和原模板/配置身份，有证据的历史件重新验证报告。质量门消费稳定阻断码，事件、管理摘要和 Datasheet 报告仅提供安全投影。
- 独立复核发现非空损坏栅格的检查缺口，加入实际图片结构校验及截断 PNG、有效 WMF 回归。
- `python -m unittest tests.test_template_conformance tests.test_template_package_contract tests.test_template_package_validator tests.test_document_ir_word_renderer_layout tests.test_formula_rendering_compatibility tests.test_image_group_rendering` 通过 130 项，`python -m unittest tests.test_job_render_resources` 通过 13 项。
- `python -m unittest tests.test_datasheet_quality_metrics tests.test_datasheet_quality_collector` 通过 18 项，覆盖通过、阻断、历史未采集和安全投影。
- 额外运行 `python -m unittest tests.test_document_job_result_persistence`。候选和未改 main 的该模块均为 27 个方法，21 个 failure、50 个 error（含子用例），类型一致，属于既有持久化夹具和并发等待问题。
- 统一当前默认资源的 manifest 解析，历史 YAML 的用途写在 manifest 与维护文档。核对当前默认 DOCX、v1 YAML、v2 YAML 的原始字节 SHA-256 与 main 一致。
- 复核发现历史 v1 YAML 误绑到 `default@2` 时，仅验证两份固定文件的 SHA 无法发现错绑。发布检查的 manifest 绑定项现在核对实际选中的 DOCX/YAML。内存错绑探针确认会被拒绝。
- `python scripts/ops/check_release.py` 最终通过全部八项，包括 OpenAPI、四个模板专项检查和现有 134 项定向回归。模板专项中绑定 2 项、消费及历史哈希 7 项、装饰 1 项。
- `python -m unittest tests.test_template_package_contract tests.test_openapi_export.OpenAPIExportTests.test_release_template_gate_rejects_missing_binding_and_corrupt_package tests.test_openapi_export.OpenAPIExportTests.test_check_release_aggregates_openapi_and_optional_unittest_targets` 在绑定门禁调整后通过 5 项。

## 最终本地验证

`python -m unittest` 组合通过 184 项。完整参数如下，之后发生的测试与 release 检查代码调整由上面的 5 项及最终 release check 复核。

```text
tests.test_template_seed_history
tests.test_document_ir_word_renderer_layout
tests.test_template_package_contract
tests.test_template_conformance
tests.test_template_config_consumption
tests.test_template_layout_config_schema
tests.test_template_package_validator
tests.test_job_render_resources
tests.test_datasheet_quality_metrics
tests.test_datasheet_quality_collector
tests.test_resource_versioning
tests.test_runtime_dependency_declarations
tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_only_admin_can_create_validation_job_with_draft_template_version
tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_templates_crud_replace_and_versions_preserve_uploaded_file
tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_file_replacement_preserves_version_published_outside_manifest
tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_profile_versioning_publishes_defaults_and_disables_versions
tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_admin_creates_draft_version_without_mutating_source_yaml
tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_template_layout_config_database_failure_removes_staged_version_directory
tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_resource_selection_requires_admin_and_rebinds_term_assets
tests.test_document_job_modes.DocumentJobModesTests.test_create_and_clone_snapshot_bind_selected_custom_default_template
tests.test_document_job_modes.DocumentJobModesTests.test_template_default_change_after_selection_does_not_rebind_new_job
tests.test_document_job_modes.DocumentJobModesTests.test_explicit_rule_retry_keeps_old_template_and_bound_department
```

同一份混合 Section IR 在基线和候选生成 DOCX，19 个 ZIP 成员逐字节一致。初次跨进程导出的 PDF 文字一致，位图存在差异。用同一隔离 LibreOffice 26.2.4.2 进程同时打开并导出后，3 页的栅格像素逐页相同。该对照覆盖指定样本及此版本 LibreOffice。

`python scripts/dev/run_component_pdf_regression.py --sample-id ti-opamp-opa228-p1-smoke --output-dir <临时目录> --no-timestamp` 通过 1 项，使用仓库内最小 MinerU 样本。远程 Golden Sample preflight、真实在线验证任务和在线 Word preview 尚无本轮运行证据，当前环境未配置 Golden Sample 管理凭据。

Trellis 上下文校验与 `git diff --check` 通过。新增和修改的代码说明、docstring 与开发可见错误按项目约定使用中文。

## 本地提交候选

拟议提交信息 `feat(template): 加强模板与渲染资源完整性`。以下仅列当前独立工作树的本任务文件。五组 PR 评审摘要与结果见本页上方。

<details>
<summary>展开拟提交路径</summary>

- `.trellis/spec/backend/template-layout-configuration.md`
- `.trellis/spec/backend/word-generation-rules.md`
- `.trellis/tasks/11-12-template-render-integrity/check.jsonl`
- `.trellis/tasks/11-12-template-render-integrity/design.md`
- `.trellis/tasks/11-12-template-render-integrity/implement.jsonl`
- `.trellis/tasks/11-12-template-render-integrity/implement.md`
- `.trellis/tasks/11-12-template-render-integrity/prd.md`
- `.trellis/tasks/11-12-template-render-integrity/task.json`
- `.trellis/tasks/11-12-template-render-integrity/validation.md`
- `app/conversion/docx_rules/terminology.py`
- `app/core/config.py`
- `app/domains/document_jobs/_failure_policy.py`
- `app/domains/document_jobs/publication_provenance.py`
- `app/domains/document_jobs/render_execution.py`
- `app/domains/document_jobs/router.py`
- `app/domains/document_jobs/use_cases/publication.py`
- `app/domains/document_jobs/use_cases/request_snapshot.py`
- `app/domains/document_jobs/use_cases/submission.py`
- `app/domains/jobs/resource_snapshots.py`
- `app/domains/resources/integrity.py`
- `app/domains/resources/repository.py`
- `app/domains/templates/layout_config_schema.py`
- `app/domains/templates/manifest.py`
- `app/domains/templates/package_validator.py`
- `app/domains/templates/read_service.py`
- `app/domains/templates/router.py`
- `app/infrastructure/persistence/mysql/resources.py`
- `app/services/ooxml_package.py`
- `app/services/renderer/block_evidence.py`
- `app/services/renderer/native_table_renderer.py`
- `app/services/renderer/render_event_summary.py`
- `app/services/renderer/render_evidence.py`
- `app/services/renderer/render_evidence_validation.py`
- `app/services/renderer/resource_identity.py`
- `app/services/renderer/table_renderer.py`
- `app/services/renderer/template_conformance.py`
- `app/services/renderer/word_renderer.py`
- `docs/dev/backend-local-setup-and-architecture.md`
- `docs/dev/local-conversion-sandbox.md`
- `resources/template_configs/templates_manifest.yaml`
- `scripts/dev/local_mineru_debug_config.json`
- `scripts/dev/local_mineru_debug_direct_config.json`
- `scripts/dev/local_mineru_debug_en2zh_config.json`
- `scripts/dev/local_mineru_debug_ru2zh_config.json`
- `scripts/dev/run_datasheet_quality_baseline.py`
- `scripts/dev/run_local_mineru_quality_matrix.py`
- `scripts/ops/check_release.py`
- `scripts/ops/datasheet_quality_metrics.py`
- `tests/document_job_list_query_v2_publication_fixtures.py`
- `tests/test_conversion_sandbox_dev_tools.py`
- `tests/test_database_job_repository.py`
- `tests/test_datasheet_quality_collector.py`
- `tests/test_datasheet_quality_metrics.py`
- `tests/test_document_ir_word_renderer_layout.py`
- `tests/test_document_job_modes.py`
- `tests/test_fastapi_jobs_backend.py`
- `tests/test_job_render_resources.py`
- `tests/test_local_mineru_quality_matrix.py`
- `tests/test_openapi_export.py`
- `tests/test_resource_versioning.py`
- `tests/test_template_config_consumption.py`
- `tests/test_template_conformance.py`
- `tests/test_template_package_contract.py`
- `tests/test_template_package_validator.py`
- `tests/test_template_seed_history.py`

</details>
