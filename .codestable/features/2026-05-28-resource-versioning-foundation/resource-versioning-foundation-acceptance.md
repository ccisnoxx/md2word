---
doc_type: feature-acceptance
feature: 2026-05-28-resource-versioning-foundation
status: ready-for-review
accepted_at: 2026-05-29
design: .codestable/features/2026-05-28-resource-versioning-foundation/resource-versioning-foundation-design.md
roadmap: backend-productization-implementation
roadmap_item: resource-versioning-foundation
tags: [backend, resource-versioning, mysql, acceptance]
---

# Resource Versioning Foundation 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-29
> 关联方案 doc：`.codestable/features/2026-05-28-resource-versioning-foundation/resource-versioning-foundation-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] `ResourceVersionStatus` 已落在 `app/core/resource_models.py`，状态值覆盖 `draft`、`published`、`disabled`、`superseded`。
- [x] `ResourceVersionRecord` 已落在 `app/core/resource_models.py`，字段覆盖 `resource_type`、`resource_id`、`version`、`status`、`snapshot_hash`、`payload_ref`、`payload`、`created_at`、`updated_at`。
- [x] `ResolvedResourceVersion` 已落在 `app/core/resource_models.py`，只表达 `status="published"` 的 job snapshot 可消费结果。
- [x] `ResourceVersionRepositoryProtocol` 已落在 `app/repositories/protocols.py`，包含保存、读取、列出、设置默认和读取默认指针。
- [x] `resource_default_versions` 已落在 `app/repositories/mysql_job_repository.py::MYSQL_SCHEMA_STATEMENTS`。
- [x] 方案示例 `create_or_update_draft()`、`publish(..., make_default=True)`、`resolve_default()` 已由 `ResourceVersionService` 实现，并由 `tests/test_resource_versioning.py` 覆盖。

**名词层“现状 -> 变化”逐项核对**：

- [x] `resource_versions` 从“只建基础表”扩展为 MySQL adapter 可读写的资源版本表。
- [x] repository protocols 新增通用资源版本协议，未混入 template / term-rule / translation 内部字段。
- [x] runtime 在 `JOBS_REPOSITORY_BACKEND=mysql` 下挂载 `resource_version_service`；file / sqlite 路径保持 `None`，未暴露通用 HTTP API。

**流程图核对**：

- [x] `资源子模块生成 payload + snapshot_hash -> create_or_update_draft()`：service 接收外部传入 payload / hash，不计算资源内部内容。
- [x] `save_resource_version() -> resource_versions`：MySQL adapter 按 `(resource_type, resource_id, version)` upsert。
- [x] `publish() -> status = published`：service 只允许 draft 发布。
- [x] `make_default -> resource_default_versions`：service 通过 repository 切默认指针。
- [x] `resolve_default() -> ResolvedResourceVersion`：service 只返回 published 版本。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] 通用资源版本模型和四态状态机已实现。
- [x] MySQL metadata store 复用 `resource_versions` 并新增 `resource_default_versions`。
- [x] service 层实现草稿可更新、发布版本不可变、默认指针只能指向 published、回滚只切默认指针。
- [x] `ResolvedResourceVersion` 只输出 published 版本，供后续 job snapshot 绑定。

**明确不做逐项核对**：

- [x] 未实现 template / term-rule / translation 的具体 CRUD、上传、发布 API。
- [x] 未规定每类资源内部 payload 字段；payload 只作为 dict 快照保存。
- [x] 未把资源版本塞进 jobs payload 或 artifact 合同。
- [x] 未改变现有 `/api/v1/templates`、`/api/v1/term-rules` 接口。
- [x] 未引入 Alembic / SQLAlchemy / 多数据库迁移体系。
- [x] 未实现多租户、权限审计或 job 创建时资源绑定。

**关键决策落地**：

- [x] 内部 service、不新增 HTTP API：无 `resource_versions` router，runtime 只挂 service。
- [x] 默认指针独立表：`resource_default_versions(resource_type, resource_id, version, updated_at)` 已创建。
- [x] 不可变发布语义在 service 层：`create_or_update_draft()` 拒绝改写非 draft，`publish()` 只接受 draft。
- [x] `snapshot_hash` 只校验格式：模型验证 `sha256:<64 hex>`，不计算资源内容 hash。

**编排层“现状 -> 变化”逐项核对**：

- [x] 资源子模块写草稿路径已存在：`create_or_update_draft()`。
- [x] 发布路径已存在：`publish()` 更新状态，可选设默认。
- [x] 默认 / 回滚路径已存在：`set_default()` 和 `rollback_default()` 只操作默认指针。
- [x] 禁用 / supersede 路径已存在：`disable()` 和 `mark_superseded()` 拒绝直接作用于默认版本。
- [x] 解析路径已存在：`resolve_default()` 和 `resolve_version()` 只接受 published。

**流程级约束核对**：

- [x] 错误语义：不存在版本抛 `FileNotFoundError`；状态不允许抛 `ValueError`。
- [x] 幂等性：重复写 draft 覆盖同 key；重复设置默认指针只更新同一行。
- [x] 不可变性：published / disabled / superseded 不可通过 draft 写入路径改 payload、hash 或 payload_ref。
- [x] 顺序约束：默认指针只能指向 published；默认版本 disable / supersede 前必须先切走默认指针。
- [x] 扩展点：资源子模块负责 payload 结构和 hash 计算，通用层只管版本状态和指针。

**挂载点反向核对**：

- [x] MySQL schema bootstrap：`resource_default_versions` 已在 schema statements 中。
- [x] Repository protocol：`ResourceVersionRepositoryProtocol` 已在 `app/repositories/protocols.py`。
- [x] Service 边界：`ResourceVersionService` 已在 `app/services/resource_versions/`。
- [x] Runtime 组合根：`AppRuntime.resource_version_service` 已在 MySQL backend 下挂载。
- [x] 反向核查：`rg "resource_versions|resource_default_versions|ResourceVersion|resource_version_service|/api/v1/resource|resource-version" app tests .codestable/features/2026-05-28-resource-versioning-foundation` 命中均在设计清单范围内；未发现通用 HTTP router。
- [x] 拔除沙盘推演：逆向删除 `app/core/resource_models.py`、`app/services/resource_versions/`、resource version protocol、MySQL adapter 资源版本方法 / 默认指针表、runtime 字段和测试，即可移除本 feature；无额外隐藏挂载点。

## 3. 验收场景核对

- [x] **S1**：输入 draft resource version；触发 `create_or_update_draft()`；期望记录可保存并再次更新 payload / hash。
  - 证据来源：`ResourceVersionServiceTests` 内存 repository 测试。
  - 结果：通过。
- [x] **S2**：输入 draft version；触发 `publish(..., make_default=True)`；期望状态变为 published，默认指针指向该版本。
  - 证据来源：`test_publish_make_default_and_resolve`。
  - 结果：通过。
- [x] **S3**：输入 published version；触发再次 `create_or_update_draft()` 写同 key；期望拒绝修改。
  - 证据来源：`test_published_version_cannot_be_modified_through_draft_path`。
  - 结果：通过。
- [x] **S4**：输入 draft / disabled / superseded version；触发 `set_default()`；期望拒绝非 published。
  - 证据来源：`test_default_pointer_only_accepts_published_versions`。
  - 结果：通过。
- [x] **S5**：输入默认 published version；触发 `disable()` 或 `mark_superseded()`；期望拒绝，必须先切默认指针。
  - 证据来源：`test_default_version_must_be_switched_before_disable_or_supersede`。
  - 结果：通过。
- [x] **S6**：输入两个 published 版本；触发 `rollback_default()` 指向旧版本；期望只切默认指针，不修改旧版本内容。
  - 证据来源：`test_rollback_switches_default_pointer_without_changing_versions`。
  - 结果：通过。
- [x] **S7**：输入 `resolve_default()`；期望返回 `ResolvedResourceVersion(status="published")`，不返回 draft。
  - 证据来源：`test_publish_make_default_and_resolve`、`test_default_pointer_only_accepts_published_versions`。
  - 结果：通过。
- [x] **反向核对**：不新增资源版本 HTTP router、不改变 templates / term-rules API、不写入 jobs payload 或 artifact 文件记录。
  - 证据来源：grep、diff review、`tests.test_fastapi_jobs_backend`。
  - 结果：通过。

已运行验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning tests.test_database_job_repository tests.test_fastapi_jobs_backend
python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-28-resource-versioning-foundation/resource-versioning-foundation-checklist.yaml --yaml-only
python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml --yaml-only
python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-28-resource-versioning-foundation/resource-versioning-foundation-acceptance.md
python .codestable/tools/validate-yaml.py --file .codestable/architecture/ARCHITECTURE.md
python .codestable/tools/validate-yaml.py --file .codestable/architecture/backend-fastapi-service.md
python .codestable/tools/validate-yaml.py --file .codestable/requirements/fastapi-backend-productization.md
python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md
git diff --check -- .codestable/features/2026-05-28-resource-versioning-foundation .codestable/architecture/ARCHITECTURE.md .codestable/architecture/backend-fastapi-service.md .codestable/requirements/fastapi-backend-productization.md .codestable/roadmap/backend-productization-implementation
```

