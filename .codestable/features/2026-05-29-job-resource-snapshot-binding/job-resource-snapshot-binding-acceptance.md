# Job Resource Snapshot Binding 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-29
> 关联方案 doc：`.codestable/features/2026-05-29-job-resource-snapshot-binding/job-resource-snapshot-binding-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] `ConversionOptions`：`app/core/job_models.py` 已包含 `template_version`、`term_rule_set_id`、`term_rule_set_version`、`translation_profile_id`、`translation_profile_version`，并保留 legacy `template_id`。
- [x] `JobMineruSnapshot` / `JobResourceSnapshot`：`app/core/job_models.py` 已表达 template、term_rule_set、可选 translation_profile、非敏感 MinerU 配置和 `artifact_ids`。
- [x] `JobRecord.resource_snapshot`：`app/core/job_models.py` 已新增可为空字段，旧 job 允许 `resource_snapshot=None`。
- [x] `JobResourceSnapshotResponse`：`app/schemas/jobs.py` 已返回资源摘要、MinerU snapshot 和 `artifact_ids`；`JobAcceptedResponse` 与 `JobDetailResponse` 均包含 `resource_snapshot`。
- [x] job-local term-rule YAML 路径：`app/core/job_paths.py` 已固定 `data/jobs/{job_id}/resources/runtime_subscripts_dictionary.yaml`。

**名词层“现状 → 变化”逐项核对**：

- [x] jobs create form contract：`app/api/v1/routers/jobs_ingest.py` 已在 `POST /api/v1/jobs` 和 `POST /api/v1/jobs/pdf` 接收 versioned resource selection 字段。
- [x] 创建期解析：`app/services/jobs/command.py` 在 zip / PDF job 创建前调用 `JobResourceSnapshotService.build_snapshot()`，并写入 `JobRecord.resource_snapshot` 和 `job_created` event details。
- [x] stage 执行：`app/services/jobs/stage.py` 在 conversion pipeline 中优先 materialize snapshot resources；PDF MinerU submit stage 优先使用 snapshot 中的非敏感请求配置。
- [x] response presenter：`app/api/v1/routers/jobs_presenters.py` 已把 `JobResourceSnapshot` 转成 v1 response schema。

**流程图核对**：

- [x] `POST /api/v1/jobs` / `/jobs/pdf` → `_build_conversion_options()` → `JobResourceSnapshotService.build_snapshot()` → `JobRecord.resource_snapshot` → stage materialize → `build_job_conversion_request()` 均有实际代码落点。
- [x] file/sqlite 分支：无 `ResourceVersionService` 时 `build_snapshot()` 返回 `None`，但显式 versioned resource selection 会返回 503。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] MySQL direct job 创建时绑定默认 Template Version 和 Term Rule Version，`translation_profile` 为 null；测试 `test_mysql_direct_job_binds_template_term_snapshot_and_source_alias` 覆盖。
- [x] MySQL `en2zh` job 创建时绑定 Translation Profile Version，conversion request 使用 snapshot profile；测试 `test_mysql_en2zh_job_binds_translation_profile_snapshot_and_uses_payload` 覆盖。
- [x] 创建后默认 Template / Term Rule Set 切换、禁用或 supersede，不改变已创建 job 的执行资源；测试 `test_mysql_default_switch_and_disabled_versions_do_not_change_existing_job_snapshot` 覆盖。
- [x] PDF 在线提交 stage 使用创建时 MinerU snapshot；测试 `test_mysql_pdf_job_uses_mineru_snapshot_and_source_pdf_alias` 覆盖。
- [x] file/sqlite 不传 versioned resource 参数时保持 legacy 路径；既有 FastAPI jobs suite 覆盖本地默认创建与转换路径。

**明确不做逐项核对**：

- [x] 不新增 Template / Term Rule Set / Translation Profile 编辑或发布 API：本 feature 只新增 jobs snapshot service、jobs form 字段、response 字段和 stage materialization。
- [x] 不新增 `zh2en` / `zh2ru` 或 `source_language` / `target_language` jobs API：`ConversionOptions.translation_mode` 仍为 `direct | en2zh`，`jobs_ingest.py` 只接受 `direct` / `en2zh`。
- [x] 不保存 secret 或完整 prompt：snapshot model 只保存 resource summary、非敏感 MinerU 字段和 source alias；Translation Profile payload 只 materialize model / target language / domain / prompt version / batch 阈值。
- [x] 不新增 translation segment metadata 表：本 feature 未改 repository schema 增加 segment 表，segment trace 仍是 artifact。
- [x] 不回填历史 job：`JobRecord.resource_snapshot` 可为空，stage 对空 snapshot 走 legacy path。
- [x] 不新增独立 artifact id 体系：`artifact_ids` 只写 `{"source": "source_package"}` 或 `{"source": "source_pdf"}`。

**关键决策落地**：

- [x] MySQL-only 严格 snapshot：`JobResourceSnapshotService` 在有 `ResourceVersionService` 时解析 published resources；无 service 且传 versioned 参数返回 503。
- [x] stage 只按 snapshot materialize：`materialize()` 读取 exact record，校验 `snapshot_hash`，只拒绝 draft / 缺 payload / hash mismatch；disabled / superseded 创建后仍可 replay。
- [x] term-rule job-local YAML：`_materialize_term_rule_set()` 使用 `TermRuleYamlCodec.dump_legacy_runtime_yaml()` 写入 job-local `resources/runtime_subscripts_dictionary.yaml`。
- [x] Translation Profile 只绑定 `en2zh`：`direct` 任务传 `translation_profile_id/version` 会返回 400；`en2zh` 缺 profile snapshot 会在 stage 明确失败。
- [x] MinerU snapshot 非敏感：只记录 `model_version`、`language`、`enable_formula`、`enable_table`、`callback_enabled`、`data_id`。

**挂载点反向核对（可卸载性）**：

- [x] jobs create form contract：新增字段集中在 `app/api/v1/routers/jobs_ingest.py`。
- [x] persisted job contract：`JobRecord.resource_snapshot` 在 `app/core/job_models.py`。
- [x] jobs API response contract：`app/schemas/jobs.py` 与 `app/api/v1/routers/jobs_presenters.py`。
- [x] snapshot service：`app/services/jobs/resource_snapshots.py` 承载创建期解析与 stage 物化。
- [x] stage execution contract：`app/services/jobs/stage.py` conversion pipeline 和 PDF MinerU submit 分支。
- [x] job-created event details：`app/core/job_workflow.py` 写入 `resource_snapshot`。
- [x] 反向 grep：`rg -n "JobResourceSnapshot|resource_snapshot|template_version|term_rule_set_id|translation_profile_version|artifact_ids|resource_subscript_config" app tests/test_fastapi_jobs_backend.py tests/test_database_job_repository.py` 已执行，命中均落在上述挂载点或既有资源版本模块内。
- [x] 拔除沙盘推演：移除 `resource_snapshots.py`、`JobRecord.resource_snapshot` / schema 字段、jobs form 新字段、stage materialization 分支和 runtime 注入即可卸载本 feature；file/sqlite legacy path 可继续依赖 `template_id`、全局 runtime YAML 和 settings。

## 3. 验收场景核对

- [x] **S1 MySQL direct job 绑定 template + term-rule snapshot**
  - 证据：`test_mysql_direct_job_binds_template_term_snapshot_and_source_alias` 断言 accepted/detail snapshot 一致、`translation_profile=None`、source alias 为 `source_package`，conversion request 使用 snapshot template path 与 job-local YAML。

- [x] **S2 MySQL en2zh job 绑定 Translation Profile snapshot**
  - 证据：`test_mysql_en2zh_job_binds_translation_profile_snapshot_and_uses_payload` 断言 request 的 model、target language、domain、prompt version 和 batch 阈值来自 snapshot payload。

- [x] **S3 默认资源切换后历史 job 不漂移**
  - 证据：`test_mysql_default_switch_and_disabled_versions_do_not_change_existing_job_snapshot` 在创建后发布 v2、切默认、disable template v1、supersede term v1，worker replay 后仍使用 v1 template 与 v1 term YAML。

- [x] **S4 snapshot hash mismatch 不 fallback**
  - 证据：`test_mysql_snapshot_hash_mismatch_fails_stage_without_live_fallback` 断言 job 和 stage message 失败码为 `resource_snapshot_hash_mismatch`，conversion entrypoint 未被调用。

- [x] **S5 MySQL 缺默认资源创建失败**
  - 证据：`test_mysql_resource_mode_requires_default_template_and_term_rules` 断言创建 job 返回 409。

- [x] **S6 file backend 显式 versioned resource selection 返回 503**
  - 证据：`test_file_backend_rejects_versioned_resource_selection` 断言传 `template_version` 返回 503，错误信息指向 `JOBS_REPOSITORY_BACKEND=mysql`。

- [x] **S7 PDF job 使用 MinerU snapshot 和 `source_pdf` alias**
  - 证据：`test_mysql_pdf_job_uses_mineru_snapshot_and_source_pdf_alias` 断言 snapshot 记录创建时 language / formula / table / data_id，提交 MinerU 时使用创建时配置。

- [x] **反向场景：不保存 secret / 不新增 artifact id / 不扩展翻译方向**
  - 证据：代码 grep 确认 snapshot service 只写 source alias；jobs API 仍只接受 `direct` / `en2zh`；secret 相关命中来自既有配置检查、测试 fixture 或错误文案，不进入 `JobResourceSnapshot`。

## 4. 术语一致性

- `Job Resource Snapshot`：design、architecture、requirement、acceptance 和代码中均指 `JobRecord.resource_snapshot`。
- `resource selection`：jobs form 的 versioned resource 选择字段，未扩展到 `source_language` / `target_language`。
- `ResolvedResourceVersion`：继续表示 published-only 解析摘要；snapshot stage replay 通过 exact record 校验 hash。
- `materialized job resources`：代码中对应 `MaterializedJobResources`，包含 template path、job-local subscript YAML 和 Translation Profile snapshot。
- `artifact_ids`：文档和代码均限定为 source artifact alias，不是独立 artifact id。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`
  - 已补入 `Job Resource Snapshot` 核心术语。
  - 已更新 FastAPI 外部表面、物理结构、后端主流程、数据与状态、已知边界和变更日志。
  - 已明确 MySQL-only strict snapshot、file/sqlite legacy path、source alias-only `artifact_ids` 和 no-secret snapshot 约束。

