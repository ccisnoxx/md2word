# File retention physical delete safety contract implementation plan

## Classification

- Type: behavior-changing product feature.
- Risk: destructive local file deletion, mitigated by explicit safety gates.
- Public contract change: yes, two Admin-only Files API endpoints and frontend controls.
- Storage behavior: local/local_object binaries can be removed; metadata rows are retained and marked `deleted`.
- Main-flow risk: low if scope is respected; must not trigger parsing, translation, Word generation, retry, recovery, or legacy cleanup.

## Ordered Checklist

1. Backend schemas
   - Add `FileRetentionDeletePreviewRequest`.
   - Add `FileRetentionDeleteExecuteRequest`.
   - Add `FileRetentionDeleteItemResponse`.
   - Add `FileRetentionDeleteResponse`.

2. Backend deletion service
   - Implement selected-file preview and execution.
   - Validate exact `file_ids`, non-empty IDs, duplicates, and batch limit 50.
   - Validate execution reason and confirmation phrase.
   - Require `status=expired` and `expires_at <= now`.
   - Support only `local_file` and `local_object`.
   - Resolve local paths via existing `FileUploadService.resolve_local_object_path()`.
   - Mark metadata `deleted` only after local deletion or idempotent missing object.

3. Backend routes
   - Add `POST /api/v1/files/retention/delete-preview`.
   - Add `POST /api/v1/files/retention/delete-expired`.
   - Keep static routes before `/{file_id}`.
   - Record compact audit event only for execution.

4. Backend tests
   - Add tests in `tests/test_artifact_retention.py` for pure planner/service behavior if logic is pure enough.
   - Add targeted API tests in `tests/test_fastapi_jobs_backend.py`:
     - Admin preview success and no mutation.
     - Operator forbidden.
     - Confirmation/reason validation.
     - Reject uploaded/direct deletion.
     - Delete expired local object and mark metadata deleted.
     - Missing object idempotency.
     - S3 unsupported leaves metadata unchanged.
     - Audit event recorded.

5. Frontend API/types
   - Add TypeScript types matching backend schemas.
   - Add Files API wrappers.

6. Frontend page
   - Add row selection to `FileRetentionPage.vue`.
   - Add preview action and outcome table.
   - Add delete dialog with reason and confirmation phrase.
   - Keep metadata-only copy visible.
   - Ensure S3 unsupported/skipped outcomes are visible.

7. Documentation/OpenAPI
   - Update `docs/api/files.md`.
   - Run OpenAPI check; regenerate snapshot only if needed.

8. Verification
   - Run targeted backend tests.
   - Run frontend build.
   - Run OpenAPI check.
   - Run `task.py validate`.
   - Run `git diff --check`.

## Verification Commands

Use the project conda interpreter:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_requires_reason_and_confirmation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_rejects_invalid_file_ids tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_removes_expired_local_object_and_marks_deleted tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_treats_missing_local_object_as_idempotent tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_missing_object_key tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_uploaded_without_deleting
npm --prefix frontend run build
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff
python3 ./.trellis/scripts/task.py validate 06-06-file-retention-physical-delete-safety-contract
git diff --check
```

If test method names differ after implementation, run the nearest targeted retention tests. Do not run pdf-mineru parsing, real translation provider calls, Word generation, retry, recovery, legacy cleanup, scheduled cleanup, or real S3 deletion.

## Rollback Points

- If frontend scope grows, ship backend API/docs/tests first and leave UI unchanged.
- If local deletion behavior is risky, keep preview endpoint only and remove execution route before merge.
- If audit reason is too narrow, record compact counts in this task and split structured audit details into a follow-up.
- If route ordering conflicts with `/{file_id}`, remove new static routes and re-add under a non-conflicting static prefix.

## Definition Of Done

- [x] Planning artifacts written and validated.
- [x] Task started with `task.py start` before code edits.
- [x] Backend preview and execution endpoints implemented exactly within scope.
- [x] Frontend manual controls implemented without broad file-library expansion.
- [x] Targeted verification passes.
- [x] No conversion workflow, legacy cleanup, scheduled cleanup, or real S3 deletion executed.

## Implementation Notes

- Backend adds Admin-only `POST /api/v1/files/retention/delete-preview` and `POST /api/v1/files/retention/delete-expired`.
- Execution requires exact confirmation phrase `DELETE EXPIRED FILES`, non-empty reason, non-empty unique IDs, and a 50-file batch cap.
- Eligibility is re-read per selected file and requires `status=expired`, `expires_at <= now`, supported local provider, and non-empty `object_key`.
- Local/local_object paths are resolved against the storage provider recorded on each metadata row and guarded against root escape.
- Successful deletion and eligible already-missing local objects retain metadata rows and `object_key` while moving status to `deleted`.
- `s3` remains unsupported and is never deleted in this task.
- Frontend adds selected-row preview, delete dialog, reason, confirmation phrase, and per-file outcome table on `/system-status/file-retention`.
- Docs and OpenAPI were updated for the additive contract.
- Spec update: `.trellis/spec/backend/database-guidelines.md` now records dry-run-first `document_files` physical retention deletion and the rule that S3 deletion requires a provider-specific safety contract.

## Verification Run

- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_requires_reason_and_confirmation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_rejects_invalid_file_ids tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_removes_expired_local_object_and_marks_deleted tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_treats_missing_local_object_as_idempotent tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_missing_object_key tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_uploaded_without_deleting`
- Passed: `npm --prefix frontend run build`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff`
- Passed: `python3 ./.trellis/scripts/task.py validate 06-06-file-retention-physical-delete-safety-contract`
- Passed: `git diff --check`