结果：71 个相关 unittest 通过；YAML/frontmatter 校验通过；scoped `git diff --check` 通过。conda 环境仍打印 `_distutils_hack` warning，但命令退出码为 0。

## 4. 术语一致性

- `resource version`：代码中对应 `ResourceVersionRecord`、`ResourceVersionRepositoryProtocol` 和 MySQL `resource_versions`。
- `resource type`：代码中固定为 `Literal["template", "term_rule_set", "translation_profile"]`。
- `published version`：代码中对应 `ResourceVersionStatus.PUBLISHED` 和 `ResolvedResourceVersion(status="published")`。
- `default pointer`：代码中对应 `resource_default_versions` 和 `set_default_resource_version()`。
- `snapshot_hash`：代码中要求 `sha256:<64 hex>`，不与 artifact `sha256` 字段混为同一个模型。
- 防冲突：无 `/api/v1/resource*` router；`resource_versions` 不进入 jobs payload / artifact payload。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`：已归并 `ResourceVersion / default pointer` 术语、MySQL `resource_versions` / `resource_default_versions` 数据状态、内部 service 边界、published-only 解析和不暴露 HTTP API 的已知边界。
- [x] `.codestable/architecture/backend-fastapi-service.md`：已归并 `app/core/resource_models.py`、`app/services/resource_versions/`、MySQL 默认指针表、资源版本内部服务流程和后续资源模块负责 payload / API 的边界。
- [x] `.codestable/attention.md`：本 feature 未暴露新的每次启动必读注意事项，无需补入。

## 6. requirement 回写

- [x] 方案 frontmatter 指向 `fastapi-backend-productization`，该 req 已是 `current`。
- [x] 本次实现改变后端产品化能力边界，因此已更新 `.codestable/requirements/fastapi-backend-productization.md`：
  - 用户故事补入模板、术语、翻译配置需要统一版本状态和默认指针。
  - 解决方案补入 resource versioning 内部 service。
  - 边界补入 `resource_default_versions`、不暴露通用 HTTP router、不实现具体资源 CRUD 和 job snapshot 绑定。
  - 变更日志补入 2026-05-29 resource versioning foundation。

## 7. roadmap 回写

- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml`：`resource-versioning-foundation` 已从 `in-progress` 改为 `done`，feature 指向 `2026-05-28-resource-versioning-foundation`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md`：第 3 节模块边界、第 4.1 节通用协议、第 5 节子 feature 清单、第 7 节观察项和第 8 节变更日志已同步。
- [x] YAML 校验：见最终验证命令。

## 8. attention.md 候选盘点

- [x] 无候选。本 feature 未新增需要每次启动都知道的环境变量、命令陷阱或本地服务步骤；`md2word` conda 解释器使用要求已在 attention.md 中存在。

## 9. 遗留

- 后续优化点：
  - `template-profile-versioning` 需要复用 `ResourceVersionService`，补模板 payload / hash 计算和对外 API。
  - `term-rule-set-versioning` 需要复用默认指针和 rollback 规则，补术语草稿 / 发布 API。
  - `translation-profile-and-segment-trace` 需要定义翻译配置 payload 和 segment 追踪。
  - `job-resource-snapshot-binding` 需要在 job 创建时解析 `ResolvedResourceVersion` 并写入不可变快照。
- 已知限制：
  - 当前没有真实 MySQL 服务 smoke；fake MySQL 只覆盖 repository SQL 合同。
  - `MysqlJobRepository` 名称偏 jobs，但现在也承载 resource versioning；后续如继续膨胀，可走 `cs-refactor` 评估 `mysql_metadata_repository.py` 或 mixin 拆分。
- 用户终审：待用户确认。
