# File retention file library search governance design

## Existing Context

- `DocumentFileRepositoryProtocol` exposes `list_document_files()` and concrete adapters already support file/sqlite/mysql metadata backends.
- `/api/v1/files/retention/plan`, `/storage/usage`, retention policy CRUD, and selected physical-delete preview/execution already exist.
- `FileRetentionPage.vue` is the current Admin operations page for retention and storage readiness.
- Existing retention candidate responses include `object_key`, but this slice intentionally does not expose object locators in the general file library.

## API Contract

Add:

```text
GET /api/v1/files/library/search
```

Query parameters:

- `page`, default `1`, `ge=1`
- `page_size`, default `50`, `ge=1`, `le=200`
- `sort`, default `created_at_desc`
- `q`
- `file_type`
- `status`
- `storage_provider`
- `job_id`
- `created_by`
- `expires_from`
- `expires_to`
- `created_from`
- `created_to`

Sort values:

- `created_at_desc`
- `created_at_asc`
- `updated_at_desc`
- `updated_at_asc`
- `expires_at_desc`
- `expires_at_asc`
- `size_bytes_desc`
- `size_bytes_asc`

Response:

```json
{
  "generated_at": "2026-06-06T00:00:00+00:00",
  "page": 1,
  "page_size": 50,
  "total": 1,
  "sort": "created_at_desc",
  "items": [
    {
      "file_id": "file_x",
      "job_id": "job_x",
      "file_type": "generated_word",
      "storage_provider": "local_object",
      "original_filename": "result.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "size_bytes": 123,
      "status": "expired",
      "expires_at": "2026-06-01T00:00:00+00:00",
      "created_by": "user_admin",
      "created_at": "2026-06-01T00:00:00+00:00",
      "updated_at": "2026-06-01T00:00:00+00:00",
      "expired": true,
      "physical_delete_candidate": true
    }
  ],
  "filters": {"status": "expired"}
}
```

## Projection Rules

Allowed row fields:

- file id and job id
- file type, storage provider, status
- original filename and mime type
- size and timestamps
- created_by
- derived booleans: `expired`, `physical_delete_candidate`

Forbidden row fields:

- `object_key`
- `bucket`
- `checksum_sha256`
- `etag`
- `metadata`
- local absolute paths
- file bytes
- signed URLs

## Data Flow

```text
HTTP query -> DocumentFileLibraryQuery -> DocumentFileLibrarySearchService
  -> repository.list_document_files()
  -> filter/sort/page/project
  -> FileLibrarySearchResponse -> FileRetentionPage.vue
```

The first version uses in-memory filtering through the existing repository port. This avoids changing all file/sqlite/mysql adapters and keeps the task compatible with current persistence contracts.

## Frontend

- Add a "文件库搜索" section to `/system-status/file-retention`.
- Provide compact filters for free-text, status, file type, storage provider, job id, sort, and page size.
- Show safe row fields only.
- Include a copyable `file_id` display but no direct delete/download controls.
- Existing physical deletion remains selected-file-only via the retention candidate table and delete-preview contract.

## Safety

- Admin-only through `require_admin_user`.
- No mutation and no audit event by default, matching other read-only list endpoints.
- No object locator exposure.
- No implicit linking to object storage or local filesystem.
- No broad bulk action.

## Risks

- In-memory scan is acceptable for Phase 4 first version. If production metadata volume grows, a later task can add repository-level indexed search.
- Some admins may want object locators for debugging; that remains intentionally out of scope for this general library.
