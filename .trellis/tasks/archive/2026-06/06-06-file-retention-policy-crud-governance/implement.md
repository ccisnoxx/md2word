# File retention policy CRUD governance implementation

## Classification

- Type: behavior-changing product feature.
- Public contract change: additive Admin-only Files API endpoints and frontend controls.
- Persistence change: additive policy repositories for file/sqlite/mysql backends.
- Main-flow risk: bounded to new file `expires_at` calculation through an injected resolver.
- Destructive-operation risk: no new destructive operation; physical delete remains on the existing separate safety contract.

## Implemented Work

1. Backend policy domain
   - Added `FileRetentionPolicyRecord`, lifecycle/status literals, validation, effective policy model, impact-preview model, repository protocol, and `FileRetentionPolicyService`.
   - Enforced draft-only update, reason-required lifecycle actions, default switching, fallback resolution, and dry-run impact preview.

2. Persistence
   - Added file backend JSON storage at `var/config/file_retention_policies.json`.
   - Added sqlite and mysql `file_retention_policies` tables.
   - Wired repositories into `PersistenceAdapters` and `AppRuntime`.

3. Upload expiration integration
   - Injected `retention_days_resolver` into `FileUploadService`.
   - Applied policy resolution to new `source_pdf` upload authorization.
   - Applied policy resolution to generated file registration when explicit `expires_at` is absent.
   - Preserved explicit `expires_at` override behavior.

4. Backend schemas and routes
   - Added policy request/response schemas.
   - Added Admin-only routes for list/detail/create/update/impact-preview/publish/set-default/disable.
   - Kept policy routes before `/{file_id}`.
   - Kept impact preview read-only.

5. Audit
   - Added compact write audit events for create/update/publish/set-default/disable.
   - Kept impact preview unaudited by default.

6. Frontend
   - Added policy API wrappers and response/request types.
   - Extended `/system-status/file-retention` with policy summary, list, create/edit dialog, lifecycle actions, and impact preview panel.
   - Kept policy controls separate from physical delete controls.

7. Documentation
   - Updated `docs/api/files.md`.
   - Updated `docs/api/openapi.json`.
   - Fixed touched physical-delete docs to use implemented outcomes such as `deletable` and `skipped_unsupported_storage`.

## Verification Plan

Run before finish/archive:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_crud_is_admin_only_and_audited tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_impact_preview_and_default_selection_do_not_backfill tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_applies_to_new_uploads_and_preserves_fallback
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_plan_is_admin_only_and_reports_dry_run_candidates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_mark_expired_updates_metadata_without_removing_object tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_requires_reason_and_confirmation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_rejects_invalid_file_ids tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_removes_expired_local_object_and_marks_deleted tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_treats_missing_local_object_as_idempotent tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_missing_object_key tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_uploaded_without_deleting
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention
npm --prefix frontend run build
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff
python3 ./.trellis/scripts/task.py validate 06-06-file-retention-policy-crud-governance
git diff --check
```

## Observed Verification

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_crud_is_admin_only_and_audited tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_impact_preview_and_default_selection_do_not_backfill tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_policy_applies_to_new_uploads_and_preserves_fallback` passed: 3 tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_plan_is_admin_only_and_reports_dry_run_candidates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_mark_expired_updates_metadata_without_removing_object tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_requires_reason_and_confirmation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_rejects_invalid_file_ids tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_removes_expired_local_object_and_marks_deleted tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_treats_missing_local_object_as_idempotent tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_missing_object_key tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_uploaded_without_deleting` passed: 10 tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention` passed: 2 tests.
- `npm --prefix frontend run build` passed; observed existing Rollup PURE annotation warnings and chunk-size warning.
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff` passed.
- `python3 ./.trellis/scripts/task.py validate 06-06-file-retention-policy-crud-governance` passed.
- `git diff --check` passed.

## Rollback Points

- If upload expiration behavior regresses, remove the resolver injection and keep policy CRUD/preview as read-only governance.
- If persistence compatibility regresses in sqlite/mysql, keep file backend policy storage and split sqlite/mysql into a follow-up migration task.
- If frontend scope proves unstable, keep backend API/docs/tests and reduce UI to read-only list plus manual API usage.

## Non-Execution Reminder

Do not run pdf-mineru parsing, real translation provider calls, Word generation, scheduled cleanup, quota enforcement, cross-task file search, backend audit export, real S3 deletion, or physical-delete execution outside the existing non-destructive tests.
