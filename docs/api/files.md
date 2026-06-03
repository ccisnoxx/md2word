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
  - app/domains/files/service.py
summary: Files API 提供 PDF 上传授权、本地代理上传和文件 metadata 查询，是 P0 document_jobs 的输入入口。
tags: [files, api, pdf, upload]
last_reviewed: 2026-06-03
---

## 概述

Files API 挂在 `/api/v1/files` 下，当前只面向登录用户。P0 PDF -> Word 流程先通过它登记并上传 PDF，再把返回的 `file_id` 传给 `/api/v1/document-jobs`。

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

## 与 document_jobs 的关系

`POST /api/v1/document-jobs` 的 `source_file_id` 必须来自已成功上传的 `source_pdf` 文件。调用方不应绕过 Files API 直接构造 object key。
