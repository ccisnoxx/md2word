---
doc_type: lib-api-ref
entry: health
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/health.py
  - app/api/v1/routers/health_schemas.py
  - app/services/health_service.py
summary: Health API 提供 liveness、readiness、运行时依赖状态检查、JSON metrics 和 Admin-only 运维告警 readiness。
tags: [health, api, ops]
last_reviewed: 2026-06-06
---

## 概述

Health API 当前有五条入口：

- `GET /api/v1/health/live`：只确认进程可响应。
- `GET /api/v1/health/ready`：返回 readiness 和运行时依赖检查。
- `GET /api/v1/health/metrics`：返回 JSON 运维计数。
- `GET /api/v1/health/ops-alerts`：Admin-only，只读返回运维告警 readiness 和建议入口。
- `GET /api/v1/health`：兼容入口，当前语义等同 `/ready`。

## API 参考

### `GET /api/v1/health/live`

- 用途：轻量存活检查。
- 请求参数：无
- 响应示例：

```json
{
  "status": "ok",
  "app_name": "md2word_file"
}
```

### `GET /api/v1/health/ready`

- 用途：返回运行时依赖和当前是否已具备最小可运行条件。
- 请求参数：无
- 响应示例：

```json
{
  "status": "ok",
  "app_name": "md2word_file",
  "deployment": {
    "environment": "prod",
    "public_deployment_mode": "internal",
    "version": "2026.06.17-p2",
    "deployment_id": "hostdzire-20260617-p2",
    "started_at": "2026-06-17T00:00:00+00:00"
  },
  "jobs_dir": "/abs/path/var/jobs",
  "dependency_checks": {
    "configured_repository_backend": "file",
    "effective_repository_backend": "file",
    "worker_mode": "in_process",
    "document_jobs_worker_backend": "celery",
    "document_jobs_celery_queue": "document-jobs",
    "document_jobs_translation_batch_celery_queue": "document-translation-batches",
    "stage_dispatcher": "background_tasks",
    "stage_message_store": "file",
    "artifact_storage": "local_file",
    "jobs_dir_exists": true,
    "jobs_dir_writable": true,
    "artifact_root_writable": true,
    "artifact_disk_free_bytes": 1000000000,
    "stage_spool_dir_exists": true,
    "stage_spool_pending_messages": 0,
    "stage_spool_running_messages": 0,
    "stage_spool_failed_messages": 0,
    "stage_spool_running_stale_messages": 0,
    "stage_spool_oldest_running_age_seconds": 0,
    "stage_spool_needs_attention": false,
    "tmp_dir_exists": true,
    "template_docx_exists": true,
    "layout_config_exists": true,
    "subscript_config_exists": true,
    "translation_prompt_exists": true,
    "mineru_api_token_configured": true,
    "openai_api_key_configured": true,
    "openai_base_url_configured": true,
    "openai_model": "deepseek-v4-flash",
    "translation_provider_backend": "openai_compatible",
    "translation_debug_archive_enabled": true,
    "default_translation_mode": "direct",
    "translation_client_configured": true,
    "translation_available": true,
    "default_template_version": "default@1",
    "default_term_rule_version": "electronics-default@1",
    "default_translation_profile_version": "electronics-en2zh@1",
    "mysql_schema_bootstrap_available": true,
    "deployment_init_ready": true,
    "deployment_init_missing_steps": []
  }
}
```

### `GET /api/v1/health/metrics`

- 用途：返回内部运维 JSON 计数；不是 Prometheus 格式。
- 请求参数：无
- 响应示例：

```json
{
  "status": "ok",
  "app_name": "md2word_file",
  "generated_at": "2026-05-29T00:00:00+00:00",
  "deployment": {
    "environment": "prod",
    "public_deployment_mode": "internal",
    "version": "2026.06.17-p2",
    "deployment_id": "hostdzire-20260617-p2",
    "started_at": "2026-06-17T00:00:00+00:00"
  },
  "metadata_store": "mysql",
  "artifact_storage": "local_file",
  "worker_mode": "in_process",
  "stage_dispatcher": "background_tasks",
  "jobs": {
    "completed": 12,
    "failed": 1
  },
  "stage_messages": {
    "pending": 0,
    "running": 0,
    "failed": 1
  },
  "resources": {
    "template_versions": 2,
    "term_rule_set_versions": 3,
    "translation_profile_versions": 1,
    "default_template_version": "default@1",
    "default_term_rule_version": "electronics-default@1",
    "default_translation_profile_version": "electronics-en2zh@1"
  },
  "audit_events": {
    "total": 24
  }
}
```

### `GET /api/v1/health/ops-alerts`

- 用途：返回 Ops Dashboard 使用的只读运维告警 readiness 合同。
- 鉴权：Bearer JWT，必须是 `admin` 角色；兼容 legacy `X-Admin-Token`，用于线上 gate 脚本读取只读告警证据。
- 安全边界：不执行 retry、cancel、archive、replay、recover、cleanup、physical delete、provider call、notification delivery，也不默认写 audit event。
- 响应示例：

