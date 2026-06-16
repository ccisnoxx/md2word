---
doc_type: dev-guide
slug: runbook
component: backend-runbook
status: current
summary: 当前后端本地联调、运维动作和真实样例验证的运行说明。
tags: [backend, runbook, jobs, local]
last_reviewed: 2026-05-28
---

# 本地运行与联调说明

## 0. 访问控制口径

本地单机联调可以使用：

```env
JOBS_ACCESS_MODE=open
JOBS_OPS_ACCESS_MODE=admin
ADMIN_TOKEN=local-admin-token
```

`JOBS_ACCESS_MODE=open` 只适合本地开发。生产或任何可被外部访问的环境不要使用 `open`，应改为：

- `JOBS_ACCESS_MODE=token`，并配置 `JOBS_ACCESS_TOKEN`
- 或 `JOBS_ACCESS_MODE=admin`，并配置 `ADMIN_TOKEN`

jobs 运维动作默认由 `JOBS_OPS_ACCESS_MODE=admin` 控制，需要 `X-Admin-Token`。只有明确接受 `retry/cancel/cleanup-local-files` 和普通 jobs 查询同级时，才设置 `JOBS_OPS_ACCESS_MODE=jobs`。

## 0.1 环境配置样例

仓库根目录提供 `.env.example`，覆盖单实例生产化需要的主要配置：

- `JOBS_REPOSITORY_BACKEND=mysql` 与 `JOBS_MYSQL_*`
- `JOBS_ARTIFACT_STORAGE_BACKEND=local_file`，artifact 二进制仍保存在 artifact storage，不写入 MySQL
- `JOBS_WORKER_MODE=in_process` / `external`
- `JOBS_ACCESS_MODE`、`JOBS_ACCESS_TOKEN`、`JOBS_OPS_ACCESS_MODE`、`ADMIN_TOKEN`
- `MINERU_CALLBACK_URL`、`MINERU_UID` 和 `MINERU_RESULT_HOST_ALLOWLIST`
- `LOG_FORMAT=json`

`MINERU_CALLBACK_URL` 直接按官方 callback 地址填写；callback 验签依赖 `uid + seed + content`，不要再给 URL 追加自定义 token 或 query 参数。

不要把真实 token 或 password 提交到仓库；复制样例后在本地 `.env` 或部署环境里填真实值。

## 1. 启动服务

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_api.py
```

默认监听：

```text
http://127.0.0.1:8000
```

## 2. 健康检查

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

## 2.0 独立 worker 模式

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
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_api.py
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_stage_worker.py
```

预期：

- `/health/ready` 返回 `worker_mode=external`
- `/health/ready` 返回 `stage_dispatcher=external_worker`
- API 上传后只写入 `pending` stage message
- `scripts/dev/run_stage_worker.py` 轮询 `pending/running` stage message 并调用 `JobStageService`

当前外部 worker 仍面向单 worker 进程；`lease_owner`、`leased_at`、`lease_expires_at`
用于 readiness 观察 stale running message，不是多 worker 抢占锁。

## 2.1 jobs metadata backend 与 file -> sqlite 迁移

默认策略：

- `JOBS_REPOSITORY_BACKEND=file` 是代码默认值，用于本地开发和最小联调。
- `JOBS_REPOSITORY_BACKEND=database` 使用 sqlite 保存 jobs、files、events 和 stage messages，推荐给准生产单实例部署。
- sqlite 只迁移 metadata；artifact 文件仍由 `JOBS_ARTIFACT_STORAGE_BACKEND` 控制，默认继续使用 job 本地目录。
- `JOBS_REPOSITORY_BACKEND=mysql` 使用 MySQL 保存 jobs、files、events、stage messages 和 resource_versions 基础表，面向单实例生产化部署。
- MySQL 只保存 metadata；PDF、DOCX、MinerU zip 等 artifact 二进制仍由 `JOBS_ARTIFACT_STORAGE_BACKEND` 控制。

从已有 file backend 切到 sqlite 前，先做只读完整性检查：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_local_file_storage_integrity.py \
  --data-dir var
```

如果 `blocker_count` 不为 `0`，先修复缺失或不可解析的本地记录，不要切换 backend。

生成并校验 sqlite shadow copy：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/shadow_copy_metadata_to_database.py \
  --data-dir var \
  --database-path var/metadata.sqlite3
```

只读复核：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/shadow_copy_metadata_to_database.py \
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
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/shadow_copy_metadata_to_mysql.py \
  --data-dir var
```

只读复核：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/shadow_copy_metadata_to_mysql.py \
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
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/shadow_upload_artifacts_to_object_storage.py \
  --data-dir var \
  --object-root var/object_artifacts \
  --metadata-backend file
```

