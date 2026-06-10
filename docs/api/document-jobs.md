---
doc_type: lib-api-ref
entry: document-jobs
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/document_jobs/router.py
  - app/domains/document_jobs/schemas.py
  - app/domains/document_jobs/models.py
  - app/domains/document_jobs/service.py
  - app/domains/document_jobs/execution.py
summary: Document Jobs API 提供 P0 PDF -> Word 任务创建、查询、事件、重试、clone、取消、归档和下载入口。
tags: [document-jobs, api, pdf, word]
last_reviewed: 2026-06-09
---

## 概述

Document Jobs API 挂在 `/api/v1/document-jobs` 下，是当前 P0 PDF -> Word 工作台和 Golden Sample 回归使用的主链路。

典型流程：

```text
POST /api/v1/files/upload-url
PUT /api/v1/files/{file_id}/content
POST /api/v1/document-jobs
GET /api/v1/document-jobs/{job_id}
GET /api/v1/document-jobs/{job_id}/events
GET /api/v1/document-jobs/{job_id}/translation-qa
PATCH /api/v1/document-jobs/{job_id}/translation-qa
GET /api/v1/document-jobs/config-summary
POST /api/v1/document-jobs/bulk-retry
POST /api/v1/document-jobs/{job_id}/clone
POST /api/v1/document-jobs/bulk-archive
POST /api/v1/document-jobs/bulk-cancel
POST /api/v1/document-jobs/{job_id}/unarchive
GET /api/v1/document-jobs/{job_id}/download-url
GET /api/v1/document-jobs/{job_id}/download?token=...
```

## 枚举

### `mode`

| 值 | 含义 |
|---|---|
| `direct_pdf_to_word` | P0 默认路径，直接生成 Word。 |
| `en2zh_pdf_to_word` | 实验能力，先翻译 DocumentIR 再生成 Word。 |

### 失败诊断字段

失败任务会在详情中返回：

- `failed_stage`
- `error_code`
- `error_message`

前端和联调脚本应优先用这三个字段定位上传、解析、IR、渲染或对象存储问题。

### `translation_qa_status`

| 值 | 含义 |
|---|---|
| `unreviewed` | 未复核。 |
| `approved` | 已通过。 |
| `needs_fix` | 需要修正或跟进。 |
| `blocked` | 阻塞或无法判断。 |

该状态只用于 `en2zh_pdf_to_word` 翻译 QA。列表筛选传 `translation_qa_status` 时，后端只返回 `en2zh_pdf_to_word` 且状态匹配的任务，避免把 direct 任务的默认值误当成翻译 QA 待办。

## API 参考

### `POST /api/v1/document-jobs`

- 用途：用已上传 PDF 创建转换任务。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `source_file_id` | 是 | 来自 Files API 的 source PDF file id。 |
| `mode` | 否 | 默认 `direct_pdf_to_word`。 |
| `document_language` | 否 | `auto` / `zh` / `en`，默认 `auto`。 |
| `template_version_id` | 否 | 模板版本选择。 |
| `term_version_id` | 否 | 兼容术语版本字段。 |
| `term_rule_set_id` | 否 | 术语规则集。 |
| `term_rule_set_version` | 否 | 术语规则集版本。 |
| `translation_term_set_id` | 否 | 翻译术语集。 |
| `translation_term_version` | 否 | 翻译术语集版本。 |
| `translation_profile_id` | 否 | 翻译配置 ID，仅 Admin 可显式选择。 |
| `translation_profile_version` | 否 | 翻译配置版本，仅 Admin 可显式选择。 |
| `debug_full_text` | 否 | 是否保留全文调试信息。 |

- 响应：`201 Created`，包含 `job_id`、`status`、`stage`、`progress` 和完整 `job`。
- 成功动作写入 `document_job.create` audit event。
- 权限：Operator 只能使用默认配置；显式传 `template_version_id`、`term_version_id`、术语资产、翻译术语资产或翻译配置选择字段会返回 `403`。Admin 可绑定 published 资源版本。

### `GET /api/v1/document-jobs/config-summary`

- 用途：读取创建/重试任务所需的配置摘要。
- 认证：Bearer JWT。
- 响应：
  - `role`
  - `resource_mode`：`legacy` / `versioned`
  - `defaults`：默认 Template、Term Rule Set、Translation Term Set、Translation Profile 摘要
  - `options`：Admin 可选 published 版本；Operator 返回空列表
  - `readiness`：创建任务前的只读配置状态
    - `en2zh_available`：默认翻译术语集和翻译配置是否可用。
    - `p0_document_jobs_required`：当前环境是否要求 P0 document_jobs 自动执行链路通过门禁。
    - `p0_document_jobs_ready`：P0 document_jobs 自动执行链路是否通过门禁。
    - `document_jobs_worker_backend`：`disabled` / `celery` / `eager`。
    - `document_jobs_automatic_execution_enabled`：当前 worker backend 是否会自动执行任务。
    - `blockers`：P0 门禁阻断项，上传页应在 required 且 not ready 时阻止创建任务。
    - `warnings`：非阻塞 warning。
