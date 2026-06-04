---
doc_type: lib-api-ref
entry: files
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/files/router.py
  - app/domains/files/schemas.py
  - app/domains/files/models.py
  - app/domains/files/retention.py
  - app/domains/files/service.py
summary: Files API 提供 PDF 上传授权、本地代理上传、文件 metadata 查询和 Admin-only metadata 保留期管理。
tags: [files, api, pdf, upload]
last_reviewed: 2026-06-04
---

## 概述

Files API 挂在 `/api/v1/files` 下，当前只面向登录用户。P0 PDF -> Word 流程先通过它登记并上传 PDF，再把返回的 `file_id` 传给 `/api/v1/document-jobs`。

保留期管理接口只面向 Admin，用于查看或标记过期 metadata。它不删除本地文件、不删除对象存储对象、不移除 `object_key`，也不触发 PDF 解析、翻译或 Word 生成流程。

## API 参考

### `POST /api/v1/files/upload-url`

- 用途：为 PDF 创建上传授权。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `filename` | 是 | 原始文件名。 |
| `mime_type` | 否 | 默认 `application/pdf`。 |
| `size_bytes` | 是 | 文件大小。 |
| `file_type` | 否 | 当前默认 `source_pdf`。 |
| `checksum_sha256` | 否 | `sha256:<hex>`。 |
| `job_id` | 否 | 可选关联任务。 |

- 响应：`201 Created`，包含 `file_id`、`upload_url`、`method=PUT`、`headers`、`expires_at`、`object_key`、`max_bytes` 和 `file`。
- 成功动作写入 `file.upload_authorize` audit event。

### `PUT /api/v1/files/{file_id}/content`

- 用途：本地代理上传 PDF 内容。
- 请求体：PDF 二进制。
- 关键行为：
  - 请求体不能超过 `JOBS_UPLOAD_MAX_BYTES`。
  - 本地代理上传需要继续带 Bearer token。
  - 成功后文件状态变为可用于创建 document job。
- 响应：`201 Created`，返回 `file`。
- 成功动作写入 `file.upload_content` audit event。

### `GET /api/v1/files/{file_id}`

- 用途：读取文件 metadata。
- 响应：`DocumentFileResponse`。

### `GET /api/v1/files/retention/plan`

- 用途：读取 `document_files` 保留期 dry-run 计划。
- 认证：Bearer JWT，Admin only。
- 行为：
  - 基于 `expires_at` 选择过期候选。
  - `deleted` 状态文件不会进入候选。
  - 不修改 metadata。
  - 不删除任何本地文件或对象存储对象。
- 响应：`FileRetentionPlanResponse`。

关键字段：

| 字段 | 说明 |
|---|---|
| `generated_at` | 计划生成时间。 |
| `retention_days` | 当前后端配置的保留天数。 |
| `deletion_supported` | 当前固定为 `false`。 |
| `action_mode` | `dry_run`。 |
| `totals` | `files_seen`、`candidate_files`、`candidate_local_files`、`candidate_objects` 等计数。 |
| `candidates` | 过期候选文件 metadata，包含 `file_id`、`job_id`、`file_type`、`storage_provider`、`object_key`、`size_bytes`、`status`、`expires_at` 和 `reason`。 |

### `POST /api/v1/files/retention/mark-expired`

- 用途：把当前过期候选中仍为 `uploaded` 的文件 metadata 标记为 `expired`。
- 认证：Bearer JWT，Admin only。
- 行为：
  - 不删除任何本地文件或对象存储对象。
  - 不删除任务、文件 metadata 记录或 `object_key`。
  - 不触发任务处理主流程。
  - 成功动作写入 `file.retention_mark_expired` audit event。
- 响应：`FileRetentionPlanResponse`，其中：
  - `action_mode=mark_expired`
  - `marked_file_ids` 为本次从 `uploaded` 标记为 `expired` 的文件 ID。

## 与 document_jobs 的关系

`POST /api/v1/document-jobs` 的 `source_file_id` 必须来自已成功上传的 `source_pdf` 文件。调用方不应绕过 Files API 直接构造 object key。
