# Template Profile Versioning 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-29
> 关联方案 doc：`.codestable/features/2026-05-29-template-profile-versioning/template-profile-versioning-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] `TemplateManifestItem` 兼容字段：`app/core/template_models.py` 已包含 `render_policy: dict[str, Any]` 和 `disabled_versions: list[int]`，旧 manifest 未写字段时走默认值。
- [x] `TemplateVersionResponse`：`app/schemas/templates.py` 已返回 `status`、`is_current`、`is_default`、`snapshot_hash`、`render_policy`、`template` 和 `layout_config`。
- [x] 写请求：`TemplateVersionPublishRequest.make_default` 与 `TemplateVersionDefaultRequest.reason` 已在 `app/schemas/templates.py` 定义并从 `app/schemas/api_v1.py` 导出。
- [x] Template version payload：`TemplateReadService._build_template_version_payload()` 生成 `template_id`、`version`、`docx_path`、`docx_sha256`、`layout_config_path`、`layout_config_sha256`、`render_policy`、`name`、`description`；`_snapshot_hash()` 基于完整 payload 计算 `sha256:<hex>`。
- [x] HTTP API：`app/api/v1/routers/templates.py` 已接入 `POST /templates/{template_id}/versions`、`GET /templates/{template_id}/versions`、`POST /templates/{template_id}/versions/{version}/publish`、`POST /templates/{template_id}/versions/{version}/set-default`、`POST /templates/{template_id}/versions/{version}/disable`。

**名词层“现状 → 变化”逐项核对**：

- [x] `TemplateManifestItem`：从只描述当前模板文件扩展为记录 render policy 和 disabled versions。
- [x] `TemplateReadService`：从 manifest/default/file 管理扩展为 Template Version 文件落盘、payload/hash 构建和 resource version service 对接。
- [x] templates router/schema：从已有 CRUD/replace/list versions 扩展为发布状态 API。
- [x] `ResourceVersionService`：仍是通用资源版本状态机；模板模块只写 `resource_type="template"` 的 payload，不新增模板专用状态机。

**流程图核对**：

- [x] 保存 DOCX 到 `data/config/templates/{id}/vN/`：`TemplateReadService._store_versioned_template_file()` 使用 `settings.templates_storage_dir / template_id / f"v{version}"`。
- [x] 构建 payload / snapshot hash：`_build_template_version_payload()` + `_snapshot_hash()`。
- [x] service 可用时写 draft：`_create_template_resource_draft()` 调用 `ResourceVersionService.create_or_update_draft(resource_type="template")`。
- [x] publish / set-default / disable：`publish_template_version()`、`set_default_template_version()`、`disable_template_version()` 分别调用通用 service。
- [x] 同步兼容态：`_activate_template_version()` 更新 manifest 当前 `version`、`template_path`、`layout_config_path`、`render_policy`，并写 `template_state.json`。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] 新建 Template Profile 保存 `docx + layout + render_policy` 为第一个版本：`create_template()` 保存 v1 文件，并在 resource service 存在时创建 template draft；测试 `test_template_profile_versioning_publishes_defaults_and_disables_versions` 覆盖创建后发布为默认。
- [x] 显式创建版本、发布、设默认、禁用接口已落地：router 和 service 均有对应函数，测试覆盖 draft -> published -> default -> disabled。
- [x] 已发布版本不可通过草稿路径改写：新版本创建走 `_next_template_version()`，不会覆盖旧版本目录；发布状态由 `ResourceVersionService` 控制。
- [x] 默认指针只能指向 published：`ResourceVersionService.set_default()` 负责状态校验；测试覆盖 v2 发布后才能 set-default。
- [x] file backend 兼容：旧 create / replace / default / list versions 仍可用；版本发布状态接口在无 resource service 时返回 503，测试 `test_template_versioning_endpoints_require_mysql_resource_service` 覆盖。

**明确不做逐项核对**：

- [x] 不把术语规则或翻译配置塞进 Template Profile：payload 构建只含 DOCX、layout、render policy 和元数据；测试断言 `term_rules` 不在 payload。
- [x] 不做可视化模板编辑器：本次只新增后端 API / service / schema。
- [x] 不在 job 创建时绑定 template version 快照：jobs 模型和 ingest 仍只处理 `template_id`；grep 只看到既有 `template_id` 字段和模板路径解析。
- [x] 不引入 Alembic / SQLAlchemy：本次没有新增迁移体系或相关依赖。
- [x] 不删除历史 DOCX 文件：`delete_template()` 和 `disable_template_version()` 都保留历史版本文件。
- [x] 不强制旧 manifest 模板迁入 MySQL：无 resource service 时保持 manifest 兼容，发布状态接口显式 503。

**关键决策落地**：

- [x] D1 复用 `ResourceVersionService`：`app/main.py` 在 MySQL backend 下挂载 service，`TemplateReadService` 通过它写 draft、publish、set-default、disable。
- [x] D2 只在 `resource_version_service` 可用时启用发布状态：`_require_resource_version_service()` 抛出 RuntimeError，router 映射为 503。
- [x] D3 继续使用整数版本：API response 和 path 用 `int`，写入 resource version 时用 `str(version)`。
- [x] D4 snapshot hash 基于 payload：payload 包含 DOCX hash、layout hash 和 render policy，`snapshot_hash` 不是只 hash DOCX。

**挂载点反向核对（可卸载性）**：

- [x] `TemplateReadService`：本 feature 的文件落盘、payload/hash、默认态同步都集中在这里。
- [x] `ResourceVersionService`：模板发布状态只通过通用 service，不新增状态机。
- [x] templates router：新增 HTTP 入口全部在 `app/api/v1/routers/templates.py`。
- [x] schema：新增响应字段和请求模型在 `app/schemas/templates.py`，并从 `app/schemas/api_v1.py` 汇出。
- [x] `template_state.json`：仍作为当前 conversion path 的默认模板兼容态。
- [x] 反向 grep：`rg -n "term_rules|translation_profile|template_version|resource_version_service|render_policy|JobCreate|template_id" app tests .codestable/features/2026-05-29-template-profile-versioning` 已执行；除既有 jobs `template_id` 和 term-rules 模块外，本 feature 命中均落在设计挂载点内。
- [x] 拔除沙盘推演：移除 router 新入口、schema 新类型、`TemplateReadService` 版本方法和 `app/main.py` service 注入即可卸载发布状态能力；旧 manifest templates API 仍可保留。

## 3. 验收场景核对

- [x] **S1 新建 Template Profile**
  - 输入 / 触发：上传新 Template Profile，`POST /api/v1/templates`。
  - 期望：manifest 有新模板，第一个版本文件存在，MySQL resource service 可保存 draft。
  - 证据：`tests/test_fastapi_jobs_backend.py::FastApiJobsBackendTest::test_template_profile_versioning_publishes_defaults_and_disables_versions` 覆盖创建、发布和 resource record 查询。

- [x] **S2 创建下一版 draft**
  - 输入 / 触发：已有 Template Profile，`POST /api/v1/templates/{template_id}/versions`。
  - 期望：创建下一版 draft，不覆盖旧版本文件。
  - 证据：同一测试断言 v2 response 为 `status == "draft"`，后续下载 v2 内容且 versions list 同时可见 v1/v2。

- [x] **S3 发布 draft**
  - 输入 / 触发：draft version，publish。
  - 期望：状态变为 published，可选设为默认。
  - 证据：测试断言 v1 publish with `make_default=True` 返回 `published` 且 `is_default=True`，v2 publish 后可 set-default。

- [x] **S4 set-default 同步兼容态**
  - 输入 / 触发：published version，set-default。
  - 期望：resource 默认指针切换，manifest 当前 version 与 `template_state.json` 同步。
  - 证据：测试断言 v2 set-default 后 `is_default=True`、下载内容为 v2，repository default record 为 `"2"`。

- [x] **S5 默认版本不能禁用**
  - 输入 / 触发：默认 published version，disable。
  - 期望：拒绝禁用。
  - 证据：测试断言禁用 v2 返回 400。

- [x] **S6 非默认版本可禁用**
  - 输入 / 触发：非默认 published version，disable。
  - 期望：状态变为 disabled，版本列表可观察。
  - 证据：测试断言禁用 v1 返回 200，versions list 中 v1 为 `disabled`，repository record 也为 disabled。

- [x] **反向场景：不塞术语 / 翻译配置**
  - 证据：payload 代码只包含模板字段；测试断言 `term_rules` 不在 records["2"].payload。

- [x] **反向场景：不改 jobs payload**
  - 证据：grep 仍只看到 `template_id`，未新增 job-level template version 字段。

- [x] **反向场景：file backend 兼容**
  - 证据：`test_templates_crud_replace_and_versions_preserve_uploaded_file` 覆盖旧 create / replace / download / versions / delete；`test_template_versioning_endpoints_require_mysql_resource_service` 覆盖无 MySQL resource service 时版本状态接口返回 503。

## 4. 术语一致性

- `Template Profile`：design、architecture、requirement 和 roadmap 中均用于表示 `template_id` 标识的模板资源。
- `Template Version`：代码和文档均使用版本资源语义，HTTP 路径统一为 `/templates/{template_id}/versions...`。
- `render_policy`：代码字段、form 字段 `render_policy_json`、payload 和文档命名一致。
- `snapshot_hash`：schema、payload record 和 architecture 均使用 `sha256:<hex>` 语义。
- 防冲突：grep 确认 Template Profile payload 未引入 `term_rules` / `translation_profile` 作为模板字段；jobs 层未新增 template version 快照字段。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`
  - 已补入 `Template Profile / Template Version` 核心术语。
  - 已更新 FastAPI 外部表面、物理结构、数据与状态、已知边界和变更日志。
  - 已明确 Template Profile 只覆盖 DOCX、`layout_config`、`render_policy`，不承担术语 / 翻译配置和 job 快照绑定。