```json
{
  "status": "needs_attention",
  "app_name": "md2word_file",
  "generated_at": "2026-06-06T00:00:00+00:00",
  "summary": {
    "readiness_blockers": 0,
    "readiness_warnings": 2,
    "stage_failed_messages": 1,
    "stage_stale_running_messages": 1,
    "stage_replayable_messages": 2,
    "failed_jobs": 1,
    "running_jobs": 1,
    "worker_mode": "in_process",
    "stage_dispatcher": "background_tasks",
    "stage_message_store": "file",
    "artifact_storage": "local_file"
  },
  "alerts": [
    {
      "code": "stage_spool_failed_messages_present",
      "severity": "critical",
      "source": "stage_spool",
      "title": "存在失败的阶段消息",
      "description": "失败的阶段消息不会自动重放，需要结合任务详情和事件流判断下一步。",
      "count": 1,
      "suggested_route": "/jobs?status=failed&sort=updated_at_desc",
      "suggested_action": "查看失败任务和事件；如需重试，使用既有任务流程手动处理。"
    }
  ],
  "safety": {
    "read_only": true,
    "writes_performed": false,
    "recovery_actions_executed": false,
    "provider_calls_executed": false,
    "notification_delivery_executed": false,
    "audit_events_written": false
  }
}
```

## 字段说明

| 字段 | 说明 |
|---|---|
| `deployment` | ready/metrics 共同返回的非敏感部署追踪对象，用于 P2 线上证据 |
| `deployment.environment` | 当前 `APP_ENV` |
| `deployment.public_deployment_mode` | 当前 `PUBLIC_DEPLOYMENT_MODE`，内部单租户默认仍为 `internal` |
| `deployment.version` | 当前 `APP_VERSION`，用于区分同步批次或发布版本 |
| `deployment.deployment_id` | 当前 `DEPLOYMENT_ID`；未设置时为 `null` |
| `deployment.started_at` | 当前 API 进程启动时间 |
| `configured_repository_backend` | 当前配置期望的 jobs metadata 后端；默认 `file`，可配置为 `database` 或 `mysql` |
| `effective_repository_backend` | 当前真实接入的 jobs metadata 后端；应与运行时实际 repository adapter 一致 |
| `worker_mode` | 当前 worker 模式；`in_process` 表示 API 同进程执行，`external` 表示独立 worker 消费 stage message |
| `document_jobs_worker_backend` | Document Jobs 自动执行 backend；生产基线为 `celery` |
| `document_jobs_celery_queue` | `document_jobs.run` 投递的 Celery 主任务队列；生产默认 `document-jobs` |
| `document_jobs_translation_batch_celery_queue` | `document_jobs.translate_batch` 投递的翻译批次队列；生产默认 `document-translation-batches`，worker 必须订阅该队列 |
| `stage_dispatcher` | 当前后台 stage 调度 adapter；`background_tasks` 或 `external_worker` |
| `stage_message_store` | 当前 stage message store adapter；随 jobs metadata backend 为 `file`、`database` 或 `mysql` |
| `artifact_storage` | 当前 artifact storage adapter；默认 `local_file`，可切换为 `local_object` 或 `s3` |
| `jobs_dir_exists` | `var/jobs/` 是否存在 |
| `jobs_dir_writable` | 运行态根目录是否可写 |
| `artifact_root_writable` | 当前 artifact 本地根目录是否可写；`local_file` 检查 jobs 目录，`local_object` 检查对象目录 |
| `artifact_disk_free_bytes` | 当前 artifact 本地根所在磁盘剩余字节数；这是运行时 readiness 上下文，不是 `document_files` 已用空间统计。文件 metadata 使用量和可回收空间估算见 `GET /api/v1/files/storage/usage` |
| `stage_spool_dir_exists` | stage spool 是否可用；file 模式检查 `var/stage_messages/`，database/mysql 模式表示数据库内 store 可用 |
| `stage_spool_pending_messages` | 当前 pending 的 stage message 数量；启动 replay 会尝试恢复 |
| `stage_spool_running_messages` | 当前 running 的 stage message 数量；启动 replay 会尝试恢复 |
| `stage_spool_failed_messages` | 当前 failed 的 stage message 数量；不会被启动 replay 自动恢复 |
| `stage_spool_running_stale_messages` | 当前 running 且 lease 已过期的 stage message 数量 |
| `stage_spool_oldest_running_age_seconds` | 最老 running stage message 距离最后更新时间的秒数 |
| `stage_spool_needs_attention` | 是否存在 failed 或 stale running stage message，需要人工关注 |
| `tmp_dir_exists` | `var/tmp/` 是否存在 |
| `template_docx_exists` | 默认 Word 模板是否可读 |
| `layout_config_exists` | 页面布局 YAML 是否可读 |
| `subscript_config_exists` | 术语上下标 YAML 是否可读 |
| `translation_prompt_exists` | `resources/prompts/translation_en2zh.md` 是否存在 |
| `mineru_api_token_configured` | 当前有效配置是否包含 MinerU API token；运行时文件优先，文件不存在时读取 `MINERU_API_TOKEN` |
| `mineru_config_source` | 当前密钥来源：`settings` 或 `runtime_config` |
| `mineru_config_updated_at` | 配置中心最近更新时间；环境变量来源时为 `null` |
| `mineru_config_error` | 运行时文件损坏时为 `mineru_config_invalid`，正常时为 `null` |
| `mineru_callback_url_configured` | 是否配置 `MINERU_CALLBACK_URL` |
| `mineru_uid_configured` | 是否配置 `MINERU_UID`，用于 callback checksum 验签 |
| `public_deployment_mode` | 当前公开部署模式；公开域名部署应为 `single_tenant_public` |
| `openai_api_key_configured` | 是否配置 `OPENAI_API_KEY` |
| `openai_base_url_configured` | 是否显式配置 `OPENAI_BASE_URL` |
| `openai_model` | 当前默认翻译模型名 |
| `translation_provider_backend` | 当前翻译 provider backend；`en2zh` 线上可用时应为 `openai_compatible` |
| `translation_debug_archive_enabled` | 是否允许 admin 为 `en2zh_pdf_to_word` 保存短期全文调试归档 |
| `default_translation_mode` | 当前默认转换模式 |
| `translation_client_configured` | 翻译客户端是否具备最小配置 |
| `translation_available` | 当前 `en2zh` 分支是否可用；需要 provider backend、OpenAI-compatible client 和翻译 prompt 同时可用 |
| `translation_unavailable_reason` | 翻译不可用时的原因 |
| `default_template_version` | MySQL resource mode 下当前默认 Template Version，形如 `{template_id}@{version}`；无默认值时为 `null` |
| `default_term_rule_version` | MySQL resource mode 下当前默认 Term Rule Version，形如 `{set_id}@{version}`；无默认值时为 `null` |
| `default_translation_profile_version` | MySQL resource mode 下当前默认 Translation Profile Version；无默认值时为 `null` |
| `mysql_schema_bootstrap_available` | 当前实例是否实际使用 MySQL metadata store 并完成启动期 schema bootstrap |
| `deployment_init_ready` | 当前实例是否已满足最小运行条件 |
| `deployment_init_missing_steps` | 若未 ready，缺少哪些步骤 |
| `status` | `/ops-alerts` 的整体状态；`needs_attention` 表示存在 critical 告警，`watch` 表示存在 warning/info 告警，`ok` 表示当前无告警 |
| `summary` | `/ops-alerts` 的稳定摘要，汇总 readiness、stage spool 和未归档 document_jobs 状态计数 |
| `alerts[]` | `/ops-alerts` 的告警列表；每项包含 `severity`、`source`、`code`、`count`、说明、建议路由和建议动作文本 |
| `safety` | `/ops-alerts` 的安全声明；当前合同必须保持只读且不执行恢复、写入、provider 或通知动作 |

