---
doc_type: feature-acceptance
feature: 2026-05-29-term-rule-set-versioning
status: passed
summary: 验收 Term Rule Set 草稿、发布、默认版本和回滚 API 已按 design 落地，并完成架构、requirement、roadmap 回写
tags: [backend, term-rules, resource-versioning, productization]
---

# Term Rule Set Versioning 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-29
> 关联方案 doc：`.codestable/features/2026-05-29-term-rule-set-versioning/term-rule-set-versioning-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] `TermRuleSetVersionResponse`：`app/schemas/term_rules.py` 已返回 `term_rule_set_id`、`version`、`status`、`rule_count`、`enabled_rule_count`、`snapshot_hash`、`is_default`、`published_by`、`publish_reason`、`published_at`。
- [x] `TermRuleSetDraftResponse`：`app/schemas/term_rules.py` 已返回 `term_rule_set_id`、`base_version`、`rule_count`、`enabled_rule_count`、`yaml_text`、`snapshot_hash`。
- [x] `TermRuleSetDraftUpdateRequest` / `TermRuleSetPublishRequest` / `TermRuleSetRollbackRequest`：schema 已定义，并从 `app/schemas/api_v1.py` 导出。
- [x] HTTP API：`app/api/v1/routers/term_rule_sets.py` 已接入 `GET /term-rule-sets`、`GET /{set_id}`、`GET /{set_id}/draft`、`PUT /{set_id}/draft/rules`、`POST /{set_id}/publish`、`POST /{set_id}/versions/{version}/set-default`、`POST /{set_id}/rollback`。

**名词层“现状 → 变化”逐项核对**：

- [x] `TermRulesStore`：仍是 live runtime store 的结构，Term Rule Version payload 通过 `store: store.model_dump(mode="json")` 保存完整 v2 store。
- [x] `TermRuleService`：继续负责 legacy live store CRUD / import / export / simulate / sync-files；版本发布编排未塞入该 service。
- [x] `TermRuleSetVersionService`：新增在 `app/services/term_rules/versioning_service.py`，负责 draft、publish、set-default、rollback 和 runtime YAML 同步。
- [x] `ResourceVersionService`：复用通用 `resource_type="term_rule_set"`，不新增术语专用状态机。

**流程图核对**：

- [x] `PUT /draft/rules` 先走 YAML 校验：router 调用 `runtime.term_rule_import_validation_service.validate_yaml_text()`。
- [x] Draft payload 写入 `ResourceVersionService.create_or_update_draft(version="draft")`，不调用 live repository save / runtime YAML export。
- [x] Publish 生成 `YYYY.MM.DD-N` 版本，先创建实际版本 draft，再调用 `ResourceVersionService.publish()`。
- [x] `make_default=true`、set-default、rollback 都调用 `_sync_live_store()`，把 published payload 写回 `TermRuleRepository` 并导出 legacy runtime YAML。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] 草稿可更新且不影响任务使用的 runtime YAML：测试 `test_term_rule_set_versioning_draft_publish_default_and_rollback` 断言 draft 更新后 runtime YAML 未变。
- [x] 发布版本写入 resource version 底座且不可原地修改：`publish_draft()` 写入 `resource_type="term_rule_set"`，通用测试 `test_published_version_cannot_be_modified_through_draft_path` 覆盖 published 版本不可通过 draft 路径覆盖。
- [x] 默认指针只能指向 published：本次补了 HTTP 级断言，`POST /versions/draft/set-default` 返回 400，默认指针仍保持旧 published 版本。
- [x] set-default / rollback 同步 live runtime：测试覆盖 v2 设默认后 runtime YAML 出现 `VTWO`，rollback 到 v1 后 export 只含 `VONE`。
- [x] 查询默认 Term Rule Set 只列 published versions：`_version_records()` 过滤 `version != "draft"`，detail 测试断言发布两版后 versions 长度为 2。
- [x] file/sqlite 兼容路径保留：无 resource service 时 `/term-rule-sets` 写接口返回 503，legacy category 创建仍返回 201。

**明确不做逐项核对**：

- [x] 不修改 jobs payload / job snapshot：对 `app/core/job_models.py`、`app/services/jobs`、jobs routers、`app/schemas/jobs.py` grep `term_rule_set_id|term_rule_set_version|term_rule_version|translation_profile|template_profile|resource_snapshot` 无命中。
- [x] 不实现 Translation Profile 或 Template Profile 字段：对 term-rule-set service/router/schema grep `TemplateProfile|TranslationProfile|template_profile|translation_profile|render_policy|layout_config` 无命中。
- [x] 不新增审计事件表或权限角色系统：本次只保留 payload 元数据 `published_by`；未新增 actor / role / permission 模型或 repository。
- [x] 不引入 Alembic / SQLAlchemy：未新增迁移体系。
- [x] 不做多租户隔离：`TermRuleSetVersionService` 当前只允许 `electronics-default`。

**关键决策落地**：

- [x] D1 复用 `ResourceVersionService`：draft、publish、set-default、rollback 均通过通用 service。
- [x] D2 草稿更新不写 live runtime store：`update_draft()` 只构建 payload 并写 resource draft。
- [x] D3 版本化能力只在 resource service 可用时启用：router `_require_term_rule_set_version_service()` 无 service 时返回 503。
- [x] D4 legacy 写接口在 versioned mode 下拒绝直改 runtime：`ensure_legacy_term_rule_write_allowed()` 已挂到 category/rule create/update/delete、import、sync-files。
- [x] D5 初始草稿派生：`_ensure_draft_record()` 优先复制默认 published 版本，否则复制当前 live store。

**挂载点反向核对（可卸载性）**：

- [x] `ResourceVersionService`：term rule set 所有 draft / published / default pointer / rollback 状态都挂在这里。
- [x] `/api/v1/term-rule-sets` router：所有新 HTTP 入口集中在 `term_rule_sets.py`，由 `app/api/v1/router.py` 注册。
- [x] `app/schemas/term_rules.py`：Term Rule Set / Draft / Version API 合同集中在该文件。
- [x] `TermRuleRepository` + `runtime_subscripts_dictionary.yaml`：只有 `_sync_live_store()` 在 published default 路径写回兼容 live runtime。
- [x] legacy 写入口：grep `ensure_legacy_term_rule_write_allowed` 命中 `term_rule_categories.py` 3 处、`term_rules.py` 5 处，均为写路径。
- [x] 反向 grep：`term_rule_set` 命中集中在 service/router/schema/runtime wiring/tests 和 resource version 通用类型内；未发现清单外业务挂载点。
- [x] 拔除沙盘推演：移除 `term_rule_sets.py`、`term_rule_write_guard.py` 调用、`TermRuleSetVersionService` wiring 和 schema 导出即可卸载本能力；legacy read/export/simulate 与 file/sqlite 写路径仍可保留。

## 3. 验收场景核对

- [x] **S1 有效 YAML 更新 draft 不改 runtime YAML**
  - 证据：`tests/test_fastapi_jobs_backend.py::FastAPIJobsBackendTests::test_term_rule_set_versioning_draft_publish_default_and_rollback`
  - 结果：draft 返回 200 / `rule_count=1`，runtime YAML 与更新前相同。

- [x] **S2 无效 YAML 返回 400 且 draft 不变化**
  - 证据：`test_term_rule_set_draft_rejects_invalid_yaml_without_mutating_draft`
  - 结果：返回 `code=invalid_term_rule_set_draft`，前后 `snapshot_hash` 相同。

- [x] **S3 publish `make_default=true` 生成 published version 并同步 runtime**
  - 证据：主流程测试断言 response `status == "published"`、`is_default == true`，runtime YAML 包含 `VONE`。

- [x] **S4 publish `make_default=false` 不改变默认指针和 runtime YAML**
  - 证据：主流程测试断言 v2 `is_default == false`，runtime YAML 不含 `VTWO`。

- [x] **S5 set-default 到旧/新 published version 只切默认并同步 live store**
  - 证据：主流程测试断言 v2 set-default 后 runtime YAML 包含 `VTWO`，detail/export 行为一致。

- [x] **S6 rollback 只切默认指针，不修改历史 payload**
  - 证据：主流程测试保存 rollback 前后 resource version payload 并断言 v1 payload 相等。

- [x] **S7 draft version set-default 被拒绝**
  - 证据：本次补充主流程测试断言 `POST /versions/draft/set-default` 返回 400，default version 仍是 v1。

- [x] **S8 file/sqlite backend versioned 写接口返回 503，legacy 写仍可用**
  - 证据：`test_term_rule_set_versioning_backend_requirements_and_legacy_write_guard`
  - 结果：versioned draft update 503，legacy category create 201。

- [x] **S9 MySQL versioned mode legacy 写接口拒绝绕过**
  - 证据：同一测试断言 MySQL mode legacy category create 返回 400，detail 指向 `/api/v1/term-rule-sets`。

## 4. 术语一致性

- [x] `Term Rule Set` / `term_rule_set`：代码命中均用于术语规则集版本服务、router、schema、runtime wiring、tests 和 resource type。
- [x] `Term Rule Draft`：代码中以固定 `DRAFT_VERSION = "draft"` 表达，HTTP 路径为 `/draft/rules`。
- [x] `Term Rule Version`：发布版本通过 `YYYY.MM.DD-N` 生成，`draft` 不出现在 detail 的 published versions 列表。
- [x] `default term rule version`：默认指针走 `resource_default_versions` / `ResourceVersionService.set_default()`。
- [x] `live runtime store`：代码只在 `_sync_live_store()` 写 `TermRuleRepository` 和 runtime YAML。
- [x] 防冲突：Term Rule Set payload 未混入 Template Profile / Translation Profile 字段；jobs payload 未新增 term-rule snapshot 字段。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`：新增 Term Rule Set / Term Rule Version 术语、HTTP 表面、service 挂载点、runtime 同步约束、known boundary 和变更日志。
- [x] `.codestable/architecture/backend-fastapi-service.md`：新增 `term_rule_sets.py` router、Term Rule Set 版本管理流程图、API 合同、legacy 写保护和 resource versioning 当前边界。
- [x] `.codestable/attention.md`：本 feature 未新增新的通用环境坑；上一轮已把 conda 测试解释器约定写入“测试”分节。

