---
doc_type: dev-guide
slug: backend-design-implementation-plan
component: backend-implementation-plan
status: draft
summary: 基于当前 FastAPI 后端现状，把后端设计草案拆成可逐步执行的阶段计划。
tags: [backend, implementation-plan, architecture, jobs]
last_reviewed: 2026-05-28
---

# 后端设计实现计划

## 设计前提

本计划基于当前 `app/` FastAPI 后端继续演进，不推倒重来。

已确认的前提：

- 旧根入口正式移除，不再维护本地脚本入口。
- `app/main.py` 是后端组合根。
- `app/conversion/` 是唯一转换入口。
- `jobs` 是主流程域，`templates`、`term_rules`、`health` 是支撑域。
- 当前默认运行形态是单体、单实例、`BackgroundTasks + stage message store + in-process dispatcher`。

优先级定义：

| 优先级 | 含义 |
|---|---|
| 必须 | 继续开发前应先完成，或生产化前必须补齐 |
| 应做 | 不阻塞当前小步开发，但会降低后续风险 |
| 后续优化 | 等主链路稳定后再做，避免过早复杂化 |

任务类型定义：

| 类型 | 含义 |
|---|---|
| 架构整理 | 调整边界、文档、目录和职责，不引入新业务能力 |
| 功能开发 | 改变或新增可见后端能力 |
| 测试补齐 | 补单元测试、API 测试、回归测试或迁移验证 |
| 部署支持 | 运行配置、健康检查、迁移、运维脚本和生产准备 |

## 阶段 0：入口收口与文档基线

目标：把项目正式收口为 FastAPI 后端，清除旧根入口仍是主入口的假设。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 必须 | 架构整理 | 删除或改写 docs / architecture 中所有旧本地入口表述 | `docs/dev/*.md`, `.codestable/architecture/*.md` | 文档只把 `app/main.py` 和 `app/conversion/` 作为后端 / 转换入口 | 搜索 docs 和 architecture，确认旧入口名和旧 IDE 入口名不再出现 |
| [x] | 必须 | 架构整理 | 清理仍从旧根入口加载 runtime 的测试或说明 | `tests/test_render_table_from_html_characterization.py`, `tests/test_input_adapter_characterization.py` | 测试直接依赖 `app/conversion/runtime*` 或移除旧入口专属断言 | 搜索 tests 和 app，确认旧入口名不再出现 |
| [x] | 必须 | 测试补齐 | 跑现有后端主测试，确认入口收口不影响 FastAPI | `tests/test_fastapi_jobs_backend.py`, `tests/test_job_workflow_policy.py`, `tests/test_job_artifact_contract.py`, `tests/test_database_job_repository.py` | 后端主链路测试仍通过 | `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend tests.test_job_workflow_policy tests.test_job_artifact_contract tests.test_database_job_repository` |
| [x] | 应做 | 架构整理 | 更新后端文档索引，让新计划成为后续实施入口 | `docs/dev/backend-dev-docs-index.md` | 新人能从索引找到本计划 | 人工检查索引链接 |

## 阶段 1：API 错误与权限边界收口

目标：先把 API 外壳变稳，减少后续 feature 在 router 中重复写错误处理和权限判断。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 必须 | 架构整理 | 新增统一异常映射模块 | `app/api/errors.py`, `app/main.py` | `JobWorkflowViolation`、`ConversionFailure`、artifact 下载错误有统一 HTTP 映射入口 | 新增异常映射单元测试 |
| [x] | 必须 | 架构整理 | 将 router 内重复的 `try/except` 迁到统一异常层或保留最小边界转换 | `app/api/v1/routers/*.py` | router 更薄，错误响应格式更一致 | `rg "except .* as exc" app/api/v1/routers app/api` |
| [x] | 必须 | 功能开发 | 收紧 job ops 权限策略 | `app/api/dependencies.py`, `app/api/v1/routers/jobs_ops.py`, `app/core/config.py` | `retry/cancel/cleanup-local-files` 可配置为 admin-only，不再默认和普通 jobs 查询同级 | API 测试覆盖无 token、jobs token、admin token 三种情况 |
| [x] | 必须 | 测试补齐 | 固定错误响应和权限行为 | `tests/test_fastapi_jobs_backend.py` | 关键 400/403/409/503 响应稳定 | `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend` |
| [x] | 应做 | 部署支持 | 更新最小 `.env` 文档，明确生产不应使用 `JOBS_ACCESS_MODE=open` | `docs/dev/backend-local-minimal-env-and-commands.md`, `docs/runbook.md` | 本地和生产权限差异被写清 | 人工检查文档 |

## 阶段 2：Jobs workflow 与 stage driver 压薄

