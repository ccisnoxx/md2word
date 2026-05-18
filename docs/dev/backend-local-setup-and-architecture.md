---
doc_type: dev-guide
slug: backend-local-setup-and-architecture
component: backend-setup
status: current
summary: 说明如何启动当前 FastAPI 后端，以及如何理解项目结构和主链路。
tags: [backend, setup, architecture, onboarding]
last_reviewed: 2026-05-18
---

## 概述

当前 `md2word_file` 已经不是单纯的 CLI 仓库了。它现在有一条可运行的后端主链路：

```text
上传 MinerU 输出 zip -> BackgroundTasks 推进 convert_package -> 生成 result.docx -> 下载
```

并且已经有一条在线解析前半程：

```text
上传原始 PDF -> BackgroundTasks 推进 submit_to_mineru -> 等待 callback -> 任务进入 parsed/failed
```

一句话理解：

- `mineru_to_docx.py` 仍然是转换核心入口
- `app/` 是 FastAPI 后端壳层
- `app/conversion/` 把现有转换能力包成服务内 conversion library
- `app/services/jobs/` 承担任务编排、产物合同和本地运维动作
- `data/` 是运行态目录，不是版本化资产

## 项目结构

### `app/api/v1/`

- `routers/health.py`
  - `health/live` 和 `health/ready`
- `routers/jobs.py`
  - MinerU zip 上传、原始 PDF 上传、列表、详情、事件、结果下载、retry、cancel、cleanup-local-files
- `routers/mineru_callbacks.py`
  - MinerU callback ingress、payload 归一化、鉴权和 stage 入队
- `routers/templates.py`
  - 默认模板和绑定 YAML 配置的只读接口

### `app/services/jobs/`

- `command.py`
  - 创建任务并落盘
- `stage.py`
  - 后台 stage 入队、dispatch、replay；当前包含 `convert_package`、`submit_to_mineru` 和 `process_callback`
- `query.py`
  - jobs 读模型
- `artifacts.py`
  - 产物 alias、下载 URL、逻辑路径、media type 合同
- `lifecycle.py`
  - retry、cancel、cleanup-local-files

### `app/services/templates/`

- `read_service.py`
  - 默认模板、layout YAML、subscript YAML 的只读元数据与下载入口

### `app/conversion/`

- `contracts.py`
  - conversion 输入输出合同
- `entrypoint.py`
  - job -> conversion request 的组装入口
- `service.py`
  - 真正调用 `run_conversion()` 的服务层入口

### `app/core/`

- `config.py`
  - `.env` 和路径配置
- `job_models.py`
  - job / file / event / stage message 模型
- `job_paths.py`
  - 运行态目录结构和逻辑路径推导
- `logging.py`
  - access / business / system 三类日志配置

### `data/`

当前运行态结构：

```text
data/
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

1. `POST /api/v1/jobs` 接收 MinerU 输出 zip
2. `JobCommandService` 创建 job、登记 `source_package`
3. `JobStageService.enqueue_conversion()` 写入 stage spool
4. FastAPI `BackgroundTasks` 调用 `dispatch_message()`
5. `ConversionEntrypoint` 组装 `ConversionRequest`
6. `ConversionService` 调现有 `run_conversion()`
7. `JobArtifactService` 登记 `result_docx` 和可选 `translation_request`
8. `GET /api/v1/jobs/{job_id}/result` / `download/result` 提供下载

### 原始 PDF 在线解析前半程

1. `POST /api/v1/jobs/pdf` 接收原始 PDF
2. `JobCommandService` 创建 job、登记 `source_pdf`
3. `JobStageService.enqueue_mineru_submission()` 写入 stage spool
4. FastAPI `BackgroundTasks` 调用 `submit_to_mineru`
5. `MinerUClient.upload_files_batch()` 成功后持久化 `mineru_batch_id/data_id`
6. 任务进入 `parsing`

### callback ingress

1. `POST /api/v1/mineru-callbacks/result` 接收 callback
2. `api/dependencies.py` 负责 internal/public 模式鉴权、payload 归一化、checksum 和 `full_zip_url` 校验
3. `JobCommandService.enqueue_callback()` 匹配任务并写入 `process_callback`
4. FastAPI `BackgroundTasks` 调用 `process_callback`
5. `done + full_zip_url` 时任务进入 `parsed`
6. `failed` 时任务进入 `failed`

## 当前边界

- 支持“上传原始 PDF -> 成功提交 MinerU -> 接收 callback -> 任务进入 parsed/failed”，但还不支持下载结果 zip、恢复结果和 DOCX 后处理回流。
- 只支持 file backend，还没有 SQLite/MySQL。
- 当前没有模板 CRUD 和术语规则 CRUD；模板和 YAML 文件仍是版本化资产。
- `retry/cancel/cleanup-local-files` 已实现，但按普通 jobs 访问口径开放，不要求 `X-Admin-Token`。