归并后，未读 design 的读者可以从 architecture 看到：MySQL backend 下 `/term-rule-sets` 管理 draft/published/default/rollback，默认 published payload 同步到 legacy live runtime；file/sqlite 保持 legacy 写兼容，versioned mode 保护 legacy 写入口。

## 6. requirement 回写

- [x] `requirement: fastapi-backend-productization` 已是 `current`，本次更新用户故事、解决方案、边界和变更日志。
- [x] 新能力已从“术语 / 翻译配置后续共用”更新为“Template Profile 与 Term Rule Set 已接入，Translation Profile 后续共用”。
- [x] 明确保留边界：job 创建时绑定术语版本快照仍由 `job-resource-snapshot-binding` 处理。

## 7. roadmap 回写

- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml`：`term-rule-set-versioning` 已从 `in-progress` 改为 `done`，feature 保持 `2026-05-29-term-rule-set-versioning`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md`：第 5 条子 feature 状态已同步为 `done`，观察项和变更日志已补入 Term Rule Set 已落地边界。
- [x] YAML 校验已纳入验证命令。

## 8. attention.md 候选盘点

- [x] 无候选。本 feature 未暴露新的每次会话都必须知道的环境变量、本地服务步骤或命令陷阱；测试解释器约定已经在 `.codestable/attention.md` 中存在。

