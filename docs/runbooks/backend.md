---
doc_type: dev-guide
slug: runbook
component: backend-runbook
status: current
summary: 当前后端本地开发、线上优先验证、运维动作和真实样例验证的运行说明。
tags: [backend, runbook, jobs, deploy, hostdzire]
last_reviewed: 2026-06-17
---

# 后端运行与线上验证说明

## 0. 线上优先验证边界

当前 P0 验收以 [线上优先验证流程](/Users/sc/PycharmProjects/md2word/docs/deploy/online-first-validation-workflow.md) 为准：本地只做代码/文档改写和不依赖真实服务的检查，完整 API、Worker、MySQL、Redis/Celery、MinerU 和 Golden Sample 证据在 `hostdzire` 收集。

不要为了当前 P0 验收在本机启动前后端、MySQL、Redis/Celery、Worker 或前端 smoke。以下本地命令仅保留给专项开发调试使用，不构成本轮发布证据。

## 0.1 访问控制口径

当前 P0 主流程是 Files + Document Jobs，调用方先登录 `/api/v1/auth/login` 获取 Bearer JWT，再按 `operator` / `admin` 角色访问接口。普通 operator 可以上传、创建、查看、下载、取消、重试、归档自己的任务；任务级删除只允许 admin。

本地 legacy jobs 排查仍可以使用旧访问模式：

```env
JOBS_ACCESS_MODE=open
JOBS_OPS_ACCESS_MODE=admin
ADMIN_TOKEN=local-admin-token
```

`JOBS_ACCESS_MODE=open` 只适合本地开发。生产或任何可被外部访问的环境不要使用 `open`，应改为：

- `JOBS_ACCESS_MODE=token`，并配置 `JOBS_ACCESS_TOKEN`
- 或 `JOBS_ACCESS_MODE=admin`，并配置 `ADMIN_TOKEN`

这些 `JOBS_*` 配置只用于 legacy jobs 入口和历史排查口径；新联调不要用它们替代 Bearer JWT。部分旧配置写接口仍兼容 legacy `X-Admin-Token`，但 P0 Document Jobs 工作台和 admin delete 以 Bearer admin JWT 为准。

## 0.2 环境配置样例

仓库根目录提供 `.env.example`，覆盖单实例生产化需要的主要配置：

- `JOBS_REPOSITORY_BACKEND=mysql` 与 `JOBS_MYSQL_*`
- `JOBS_ARTIFACT_STORAGE_BACKEND=local_file`，artifact 二进制仍保存在 artifact storage，不写入 MySQL
- `DOCUMENT_JOBS_WORKER_BACKEND=celery` 与 `DOCUMENT_JOBS_CELERY_*`
- legacy `JOBS_WORKER_MODE=in_process` / `external`
- `JOBS_ACCESS_MODE`、`JOBS_ACCESS_TOKEN`、`JOBS_OPS_ACCESS_MODE`、`ADMIN_TOKEN`
- `MINERU_CALLBACK_URL`、`MINERU_UID` 和 `MINERU_RESULT_HOST_ALLOWLIST`
- `LOG_FORMAT=json`
- `APP_VERSION` 和 `DEPLOYMENT_ID`，用于 P2 线上门禁和 health evidence 区分发布批次

`MINERU_CALLBACK_URL` 直接按官方 callback 地址填写；callback 验签依赖 `uid + seed + content`，不要再给 URL 追加自定义 token 或 query 参数。

不要把真实 token 或 password 提交到仓库；复制样例后在本地 `.env` 或部署环境里填真实值。

## 1. 本地服务启动（仅开发）

当前机器不作为 P0 full-stack 验证环境；只有在专项开发排查时才使用本节命令。

```bash
.venv/bin/python scripts/dev/run_api.py
```

默认监听：

```text
http://127.0.0.1:8000
```

## 2. 本地健康检查（仅开发）

```bash
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
curl http://127.0.0.1:8000/api/v1/health/metrics
```

`ready` 里当前 worker/storage 口径应为：

- `worker_mode=in_process`（默认）或 `external`
- `stage_dispatcher=background_tasks`（默认）或 `external_worker`
- `configured_repository_backend=file`（默认；切换后可为 `database` 或 `mysql`）
- `effective_repository_backend=file`（默认；切换后可为 `database` 或 `mysql`）
- `stage_message_store=file`（默认；切换后可为 `database` 或 `mysql`）
- `artifact_storage=local_file`（默认；切换后可为 `local_object` 或 `s3`）

