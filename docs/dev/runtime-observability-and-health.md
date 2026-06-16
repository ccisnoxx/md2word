---
doc_type: dev-guide
slug: runtime-observability-and-health
component: runtime-observability
status: current
summary: 说明当前后端的 access/business/system 日志分层和 health readiness 字段。
tags: [backend, logging, health, observability]
last_reviewed: 2026-05-28
---

## 日志分层

当前后端约定三类日志：

| 通道 | 用途 | 典型来源 |
|---|---|---|
| `access` | 请求访问日志 | `trace_logging_middleware` |
| `business` | 带 job 上下文的业务链路日志 | stage dispatch、retry、cleanup |
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

其中业务日志要求 message 自带上下文，例如：

```text
[trace_id=... job_id=... stage=convert_package message_id=... status=completed] result=/abs/path/result.docx
```

在线解析 callback 常见日志还包括：

```text
[trace_id=... job_id=... stage=submit_to_mineru message_id=... status=parsing] batch_id=... data_id=...
[trace_id=... job_id=... stage=process_callback message_id=... status=parsed] batch_id=... state=done
```

## `/health/ready` 应怎么看

最重要的字段分四类：

### readiness 分类

- `readiness_required_checks`：最小可运行链路必须满足的检查项名称。
- `readiness_non_blocking_checks`：能力或观察项，不阻塞最小启动。
- `deployment_init_ready`：必检项是否都通过。
- `readiness_blockers`：导致 `deployment_init_ready=false` 的原因。
- `readiness_warnings`：非阻塞提示，例如 MinerU token 缺失、翻译不可用或 stage spool 有遗留消息。

### 运行目录

- `jobs_dir_exists`
- `jobs_dir_writable`
- `artifact_root_writable`
- `artifact_disk_free_bytes`
- `stage_spool_dir_exists`
- `tmp_dir_exists`

### 版本化资产

- `template_docx_exists`
- `layout_config_exists`
- `subscript_config_exists`

### 翻译能力

- `mineru_api_token_configured`
- `pdf_submission_available`
- `openai_api_key_configured`
- `translation_prompt_exists`
- `translation_required_for_default_mode`
- `translation_client_configured`
- `translation_available`
- `translation_unavailable_reason`

### 当前实例状态

- `configured_repository_backend`
- `effective_repository_backend`
- `worker_mode`
- `stage_dispatcher`
- `stage_message_store`
- `artifact_storage`
- `stage_spool_pending_messages`
- `stage_spool_running_messages`
- `stage_spool_failed_messages`
- `stage_spool_replayable_messages`
- `stage_spool_running_stale_messages`
- `stage_spool_oldest_running_age_seconds`
- `stage_spool_needs_attention`
- `stage_spool_observation_status`
- `document_jobs_worker_backend`
- `document_jobs_celery_queue`
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

- `DOCUMENT_JOBS_WORKER_BACKEND` 不能是 `disabled`。
- `DOCUMENT_JOBS_WORKER_BACKEND=celery` 时必须配置 broker URL 和 queue。
- `AUTH_JWT_SECRET_KEY` 和内部账号来源不能为空。
- `MINERU_API_TOKEN`、`MINERU_CALLBACK_URL` 必须配置；callback URL 存在时 `MINERU_UID` 也必须配置。

开发态如果仍使用 `DOCUMENT_JOBS_WORKER_BACKEND=disabled`，会出现在 `p0_document_jobs_warnings` / `readiness_warnings`，但不会阻断 `deployment_init_ready`。
`document_jobs_running_stale_count`、`document_jobs_timed_out_count` 只做只读观察，不会重投递、取消或恢复任务。

## `/health/metrics` 应怎么看

`GET /api/v1/health/metrics` 返回 JSON 运维计数，不是 Prometheus 格式，也不暴露 token、payload、客户文件名或 artifact 本地绝对路径。当前主要字段：