## 9. 遗留

- 后续优化点：
  - `job-resource-snapshot-binding`：任务创建时绑定默认 Term Rule Version，保证历史 job 可复现。
  - `translation-profile-and-segment-trace`：Translation Profile 仍未接入资源版本。
  - `permission-and-audit-baseline`：当前仅保留 `published_by` / `publish_reason` payload 元数据，没有 actor / audit event。
- 已知限制：
  - MVP 只支持默认术语规则集 `electronics-default`。
  - `/term-rule-sets` 写能力要求 MySQL resource service；file/sqlite backend 保持 legacy live store 写兼容。
  - 没有前端 UI，本次只验收后端 API / service / schema / tests。
- 实现阶段顺手发现：
  - Release check 在新增 `/term-rule-sets` API 后检测到 OpenAPI snapshot 变化；已用 conda 解释器运行 `scripts/ops/export_openapi.py` 刷新 `docs/api/openapi.json`，复跑 release check 通过。

## 验证记录

- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_set_versioning_draft_publish_default_and_rollback tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_set_draft_rejects_invalid_yaml_without_mutating_draft tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_set_versioning_backend_requirements_and_legacy_write_guard`
  - 结果：3 tests OK。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_resource_versioning tests.test_openapi_export`
  - 结果：68 tests OK。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`
  - 初次结果：OpenAPI changed；刷新 snapshot 后复跑通过。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
  - 结果：`docs/api/openapi.json` 已刷新，`path_count=40`，`schema_count=59`。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile app/services/term_rules/versioning_service.py app/api/v1/routers/term_rule_sets.py app/api/v1/routers/term_rule_write_guard.py app/schemas/term_rules.py app/core/runtime.py app/main.py tests/test_fastapi_jobs_backend.py`
  - 结果：通过。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file <design/checklist/acceptance/items/roadmap/architecture/requirement>`
  - 结果：本 feature design、checklist、acceptance、roadmap items / 主文档、`ARCHITECTURE.md`、`backend-fastapi-service.md`、`fastapi-backend-productization.md` 均通过。