- [x] `.codestable/architecture/backend-fastapi-service.md`
  - 已更新 backend summary、templates router/service 描述和 resource version service 复用关系。
  - 已加入 Template Profile 版本管理流程图。
  - 已补齐 templates API 合同和 file/sqlite / MySQL resource service 边界。

- [x] `.codestable/attention.md`
  - 本 feature 未发现必须立刻写入 attention 的新项目规约；环境 warning 作为候选记录在第 8 节。

## 6. requirement 回写

- [x] `requirement: fastapi-backend-productization` 指向 current req，本次改变用户可见模板管理能力，已更新 `.codestable/requirements/fastapi-backend-productization.md`。
- [x] 用户故事已加入“模板维护者通过 API 管理 Template Profile 版本，发布后再设默认或禁用旧版本”。
- [x] “怎么解决”已从只读 `GET /api/v1/templates*` 更新为支持 Template Version 状态、模板 CRUD、文件替换、删除、版本 draft/publish/set-default/disable。
- [x] 边界已更新：Template Profile 已接入 resource versioning；Term Rule Set / Translation Profile 和 job 创建资源快照仍留给后续 roadmap。
- [x] 变更日志已追加 2026-05-29 Template Profile versioning 条目。

## 7. roadmap 回写

- [x] 方案 frontmatter 有 `roadmap: backend-productization-implementation` 和 `roadmap_item: template-profile-versioning`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml` 中 `template-profile-versioning` 已从 `in-progress` 更新为 `done`，feature 仍指向 `2026-05-29-template-profile-versioning`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md` 第 5 节子 feature 清单已同步为 `done`。
- [x] roadmap 观察项和变更日志已补入 Template Profile versioning 已落地边界。
- [x] YAML 校验命令：`/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml --yaml-only`。

