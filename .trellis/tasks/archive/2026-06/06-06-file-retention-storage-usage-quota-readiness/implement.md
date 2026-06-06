# File retention storage usage quota readiness implementation

## Classification

- Type: behavior-changing product feature, but read-only operational reporting.
- Current task state: in_progress.
- Public contract change: additive Admin-only Files API endpoint and frontend UI section.
- Persistence change: no table or metadata schema change.
- Destructive-operation risk: none; implementation remains read-only.
- Main-flow risk: low; upload authorization, conversion, parsing, translation, Word generation, policy publishing, mark-expired, and physical delete behavior are unchanged.

## Implemented Work

1. Backend domain model/service
   - Added `app/domains/files/storage_usage.py`.
   - Added records for totals, groups, reclaim summary, quota readiness, and response report.
   - Reads only `DocumentFileRepositoryProtocol.list_document_files()`.
   - Uses `size_bytes` as metadata-estimated usage.
   - Does not crawl the filesystem or verify object existence.

2. Quota readiness
   - Did not add quota env settings in this slice.
   - Returns `quota.status=not_configured`.
   - Keeps quota advisory-only and disconnected from upload authorization.

3. Runtime and readiness context
   - Uses `HealthService.build_dependency_checks()` for artifact storage backend, root writable state, and disk free bytes.
   - Does not expose local absolute artifact paths.

4. Backend schemas and route
   - Added `FileStorageUsageResponse` and `FileStorageUsageGroupResponse`.
   - Added `GET /api/v1/files/storage/usage` before `/{file_id}`.
   - Enforces Admin-only auth.
   - Does not record audit by default.

5. Frontend API/types
   - Added `FileStorageUsageResponse` and group types.
   - Added `filesApi.getStorageUsage()`.

6. Frontend page
   - Extended `/system-status/file-retention`.
   - Added storage usage cards and grouped tables.
   - Kept storage usage separate from physical-delete controls.
   - Did not auto-select rows from reclaim summary.

7. Documentation/OpenAPI
   - Updated `docs/api/files.md`.
   - Updated `docs/api/health.md`.
   - Regenerated `docs/api/openapi.json`.

8. Tests
   - Added API coverage in `tests/test_fastapi_jobs_backend.py` for Admin-only access, totals, reclaim categories, quota `not_configured`, and read-only behavior.

## Observed Verification

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_storage_usage_is_admin_only_readonly_and_reports_reclaim_estimates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_plan_is_admin_only_and_reports_dry_run_candidates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_mark_expired_updates_metadata_without_removing_object tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_requires_reason_and_confirmation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_rejects_invalid_file_ids tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_removes_expired_local_object_and_marks_deleted tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_treats_missing_local_object_as_idempotent tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_missing_object_key tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_uploaded_without_deleting` passed: 11 tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_crud_is_admin_only_and_audited tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_impact_preview_and_default_selection_do_not_backfill tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_applies_to_new_uploads_and_preserves_fallback` passed: 3 tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention` passed: 2 tests.
- `npm --prefix frontend run build` passed; observed existing Rollup PURE annotation warnings and chunk-size warning.
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff` passed after OpenAPI regeneration.

## Rollback Points

- If quota status creates ambiguity, keep usage/reclaim summary and remove quota card from UI.
- If runtime health-context reuse becomes tangled, return usage summary first and defer disk-free/writable context to a follow-up.
- If frontend scope grows, keep backend API/docs/tests and reduce UI to a minimal read-only card section.
- If full-list scans become too slow, do not add caching in this task; instead split a repository aggregation/indexing task.

## Definition Of Done For This Implementation Task

- [x] Task created and scoped.
- [x] `prd.md` written.
- [x] `design.md` written.
- [x] `implement.md` written.
- [x] Context manifests curated.
- [x] `task.py start` completed after review.
- [x] Backend/API implementation completed.
- [x] Frontend implementation completed.
- [x] Docs/OpenAPI updated.
- [x] Targeted backend and frontend verification passed.
- [x] `task.py validate` passes after implementation docs update.
- [x] `git diff --check` passes after implementation docs update.
- [x] Task is finished, archived, and committed after user request.

## Non-Execution Reminder

Do not run pdf-mineru parsing, real translation provider calls, Word generation, scheduled cleanup, quota enforcement, cross-task file search, backend audit export, real S3 deletion, metadata mutation beyond test fixture setup, mark-expired execution outside tests, or physical-delete execution outside non-destructive safety tests.
