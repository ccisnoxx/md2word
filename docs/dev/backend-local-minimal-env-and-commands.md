---
doc_type: dev-guide
slug: backend-local-minimal-env-and-commands
component: backend-setup
status: current
summary: 当前后端最小 .env 模板和启动命令速查版。
tags: [backend, setup, quickstart, env]
last_reviewed: 2026-05-29
---

## 最小 `.env`

当前仓库根目录 `.env` 最小只需要保证下面这些值：

仓库根目录同时提供 `.env.example`，作为单实例生产化样例；里面包含 MySQL metadata、artifact storage、worker、access token、callback、JSON logging 和翻译配置占位值，不包含真实 secret。

```env
APP_NAME=md2word_file
APP_ENV=dev
LOG_FORMAT=text
APP_CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
DATA_DIR=var
JOBS_REPOSITORY_BACKEND=file
JOBS_METADATA_DATABASE_PATH=var/metadata.sqlite3
JOBS_MYSQL_HOST=127.0.0.1
JOBS_MYSQL_PORT=3306
JOBS_MYSQL_USER=md2word
JOBS_MYSQL_PASSWORD=
JOBS_MYSQL_DATABASE=md2word
JOBS_MYSQL_CHARSET=utf8mb4
JOBS_MYSQL_CONNECT_TIMEOUT_SECONDS=10
JOBS_ARTIFACT_STORAGE_BACKEND=local_file
JOBS_ARTIFACT_OBJECT_STORE_PATH=var/object_artifacts
JOBS_ARTIFACT_S3_BUCKET=
JOBS_ARTIFACT_S3_ENDPOINT_URL=
JOBS_ARTIFACT_S3_REGION=us-east-1
JOBS_ARTIFACT_S3_ACCESS_KEY_ID=
JOBS_ARTIFACT_S3_SECRET_ACCESS_KEY=
JOBS_ARTIFACT_S3_KEY_PREFIX=
JOBS_ARTIFACT_S3_PUBLIC_BASE_URL=
JOBS_ARTIFACT_S3_DOWNLOAD_MODE=redirect
JOBS_ARTIFACT_S3_PRESIGN_EXPIRES_SECONDS=3600
JOBS_WORKER_MODE=in_process
JOBS_WORKER_POLL_INTERVAL_SECONDS=2
JOBS_WORKER_ID=md2word-worker
STAGE_MESSAGE_LEASE_SECONDS=900
JOBS_ACCESS_MODE=open
JOBS_ACCESS_TOKEN=
JOBS_OPS_ACCESS_MODE=admin
ADMIN_TOKEN=
DEFAULT_TRANSLATION_MODE=direct
MINERU_API_TOKEN=
MINERU_MODEL_VERSION=vlm
MINERU_LANGUAGE=en
MINERU_ENABLE_FORMULA=true
MINERU_ENABLE_TABLE=true
MINERU_CALLBACK_URL=
MINERU_UID=
MINERU_CALLBACK_TOKEN=
MINERU_CALLBACK_TOKEN_QUERY_NAME=callback_token
MINERU_RESULT_HOST_ALLOWLIST=mineru.net,cdn-mineru.openxlab.org.cn
PUBLIC_DEPLOYMENT_MODE=internal

OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_MODEL=deepseek-v4-flash
TRANSLATION_MAX_PAGES=20
TRANSLATION_MAX_CHARS=60000
DEFAULT_TEMPLATE_ID=default
TEMPLATES_MANIFEST_PATH=resources/template_configs/templates_manifest.yaml
TEMPLATES_STORAGE_PATH=var/config/templates
TEMPLATE_STATE_PATH=var/config/template_state.json
```

说明：

- `MINERU_API_TOKEN` 为空时：
  - `POST /api/v1/jobs/pdf` 不可用
  - `POST /api/v1/jobs` 仍可继续接收 MinerU 输出 zip
- `PUBLIC_DEPLOYMENT_MODE=internal`
  - 本地联调 callback 最省事，不要求 callback token
- 若切到 `PUBLIC_DEPLOYMENT_MODE=single_tenant_public`
  - 需要同时配置 `MINERU_CALLBACK_TOKEN`
  - MinerU 回调时必须带 header 或 query token
- `OPENAI_API_KEY` 为空时：
  - `translation_mode=direct` 仍可用
  - `translation_mode=en2zh` 会被 health 标记为 unavailable，`POST /api/v1/jobs` 也会直接返回 `503`
- `LOG_FORMAT=text`
  - 默认输出便于本地阅读的文本日志
  - 容器或云日志采集环境可改为 `LOG_FORMAT=json`
- `JOBS_ACCESS_MODE=open`
  - 只适合本地联调
  - 生产或可被外部访问的环境不要使用 `open`
  - 准生产和生产应改成 `token` 或 `admin`
  - `token` 模式需要同时配置 `JOBS_ACCESS_TOKEN`
  - artifact 下载成功会写 audit event；`open` 模式下 actor 固定为 `anonymous`，即使请求带 `X-Actor-Id` 也不会采信
- `JOBS_OPS_ACCESS_MODE=admin`
  - `retry`、`cancel`、`recover-mineru-result`、`cleanup-local-files` 默认要求 `X-Admin-Token`
  - 需要本地调这些运维接口时，设置 `ADMIN_TOKEN` 并在请求里带上 `X-Admin-Token`
  - 只有明确要复用普通 jobs 访问口径时，才改成 `JOBS_OPS_ACCESS_MODE=jobs`
  - `retry`、`cancel`、`cleanup-local-files` 成功会写 audit event；认证通过后可用 `X-Actor-Id` 标记操作者