`stage_spool_pending_messages` 和 `stage_spool_running_messages` 表示启动时会尝试 replay 的后台消息；`stage_spool_failed_messages` 只作为诊断信号，不会自动恢复。

`ready` 还会报告：

- `artifact_root_writable`
- `artifact_disk_free_bytes`
- `default_template_version`
- `default_term_rule_version`
- `default_translation_profile_version`
- `mysql_schema_bootstrap_available`

`metrics` 是 JSON 运维计数，不是 Prometheus 格式；当前包括 jobs 状态计数、stage message 状态计数、资源版本计数和 audit event 总数。

`ready` 和 `metrics` 都包含非敏感 `deployment` 对象：

- `environment`：当前 `APP_ENV`
- `public_deployment_mode`：当前 `PUBLIC_DEPLOYMENT_MODE`
- `version`：当前 `APP_VERSION`
- `deployment_id`：当前 `DEPLOYMENT_ID`，未设置时为 `null`
- `started_at`：API 进程启动时间

P2 内部单租户发布时，推荐在 hostdzire `.env` 中显式设置 `APP_VERSION` 和 `DEPLOYMENT_ID`，并用 `scripts/ops/run_p2_online_gate.py` 生成线上证据报告。

## 2.0 Document Jobs worker 模式

P0 准生产/生产基线使用 MySQL metadata + Celery/Redis + 单 worker：

```env
JOBS_REPOSITORY_BACKEND=mysql
DOCUMENT_JOBS_WORKER_BACKEND=celery
DOCUMENT_JOBS_CELERY_BROKER_URL=redis://redis:6379/0
DOCUMENT_JOBS_CELERY_QUEUE=document-jobs
DOCUMENT_JOBS_TRANSLATION_BATCH_CELERY_QUEUE=document-translation-batches
```

启动 API 后另起 Document Jobs worker：

```bash
.venv/bin/python scripts/dev/run_document_worker.py
```

预期：

- `/health/ready` 返回 `effective_repository_backend=mysql`
- `/health/ready` 返回 `document_jobs_worker_backend=celery`
- `/health/ready` 不出现 `document_jobs_metadata_store_not_mysql` 或 `document_jobs_worker_backend_eager_in_production`
- `/health/ready` 不出现 `document_jobs_celery_broker_url_missing`、`document_jobs_celery_queue_missing` 或 `document_jobs_translation_batch_celery_queue_missing`
- 生产部署默认保持单 worker，但该 worker 必须同时订阅 `document-jobs` 和 `document-translation-batches`，否则 P1 翻译任务会在 `ir_converting` 阶段留下 queued batch；多 worker 原子并发语义不是当前 P0 范围

## 2.1 legacy stage worker 模式

默认 `JOBS_WORKER_MODE=in_process` 时，API 进程在响应返回后通过 FastAPI
`BackgroundTasks` 直接推进 stage。若要让 API 只接请求、由独立 worker 消费 stage
message，设置：

```env
JOBS_WORKER_MODE=external
JOBS_WORKER_POLL_INTERVAL_SECONDS=2
JOBS_WORKER_ID=md2word-worker-1
```

分别启动：

```bash
.venv/bin/python scripts/dev/run_api.py
.venv/bin/python scripts/dev/run_stage_worker.py
```

预期：

- `/health/ready` 返回 `worker_mode=external`
- `/health/ready` 返回 `stage_dispatcher=external_worker`
- API 上传后只写入 `pending` stage message
- `scripts/dev/run_stage_worker.py` 轮询 `pending/running` stage message 并调用 `JobStageService`

当前外部 worker 仍面向单 worker 进程；`lease_owner`、`leased_at`、`lease_expires_at`
用于 readiness 观察 stale running message，不是多 worker 抢占锁。

## 2.2 jobs metadata backend 与 file -> sqlite 迁移

默认策略：

- `JOBS_REPOSITORY_BACKEND=file` 是代码默认值，用于本地开发和最小联调。
- `JOBS_REPOSITORY_BACKEND=database` 使用 sqlite 保存 jobs、files、events 和 stage messages，推荐给准生产单实例部署。
- sqlite 只迁移 metadata；artifact 文件仍由 `JOBS_ARTIFACT_STORAGE_BACKEND` 控制，默认继续使用 job 本地目录。
- `JOBS_REPOSITORY_BACKEND=mysql` 使用 MySQL 保存 jobs、files、events、stage messages 和 resource_versions 基础表，面向单实例生产化部署。
- MySQL 只保存 metadata；PDF、DOCX、MinerU zip 等 artifact 二进制仍由 `JOBS_ARTIFACT_STORAGE_BACKEND` 控制。