- 语义：只读聚合接口，不修改默认指针、不导入导出术语、不触发任务处理。

### `GET /api/v1/document-jobs`

- 用途：分页查询任务列表。
- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `page` | `1` | 从 `1` 开始。 |
| `page_size` | `20` | 当前限制 `1-100`。 |
| `status` | 无 | 按任务状态过滤。 |
| `translation_qa_status` | 无 | 按翻译 QA 状态过滤；仅匹配 `en2zh_pdf_to_word` 任务。 |
| `q` | 无 | 按任务 ID、源文件 ID、源文件名、错误码或错误信息搜索。 |
| `sort` | `created_at_desc` | `created_at_desc` / `created_at_asc` / `updated_at_desc` / `updated_at_asc`。 |
| `include_archived` | `false` | 是否包含已归档任务。 |
| `created_from` | 无 | 按创建时间下界过滤，ISO datetime。 |
| `created_to` | 无 | 按创建时间上界过滤，ISO datetime。 |

- 响应：`items`、分页信息和 `summary`。

### `GET /api/v1/document-jobs/{job_id}`

- 用途：读取任务详情。
- 响应：`DocumentJobResponse`，包括状态、阶段、进度、中间产物 file id、失败诊断字段、retry count、`source_job_id`、request snapshot 和 `available_actions`。
- `available_actions` 是服务端对当前用户和任务状态的操作可用性判断，键包括 `download`、`retry`、`cancel`、`archive`、`unarchive`、`clone`。每个 action 返回：

| 字段 | 说明 |
|---|---|
| `enabled` | 当前用户能否执行该动作。 |
| `disabled_reason` | 禁用原因；`enabled=true` 时为 `null`。 |

### `GET /api/v1/document-jobs/{job_id}/events`

- 用途：读取任务事件。
- 响应：事件列表，包含 `stage`、`level`、`event_type`、`message`、`payload`、`duration_ms` 和 `trace_id`。

### `GET /api/v1/document-jobs/{job_id}/translation-qa`

- 用途：读取翻译结果 QA 证据摘要和任务级复核状态。
- 支持范围：仅 `en2zh_pdf_to_word` 任务具备翻译 QA 证据；其他模式返回 `available=false` 和 `availability_reason=unsupported_mode`。
- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `limit` | `200` | 返回最终文本片段数量，限制 `1-500`。 |

- 响应包含：
  - `qa`：任务级复核状态、问题归因、备注、复核人和复核时间。
  - `artifacts`：`document_ir`、`ai_call_log`、`ai_debug_archive` 文件 ID 摘要。
  - `summary`：最终片段数、返回片段数、quality flags、AI call 数、术语 trace 数和源文对照可用性。
  - `segments`：从 `document_ir` 读取的最终文本片段；只有 debug archive 存在且未过期时才带源文/AI 译文对照。
  - `term_traces`：从 `ai_call_log` 读取的脱敏术语命中摘要。
  - `ai_calls`：metadata-only AI 调用摘要，不包含完整 prompt、response、正文或密钥。
- 证据读取只消费已登记文件，不触发 PDF 解析、翻译 provider 调用或 Word 生成。

### `PATCH /api/v1/document-jobs/{job_id}/translation-qa`

- 用途：保存任务级翻译 QA 复核结论。
- 支持范围：仅 `en2zh_pdf_to_word` 任务；其他模式返回 `409 conflict`。
- 请求体：

| 字段 | 必填 | 说明 |
|---|---|---|
| `status` | 是 | `unreviewed` / `approved` / `needs_fix` / `blocked`。 |
| `issue_type` | 否 | `translation` / `terminology` / `layout` / `source_quality` / `artifact_missing` / `other`。 |
| `note` | 否 | 备注，最多 1000 字符。 |

- 返回：`job_id`、最新 `qa` 和最新 `job`。
- 事件：成功保存会写入 `translation_qa_updated` 任务事件，payload 只包含状态、问题归因、复核人和备注长度，不写入全文正文、prompt、response 或密钥。

### `POST /api/v1/document-jobs/{job_id}/retry`

- 用途：对失败任务重试。
- 请求体可包含 `reason`、`use_latest_term_assets` 和术语资产选择字段。
- 成功动作写入 `document_job.retry` audit event。
- 权限：Operator 只能提交原因并沿用原配置；Admin 可选择使用最新默认术语资产或指定 published 术语资产。Retry 当前不重新绑定模板或翻译配置。
- 边界：Retry 只用于失败任务原地重试，不创建新任务，不等同于 clone。

### `POST /api/v1/document-jobs/{job_id}/clone`

- 用途：基于已有任务源 PDF 创建一个新的 document job，语义是 “rerun as new job”。
- 行为：不会修改源任务，不增加源任务 `retry_count`，不会把源文件归属改到新任务；新任务的 `source_job_id` 指向源任务。
- 请求体：