如果 metadata 已切到 sqlite：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/shadow_upload_artifacts_to_object_storage.py \
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
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
```

发布前执行只读检查：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

预期 `Release check report` 顶层 `ok: True`。

当前 release check 包含：

- OpenAPI snapshot 一致性检查
- health/ready 和 health/metrics targeted smoke
- file -> MySQL metadata migration fake-MySQL smoke
- MySQL resource mode PDF -> callback -> completed smoke
- job workflow policy tests
- JSON logging tests

如果 OpenAPI 分项失败，说明当前代码生成的 OpenAPI 与 `docs/api/openapi.json` 不一致；先确认 API 变更是否预期，再重新导出并提交快照。release check 不访问真实 MinerU、OpenAI 或公网。

## 3. 创建 Document Job

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

## 3.1 历史 legacy jobs 入口

以下旧入口已从公开 v1 API 移除，仅作为历史排查材料保留；不要用于新开发或验收。

## 3. 上传 MinerU 输出 zip

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs" \
  -F "package=@/path/to/mineru-output.zip" \
  -F "translation_mode=direct"
```

如果要走翻译：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs" \
  -F "package=@/path/to/mineru-output.zip" \
  -F "translation_mode=en2zh"
```

前提：

- `GET /api/v1/health/ready` 里的 `translation_available=true`
- `translation_prompt_exists=true`

## 3.1 上传原始 PDF 并提交 MinerU

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/pdf" \
  -F "pdf=@/path/to/source.pdf" \
  -F "translation_mode=direct"
```

前提：

- `GET /api/v1/health/ready` 里的 `mineru_api_token_configured=true`

当前这条链路会先做到：

- 创建 job
- 登记 `source_pdf`
- 后台提交 MinerU
- 任务进入 `parsing`

接下来 callback 命中 `done + full_zip_url` 后，会自动继续：

- 恢复远端结果 zip 到本地 `parsed_result_package`
- 继续走后处理 conversion
- 最终把任务推进到 `completed` 或 `failed`

## 3.2 本地回放 MinerU callback

先拿到上一步 PDF 任务的 `job_id` 和详情里的 `mineru_batch_id`：

```bash
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}"
```

然后按 `uid + mineru_callback_seed + content` 计算 `sha256`，再发送 callback：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/mineru-callbacks/result" \
  -H "Content-Type: application/json" \
  -d '{"batch_id":"batch_test_001","checksum":"sha256(uid+seed+content) 的十六进制值","content":"{\"batch_id\":\"batch_test_001\",\"extract_result\":[{\"data_id\":\"job_123\",\"state\":\"done\",\"full_zip_url\":\"https://mineru.net/result.zip\"}]}"}'
```

预期：

- `GET /api/v1/jobs/{job_id}` 通常会继续推进到 `completed`
- `mineru_result_zip_url` 已持久化
- `files` 里会新增 `parsed_result_package`
- `events` 里出现：
  - `mineru_callback_received`
  - `mineru_callback_processed`
  - `parsed_result_package_recovered`
  - `job_completed`

如果要模拟失败回调，把 `state` 改成 `failed`。预期是：

- `status=failed`
- `error_code=mineru_failed`

## 4. 查询任务与下载结果

```bash
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}"
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}/files"
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}/events"
curl -L "http://127.0.0.1:8000/api/v1/jobs/{job_id}/download/result" -o result.docx
```

如果是 `en2zh`，`events` 里会多出：

- `translation_started`
- `translation_completed`
- 失败时的 `translation_failed`

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
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/{job_id}/retry" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -F "reason=rerun"
```

### cancel

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/{job_id}/cancel" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -F "reason=stop"
```

### cleanup-local-files

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/{job_id}/cleanup-local-files" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -F "reason=cleanup"
```

### recover-mineru-result

callback 长时间未到时，可以主动查询 MinerU batch 结果并恢复后续处理：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/{job_id}/recover-mineru-result" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}"
```

注意：

- 这些运维动作默认需要 `ADMIN_TOKEN`
- `recover-mineru-result` 要求任务是已提交 MinerU 的 `source_pdf` parsing 任务
- `cleanup-local-files` 当前只删未登记的运行态目录，例如 `work/`
- `input/source.zip` 和 `output/result.docx` 会保留，因为它们还是唯一副本

## 6. 真实样例联调口径

当前本地已经验证过一条真实样例链路：

- 样例目录：`/Users/sc/MinerU/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4`
- 打包 zip：`/private/tmp/opa228_mineru_sample.zip`
- 实际成功任务：`job_d93a9b69f751`

这条链路已经证明：

- `POST /api/v1/jobs` 可接收真实 MinerU zip
- 后台 stage 能推进到 `completed`
- `download/result` 能得到有效 DOCX

当前 PDF 在线提交能力只做到了对象级测试验证：

- 合法 PDF 可进入 `parsing`
- 缺 `MINERU_API_TOKEN` 时 `POST /api/v1/jobs/pdf` 返回 `503`
- MinerU 提交失败时任务进入 `failed` 且 `error_code=mineru_submit_failed`
- 合法 callback 可自动继续推进到 `completed`
- 非法 `full_zip_url` 会被 callback ingress 直接以 `400` 拒绝