从已有 file backend 切到 sqlite 前，先做只读完整性检查：

```bash
.venv/bin/python scripts/ops/check_local_file_storage_integrity.py \
  --data-dir var
```

如果 `blocker_count` 不为 `0`，先修复缺失或不可解析的本地记录，不要切换 backend。

生成并校验 sqlite shadow copy：

```bash
.venv/bin/python scripts/ops/shadow_copy_metadata_to_database.py \
  --data-dir var \
  --database-path var/metadata.sqlite3
```

只读复核：

```bash
.venv/bin/python scripts/ops/shadow_copy_metadata_to_database.py \
  --data-dir var \
  --database-path var/metadata.sqlite3 \
  --validate-only
```

报告 `ok: true` 后再切换 `.env`：

```env
JOBS_REPOSITORY_BACKEND=database
JOBS_METADATA_DATABASE_PATH=var/metadata.sqlite3
```

重启服务后检查：

```bash
curl http://127.0.0.1:8000/api/v1/health/ready
```

预期：

- `configured_repository_backend=database`
- `effective_repository_backend=database`
- `stage_message_store=database`

如果要启用 MySQL metadata store，先确保依赖和 MySQL schema bootstrap 可在启动时执行：

```env
JOBS_REPOSITORY_BACKEND=mysql
JOBS_MYSQL_HOST=127.0.0.1
JOBS_MYSQL_PORT=3306
JOBS_MYSQL_USER=md2word
JOBS_MYSQL_PASSWORD=change-me
JOBS_MYSQL_DATABASE=md2word
```

重启服务后检查：

```bash
curl http://127.0.0.1:8000/api/v1/health/ready
```

预期：

- `configured_repository_backend=mysql`
- `effective_repository_backend=mysql`
- `stage_message_store=mysql`

如果缺少 `PyMySQL` 或 MySQL 无法连接，服务启动应直接失败；不要回退到 file backend 后继续运行。

从 file metadata 切到 MySQL 前，先让目标 MySQL database 保持空 metadata，再执行 shadow copy：

```bash
.venv/bin/python scripts/ops/shadow_copy_metadata_to_mysql.py \
  --data-dir var
```

只读复核：

```bash
.venv/bin/python scripts/ops/shadow_copy_metadata_to_mysql.py \
  --data-dir var \
  --validate-only
```

报告 `ok: true` 后再切换 `.env` 到 `JOBS_REPOSITORY_BACKEND=mysql` 并重启服务。脚本默认拒绝写入非空 MySQL metadata 目标，避免 job events、stage messages 或 audit events 被重复追加。

## 2.2 artifact storage 与对象 adapter

默认策略：

- `JOBS_ARTIFACT_STORAGE_BACKEND=local_file` 是代码默认值，artifact 二进制文件保留在 `var/jobs/{job_id}/` 下。
- `JOBS_ARTIFACT_STORAGE_BACKEND=local_object` 使用本地目录模拟对象存储，适合在接入真实 S3-compatible backend 前验证 `object_key` 合同。
- `JOBS_ARTIFACT_STORAGE_BACKEND=s3` 使用 S3-compatible API 上传 artifact，并在下载时返回临时重定向或对象流。
- `JOBS_ARTIFACT_OBJECT_STORE_PATH=var/object_artifacts` 是默认对象目录；相对路径会解析到当前 `DATA_DIR` 下。

新任务启用 local object adapter：

```env
JOBS_ARTIFACT_STORAGE_BACKEND=local_object
JOBS_ARTIFACT_OBJECT_STORE_PATH=var/object_artifacts
```

重启后检查：

```bash
curl http://127.0.0.1:8000/api/v1/health/ready
```

预期：

- `artifact_storage=local_object`
- 新登记的 artifact `storage_backend=object`
- `object_key` 形如 `jobs/{job_id}/input/source.pdf`、`jobs/{job_id}/output/result.docx`

已有本地 artifact 切换到 local object 前，可先 shadow upload 并回填 `JobFile` metadata：

```bash
.venv/bin/python scripts/ops/shadow_upload_artifacts_to_object_storage.py \
  --data-dir var \
  --object-root var/object_artifacts \
  --metadata-backend file
```

如果 metadata 已切到 sqlite：