## 8. attention.md 候选盘点

- 候选 1：使用 `/Users/sc/miniconda3/envs/md2word/bin/python` 运行测试和检查时会打印 `_distutils_hack` / `distutils-precedence.pth` warning，但命令仍可通过；如果后续 feature 也频繁遇到，可由 `cs-note` 补入环境提示。

## 9. 遗留

- 后续 roadmap：`term-rule-set-versioning`、`translation-profile-and-segment-trace`、`job-resource-snapshot-binding` 仍未完成，job 当前仍只绑定 `template_id`。
- 已知限制：Template Version 发布状态 API 需要 MySQL-backed `ResourceVersionService`；file/sqlite backend 保持 manifest 兼容并对发布状态接口返回 503。
- 已知限制：当前不做可视化模板编辑器，不删除历史 DOCX 文件，不强制旧 manifest 模板迁入 MySQL。
- 结构观察：`TemplateReadService` 名称已经从只读服务漂移为读写 / version 管理服务；后续模板、术语版本化都稳定后可另起 refactor 拆分。

## 验证记录

- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_resource_versioning tests.test_database_job_repository tests.test_openapi_export`
  - 结果：通过，75 tests。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`
  - 结果：通过，`changed=False`。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml --yaml-only`
  - 结果：通过，1 file passed。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-29-template-profile-versioning/template-profile-versioning-checklist.yaml --yaml-only`
  - 结果：通过，1 file passed。
- [x] `git diff --check`
  - 结果：通过。

说明：上述 Python 命令都会打印 `_distutils_hack` / `distutils-precedence.pth` warning，但退出码为 0，测试和校验结果有效。
