---
doc_type: dev-guide
slug: runtime-observability-and-health
component: runtime-observability
status: current
summary: 说明当前后端的 access/business/system 日志分层和 health readiness 字段。
tags: [backend, logging, health, observability]
last_reviewed: 2026-05-18
---

## 日志分层

当前后端约定三类日志：

| 通道 | 用途 | 典型来源 |
|---|---|---|
| `access` | 请求访问日志 | `trace_logging_middleware` |
| `business` | 带 job 上下文的业务链路日志 | stage dispatch、retry、cleanup |
| `system` | 无业务上下文或第三方库日志 | `uvicorn`、`httpx`、`python_multipart`、异常堆栈 |

## 当前日志格式

统一格式：

```text
{time} | {logger_name} | {level} | {message}
```

其中业务日志要求 message 自带上下文，例如：

```text
[trace_id=... job_id=... stage=convert_package status=completed] result=/abs/path/result.docx
```

在线解析 callback 常见日志还包括：

```text
[trace_id=... job_id=... stage=submit_to_mineru status=parsing] batch_id=... data_id=...
[trace_id=... job_id=... stage=process_callback status=parsed] batch_id=... state=done
```

## `/health/ready` 应怎么看

最重要的字段分三类：

### 运行目录

- `jobs_dir_exists`
- `jobs_dir_writable`
- `stage_spool_dir_exists`
- `tmp_dir_exists`

### 版本化资产

- `template_docx_exists`
- `layout_config_exists`
- `subscript_config_exists`

### 翻译能力

- `mineru_api_token_configured`
- `openai_api_key_configured`
- `translation_prompt_exists`
- `translation_client_configured`
- `translation_available`
- `translation_unavailable_reason`

### 当前实例状态

- `stage_spool_pending_messages`
- `deployment_init_ready`
- `deployment_init_missing_steps`

## 典型排障

### 场景 1：上传成功，但任务不推进

先看：

- `stage_spool_pending_messages`
- `GET /api/v1/jobs/{job_id}/events`

如果 `stage_spool_pending_messages > 0`，说明有后台消息还没完成，重启应用会 replay。

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