```bash
.venv/bin/python scripts/ops/shadow_upload_artifacts_to_object_storage.py \
  --data-dir var \
  --object-root var/object_artifacts \
  --metadata-backend database \
  --database-path var/metadata.sqlite3
```

排障口径：

- local object adapter 下载时优先读 `object_key` 对应文件；对象副本缺失时，会回退到 `JobFile.path` 指向的本地 artifact。
- 如果对象副本和本地 fallback 都不存在，下载接口会返回 artifact missing。
- `JobFile.path` 仍是 job 内逻辑路径，不要改成对象目录绝对路径。
- 新登记 artifact 会写入 `size_bytes` 和 `sha256`；旧记录缺少这两个字段时仍按兼容路径下载。
- 下载诊断口径：本地文件缺失返回 missing，logical path 越界 / 不匹配返回 bad request，fingerprint 不匹配返回 conflict。
- `cleanup-local-files` 只删除 `work/` 运行态目录，不删除登记 artifact，也不会清理 `var/object_artifacts/`。

启用 S3-compatible adapter 前，确保运行环境安装了 `boto3` 并能访问目标 bucket：

```env
JOBS_ARTIFACT_STORAGE_BACKEND=s3
JOBS_ARTIFACT_S3_BUCKET=md2word-artifacts
JOBS_ARTIFACT_S3_ENDPOINT_URL=https://s3.example.com
JOBS_ARTIFACT_S3_REGION=us-east-1
JOBS_ARTIFACT_S3_ACCESS_KEY_ID=
JOBS_ARTIFACT_S3_SECRET_ACCESS_KEY=
JOBS_ARTIFACT_S3_KEY_PREFIX=
JOBS_ARTIFACT_S3_PUBLIC_BASE_URL=
JOBS_ARTIFACT_S3_DOWNLOAD_MODE=redirect
JOBS_ARTIFACT_S3_PRESIGN_EXPIRES_SECONDS=3600
```

说明：

- `ACCESS_KEY_ID` / `SECRET_ACCESS_KEY` 可留空，让运行环境使用实例角色、容器注入或标准 boto3 credential chain。
- `DOWNLOAD_MODE=redirect` 会返回 S3 `get_object` 临时签名 URL；`DOWNLOAD_MODE=stream` 会由后端读取对象并流式返回。
- `KEY_PREFIX` 可用于多环境隔离，例如 `prod` 或 `tenant-a`；生成的 `object_key` 仍保持 `jobs/{job_id}/...` 后缀。
- 旧 `storage_backend=local` 的记录仍可通过本地 fallback 下载；新登记 artifact 会写入 `storage_backend=object` 和 `object_key`。

## 2.3 artifact retention dry-run 策略

当前 retention 只生成 dry-run 计划，不执行删除。默认策略面向已登记 artifact：

| job 状态 | 默认保留期 |
|---|---|
| `completed` | 30 天 |
| `failed` | 14 天 |
| `canceled` | 7 天 |

策略口径：

- `storage_backend=local` 且有 logical `path` 的 `JobFile` 会进入候选。
- `storage_backend=object` 且有 `object_key` 的 `JobFile` 会进入候选。
- dry-run 候选会带 `path`、`object_key`、`size_bytes` 和 `sha256`，用于人工复核。
- `uploaded/queued/submitting/parsing/parsed/converting` 不进入清理候选。
- 年龄按 `completed_at` 优先，其次 `updated_at`，最后 `created_at` 计算。
- 计划输出来自 `ArtifactRetentionPlanner.build_dry_run()`；真正删除 artifact 前必须先人工复核 dry-run 结果。

## 2.4 OpenAPI 快照与发布前检查

OpenAPI 快照保存在：

```text
docs/api/openapi.json
```

路由、schema、response model 或 endpoint 文档变更后，重新导出：

```bash
.venv/bin/python scripts/ops/export_openapi.py
```

发布前执行只读检查：

```bash
.venv/bin/python scripts/ops/check_release.py
```

预期 `Release check report` 顶层 `ok: True`。

hostdzire 准生产/生产环境还应带运行时和 Golden Sample 预检：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
.venv/bin/python scripts/ops/check_release.py \
  --runtime-url http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000} \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json