| 字段 | 必填 | 说明 |
|---|---|---|
| `reason` | 否 | 操作原因。 |
| `config_strategy` | 否 | `keep_source_snapshot` / `use_current_defaults` / `select_published_versions`，默认 `keep_source_snapshot`。 |
| `document_language` | 否 | 覆盖新任务文档语言；未传则沿用源任务。 |
| `template_version_id` | 否 | 仅 `select_published_versions` 下可传，Admin-only。 |
| `term_rule_set_id` / `term_rule_set_version` | 否 | 仅 `select_published_versions` 下可传，Admin-only。 |
| `translation_term_set_id` / `translation_term_version` | 否 | 仅 `select_published_versions` 下可传，Admin-only。 |
| `translation_profile_id` / `translation_profile_version` | 否 | 仅 `select_published_versions` 下可传，Admin-only。 |
| `debug_full_text` | 否 | 覆盖新任务 debug 全文开关。 |

- 成功：`201 Created`，返回 `source_job_id`、新 `job_id` 和完整新 `job`，并写入 `job_cloned` 任务事件和 `document_job.clone` audit event。
- 失败：源 PDF 不存在、不可见、过期或不是 uploaded source PDF 时返回 404/403/409；Operator 传显式资源版本返回 403。

### `POST /api/v1/document-jobs/bulk-retry`

- 用途：批量重试失败任务。
- 请求体：`job_ids` 加单任务 retry 的现有选项字段。
- 行为：逐个复用单任务 retry 语义，支持部分成功；不会因为某个任务失败而阻断后续任务。
- 成功项写入 `document_job.retry` audit event。
- 响应：`action=retry`、`total`、`succeeded`、`failed`、`items`。

单个 `items` 元素：

| 字段 | 说明 |
|---|---|
| `job_id` | 本次处理的任务 ID。 |
| `ok` | 单项是否成功。 |
| `status_code` | 成功为 `200`，失败为单任务接口对应 HTTP 状态。 |
| `error_code` | 失败时返回稳定错误码，成功为 `null`。 |
| `detail` | 失败原因，成功为 `null`。 |
| `job` | 成功时返回最新任务摘要，失败为 `null`。 |

### `POST /api/v1/document-jobs/{job_id}/cancel`

- 用途：取消可取消任务。
- 成功动作写入 `document_job.cancel` audit event。

### `POST /api/v1/document-jobs/bulk-cancel`

- 用途：批量取消 pending / queued / running 任务。
- 请求体：`job_ids`。
- 行为：逐个复用单任务 cancel 语义；取消只标记任务为 `canceled` 并停止后续处理，不承诺强制中断已进入外部服务的长任务。
- 成功项写入 `document_job.cancel` audit event。
- 响应结构同 `bulk-retry`，`action=cancel`。

### `DELETE /api/v1/document-jobs/{job_id}`

- 用途：归档任务。
- 成功动作写入 `document_job.archive` audit event。
- 边界：归档不是删除，不删除源文件、结果文件、debug/log 文件或事件。

### `POST /api/v1/document-jobs/{job_id}/unarchive`

- 用途：取消归档，让任务重新出现在默认列表中。
- 行为：清空 `archived_at` / `archived_by`，保留所有文件和事件；未归档任务调用该接口是幂等 no-op。
- 成功动作写入 `document_job.unarchive` audit event，并写入 `job_unarchived` 任务事件。

### `POST /api/v1/document-jobs/bulk-archive`

- 用途：批量归档 succeeded / failed / canceled 终态任务。
- 请求体：`job_ids`。
- 行为：逐个复用单任务 archive 语义；归档只从默认列表隐藏任务，不删除源文件、结果文件、debug/log 文件或事件。
- 成功项写入 `document_job.archive` audit event。
- 响应结构同 `bulk-retry`，`action=archive`。

### 批量请求校验

三个批量接口都会对请求整体做校验：

- `job_ids` 为空：`400 invalid_request`。
- `job_ids` 超过 50 个：`400 invalid_request`。
- `job_ids` 包含重复或空白项：`400 invalid_request`。

通过整体校验后，单个任务的 `404`、`403`、`409` 等错误进入对应 item，不改变批量响应的 `200 OK`。

### `GET /api/v1/document-jobs/{job_id}/download-url`

- 用途：为成功任务生成临时下载链接。
- 响应包含 `download_url`、`method=GET`、`expires_at` 和结果文件 metadata。
- 成功动作写入 `document_job.download_authorize` audit event。

### `GET /api/v1/document-jobs/{job_id}/download`

- 用途：使用 `download-url` 返回的短期 token 下载 Word。
- 本地文件缺失返回 404，token 无效或过期返回 403。

## 当前边界

- `direct_pdf_to_word` 是 P0 默认发布路径。
- `en2zh_pdf_to_word` 仍按实验能力处理，不阻塞 P0 direct 发布。
- Golden Sample 当前仍 blocked：正式规模和人工质量验收尚未完成。