目标：保持现有行为不变，把状态规则、stage 执行和外部 provider 调用的边界继续拆清。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 必须 | 架构整理 | 盘点 `JobStageService` 当前职责，标出可拆 helper | `app/services/jobs/stage.py` | 明确哪些逻辑属于 workflow rule、stage executor、provider handler | 形成代码注释或小文档，不改行为 |
| [x] | 必须 | 架构整理 | 将 stage message 状态更新封装成更窄 helper | `app/services/jobs/stage.py` | running/failed/delete 的写法更集中 | `tests.test_fastapi_jobs_backend` 通过 |
| [x] | 必须 | 架构整理 | 将 MinerU submit / result download 调用拆成私有 provider handler | `app/services/jobs/stage.py`, `app/clients/mineru_client.py` | `dispatch_message()` 只做分派，不直接堆 provider 细节 | PDF submit 和 callback 自动完成测试通过 |
| [x] | 应做 | 架构整理 | 将 conversion stage 调用拆成私有 conversion handler | `app/services/jobs/stage.py`, `app/conversion/entrypoint.py` | conversion 成功/失败路径更容易单测 | zip 上传、en2zh、失败 retry 测试通过 |
| [x] | 必须 | 测试补齐 | 给 `job_workflow.py` 补齐新增或已遗漏的状态迁移测试 | `tests/test_job_workflow_policy.py` | workflow rule 变更不依赖 API 测试兜底 | `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_job_workflow_policy` |

## 阶段 3：Repository 与 metadata 默认策略

目标：让 metadata 存储从“file 默认 + sqlite 可选”演进到清晰可迁移的策略，但不立即引入重型数据库。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 必须 | 架构整理 | 明确 file backend 和 sqlite backend 的定位 | `docs/dev/backend-design-implementation-plan.md`, `docs/dev/backend-local-setup-and-architecture.md` | file 用于本地开发，sqlite 作为准生产 metadata store | 人工检查文档 |
| [x] | 应做 | 功能开发 | 明确保留 file 为本地代码默认，sqlite 作为准生产推荐显式配置 | `app/core/config.py`, `docs/dev/backend-local-minimal-env-and-commands.md` | 默认策略明确，不再靠口头约定 | readiness 测试覆盖默认值 |
| [x] | 必须 | 部署支持 | 补 metadata shadow copy / integrity check 的使用说明 | `scripts/ops/*`, `docs/runbook.md` | 从 file 迁到 sqlite 有可执行步骤 | 运行已有 metadata shadow copy 测试 |
| [x] | 必须 | 测试补齐 | 保持 file/sqlite repository 合同一致性测试 | `tests/test_database_job_repository.py` | 两种 backend 对 jobs/files/events/stage messages 行为一致 | `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository` |
| [ ] | 后续优化 | 部署支持 | 若引入 PostgreSQL，再增加 Alembic | `alembic/`, `app/repositories/` | 有版本化 schema migration | Alembic upgrade/downgrade smoke |

## 阶段 4：Artifact storage 与文件生命周期

目标：把 artifact 从“本地文件路径集合”收口为稳定结果合同，为对象存储和清理策略做准备。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 必须 | 架构整理 | 固定 artifact alias / file_type / media_type 合同 | `app/services/jobs/artifacts.py`, `tests/test_job_artifact_contract.py` | `source-package`、`source-pdf`、`parsed-result-package`、`translation-request`、`result` 稳定 | `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_job_artifact_contract` |
| [x] | 必须 | 功能开发 | 明确 `cleanup-local-files` 只清理 work dir，不删除唯一登记 artifact | `app/services/jobs/lifecycle.py` | 清理动作不会造成结果丢失 | 对 cleanup 增加回归测试 |
| [x] | 应做 | 部署支持 | 补 local object adapter 运维说明 | `app/services/jobs/object_artifact_storage.py`, `docs/runbook.md` | `local_object` 模式如何启用和排障写清楚 | object storage switch 测试通过 |
| [x] | 后续优化 | 功能开发 | 接入真正 S3-compatible adapter | `app/services/jobs/artifact_storage.py`, `app/services/jobs/object_artifact_storage.py` | `resolve_download()` 可返回 redirect 或 stream | stream/redirect API 测试通过 |
| [x] | 后续优化 | 部署支持 | 设计 artifact retention 策略 | `docs/runbook.md`, `app/services/jobs/artifact_retention.py` | 可按 job 状态和保存期清理对象 | retention dry-run 测试 |

## 阶段 5：Stage message 可恢复性与 worker readiness

目标：不马上拆独立 worker，但先让 stage message 合同足够清晰，避免未来多实例改造推倒重写。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 必须 | 架构整理 | 定义 stage message 状态语义 | `app/core/job_models.py`, `app/repositories/protocols.py`, `docs/dev/runtime-observability-and-health.md` | `pending/running/failed`、replay 规则、失败保留规则写清 | health readiness 测试覆盖 counts |
| [x] | 必须 | 功能开发 | 增加 stage message 幂等保护 | `app/services/jobs/stage.py`, `app/core/job_workflow.py` | 重复 dispatch 不应重复登记关键 artifact 或错误推进状态 | replay / duplicate callback 测试 |
| [x] | 应做 | 功能开发 | 增加 claim/lease 字段的设计或最小实现 | `app/core/job_models.py`, `app/repositories/*` | 为独立 worker 留出非破坏性扩展点 | repository contract 测试 |
| [x] | 应做 | 部署支持 | `health/ready` 暴露 running 过久或 failed stage message 观察项 | `app/services/health_service.py`, `app/schemas/api_v1.py` | 运维能发现卡住任务 | health API 测试 |
| [x] | 后续优化 | 功能开发 | 拆出独立 worker 进程 | `app/workers/`, `run_worker.py` | FastAPI 可配置为只接请求，worker 消费 stage message | external worker API + worker smoke |