## 典型排障

- `jobs_dir_writable=false`
  - 说明当前进程没有权限写运行态目录，上传和转换都会失败。
- `artifact_root_writable=false`
  - 说明当前 artifact 本地根不可写，新上传或对象 adapter shadow upload 可能失败。
- `template_docx_exists=false`
  - 说明默认模板缺失，`direct` 和 `en2zh` 都无法成功生成 DOCX。
- `translation_available=false`
  - 说明 `translation_mode=en2zh` 目前不可用，优先检查 `TRANSLATION_PROVIDER_BACKEND`、`OPENAI_API_KEY` 和翻译 prompt。
- `translation_prompt_exists=false`
  - 说明翻译 prompt 资源缺失，`en2zh` 会被预检拒绝。
- `mineru_api_token_configured=false`
  - 说明依赖 MinerU 的 `/api/v1/document-jobs` 异步解析不可用，创建任务会被预检拒绝或停留在等待恢复状态。
- `mineru_config_error=mineru_config_invalid`
  - 说明共享运行时文件不可读取或格式非法。系统不会回退环境变量，应由管理员进入 `/settings/mineru` 覆盖修复。
- `mineru_callback_url_missing`
  - 说明已配置 MinerU token 但未配置异步回调 URL，document_jobs 可能停在 `running/parsing` 等待重投递或人工恢复。
- `mineru_uid_missing`
  - 说明已启用 MinerU callback，但实例缺少 `MINERU_UID`，无法按官方 `uid + seed + content` 规则验签。
- `stage_spool_pending_messages>0`
  - 说明有上次未完成的后台 stage；应用启动时会尝试 replay。
- `stage_spool_failed_messages>0`
  - 说明存在失败的后台 stage message；需要结合 job 详情和 events 判断是否 retry。
- `stage_spool_running_stale_messages>0`
  - 说明存在超过 lease 的 running stage message；`in_process` 可先重启服务触发 replay，`external` 应检查 `scripts/dev/run_stage_worker.py` 进程是否仍在运行。
