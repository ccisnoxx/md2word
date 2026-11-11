---
doc_type: dev-guide
slug: runtime-observability-and-health
component: runtime-observability
status: current
summary: 说明当前后端的 access/business/system 日志分层和 health readiness 字段。
tags: [backend, logging, health, observability]
last_reviewed: 2026-05-28
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  全文用途、原字段与现有入口/命令参数声明的局部静态核对；原历史结果和执行条件保留，未运行命令或重新验收。输入身份及旧说明差异见 ../../.trellis/tasks/11-10-documentation-evidence-governance/research/b3-preparation.md。
---

## 日志分层

本页维护正式任务的日志与健康观察方法，示例字段不代表当前实例观测值。末尾额外 callback token 排障提示属旧口径；现行回调按 [MinerU callbacks](../api/mineru-callbacks.md) 的 checksum 合同解释，本批未执行健康查询或恢复动作。

当前后端约定三类日志：

| 通道 | 用途 | 典型来源 |
|---|---|---|
| `access` | 请求访问日志 | `trace_logging_middleware` |
| `business` | 带 job 上下文的业务链路日志 | 正式任务执行、retry、文件清理 |
| `system` | 无业务上下文或第三方库日志 | `uvicorn`、`httpx`、`python_multipart`、异常堆栈 |

## 当前日志格式

默认 `LOG_FORMAT=text`，统一格式：

```text
{time} | {logger_name} | {level} | {message}
```

如果设置 `LOG_FORMAT=json`，同一条日志会输出为单行 JSON，至少包含：

```json
{"time":"...","logger":"access","level":"INFO","message":"..."}
```

两种格式下，message 都使用稳定 key，方便 grep 或日志平台解析。

access 日志字段约定：

```text
[trace_id=... method=GET path=/api/v1/health/ready status_code=200 duration_ms=1.5]
```

业务日志由正式 execution、callback 和 recovery 记录，使用实际可用的 `trace_id`、`job_id`、`stage` 等上下文。旧 stage worker 日志已停止，不以旧消息 ID 判断正式任务执行。

## `/health/ready` 应怎么看

最重要的字段分四类：

### readiness 分类

- `readiness_required_checks`：最小可运行链路必须满足的检查项名称。
- `readiness_non_blocking_checks`：能力或观察项，不阻塞最小启动。
- `deployment_init_ready`：必检项是否都通过。
- `readiness_blockers`：导致 `deployment_init_ready=false` 的原因。
- `readiness_warnings`：非阻塞提示，例如 MinerU token 缺失、翻译不可用或正式 callback 有待处理消息。

### 运行目录

- `jobs_dir_exists`
- `jobs_dir_writable`
- `artifact_root_writable`
- `artifact_disk_free_bytes`
- `tmp_dir_exists`

### 版本化资产

- `template_docx_exists`
- `layout_config_exists`
- `subscript_config_exists`

### 翻译能力

- `mineru_api_token_configured`
- `mineru_config_source`
- `mineru_config_updated_at`
- `mineru_config_error`
- `pdf_submission_available`
- `openai_api_key_configured`
- `translation_prompt_exists`
- `translation_provider_backend`
- `translation_debug_archive_enabled`
- `translation_required_for_default_mode`
- `translation_client_configured`
- `translation_available`
- `translation_unavailable_reason`

### 当前实例状态

- `configured_repository_backend`
- `effective_repository_backend`
- `worker_mode`
- `artifact_storage`
- `document_jobs_worker_backend`
- `document_jobs_celery_queue`
- `document_jobs_translation_batch_celery_queue`
- `p0_document_jobs_required`
- `p0_document_jobs_ready`
- `document_jobs_automatic_execution_enabled`
- `p0_document_jobs_blockers`
- `p0_document_jobs_warnings`
- `document_jobs_running_stale_count`
- `document_jobs_timed_out_count`
- `document_jobs_running_oldest_age_seconds`
- `default_template_version`
- `default_term_rule_version`
- `default_translation_profile_version`
- `mysql_schema_bootstrap_available`
- `deployment_init_ready`
- `deployment_init_missing_steps`

### P0 document jobs 门禁

`APP_ENV` 不属于 `dev` / `local` / `test`，或 `PUBLIC_DEPLOYMENT_MODE=single_tenant_public` 时，`p0_document_jobs_required=true`。

此时 `/health/ready` 会把 document_jobs 自动执行链路纳入 `deployment_init_ready`：