```

当前 release check 包含：

- OpenAPI snapshot 一致性检查
- P0 health/ready、MySQL metadata、Celery worker 和 health/metrics targeted smoke
- P0 Word renderer/layout/table/formula 语义 targeted smoke
- Golden Sample manifest、DOCX quality evidence、admin sign-off validation targeted smoke
- Document Jobs admin delete 和 generated Word OOXML metadata smoke
- file -> MySQL metadata migration fake-MySQL smoke
- job workflow policy tests
- JSON logging tests
- 可选 `--runtime-url` 真实 `/health/ready` 检查，要求 `deployment_init_ready=true`、`p0_document_jobs_ready=true`、`effective_repository_backend=mysql`、`document_jobs_worker_backend=celery`，且 `document_jobs_translation_batch_celery_queue` 已配置
- 可选 `--golden-sample-preflight`，只检查 4 个 canonical PDF、admin 登录角色和运行时门禁，不提交真实转换任务

如果 OpenAPI 分项失败，说明当前代码生成的 OpenAPI 与 `docs/api/openapi.json` 不一致；先确认 API 变更是否预期，再重新导出并提交快照。无 `--runtime-url` 的本地 release check 不访问真实 MinerU、OpenAI 或公网；带 `--runtime-url` 的运行时门禁应在 hostdzire 执行。

## 3. 本地 Document Job 调试（仅开发）

当前公开 P0 主链路是 Files + Document Jobs。Legacy `/api/v1/jobs` endpoint family 已从 v1 router 移除，只保留历史文档说明；新联调、前端和集成方不要再使用旧入口。

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/files/upload-url" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"filename":"source.pdf","mime_type":"application/pdf","size_bytes":12345,"file_type":"source_pdf"}'
```

按响应里的 `upload_url` 上传 PDF 内容后创建任务：

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"source_file_id":"{file_id}","mode":"direct_pdf_to_word","document_language":"auto"}'
```

查询任务和获取临时下载链接：

```bash
curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}" \
  -H "Authorization: Bearer ${TOKEN}"

curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/download-url" \
  -H "Authorization: Bearer ${TOKEN}"
```

## 3.1 翻译 Provider 批次诊断

英译中 / 俄译中任务在 `ir_converting` 阶段会把 DocumentIR 文本拆成 provider batches。单任务诊断入口是内部工作台：

```text
/jobs/{job_id} -> 诊断 -> Provider 批次
```

也可以直接读取只读摘要接口：

```bash
curl -sS "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/translation-batches" \
  -H "Authorization: Bearer ${TOKEN}"
```

该接口只返回 batch 元数据、错误摘要和文件 ID，不返回完整 prompt、provider response、source text、translated text、debug archive 内容、对象存储定位或签名 URL。

常见判断口径：

| 现象 | Provider 批次信号 | 处理建议 |
|---|---|---|
| 正常成功 | 当前 leaf batches 均为 `succeeded`，任务 `status=succeeded`，结果文件存在。 | 可进入下载、QA 或验收复核。 |
| 截断自动恢复 | 父 batch 为 `split`，`finish_reason=length` 或 `truncation_retry=true`，子 batches 后续 `succeeded`。 | 这是预期恢复路径；记录 job id、batch id 和 AI call log file id 数量即可。 |
| 批次失败且重试耗尽 | batch 为 `failed`，`retryable=false`，`attempt_count=max_attempts`，`error_code/error_message` 有摘要。 | 使用任务级 `retry`，或把 job id、batch id、页范围、attempt、finish_reason 和 error 摘要交给开发排查。 |
| 批次仍在执行 | batch 为 `pending` / `queued` / `running`，任务仍在 `ir_converting`。 | 等待 bounded polling；若 `updated_at` 长时间不变，再检查 worker、Celery queue 和 lease 过期恢复。 |
| 疑似 fan-in 卡住 | 当前 leaf batches 均已 `succeeded`，但任务没有推进到渲染/结果保存。 | 记录全部 leaf batch id、generation、job retry_count、最近事件和 trace_id，升级开发排查 finalizer。 |
| 无 batch 记录 | 非翻译任务，或翻译任务尚未进入 provider batch 创建阶段。 | 先看任务 mode、stage、事件和 callback summary；不要把 direct PDF 任务视为异常。 |

排查时优先记录这些字段：

- `job_id`
- `generation`
- `batch_id`
- `root_batch_id` / `parent_batch_id`
- `status`
- `page_start` / `page_end`
- `item_count` / `char_count`
- `attempt_count` / `max_attempts`
- `finish_reason`
- `truncation_retry`
- `retryable`
- `provider_call_budget`
- `error_code` / `error_message`
- `ai_call_log_file_ids` 的数量或 ID 摘要

当前允许运维使用的动作仍是任务级动作：`retry`、`cancel`、`archive`、`unarchive`、`clone`、`download`，具体以任务详情返回的 `available_actions` 为准。当前没有批次级 `retry`、`cancel`、`requeue` 或强制 finalizer 写操作；不要通过数据库或队列手工改 batch 状态。

长 PDF 英译中上线验证应在 hostdzire 或等价 staging 执行。若使用私有 32 页失败样本或等价长 PDF，报告只记录样本标识、页数、job id、部署版本、batch 摘要和结果，不提交 PDF、全文、prompt、provider response、密钥或签名 URL。

## 3.2 历史 legacy jobs 入口

旧 `/api/v1/jobs` 和 `/api/v1/jobs/pdf` 入口已从公开 v1 API 移除，仅作为历史排查背景保留；不要用于新开发、联调或 P0 验收。历史链路曾支持 MinerU zip 上传、原始 PDF 在线提交、本地 callback 回放和旧 `download/result` 下载，但当前主合同统一使用 Files + Document Jobs：

- 上传和创建：`POST /api/v1/files/upload-url` -> `PUT /api/v1/files/{file_id}/content` -> `POST /api/v1/document-jobs`
- 查询：`GET /api/v1/document-jobs/{job_id}`
- 事件：`GET /api/v1/document-jobs/{job_id}/events`
- 文件：`GET /api/v1/document-jobs/{job_id}/files`
- 下载：`GET /api/v1/document-jobs/{job_id}/download-url`

MinerU callback 仍命中 `POST /api/v1/mineru-callbacks/result`，但任务观察和恢复证据读取 Document Jobs 详情、事件、文件和 callback summary，不再读取旧 jobs 详情页。

## 4.1 查询默认模板和配置元数据

```bash
curl "http://127.0.0.1:8000/api/v1/templates"
curl "http://127.0.0.1:8000/api/v1/templates/default"
curl -L "http://127.0.0.1:8000/api/v1/templates/default/download" -o template.docx
```

当前 `templates` 接口会返回：

- 默认 DOCX 模板元数据
- `datasheet_template.yaml` 元数据
- `subscripts_dictionary.yaml` 元数据
- API 上传模板的当前版本号

## 5. 本地运维动作

### retry

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/retry" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"reason":"rerun"}'
```

