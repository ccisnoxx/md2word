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
summary: Document Jobs API 提供 P0 PDF -> Word 任务创建、查询、事件、重试、取消、归档和下载入口。
tags: [document-jobs, api, pdf, word]
last_reviewed: 2026-06-03
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
| `debug_full_text` | 否 | 是否保留全文调试信息。 |

- 响应：`201 Created`，包含 `job_id`、`status`、`stage`、`progress` 和完整 `job`。
- 成功动作写入 `document_job.create` audit event。

### `GET /api/v1/document-jobs`

- 用途：分页查询任务列表。
- 查询参数：`page`、`page_size`、`status`。
- 响应：`items`、分页信息和 `summary`。

### `GET /api/v1/document-jobs/{job_id}`

- 用途：读取任务详情。
- 响应：`DocumentJobResponse`，包括状态、阶段、进度、中间产物 file id、失败诊断字段、retry count 和 request snapshot。

### `GET /api/v1/document-jobs/{job_id}/events`

- 用途：读取任务事件。
- 响应：事件列表，包含 `stage`、`level`、`event_type`、`message`、`payload`、`duration_ms` 和 `trace_id`。

### `POST /api/v1/document-jobs/{job_id}/retry`

- 用途：对失败任务重试。
- 请求体可包含 `reason`、`use_latest_term_assets` 和术语资产选择字段。
- 成功动作写入 `document_job.retry` audit event。

### `POST /api/v1/document-jobs/{job_id}/cancel`

- 用途：取消可取消任务。
- 成功动作写入 `document_job.cancel` audit event。

### `DELETE /api/v1/document-jobs/{job_id}`

- 用途：归档任务。
- 成功动作写入 `document_job.archive` audit event。

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