- [x] `.codestable/architecture/backend-fastapi-service.md`
  - 已更新 backend summary、jobs service 物理结构、主流程、jobs API 合同、翻译能力和已知边界。
  - 已新增 Job Resource Snapshot Binding 流程图，说明创建期绑定和 stage exact materialization。

- [x] `.codestable/attention.md`
  - 本 feature 未发现必须补入 attention 的新项目规约；既有 conda python 测试约束已覆盖本轮验证。

## 6. requirement 回写

- [x] `requirement: fastapi-backend-productization` 指向 current req，本次改变用户可见 jobs 创建 / 详情 / 可复现执行能力，已更新 `.codestable/requirements/fastapi-backend-productization.md`。
- [x] 用户故事已加入“任务创建时锁定实际使用的模板、术语规则、翻译配置和非敏感 MinerU 请求配置”。
- [x] “怎么解决”已加入 jobs 创建期绑定 snapshot、stage 只按 snapshot materialize runtime resources、PDF 提交使用 MinerU snapshot。
- [x] 边界已更新：MySQL resource mode strict snapshot 已落地；file/sqlite 保持 legacy；显式 versioned selection 返回 503；不保存 secret、不回填历史 job、不新增独立 artifact id、不扩展翻译方向。
- [x] 变更日志已追加 2026-05-29 Job Resource Snapshot Binding 条目。

