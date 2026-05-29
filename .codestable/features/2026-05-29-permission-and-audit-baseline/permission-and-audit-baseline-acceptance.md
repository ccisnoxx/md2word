---
doc_type: feature-acceptance
feature: 2026-05-29-permission-and-audit-baseline
status: passed
summary: 验收最小 ActorContext、AuditEvent、审计持久化和高风险动作审计已按 design 落地，并完成架构、requirement、roadmap 回写
tags: [backend, permission, audit, jobs, productization]
---

# Permission and Audit Baseline 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-29
> 关联方案 doc：`.codestable/features/2026-05-29-permission-and-audit-baseline/permission-and-audit-baseline-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] `ActorRole` / `ActorContext`：`app/core/audit_models.py` 已定义 `admin`、`jobs`、`anonymous` 三类最小 actor role；`ActorContext` 只包含 `actor_id`、`actor_role` 和 `source`，不包含 token 原文。
- [x] `AuditEvent`：`app/core/audit_models.py` 已定义独立审计事件，包含 `audit_id`、`actor_id`、`actor_role`、`action`、`target_type`、`target_id`、`reason`、`trace_id` 和 `created_at`。
- [x] `AuditEventRepositoryProtocol`：`app/repositories/protocols.py` 已新增 `append_audit_event()` 和 `list_audit_events()`。
- [x] `AuditService.record()`：`app/services/audit.py` 已统一生成 `audit_id`、过滤空白 reason，并写入 audit repository。
- [x] 动作命名：代码中已落地 `template.publish`、`template.set_default`、`template.disable`、`term_rule_set.publish`、`term_rule_set.set_default`、`term_rule_set.rollback`、`translation_profile.publish`、`translation_profile.set_default`、`translation_profile.rollback`、`job.retry`、`job.cancel`、`job.cleanup_local_files` 和 `artifact.download`。

**名词层“现状 → 变化”逐项核对**：

- [x] `require_admin_access()` / `require_jobs_access()` / `require_job_ops_access()` 保留兼容函数；`require_admin_actor()` / `require_jobs_actor()` / `require_job_ops_actor()` 返回 `ActorContext`。
- [x] `JobEvent` 未被复用为跨资源审计；`AuditEvent` 是独立模型和独立 repository 端口。
- [x] file backend 写 `data/audit_events.jsonl`；sqlite / MySQL backend 均新增 `audit_events` 表和按 `created_at, id` 排序读取方法。
- [x] `AppRuntime` 已挂载 `audit_event_repository` 与 `audit_service`，`app/main.py` 组合根把 audit service 注入模板、术语、翻译配置和 job lifecycle service。

**流程图核对**：

- [x] `HTTP request` → `dependency 解析 token` → `ActorContext`：`app/api/dependencies.py` 中 `require_*_actor()` 完成。
- [x] `router 调用 service`：templates、term-rule-sets、translation-profiles 和 jobs ops router 均显式接收 actor 并传入 service。
- [x] `业务动作成功` → `AuditService.record()`：资源 service 和 job lifecycle 均在成功路径写 audit；download router 在确认可返回 file / stream / redirect 后写 audit。
- [x] `audit repository` → `file / sqlite / MySQL audit_events`：三种 repository 均实现 append / list，测试覆盖 repository contract。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] admin-only 资源动作继续用 `X-Admin-Token` 保护，并可把 `ActorContext` 传给 service；模板、术语规则集和翻译配置的发布 / 默认 / 回滚 / 禁用动作均写 audit。
- [x] `retry`、`cancel`、`cleanup-local-files` 继续遵守 `JOBS_OPS_ACCESS_MODE`；默认 admin-only，配置为 jobs 时可用 `X-Jobs-Token`，成功审计记录 actor、reason 和 trace_id。
- [x] artifact download 在 `JOBS_ACCESS_MODE=open/token/admin` 口径下通过 `require_jobs_actor()` 拿 actor；open 模式写 `actor_role=anonymous`、`actor_id=None`。
- [x] 审计事件独立于 JobEvent；job ops 成功时原有 JobEvent 仍保留，额外写 `AuditEvent`。

**明确不做逐项核对**：

- [x] 不做多租户、公司隔离、SSO、session、用户表或密码登录：grep 未发现新增相关模型 / router / schema；`single_tenant_public` 命中来自既有 callback 部署模式。
- [x] 不新增细粒度 ACL、资源所有者校验或前端权限菜单：本次只从现有 token 边界派生最小 actor。
- [x] 不新增审计查询 HTTP API 或审计 UI：无 audit router；audit 只通过 repository 端口供测试和后续运维脚本读取。
- [x] 不改变既有 token 配置语义：测试覆盖缺配置仍 503、错误 token 仍 403。
- [x] 不把 token、secret、完整 payload 或本地绝对私密路径写入 audit event：audit payload 只含 actor/action/target/reason/trace_id；download `target_id` 使用 `{job_id}:{artifact_alias}`。
- [x] 不执行真实 artifact 删除：cleanup 仍是既有本地清理语义，retention 真实删除继续留给后续 operations feature。

**关键决策落地**：

- [x] actor 从现有 token 边界派生：`admin` 来自 admin token，`jobs` 来自 jobs token，open 下载为 `anonymous`。
- [x] `X-Actor-Id` 只在已认证 token 场景作为标签；open 下载即使传 `X-Actor-Id` 也保持 `actor_id=None`。
- [x] audit 不复用 JobEvent：`AuditEventRepositoryProtocol` 独立于 `JobRepositoryProtocol` 的 job event 方法。
- [x] router 负责拿 actor，service 负责动作语义：资源类 audit 字段由 service 生成；download 因动作本身就是 HTTP 下载，由 router 写 `artifact.download`。
- [x] 覆盖 roadmap 指定动作，不扩展到所有 CRUD：template create / update / replace / delete、legacy term-rules CRUD 仍只保留 admin token 保护，不在本 feature 内写审计。

**编排层“现状 → 变化”逐项核对**：

- [x] 旧 `require_*_access()` 兼容函数仍存在，内部委托 actor dependency。
- [x] 高风险 router 已从纯 `dependencies=[Depends(...)]` 扩展为显式 actor 参数，成功路径将 actor 传给 service。
- [x] file / sqlite / MySQL repository 均新增 audit event 持久化，不影响旧 job / resource 读取。
- [x] `AuditService` 集中生成事件，避免各 router 手写不一致结构。

**流程级约束核对**：

- [x] 权限语义：缺 token 配置仍 503，token 错误仍 403。
- [x] 审计时机：只记录权限通过且业务动作成功的事件；失败路径没有对应成功 audit event。
- [x] 幂等性：重复成功动作会产生多条 audit event，不做去重。
- [x] 隐私：audit event 不记录 token、secret、完整 payload 或本地绝对路径。
- [x] 兼容性：旧数据无 audit event 不影响 job / resource 读取。
- [x] 可观测性：每条 audit event 带 `trace_id`，可与 access log / JobEvent 串联。

**挂载点反向核对（可卸载性）**：

- [x] `app/api/dependencies.py`：新增返回 actor 的 access dependency。
- [x] `app/core/audit_models.py`：新增 actor / audit 值对象。
- [x] `app/services/audit.py`：新增 audit 写入 service。
- [x] `app/repositories/*_job_repository.py` 与 `app/repositories/protocols.py`：新增 audit event 持久化端口和 backend 表 / 文件实现。
- [x] 高风险 routers / services：template、term-rule-set、translation-profile、jobs ops、jobs download 接入 actor 和 audit。
- [x] 反向 grep：`rg -n "require_admin_actor|require_jobs_actor|require_job_ops_actor|ActorContext|AuditEvent|AuditService|append_audit_event|artifact\\.download|job\\.retry|job\\.cancel|job\\.cleanup_local_files|template\\.publish|term_rule_set\\.rollback|translation_profile\\.rollback" app tests/test_fastapi_jobs_backend.py tests/test_database_job_repository.py` 已执行，命中均落在上述挂载点或测试断言内。
- [x] 拔除沙盘推演：移除 `audit_models.py`、`audit.py`、repository audit methods / `audit_events` schema、runtime 注入，以及 router/service 中的 actor 参数和 audit 调用后，系统可回到原 token 校验和无审计状态；历史 audit events 可作为日志保留，旧业务读路径不依赖它们。

## 3. 验收场景核对

- [x] **S1 admin 资源发布审计**
  - 证据：`tests/test_fastapi_jobs_backend.py::FastAPIJobsBackendTests.test_template_profile_versioning_publishes_defaults_and_disables_versions` 断言 `template.publish` / `template.set_default` / `template.disable` audit event，actor_role 为 `admin`，target_id 为 `{template_id}@{version}`。

- [x] **S2 term-rule / translation 回滚审计**
  - 证据：`test_term_rule_set_versioning_draft_publish_default_and_rollback` 断言 `term_rule_set.rollback`，且 publish reason 进入 audit；`test_translation_profile_rollback_writes_audit_event` 断言 `translation_profile.rollback`、target_id 和 admin actor。

- [x] **S3 job ops 审计**
  - 证据：`test_retry_failed_zip_job_requeues_and_completes`、`test_cancel_uploaded_job_marks_canceled_and_clears_pending_stage_messages`、`test_job_ops_default_admin_only_checks_no_token_jobs_token_and_admin_token` 分别覆盖 `job.retry`、`job.cancel`、`job.cleanup_local_files`，reason 与请求一致，原 JobEvent 仍存在。

- [x] **S4 jobs token 模式下 ops 审计**
  - 证据：`test_job_ops_can_follow_jobs_access_mode_when_configured` 覆盖 `JOBS_OPS_ACCESS_MODE=jobs` + `JOBS_ACCESS_MODE=token`，成功 audit actor_role 为 `jobs`，actor_id 为 `jobs-client`。

- [x] **S5 open 下载审计**
  - 证据：`test_upload_zip_runs_background_conversion_and_downloads_docx` 下载 result 成功后断言 `artifact.download`，actor_role 为 `anonymous`，actor_id 为 `None`，target_id 不含本地临时目录；测试同时传入 `X-Actor-Id` 证明 open 模式不接受匿名自报 actor。

- [x] **S6 权限失败不写成功审计**
  - 证据：job ops admin-only 测试先用无 token / jobs token 得到 403，最后只有 admin 成功请求写入一条 `job.cleanup_local_files` audit event；资源端无 token / 错 token 行为由 FastAPI suite 与 OpenAPI 测试覆盖。

- [x] **反向核对**
  - 证据：grep 只发现 audit repository/schema、测试断言和 design/checklist 中的范围说明；未发现新增 SSO、用户表、多租户字段或 audit HTTP router。

## 4. 术语一致性

- `ActorContext`：design、architecture、requirement、代码和测试均指请求级最小操作者上下文，不包含 token 原文。
- `ActorRole`：代码中只有 `admin`、`jobs`、`anonymous` 三类，和 design 一致。
- `AuditEvent`：代码、architecture 和 acceptance 均指独立于 `JobEvent` 的跨资源成功动作审计事件。
- `audit repository`：file/sqlite/MySQL 三种 metadata backend 的 append / list 端口，未新增 HTTP 查询 API。
- `artifact.download`：只记录下载动作目标 `{job_id}:{artifact_alias}`，不记录本地绝对路径。

## 5. 架构归并

方案第 4 节实际写的是“回滚与卸载”而不是“与项目级架构文档的关系”；本次 acceptance 按新增名词、编排骨架和流程约束现场评估并完成归并。

- [x] `.codestable/architecture/ARCHITECTURE.md`
  - 已补入 `ActorContext / AuditEvent` 核心术语。
  - 已更新 FastAPI 外部表面、物理结构、数据与状态、已知边界和变更日志。
  - 已明确 MySQL metadata store 保存 `audit_events`，open 下载 anonymous 且不接受自报 actor，不新增审计查询 API。

- [x] `.codestable/architecture/backend-fastapi-service.md`
  - 已更新 summary、定位、物理结构、repository schema 描述、API 合同、运行时与可观测性、已知边界和变更日志。
  - 已新增 Permission and Audit Baseline 流程图，说明 `require_*_actor()` → `ActorContext` → 成功动作 → `AuditService.record()` → audit repository。

- [x] `.codestable/attention.md`
  - 本 feature 未发现必须补入 attention 的新环境、工具或工作流信息；既有条目已经说明测试必须使用 `/Users/sc/miniconda3/envs/md2word/bin/python`。

## 6. requirement 回写

- [x] `requirement: fastapi-backend-productization` 指向 current req，本次新增维护者和集成方可感知的审计能力，已更新 `.codestable/requirements/fastapi-backend-productization.md`。
- [x] 用户故事已加入“高风险动作有最小操作者上下文和审计流水”。
- [x] “怎么解决”已加入 `require_*_actor()` 与 `AuditEvent` 覆盖范围。
- [x] 边界已更新：只表达 `admin`、`jobs`、`anonymous`；不新增 SSO、用户表、多租户、资源所有者校验、审计查询 HTTP API 或审计 UI。
- [x] 变更日志已追加 2026-05-29 Permission and Audit Baseline 条目。

## 7. roadmap 回写

- [x] 方案 frontmatter 有 `roadmap: backend-productization-implementation` 和 `roadmap_item: permission-and-audit-baseline`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml` 中 `permission-and-audit-baseline` 已从 `in-progress` 更新为 `done`，feature 指向 `2026-05-29-permission-and-audit-baseline`。
- [x] `.codestable/roadmap/backend-productization-implementation/backend-productization-implementation-roadmap.md` 第 5 节子 feature 清单已同步为 `done`。
- [x] roadmap 观察项和变更日志已补入 Permission and Audit Baseline 已落地边界。

## 8. attention.md 候选盘点

- [x] 无候选：本 feature 未暴露需要补入 `.codestable/attention.md` 的新环境、工具或工作流信息。测试环境约束已由既有 attention 条目覆盖。

## 9. 遗留

- 后续 roadmap：`operations-readiness-and-test-baseline` 仍未完成，将继续承接真实 MySQL smoke、migration/runbook、readiness/metrics 和更完整的运维测试基线。
- 已知限制：audit event 当前没有 HTTP 查询 API 或 UI；后续若需要运营查询，应另起 feature。
- 已知限制：权限模型只包含 `admin`、`jobs`、`anonymous`，不做 SSO、多租户、资源所有者校验或细粒度 ACL。
- 已知限制：artifact retention 仍是 dry-run；真实删除、删除审计和恢复策略留给 operations / cleanup feature。
- 结构观察：`MysqlJobRepository` 已同时承担 jobs、stage、resource versions 和 audit events；后续 metadata 域继续扩展时，适合单独走 repository 拆分 refactor。

## 验证记录

- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
  - 结果：通过，68 tests。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository`
  - 结果：通过，10 tests。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
  - 结果：通过，2 tests。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile app/core/audit_models.py app/services/audit.py app/api/dependencies.py app/api/v1/routers/jobs_ops.py app/api/v1/routers/jobs_query.py app/api/v1/routers/templates.py app/api/v1/routers/term_rule_sets.py app/api/v1/routers/translation_profiles.py app/repositories/protocols.py app/repositories/file_job_repository.py app/repositories/database_job_repository.py app/repositories/mysql_job_repository.py app/services/templates/read_service.py app/services/term_rules/versioning_service.py app/services/translation_profiles/versioning_service.py app/services/jobs/lifecycle.py app/core/runtime.py app/main.py`
  - 结果：通过。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-29-permission-and-audit-baseline/permission-and-audit-baseline-checklist.yaml --yaml-only`
  - 结果：通过。
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/backend-productization-implementation/backend-productization-implementation-items.yaml --yaml-only`
  - 结果：通过。
- [x] `rg -n "require_admin_actor|require_jobs_actor|require_job_ops_actor|ActorContext|AuditEvent|AuditService|append_audit_event|artifact\\.download|job\\.retry|job\\.cancel|job\\.cleanup_local_files|template\\.publish|term_rule_set\\.rollback|translation_profile\\.rollback" app tests/test_fastapi_jobs_backend.py tests/test_database_job_repository.py`
  - 结果：命中均落在设计挂载点或测试断言内。
- [x] `rg -n "SSO|tenant|tenant_id|user table|audit.*router|audit.*API|audit-events|audit_events" app .codestable/features/2026-05-29-permission-and-audit-baseline tests/test_fastapi_jobs_backend.py tests/test_database_job_repository.py`
  - 结果：命中为既有 callback `single_tenant_public`、audit repository/schema、测试断言和 design/checklist 范围说明；未发现新增 SSO、用户表、多租户字段或 audit HTTP router。

## 10. 用户确认后的知识库收尾

- [x] learning 已沉淀：`.codestable/compound/2026-05-29-learning-audit-actor-boundary.md`
  - 主题：审计 actor 必须来自认证边界，open 请求不能通过 `X-Actor-Id` 自报身份。
- [x] 长期决定已归档：`.codestable/compound/2026-05-29-decision-token-derived-actor-and-independent-audit-event.md`
  - 主题：token-derived `ActorContext`、独立 `AuditEvent`，本阶段不引入 SSO / 用户表 / 多租户 / audit HTTP API。
- [x] dev guide 已更新：
  - `docs/dev/term-rule-set-versioning-guide.md`
  - `docs/dev/translation-profile-and-segment-trace-guide.md`
  - `docs/dev/backend-local-minimal-env-and-commands.md`
- [x] API reference 已更新：
  - `docs/api/jobs.md`
  - `docs/api/templates.md`
  - `docs/api/term-rule-sets.md`
  - `docs/api/translation-profiles.md`
  - `docs/api/manifest.yaml`
- [x] 收尾校验：
  - `validate-yaml.py` 已校验上述新增/更新的 frontmatter 与 manifest。
  - `rg` 已确认 docs 中无旧的 snapshot / audit / profile 限制口径残留。
  - `git diff --check` 通过。
