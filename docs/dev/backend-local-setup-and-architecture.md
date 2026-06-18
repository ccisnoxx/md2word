---
doc_type: dev-guide
slug: backend-local-setup-and-architecture
component: backend-setup
status: current
summary: 说明如何启动当前 FastAPI 后端，以及如何理解项目结构和主链路。
tags: [backend, setup, architecture, onboarding]
last_reviewed: 2026-05-31
---

## 概述

当前 `md2word` 已经收口为 FastAPI 后端项目。它现在有一条可运行的后端主链路：

```text
上传 MinerU 输出 zip -> stage message -> 同进程或独立 worker 推进 convert_package -> 生成 result.docx -> 下载
```

并且已经有一条在线解析前半程：

```text
上传原始 PDF -> stage message -> 同进程或独立 worker 推进 submit_to_mineru -> 等待 callback -> 自动恢复结果 zip -> 后处理 conversion -> completed/failed
```

一句话理解：

- `app/main.py` 是 FastAPI 后端组合根
- `app/` 是 FastAPI 后端壳层
- `app/conversion/` 是 conversion library，真正的 `run_conversion()` 总调度在这里
- `app/domains/` 承担业务 domain 的模型、schema、router、service 和 repository port
- `app/infrastructure/persistence/` 承担 file/sqlite/mysql metadata adapters
- `app/workers/` 承担独立 worker 进程轮询和 stage message 消费
- `var/` 是运行态目录，不是版本化资产

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
  - jobs 聚合 router、ingest/query/ops 子 router、任务编排、stage 推进、产物合同、本地运维动作和 repository ports
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
  - 本地开发默认 metadata backend，使用 `var/jobs/*/*.json`、`events.jsonl` 和 `var/stage_messages/*.json`
- `sqlite/`
  - sqlite metadata backend，面向准生产或需要更清晰 metadata snapshot 的单实例部署
- `mysql/`
  - MySQL metadata backend，面向单实例生产化部署；只保存业务 metadata，不保存 artifact 二进制
- `factory.py`
  - 组装 `PersistenceAdapters`，供 `app/main.py` 注入 runtime

### `app/workers/`

- `stage_worker.py`
  - 独立 worker 进程的轮询循环；`scripts/dev/run_stage_worker.py` 是 PyCharm / 本地直跑入口

### `app/conversion/`

- `contracts.py`
  - conversion 输入输出合同
- `entrypoint.py`
  - job -> conversion request 的组装入口
- `service.py`
  - FastAPI conversion 服务层，调用 `runtime_facade.py`
- `runtime_facade.py`
  - FastAPI 侧稳定导入面，避免后端直接 import root script
- `runtime_runner.py`
  - 共享转换总调度
- `runtime_helpers.py`
  - 路径解析、语言判定、render config 组装
- `runtime_rendering_api.py`
  - shared Document / HTML table wrapper
- `runtime_models.py`
  - shared dataclass

### `app/core/`

- `config.py`
  - `.env` 和路径配置
- `logging.py`
  - access / business / system 三类日志配置
- `auth_models.py`、`document_ir_models.py`、`template_config_models.py`
  - 跨 domain 或 conversion/rendering 边界共享的基础记录

### `var/`

当前运行态结构：

```text
var/
  metadata.sqlite3        # 仅 JOBS_REPOSITORY_BACKEND=database 时使用
  config/
    term_rules_store.json
    runtime_subscripts_dictionary.yaml
    template_state.json
  jobs/{job_id}/
    job.json
    files.json
    events.jsonl
    input/source.zip
    output/result.docx
    work/
    translation/request.json
  stage_messages/
  tmp/
```

## 当前主链路

当前公开 P0 主链路是 Files + Document Jobs。下面的 `/api/v1/jobs` 流程是 legacy 历史链路，只用于理解旧模块和历史测试；新联调不要使用。

1. `POST /api/v1/jobs` 接收 MinerU 输出 zip
2. `JobCommandService` 创建 job、登记 `source_package`
3. `JobStageService.enqueue_conversion()` 写入 stage spool
4. `JOBS_WORKER_MODE=in_process` 时 FastAPI `BackgroundTasks` 调用 `dispatch_message()`；`external` 时由 `scripts/dev/run_stage_worker.py` 轮询消费
5. `ConversionEntrypoint` 组装 `ConversionRequest`
6. `ConversionService` 调 `runtime_facade.run_conversion()`，再进入 `runtime_runner.run_conversion()`
7. `JobArtifactService` 登记 `result_docx` 和可选 `translation_request`
8. `GET /api/v1/jobs/{job_id}/result` / `download/result` 提供下载

### 原始 PDF 在线解析前半程

当前新流程应使用 `POST /api/v1/files/upload-url`、`PUT /api/v1/files/{file_id}/content`、`POST /api/v1/document-jobs`。以下 `/api/v1/jobs/pdf` 只描述 legacy 历史链路。

1. `POST /api/v1/jobs/pdf` 接收原始 PDF
2. `JobCommandService` 创建 job、登记 `source_pdf`
3. `JobStageService.enqueue_mineru_submission()` 写入 stage spool
4. `in_process` 时 FastAPI `BackgroundTasks` 调用 `submit_to_mineru`；`external` 时由 `scripts/dev/run_stage_worker.py` 轮询消费
5. `MinerUClient.upload_files_batch()` 成功后持久化 `mineru_batch_id/data_id`
6. 任务进入 `parsing`

### callback ingress

1. `POST /api/v1/mineru-callbacks/result` 接收 callback
2. `api/dependencies.py` 负责 internal/public 模式鉴权、payload 归一化、checksum 和 `full_zip_url` 校验
3. `JobCommandService.enqueue_callback()` 匹配任务并写入 `process_callback`
4. `in_process` 时 FastAPI `BackgroundTasks` 调用 `process_callback`；`external` 时由 `scripts/dev/run_stage_worker.py` 轮询消费
5. `done + full_zip_url` 时任务先命中 `parsed` 里程碑，再自动恢复结果 zip 并继续后处理 conversion
6. `failed` 时任务进入 `failed`

## 当前边界

- 支持“上传原始 PDF -> 成功提交 MinerU -> 接收 callback -> 恢复结果 zip -> 后处理 conversion -> completed/failed”。
- jobs metadata backend 有三种：
  - `file` 是代码默认值，用于本地开发和最小联调。
  - `database` 使用 sqlite 文件，推荐作为准生产 metadata store；启用前应先做 local file integrity check 和 metadata shadow copy。
  - `mysql` 使用 MySQL 保存 jobs、files、events、stage messages 和 resource_versions 基础表；需要显式配置连接参数。
- 当前没有 PostgreSQL，也没有 Alembic 迁移系统；MySQL schema 由 adapter 启动时做最小 bootstrap。
- worker 默认仍是 `JOBS_WORKER_MODE=in_process`；切到 `external` 后 API 只入队，必须另起 `scripts/dev/run_stage_worker.py`。
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
- jobs 现在允许显式 `template_id` 选择可见模板；未传时回退到当前运行态默认模板。
- `retry/cancel/recover-mineru-result/cleanup-local-files` 已实现，默认按 admin 访问口径要求 `X-Admin-Token`。
