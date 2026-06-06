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
summary: Files API 提供 PDF 上传授权、本地代理上传、文件 metadata 查询、Admin-only metadata 保留期管理和受保护的过期文件物理删除。
tags: [files, api, pdf, upload, retention]
last_reviewed: 2026-06-06
---

## 概述

Files API 挂在 `/api/v1/files` 下，当前只面向登录用户。P0 PDF -> Word 流程先通过它登记并上传 PDF，再把返回的 `file_id` 传给 `/api/v1/document-jobs`。

保留期管理接口只面向 Admin，用于查看或标记过期 metadata，并在显式 dry-run 后人工执行本地过期文件物理删除。它不删除任务、文件 metadata 记录、审计记录或 `object_key`，也不触发 PDF 解析、翻译或 Word 生成流程。当前物理删除只支持 `local_file` 和 `local_object`，`s3` 会返回 unsupported 结果而不会执行真实对象存储删除。

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
| `deletion_supported` | 是否存在后端支持的本地物理删除入口。 |
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

### `POST /api/v1/files/retention/delete-preview`

- 用途：对人工选中的 `document_files` 执行物理删除 dry-run。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `file_ids` | 是 | 非空文件 ID 列表，单次最多 50 个，不能重复。 |

- 行为：
  - 不修改 metadata。
  - 不删除本地文件或对象存储对象。
  - 不写入 `file.retention_physical_delete` audit event。
  - 仅 `status=expired` 且 `expires_at <= now` 的 `local_file` 或 `local_object` 会返回 `would_delete`。
  - `uploaded`、未过期、已删除、缺失、无 `object_key` 或 `s3` provider 均返回对应 skip/unsupported outcome。
- 响应：`FileRetentionDeleteResponse`，其中 `action_mode=delete_preview`，并返回每个文件的 outcome、reason、provider、object_key、size_bytes 和是否将修改 metadata。

### `POST /api/v1/files/retention/delete-expired`

- 用途：对人工选中且已 dry-run 核对的过期本地文件执行物理删除。
- 认证：Bearer JWT，Admin only。
- 请求体：JSON。

| 字段 | 必填 | 说明 |
|---|---|---|
| `file_ids` | 是 | 非空文件 ID 列表，单次最多 50 个，不能重复。 |
| `reason` | 是 | 操作原因，不能为空，用于 audit event。 |
| `confirmation` | 是 | 必须精确等于 `DELETE EXPIRED FILES`。 |

- 行为：
  - 只会删除 `status=expired`、`expires_at <= now`、provider 为 `local_file` 或 `local_object` 且路径位于受管存储目录下的对象。
  - 成功删除或本地对象已不存在时，将对应 metadata `status` 更新为 `deleted`，但保留 metadata row、`object_key`、任务、事件和审计记录。
  - `s3` provider 当前返回 `unsupported_provider`，不会执行真实 S3 删除。
  - 非 `expired`、未过期、无 `object_key`、未知文件或路径越界会返回 skip/error outcome，不会删除对象。
  - 成功动作写入 `file.retention_physical_delete` audit event，reason 会包含人工原因和汇总计数。
- 响应：`FileRetentionDeleteResponse`，其中 `action_mode=delete_execute`。

常见 outcome：

| outcome | 说明 |
|---|---|
| `would_delete` | 预览模式下符合物理删除条件。 |
| `deleted` | 执行模式下本地对象已删除，metadata 已标记为 `deleted`。 |
| `already_missing` | 执行模式下本地对象已不存在，metadata 已标记为 `deleted`，用于幂等收口。 |
| `skipped_not_expired_status` | metadata 状态不是 `expired`。 |
| `skipped_not_expired_time` | `expires_at` 仍晚于当前时间。 |
| `skipped_unsupported_storage` | provider 当前不支持物理删除，例如 `s3`。 |
| `skipped_missing_object_key` | 本地 provider 文件缺少 `object_key`。 |
| `failed` | 路径解析、metadata 更新或本地删除失败。 |

## 与 document_jobs 的关系

`POST /api/v1/document-jobs` 的 `source_file_id` 必须来自已成功上传的 `source_pdf` 文件。调用方不应绕过 Files API 直接构造 object key。