- `TEMPLATES_STORAGE_PATH`
  - API 新增或替换模板时保存 DOCX 版本文件的目录
  - 默认位于 `var/config/templates`
- `DATA_DIR`
  - 默认就是仓库内 `var/`
- `JOBS_REPOSITORY_BACKEND=file`
  - 是代码默认值，适合本地开发和最小联调
  - sqlite 准生产可在完成 integrity check 和 metadata shadow copy 后显式改为 `database`
  - MySQL 生产化 metadata store 可显式改为 `mysql`
- `JOBS_METADATA_DATABASE_PATH=var/metadata.sqlite3`
  - 仅 `JOBS_REPOSITORY_BACKEND=database` 时使用
  - 保存 jobs、files、events 和 stage messages 的 sqlite metadata；不保存 artifact 二进制文件
- `JOBS_REPOSITORY_BACKEND=mysql`
  - 使用 MySQL 保存 jobs、files、events、stage messages 和 resource_versions 基础表
  - 需要安装 `PyMySQL`，并配置 `JOBS_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`
  - artifact 二进制文件仍由 `JOBS_ARTIFACT_STORAGE_BACKEND` 控制，默认继续保存在本地 jobs 目录
  - 启动后 `/health/ready` 预期显示 `configured_repository_backend=mysql`、`effective_repository_backend=mysql`、`stage_message_store=mysql`
  - 从 file metadata 切 MySQL 前，可用 `scripts/ops/shadow_copy_metadata_to_mysql.py` 做空目标 shadow copy 和 `--validate-only` 复核
- `JOBS_ARTIFACT_STORAGE_BACKEND=local_file`
  - 是代码默认值，保留 artifact 二进制在 `var/jobs/{job_id}/`
  - 可显式切到 `local_object` 或 `s3`
- `JOBS_ARTIFACT_STORAGE_BACKEND=s3`
  - 需要配置 `JOBS_ARTIFACT_S3_BUCKET`
  - `JOBS_ARTIFACT_S3_DOWNLOAD_MODE=redirect` 返回临时签名 URL，`stream` 由后端流式返回对象内容
- `JOBS_WORKER_MODE=in_process`
  - 是代码默认值，API 请求返回后仍由 FastAPI `BackgroundTasks` 同进程推进 stage
  - 若改为 `external`，API 只写入 stage message，不执行转换；必须另起 `scripts/dev/run_stage_worker.py`
- `JOBS_WORKER_POLL_INTERVAL_SECONDS=2`
  - 独立 worker 轮询 replayable stage message 的间隔
- `STAGE_MESSAGE_LEASE_SECONDS=900`
  - running message 超过该时间后会在 readiness 中记为 stale

## 最小启动命令

优先使用当前 attention.md 里约定的 conda 环境：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_api.py
```

或者：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果使用独立 worker 模式，`.env` 里设置：

```env
JOBS_WORKER_MODE=external
```

然后分别启动 API 和 worker：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_api.py
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_stage_worker.py
```

## 第一条检查命令

```bash
curl http://127.0.0.1:8000/api/v1/health/ready
curl http://127.0.0.1:8000/api/v1/health/metrics
```

重点看：

- `deployment_init_ready`
- `readiness_blockers`
- `readiness_warnings`
- `jobs_dir_writable`
- `template_docx_exists`
- `layout_config_exists`
- `subscript_config_exists`
- `translation_available`
- `pdf_submission_available`
- `artifact_root_writable`
- `artifact_disk_free_bytes`
- `default_template_version`
- `default_term_rule_version`
- `default_translation_profile_version`

其中 `readiness_blockers` 是最小 `direct` 链路或默认运行模式必须处理的问题；
`readiness_warnings` 是非阻塞能力提示，例如 MinerU token 未配置、翻译不可用、
stage spool 中有待 replay 或需要人工关注的消息。

`/health/metrics` 返回 JSON 运维计数，包括 jobs 状态计数、stage message 状态计数、资源版本计数和 audit event 总数；它不是 Prometheus 格式。

## 最小联调命令

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs" \
  -F "package=@/path/to/mineru-output.zip" \
  -F "translation_mode=direct"
```

拿到 `job_id` 后：

```bash
curl "http://127.0.0.1:8000/api/v1/jobs/{job_id}"
curl -L "http://127.0.0.1:8000/api/v1/jobs/{job_id}/download/result" -o result.docx
```

如果要验证本地运维动作，先在 `.env` 里设置 `ADMIN_TOKEN`，再带 admin header：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/{job_id}/retry" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -F "reason=rerun"
```

如果要验证 PDF 在线提交前半程：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/pdf" \
  -F "pdf=@/path/to/source.pdf" \
  -F "translation_mode=direct"
```

如果要本地验证 callback ingress：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/mineru-callbacks/result" \
  -H "Content-Type: application/json" \
  -d '{"batch_id":"batch_123","content":"{\"batch_id\":\"batch_123\",\"extract_result\":[{\"data_id\":\"job_123\",\"state\":\"done\",\"full_zip_url\":\"https://mineru.net/result.zip\"}]}"}'
```