- `effective_repository_backend` 必须是 `mysql`；生产/准生产 P0 不允许继续使用 file 或 sqlite metadata store。
- `DOCUMENT_JOBS_WORKER_BACKEND` 不能是 `disabled`。
- `DOCUMENT_JOBS_WORKER_BACKEND` 不能是 `eager`；P0 生产基线是 Celery + 单 worker。
- `DOCUMENT_JOBS_WORKER_BACKEND=celery` 时必须配置 broker URL 和 queue。
- `AUTH_JWT_SECRET_KEY` 和内部账号来源不能为空。
- MinerU 运行时绑定或环境变量中的 `MINERU_API_TOKEN`、`MINERU_UID` 必须配置，`MINERU_CALLBACK_URL` 仍由环境变量提供。

开发态如果仍使用 `DOCUMENT_JOBS_WORKER_BACKEND=disabled`，会出现在 `p0_document_jobs_warnings` / `readiness_warnings`，但不会阻断 `deployment_init_ready`。
`document_jobs_running_stale_count`、`document_jobs_timed_out_count` 只做只读观察，不会重投递、取消或恢复任务。

## `/health/metrics` 应怎么看

`GET /api/v1/health/metrics` 返回 JSON 运维计数，不是 Prometheus 格式，也不暴露 token、payload、客户文件名或 artifact 本地绝对路径。当前主要字段：

- `metadata_store`：当前实际 jobs metadata store，取值 `file` / `database` / `mysql`。
- `artifact_storage`：当前 artifact adapter，取值 `local_file` / `local_object` / `s3`。
- `worker_mode`：保留既有配置回显，不再代表旧 stage 消费；正式执行模式看 `document_jobs_worker_backend`。
- `jobs={}`、`stage_messages={}`：只保留兼容空字段，不读取旧仓储。
- `document_jobs`：正式任务状态计数。
- `document_job_callback_messages`：正式 callback 状态计数。
- `resources`：模板、术语规则集、翻译配置的版本数量和当前默认版本标签。
- `audit_events.total`：当前审计事件总数。

metrics 适合被脚本轮询或人工排障读取；如果后续接 Prometheus / OpenTelemetry，需要另起 feature，不在当前单实例基线里隐式引入。

## 正式任务恢复与排障

API 启动时仅调用 `DocumentJobRecoveryService.run_startup_recovery`；正式 Worker 仍按 DocumentJob 状态、callback 消息与既有恢复合同执行。旧 stage spool、dispatcher 和 StageWorker 已删除。

### 场景 1：上传成功，但任务不推进

检查 `document_jobs_worker_backend`、正式 Celery 队列订阅、任务详情和 `GET /api/v1/document-jobs/{job_id}/events`。结合 `document_job_callback_replayable_messages`、`document_job_callback_failed_messages`、`document_jobs_running_stale_count` 与 `document_jobs_timed_out_count` 判断问题；健康查询本身不会重放或修改任务。

`effective_repository_backend` 表示正式元数据后端；产物由正式 Files 服务按记录中的 `object_key` 读写。旧 jobs/file/stage 仓储已删除，`job_events` 仍供正式任务使用。三张既有旧空表留待 B08，本次不 DROP。

### 场景 2：`direct` 都跑不通

先看：

- `jobs_dir_writable`
- `template_docx_exists`
- `layout_config_exists`
- `subscript_config_exists`

这四个任意一个为 `false`，都足以让最小链路失败。

### 场景 2.1：PDF 在线任务创建返回 `503`

优先看：

- `mineru_api_token_configured`
- `mineru_config_error`

如果 token 或 UID 状态是 `false` 且 error 为空，说明当前实例的 MinerU 环境变量绑定不完整；如果 error 为 `mineru_config_invalid`，说明共享运行时文件损坏或缺少绑定字段，系统不会回退或混用环境变量。管理员应进入 `/settings/mineru` 原子更新账号与密钥。当前公开入口是 Files + Document Jobs；legacy `/api/v1/jobs/pdf` 不再作为新联调路径。

### 场景 3：`en2zh` 失败

优先看：

- `translation_available`
- `translation_unavailable_reason`
- `translation_provider_backend`
- `translation_prompt_exists`
- job 事件里的 `error_code`
- job 事件里的 `translation_started/translation_completed/translation_failed`

当前最常见的是 `TRANSLATION_PROVIDER_BACKEND` 未设为 `openai_compatible` 或 `OPENAI_API_KEY` 未配置。

### 场景 4：callback 被拒绝

优先看：

- `PUBLIC_DEPLOYMENT_MODE`
- `MINERU_CALLBACK_TOKEN`
- `MINERU_RESULT_HOST_ALLOWLIST`
- access 日志里的 `POST /api/v1/mineru-callbacks/result -> 4xx`

常见原因：

- 公开模式缺 token 或 token 不匹配
- `full_zip_url` 不是 `https`
- `full_zip_url` host 不在 allowlist