## 阶段 6：API schema 与文档分层

目标：保持 API v1 合同稳定，同时让 schema 和文档随着功能增长不继续堆大文件。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 应做 | 架构整理 | 按资源拆分 API schema | `app/schemas/api_v1.py`, future `app/schemas/jobs.py`, `app/schemas/templates.py`, `app/schemas/term_rules.py` | schema 文件不再无限增长，公开模型仍兼容 | FastAPI tests 全量通过 |
| [x] | 必须 | 测试补齐 | 固定 API v1 响应合同快照 | `tests/test_fastapi_jobs_backend.py` | 关键字段删除或改名会被测试发现 | API 测试通过 |
| [x] | 应做 | 架构整理 | 更新 `docs/api/manifest.yaml` 中的新文档和状态 | `docs/api/manifest.yaml` | API 文档索引准确 | 人工检查 manifest |
| [x] | 后续优化 | 部署支持 | 导出 OpenAPI 并纳入发布检查 | future script under `scripts/ops/` | 发布前可比对 API 变更 | OpenAPI diff |

## 阶段 7：配置、日志与运行支持

目标：让本地、测试、准生产的运行方式可重复，不靠口头记忆。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 必须 | 部署支持 | 整理最小 `.env` 模板说明 | `docs/dev/backend-local-minimal-env-and-commands.md` | 新环境能按文档启动并知道哪些能力不可用 | 按文档启动一次 |
| [x] | 必须 | 部署支持 | 明确 readiness 必检项和非阻塞项 | `app/services/health_service.py`, `docs/dev/runtime-observability-and-health.md` | `translation_available`、MinerU token、stage spool 状态语义清楚 | health tests 通过 |
| [x] | 应做 | 部署支持 | 统一日志字段约定 | `app/core/logging.py`, `app/main.py`, `app/services/jobs/stage.py` | access/business/system 日志都包含足够定位信息 | 人工检查日志样例 |
| [x] | 后续优化 | 部署支持 | 增加 JSON structured logging 开关 | `app/core/logging.py`, `app/core/config.py` | 容器或云环境可直接采集结构化日志 | 日志格式 smoke |

## 阶段 8：后续功能扩展

目标：在主链路稳定后再扩展配置管理能力，不提前扩大核心复杂度。

| Done | 优先级 | 类型 | 步骤 | 涉及文件 | 预期结果 | 验证方式 |
|---|---|---|---|---|---|---|
| [x] | 后续优化 | 功能开发 | 模板文件 CRUD / replace / version 管理 | `app/api/v1/routers/templates.py`, `app/services/templates/` | 前端可管理模板版本 | API tests + 文件完整性测试 |
| [x] | 后续优化 | 功能开发 | term-rule rule 级 CRUD | `app/api/v1/routers/term_rules.py`, `app/services/term_rules/` | 不再只能整库导入替换 | API tests |
| [x] | 后续优化 | 功能开发 | term-rule category 写接口 | `app/api/v1/routers/term_rule_categories.py`, `app/services/term_rules/` | 分类可在线管理 | API tests |
| [x] | 后续优化 | 功能开发 | callback 丢失后的主动查询恢复 | `app/clients/mineru_client.py`, `app/services/jobs/stage.py` | PDF 在线任务不完全依赖 callback | fake MinerU client 测试 |

## 推荐执行顺序

1. 阶段 0：入口收口与文档基线。
2. 阶段 1：API 错误与权限边界收口。
3. 阶段 2：Jobs workflow 与 stage driver 压薄。
4. 阶段 3：Repository 与 metadata 默认策略。
5. 阶段 4：Artifact storage 与文件生命周期。
6. 阶段 5：Stage message 可恢复性与 worker readiness。
7. 阶段 6：API schema 与文档分层。
8. 阶段 7：配置、日志与运行支持。
9. 阶段 8：后续功能扩展。

## 每阶段完成定义

| 阶段 | 完成定义 |
|---|---|
| 阶段 0 | docs、architecture、tests、app 不再出现旧根入口作为主入口的假设 |
| 阶段 1 | API 错误格式和 ops 权限有测试固定 |
| 阶段 2 | `JobStageService` 仍可运行，但状态规则不再继续扩散 |
| 阶段 3 | file/sqlite metadata 策略、迁移路径和测试都清楚 |
| 阶段 4 | artifact 合同稳定，清理动作不造成数据丢失 |
| 阶段 5 | stage message replay、failed、running 的语义明确且可观测 |
| 阶段 6 | API schema 和文档增长路径明确 |
| 阶段 7 | 新环境能按文档启动、检查 readiness、定位日志 |
| 阶段 8 | 只在主链路稳定后启动 |