### cancel

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/cancel" \
  -H "Authorization: Bearer ${TOKEN}"
```

### archive / unarchive

```bash
curl -sS -X DELETE "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}" \
  -H "Authorization: Bearer ${TOKEN}"

curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/unarchive" \
  -H "Authorization: Bearer ${TOKEN}"
```

### admin delete

任务级删除只允许 admin 执行；operator 前端不展示入口，接口返回 `403 forbidden`。执行前必须先预览，再带 `reason`、确认短语和 `preview_hash` 提交。

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/delete-preview" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"

curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-jobs/{job_id}/delete" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"reason":"cleanup duplicate internal test","confirmation":"DELETE docjob_xxx","preview_hash":"<preview_hash>"}'
```

注意：

- 普通 operator 可以使用创建、查看、下载、取消、重试、归档等任务工作台动作，但不能执行任务级删除。
- Document Jobs replay / callback 诊断通过任务详情、事件、callback summary 和 Ops Dashboard 恢复动作处理，不再使用旧 jobs 运维端点。
- 文件物理清理仍走 Files retention 的 preview -> reason -> confirmation -> audit 流程；任务删除只清理可安全删除的关联本地文件，并保留任务 metadata、事件和 audit。

## 6. 真实样例联调口径

P0 Golden Sample 以 `tests/fixtures/golden_samples/pdfs` 下的四个 OPA228 datasheet 页为 canonical suite：

- `gs-003`: `OPA228_P1.pdf`
- `gs-004`: `OPA228_P2.pdf`
- `gs-006`: `OPA228_P6.pdf`
- `gs-008`: `OPA228_P7.pdf`

这四份样本通过 Files + Document Jobs 主链路执行 `direct_pdf_to_word`。P0 通过条件是 4/4 任务成功、4/4 结果 DOCX 可由 Word 打开、4/4 由 admin reviewer 人工签字通过；不再以扩充到 10-20 份样本作为阻塞条件。人工质量线要求接近原版排版并符合 Word 文档排版标准，二者冲突时以可维护的 Word 标准结构为准。

正式执行地点是 hostdzire；本地不跑真实 Golden Sample 转换。执行、签字和证据回填步骤见 [线上优先验证流程](/Users/sc/PycharmProjects/md2word/docs/deploy/online-first-validation-workflow.md)。