## 7. roadmap 回写

- [x] 方案 frontmatter 有 `roadmap: backend-productization-implementation` 和 `roadmap_item: job-resource-snapshot-binding`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml` 中 `job-resource-snapshot-binding` 已从 `in-progress` 更新为 `done`，feature 指向 `2026-05-29-job-resource-snapshot-binding`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md` 第 4.2 节创建合同已同步当前 jobs API 范围，第 5 节子 feature 清单已同步为 `done`。
- [x] roadmap 观察项和变更日志已补入 Job Resource Snapshot Binding 已落地边界。

## 8. attention.md 候选盘点

- [x] 无候选：本 feature 未暴露需要补入 `.codestable/attention.md` 的新环境、工具或工作流信息。现有注意事项已经说明测试必须使用 `/Users/sc/miniconda3/envs/md2word/bin/python`。

## 9. 遗留

- 后续 roadmap：`permission-and-audit-baseline` 与 `operations-readiness-and-test-baseline` 仍未完成。
- 已知限制：MySQL resource mode 的严格 snapshot 依赖 `ResourceVersionService`；file/sqlite 仍是 legacy path，不能声明版本化资源绑定。
- 已知限制：历史 job 不回填 snapshot；`resource_snapshot=None` 任务继续按旧兼容路径执行。
- 已知限制：Translation Profile 当前只支持 `electronics-en2zh`；jobs API 不支持 `zh2en` / `zh2ru`。
- 结构观察：`app/services/jobs/stage.py` 仍偏胖；本 feature 已把资源解析 / 物化放入独立 service，但 provider 执行与 conversion 执行拆分仍适合后续单独 refactor。

## 验证记录

- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
  - 结果：通过，67 tests。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning tests.test_database_job_repository`
  - 结果：通过，17 tests。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile app/core/job_models.py app/core/job_paths.py app/core/job_workflow.py app/core/runtime.py app/main.py app/api/errors.py app/api/v1/routers/jobs_ingest.py app/api/v1/routers/jobs_presenters.py app/schemas/jobs.py app/schemas/api_v1.py app/services/jobs/command.py app/services/jobs/stage.py app/services/jobs/resource_snapshots.py`
  - 结果：通过。
- [x] `rg -n "OPENAI_API_KEY|mineru_api_token|MINERU_API_TOKEN|callback_token|prompt_text|prompt_content|artifact_id|source_language|target_language|zh2en|zh2ru" app/core/job_models.py app/services/jobs/resource_snapshots.py app/api/v1/routers/jobs_ingest.py app/schemas/jobs.py tests/test_fastapi_jobs_backend.py`
  - 结果：命中均为既有配置检查、测试 fixture、Translation Profile payload 字段或 source alias-only `artifact_ids`；未发现 secret 写入 `JobResourceSnapshot`，未新增 jobs API 翻译方向。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-29-job-resource-snapshot-binding/job-resource-snapshot-binding-checklist.yaml --yaml-only`
  - 结果：通过。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml --yaml-only`
  - 结果：通过。
- [x] `git diff --check -- .codestable/architecture/ARCHITECTURE.md .codestable/architecture/backend-fastapi-service.md .codestable/requirements/fastapi-backend-productization.md .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml .codestable/features/2026-05-29-job-resource-snapshot-binding/job-resource-snapshot-binding-checklist.yaml .codestable/features/2026-05-29-job-resource-snapshot-binding/job-resource-snapshot-binding-acceptance.md`
  - 结果：通过。
