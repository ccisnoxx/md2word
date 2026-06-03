# Document job files and results design

## Current State

`document-jobs` 已有任务创建、详情、事件、重试、取消、归档和生成 Word 下载授权。`files` 已有单文件元数据查询，但任务详情页目前只展示源文件 ID、结果文件 ID 和请求快照；debug/log 文件 ID 只散落在事件 payload 或文件 metadata 中，前端没有统一文件区。

后端 `document_file_repository` 已能列出所有 `DocumentFileRecord`，Worker 生成的文件都会写入 `job_id`。创建任务时源 PDF 会回填 `job_id`，因此可以通过现有 metadata 做任务级薄汇总，不需要改存储结构。

## Scope

本子任务只补“任务详情内文件/结果/日志区”：

- backend：任务文件汇总 API、按 `file_id` 的任务文件临时下载授权。
- frontend：详情页文件/结果区和行级下载。
- tests：最小 API 回归和前端类型/构建验证。

不做独立文件管理、不做真实删除、不触发主流程、不扩展术语治理。

## Backend Contract

### `GET /api/v1/document-jobs/{job_id}/files`

Response:

```json
{
  "job_id": "docjob_xxx",
  "files": [
    {
      "id": "file_xxx",
      "tenant_id": "tenant_default",
      "company_id": "company_default",
      "job_id": "docjob_xxx",
      "file_type": "generated_word",
      "storage_provider": "local_object",
      "bucket": "local-object",
      "object_key": "...",
      "original_filename": "source.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "size_bytes": 1234,
      "checksum_sha256": "sha256:...",
      "etag": "...",
      "status": "uploaded",
      "expires_at": "2026-06-04T00:00:00Z",
      "metadata": {},
      "created_by": "user_operator",
      "created_at": "2026-06-03T00:00:00Z",
      "updated_at": "2026-06-03T00:00:00Z"
    }
  ]
}
```

Rules:

- First call existing `get_job(job_id, user=user)` so job visibility remains the source of truth.
- Return `DocumentFileResponse` records filtered by `job_id == job.id`, same tenant, same company.
- Sort by a stable role order, then `created_at`, then `id`, so UI rows do not jump.
- No persistence schema change.

### `GET /api/v1/document-jobs/{job_id}/download-url`

Existing behavior remains:

- Without `file_id`, return generated Word download authorization and keep the current 409 behavior until the job is succeeded.

New compatible behavior:

- With `file_id`, authorize a task file download for that exact file.
- Validate job visibility, file existence, file/task ownership, file type, `status == uploaded`, and `expires_at` not in the past.
- Return the existing `DocumentJobDownloadUrlResponse` shape.
- The existing signed `/api/v1/document-jobs/{job_id}/download?token=...` route streams the token file using that file's `mime_type` and `original_filename`.

Allowed task file types:

- `source_pdf`
- `mineru_raw_result`
- `document_ir`
- `image_asset`
- `generated_word`
- `ai_call_log`
- `ai_debug_archive`

## Frontend Contract

Files to change:

- `frontend/src/api/types.ts`
- `frontend/src/api/documentJobs.ts`
- `frontend/src/pages/JobDetailPage.vue`

UI behavior:

- `JobDetailPage` loads files together with job/events and refreshes them during polling.
- Add a `文件和结果` section between overview/failure information and request snapshot.
- Each row shows role label, file type, filename, file ID, size, status, expiration, and a row download button.
- Row download calls `documentJobsApi.createDownloadUrl(job.id, file.id)`.
- Top `JobActions` download keeps calling `documentJobsApi.createDownloadUrl(job.id)` for generated Word.
- Frontend computes display-only availability from `status` and `expires_at`; backend remains authoritative and may still reject the download.

## Data Flow

```text
JobDetailPage mount/refresh
  -> GET /document-jobs/{job_id}
  -> GET /document-jobs/{job_id}/events
  -> GET /document-jobs/{job_id}/files
  -> render task file rows

Row download
  -> GET /document-jobs/{job_id}/download-url?file_id={file_id}
  -> backend validates job/file contract
  -> frontend opens temporary URL
```

## Compatibility

- Existing API clients that call `/download-url` without `file_id` are unaffected.
- Existing `DocumentJobDownloadUrlResponse` shape is reused.
- OpenAPI changes are additive: one new response model and one optional query parameter.
- No existing job, file, event, or stage persisted JSON shape changes.

## Risks

- Generic task-file download exposes more artifact types to users who can view the task. This is acceptable for the internal Operator/Admin workbench, but the backend must keep the job visibility and file ownership checks centralized.
- AI debug archives may include full text when explicitly enabled. The UI must show expiration and rely on backend checks before issuing a link.
- Listing files by scanning `list_document_files()` is simple and consistent with current repository patterns, but it is not optimized for very large file stores. This is acceptable for Phase 1.
