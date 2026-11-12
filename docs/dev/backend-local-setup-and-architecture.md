---
doc_type: dev-guide
slug: backend-local-setup-and-architecture
component: backend-setup
status: current
summary: 说明如何启动当前 FastAPI 后端，以及如何理解项目结构和主链路。
tags: [backend, setup, architecture, onboarding]
last_reviewed: 2026-05-31
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  全文用途、原字段与现有入口/命令参数声明的局部静态核对；原历史结果和执行条件保留，未运行命令或重新验收。输入身份及旧说明差异见 ../../.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/b3-preparation.md。
---

## 概述

本页维护正式后端的结构与接手路径，主体为 Files + Document Jobs；目录、入口与配置示例不代表相关服务已在当前环境启用。本批只做用途与局部静态入口对照，实际运行条件见 [后端运行说明](../runbooks/backend.md)。

当前公开链路统一为 Files + Document Jobs：

```text
上传 PDF → 创建 DocumentJob → MinerU 解析/回调 → DocumentIR → 可选翻译 → Renderer → DOCX
```

B05 第 3、4 步已删除旧 Jobs 服务、stage 调度/启动重放、独立 StageWorker 和旧转换运行时。`app/main.py` 装配正式服务，`app/workers/` 提供 Celery 任务，`app/conversion/` 只保留共享转换规则；本地 MinerU 包调试使用 `scripts/dev/formal_mineru_conversion.py`。

## 项目结构

### `app/api/v1/`

- `router.py`
  - 汇总 v1 API 子路由
- `routers/auth.py`、`routers/health.py`
  - API 组合层自有的 auth 和 health 入口
- `schemas.py`
  - auth/health 的 v1 请求和响应模型；业务 domain schema 不放在这里

### `app/domains/`

- `jobs/`
  - 正式 DocumentJob 共用的模型、资源快照、路径、事件端口与 MinerU callback router
- `document_jobs/`
  - document job service、execution queue、router、schema 和 repository ports
- `files/`
  - 文件上传授权、PDF 校验、文件 metadata、retention planning 和 repository port
- `templates/`
  - 模板 manifest、默认模板状态、模板 CRUD、Template Version 管理和 router/schema
- `term_rules/`
  - Term Rule Set 发布流程、legacy term-rule/category API、导入校验、sync-files、YAML codec 和 file repository
- `translation/`
  - Translation Profile 发布流程、翻译 provider、Document IR translator、term version resolver 和 translation audit
- `resources/`
  - ResourceVersionService、资源版本模型和 repository port
- `audit/`
  - ActorContext、AuditEvent、AuditService 和 audit repository port

### `app/infrastructure/persistence/`

- `file/`
  - 本地开发默认 metadata backend，保存正式 document_jobs、document_files、回调、翻译批次及事件记录
- `sqlite/`
  - sqlite metadata backend，面向准生产或需要更清晰 metadata snapshot 的单实例部署
- `mysql/`
  - MySQL metadata backend，面向单实例生产化部署；只保存业务 metadata，不保存 artifact 二进制
- `factory.py`
  - 组装 `PersistenceAdapters`，供 `app/main.py` 注入 runtime

### `app/workers/`

正式 Document Jobs 的 Celery 任务与 worker 接线；启动入口为 `scripts/dev/run_document_worker.py`。API 启动恢复由 `DocumentJobRecoveryService` 负责。

### `app/conversion/`

保留 `docx_rules/` 与 `table_html_parser.py` 等正式共享规则闭包。实际转换由 `app/services/document_ir/` 与 `app/services/renderer/` 负责，不再提供旧 conversion entrypoint/facade/runner。

### `app/core/`

- `config.py`
  - `.env` 和路径配置
- `logging.py`
  - access / business / system 三类日志配置
- `auth_models.py`、`document_ir_models.py`、`template_config_models.py`
  - 跨 domain 或 conversion/rendering 边界共享的基础记录

### `var/`

当前主要运行态目录（具体文件由所选 adapter 管理）：

```text
var/
  metadata.sqlite3
  config/
  document_jobs/
  document_files/
  document_job_callback_messages/
  document_job_translation_batches/
  document_file_objects/
  jobs/{job_id}/resources/
  tmp/
```

共享 `jobs/<id>/resources/` 仍用于正式资源快照；保留事件仓储也可读写历史 `jobs/<id>/events.jsonl`。旧 stage spool 不再装配或消费。

## 当前主链路

1. `POST /api/v1/files/upload-url` 创建上传授权，`PUT /api/v1/files/{file_id}/content` 上传文件。
2. `POST /api/v1/document-jobs` 创建正式任务并经配置的正式队列执行。
3. `DocumentJobExecutionService` 提交 MinerU、恢复结果包并转换 DocumentIR。
4. 根据模式执行正式翻译或直接渲染，登记文件与质量证据。
5. 通过 Document Jobs 详情、事件、文件和 `download-url` 读取结果。

### MinerU callback

`POST /api/v1/mineru-callbacks/result` 继续挂载。`app/api/mineru_callback_guards.py` 验证身份、payload、结果 URL 和 checksum；router 调用正式 execution 查找任务、持久化回调并按需唤醒正式队列。后续恢复由正式任务执行器和恢复服务完成。

## 当前边界

- 正式 DocumentIR + document_jobs + renderer 为唯一转换实现。
- jobs metadata backend 有三种：
  - `file` 是代码默认值，用于本地开发和最小联调。
  - `database` 使用 SQLite 文件；生产要求以现有正式 readiness 合同为准，旧 shadow copy 工具已删除。
  - `mysql` 使用 MySQL 保存正式 document_jobs、document_files、job_events、回调、批次及资源版本；需要显式配置连接参数。
- 当前没有 PostgreSQL，也没有 Alembic 迁移系统；MySQL schema 由 adapter 启动时做最小 bootstrap。
- 正式 Worker 由 `DOCUMENT_JOBS_WORKER_BACKEND` 配置；生产使用 Celery。`jobs_worker_mode` 仅保留既有健康配置回显，不再控制旧 stage 消费。
- artifact 二进制存储与 metadata backend 分开配置；sqlite/MySQL 都只保存 metadata，不搬运本地文件本身。artifact storage 可用 `local_file`、`local_object` 或 `s3`。
- 模板 CRUD、term-rule rule CRUD 和 category CRUD 已提供 admin 写接口。
- term-rules 采用三层结构：
  - `resources/term_rules/term_rules.v2.yaml` 作为版本化 seed
  - `var/config/term_rules_store.json` 作为 live runtime truth
  - `var/config/runtime_subscripts_dictionary.yaml` 作为 conversion 消费的兼容 YAML
- templates 采用两层结构：
  - `resources/template_configs/templates_manifest.yaml` 作为版本化模板清单
  - `var/config/templates/` 作为 API 管理上传模板的版本目录
  - `var/config/template_state.json` 作为运行态默认模板状态
- 正式任务的模板选择与默认版本由 DocumentJob 资源快照合同决定。
- 任务操作使用正式 Document Jobs API 与现有权限合同；旧 Jobs 运维端点已删除。
- `jobs`、`job_files`、`stage_messages` 三张既有旧空表留待 B08 治理，本次不 DROP、不迁移旧任务；`job_events` 仍用于正式事件读写并保留建表。
