---
doc_type: lib-api-ref
entry: health
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/health.py
  - app/services/health_service.py
  - app/schemas/api_v1.py
summary: Health API 提供 liveness、readiness 和运行时依赖状态检查。
tags: [health, api, ops]
last_reviewed: 2026-05-18
---

## 概述

Health API 当前有三条入口：

- `GET /api/v1/health/live`：只确认进程可响应。
- `GET /api/v1/health/ready`：返回 readiness 和运行时依赖检查。
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
  "jobs_dir": "/abs/path/data/jobs",
  "dependency_checks": {
    "configured_repository_backend": "file",
    "effective_repository_backend": "file",
    "jobs_dir_exists": true,
    "jobs_dir_writable": true,
    "stage_spool_dir_exists": true,
    "stage_spool_pending_messages": 0,
    "tmp_dir_exists": true,
    "template_docx_exists": true,
    "layout_config_exists": true,
    "subscript_config_exists": true,
    "translation_prompt_exists": true,
    "mineru_api_token_configured": true,
    "openai_api_key_configured": true,
    "openai_base_url_configured": true,
    "openai_model": "deepseek-v4-flash",
    "default_translation_mode": "direct",
    "translation_client_configured": true,
    "translation_available": true,
    "deployment_init_ready": true,
    "deployment_init_missing_steps": []
  }
}
```

## 字段说明

| 字段 | 说明 |
|---|---|
| `configured_repository_backend` | 当前配置期望的仓储后端；现阶段固定为 `file` |
| `effective_repository_backend` | 当前真实可用的仓储后端；现阶段固定为 `file` |
| `jobs_dir_exists` | `data/jobs/` 是否存在 |
| `jobs_dir_writable` | 运行态根目录是否可写 |
| `stage_spool_dir_exists` | `data/stage_messages/` 是否存在 |
| `stage_spool_pending_messages` | 当前尚未消费的 stage spool 文件数量 |
| `tmp_dir_exists` | `data/tmp/` 是否存在 |
| `template_docx_exists` | 默认 Word 模板是否可读 |
| `layout_config_exists` | 页面布局 YAML 是否可读 |
| `subscript_config_exists` | 术语上下标 YAML 是否可读 |
| `translation_prompt_exists` | `prompt/translation_en2zh.md` 是否存在 |
| `mineru_api_token_configured` | 是否配置 `MINERU_API_TOKEN` |
| `openai_api_key_configured` | 是否配置 `OPENAI_API_KEY` |
| `openai_base_url_configured` | 是否显式配置 `OPENAI_BASE_URL` |
| `openai_model` | 当前默认翻译模型名 |
| `default_translation_mode` | 当前默认转换模式 |
| `translation_client_configured` | 翻译客户端是否具备最小配置 |
| `translation_available` | 当前 `en2zh` 分支是否可用 |
| `translation_unavailable_reason` | 翻译不可用时的原因 |
| `deployment_init_ready` | 当前实例是否已满足最小运行条件 |
| `deployment_init_missing_steps` | 若未 ready，缺少哪些步骤 |

## 典型排障

- `jobs_dir_writable=false`
  - 说明当前进程没有权限写运行态目录，上传和转换都会失败。
- `template_docx_exists=false`
  - 说明默认模板缺失，`direct` 和 `en2zh` 都无法成功生成 DOCX。
- `translation_available=false`
  - 说明 `translation_mode=en2zh` 目前不可用，优先检查 `OPENAI_API_KEY`。
- `translation_prompt_exists=false`
  - 说明翻译 prompt 资源缺失，`en2zh` 会被预检拒绝。
- `mineru_api_token_configured=false`
  - 说明 `POST /api/v1/jobs/pdf` 当前不可用，系统只能接收 MinerU 已完成的输出 zip。
- `stage_spool_pending_messages>0`
  - 说明有上次未完成的后台 stage；应用启动时会尝试 replay。
