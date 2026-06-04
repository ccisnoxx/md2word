# Document job bulk APIs Implementation Plan

## Gate

Do not run `task.py start` or edit business code until this scope is reviewed.

## Checklist

1. Add backend schemas
   - Add bulk request, item result, and response models in `app/domains/document_jobs/schemas.py`.
   - Keep class docstrings concise and Chinese, matching current source style.

2. Add backend routes
   - Add `bulk-retry`, `bulk-archive`, and `bulk-cancel` routes before `/{job_id}` routes.
   - Use existing `runtime.document_job_service` single-task methods.
   - Convert `ApiError` into per-item failures for item-level errors.
   - Keep malformed batch payload errors as normal HTTP errors.
   - Record existing audit actions for each successful item.

3. Add tests
   - Extend `tests/test_fastapi_jobs_backend.py`.
   - Use runtime setup that does not execute eager document job pipeline for retry validation.
   - Verify success counts, failure item shape, persisted job status, events, and audit records.

4. Add frontend API surface
   - Add TypeScript bulk request/response types.
   - Add `documentJobsApi.bulkRetry`, `bulkArchive`, and `bulkCancel`.
   - Switch `JobsPage` current batch retry/archive handlers to use bulk responses.
   - Do not add a bulk cancel button.

5. Update API docs
   - Update `docs/api/document-jobs.md`.
   - Regenerate `docs/api/openapi.json` with `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`.

6. Minimal verification
   - Run targeted backend unittest for document_jobs API coverage.
   - Run frontend typecheck/build only if the project script is available and reasonably scoped.

## Rollback

- Remove the three bulk routes and schema models.
- Revert frontend wrappers and `JobsPage` calls to the existing `Promise.allSettled()` single-task behavior.
- Restore `docs/api/openapi.json` by regenerating from the reverted API.
