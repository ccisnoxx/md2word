# Document job files and results implementation plan

## Review Gate

Do not start implementation until the user reviews this scope/design and approves moving the task from planning to in_progress.

## Files Expected To Change

- `app/domains/document_jobs/schemas.py`
- `app/domains/document_jobs/service.py`
- `app/domains/document_jobs/router.py`
- `frontend/src/api/types.ts`
- `frontend/src/api/documentJobs.ts`
- `frontend/src/pages/JobDetailPage.vue`
- `tests/test_fastapi_jobs_backend.py`

No persistence adapter, migration, worker, MinerU client, translation provider, or Word renderer changes are planned.

## Checklist

1. Backend schemas
   - Add `DocumentJobFileListResponse`.
   - Add optional `file_id` query handling to download URL route without changing response shape.

2. Backend service
   - Add `list_files_for_job(job_id, user)`.
   - Add selected-file download validation for task artifacts.
   - Keep existing generated Word-only path as the default when `file_id` is omitted.
   - Ensure expired or non-uploaded files return 409, missing files return 404, mismatched files return 403/409 according to existing API style.

3. Backend router
   - Add `GET /api/v1/document-jobs/{job_id}/files`.
   - Reuse `_build_document_file_response`.
   - Update local signed download route to stream the authorized file's MIME type and filename.

4. Backend tests
   - Cover completed eager job file listing.
   - Cover `download-url?file_id=...` for a source PDF or generated artifact.
   - Cover operator cannot list another operator's task files; admin can.
   - Cover mismatched or unavailable file rejection if it can be done without broad setup.

5. Frontend API/types
   - Add `DocumentJobFileListResponse`.
   - Add `documentJobsApi.listFiles(jobId)`.
   - Extend `createDownloadUrl(jobId, fileId?)`.

6. Frontend page
   - Add files loading state and error propagation.
   - Render the `文件和结果` section with stable role/type labels.
   - Use `formatBytes` and existing date formatting.
   - Keep the existing top action panel unchanged.

7. Validation
   - Run targeted backend unittest:
     `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
   - Run frontend build:
     `npm run build` in `frontend/`
   - If OpenAPI snapshot drift is surfaced by validation, regenerate with:
     `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`

## Rollback Points

- If generic file download creates unexpected compatibility risk, keep `GET /document-jobs/{job_id}/files` and remove the optional `file_id` extension, leaving only generated Word download enabled.
- If frontend scope grows, ship the API plus a compact metadata table first; defer richer grouping or previews.