- `metadata_store`：当前实际 jobs metadata store，取值 `file` / `database` / `mysql`。
- `artifact_storage`：当前 artifact adapter，取值 `local_file` / `local_object` / `s3`。
- `worker_mode` 和 `stage_dispatcher`：判断 API 是否同进程消费 stage。
- `jobs`：按 job status 聚合的任务数量。
- `stage_messages`：`pending` / `running` / `failed` 数量。
- `resources`：模板、术语规则集、翻译配置的版本数量和当前默认版本标签。
- `audit_events.total`：当前审计事件总数。

metrics 适合被脚本轮询或人工排障读取；如果后续接 Prometheus / OpenTelemetry，需要另起 feature，不在当前单实例基线里隐式引入。

## Stage message 恢复语义

当前支持两种 worker 形态：

- `JOBS_WORKER_MODE=in_process`：默认模式，API 进程通过 `BackgroundTasks` 同进程推进 stage。
- `JOBS_WORKER_MODE=external`：API 只写入 stage message，`run_worker.py` 独立轮询并消费。

stage message 的持久化语义：

| 状态 | 语义 | replay 规则 | 保留规则 |
|---|---|---|---|
| `pending` | 已写入 spool，尚未被 dispatcher 尝试执行 | 应在启动恢复或显式 replay 时执行 | 成功后删除，失败后改为 `failed` |
| `running` | 已被 dispatcher claim，可能因进程退出残留 | 仍允许 replay；dispatch 前会先按 job 当前状态做幂等跳过 | 成功后删除，失败后改为 `failed` |
| `failed` | stage 已知失败，错误信息已写入 message 和 job events | 不自动 replay | 保留诊断现场，后续通过 retry/cancel 等运维动作处理 |

`lease_owner`、`leased_at`、`lease_expires_at` 是 worker readiness 字段。当前独立
worker 仍按单 worker 进程设计，不把它们当成多 worker 抢占锁；`/health/ready`
会用它们识别过期 `running` message。

## 典型排障

### 场景 1：上传成功，但任务不推进

先看：

- `stage_spool_pending_messages`
- `stage_spool_running_messages`
- `stage_spool_failed_messages`
- `GET /api/v1/jobs/{job_id}/events`

如果 `stage_spool_pending_messages > 0` 或 `stage_spool_running_messages > 0`，说明有后台消息还没完成，重启应用会 replay。
如果 `stage_spool_failed_messages > 0`，说明有失败消息留存在 spool 中；它不会被启动 replay 自动恢复，需要通过 job 详情、events 和 retry 决定下一步。
如果 `stage_spool_running_stale_messages > 0`，说明存在已经超过 lease 的 `running` message；`in_process` 模式通常可以先重启服务触发 replay，`external` 模式应先确认 `run_worker.py` 进程是否存活，再结合 job events 判断是否需要 retry。
`stage_spool_observation_status=ok` 表示没有遗留消息，`replayable` 表示有 pending/running 消息可恢复，`needs_attention` 表示存在 failed 或 stale running 消息。

如果 `effective_repository_backend=database`，说明 jobs snapshot、events、files 和 stage messages 已经切到 sqlite metadata store；如果是 `mysql`，说明这些 metadata 已切到 MySQL metadata store。artifact 二进制看 `artifact_storage`：`local_file` 表示仍读写 job 本地目录，`local_object` 表示登记时会 shadow upload 到本地对象目录并优先从 `object_key` 下载，`s3` 表示 artifact 登记时会上传到 S3-compatible bucket，下载时返回临时重定向或对象流。

### 场景 2：`direct` 都跑不通

先看：

- `jobs_dir_writable`
- `template_docx_exists`
- `layout_config_exists`
- `subscript_config_exists`

这四个任意一个为 `false`，都足以让最小链路失败。

### 场景 2.1：`/api/v1/jobs/pdf` 直接返回 `503`

优先看：

- `mineru_api_token_configured`

如果它是 `false`，说明当前实例根本不允许做 PDF 在线提交。

### 场景 3：`en2zh` 失败

优先看：

- `translation_available`
- `translation_unavailable_reason`
- `translation_prompt_exists`
- job 事件里的 `error_code`
- job 事件里的 `translation_started/translation_completed/translation_failed`

当前最常见的是 `OPENAI_API_KEY` 未配置。

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
