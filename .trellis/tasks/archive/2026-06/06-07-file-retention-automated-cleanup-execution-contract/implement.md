# File retention automated cleanup execution contract implementation

## Classification

- Type: behavior-changing backend Ops feature.
- Risk: destructive local file deletion, mitigated by existing physical-delete contract plus cleanup-run preview hash and confirmation.
- Public contract change: additive Admin-only Files API endpoints.
- Frontend change: none planned.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, `implement.md`.
   - [x] Run `task.py validate`.
   - [x] Run `task.py start`.

2. Backend schemas
   - [x] Add cleanup run preview/execute request models.
   - [x] Add cleanup run safety and response models.

3. Backend service
   - [x] Add `app/domains/files/cleanup_execution.py`.
   - [x] Build cleanup preview from `FileUploadService.preview_retention_physical_delete()`.
   - [x] Compute stable preview hash.
   - [x] Execute by validating hash and calling `FileUploadService.execute_retention_physical_delete()`.
   - [x] Keep S3 unsupported through existing physical-delete semantics.

4. Backend routes
   - [x] Add `POST /api/v1/files/retention/cleanup-runs/preview`.
   - [x] Add `POST /api/v1/files/retention/cleanup-runs/execute`.
   - [x] Keep routes before `/{file_id}`.
   - [x] Record compact audit for execute only.

5. Recovery action registry
   - [x] Mark `file_retention.automated_cleanup_execute` available for this manual cleanup-run execution contract.
   - [x] Preserve scheduler loop as a known gap.

6. Tests
   - [x] Admin-only preview and no mutation.
   - [x] Execute requires reason, confirmation, matching hash.
   - [x] Execute removes eligible local/local_object and marks deleted through existing physical-delete semantics.
   - [x] S3 is skipped without deletion/metadata mutation.
   - [x] Re-run against already deleted targets is safe.
   - [x] Registry exposes updated cleanup action contract.

7. Docs/OpenAPI
   - [x] Update `docs/api/files.md` and `docs/api/ops.md`.
   - [x] Run OpenAPI check.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_preview_is_admin_only_and_readonly tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_execute_reuses_physical_delete_contract_and_audits tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_guards_hash_limits_and_registry_contract
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff
python3 ./.trellis/scripts/task.py validate 06-07-file-retention-automated-cleanup-execution-contract
git diff --check
```

Run `npm --prefix frontend run build` only if frontend files change.

## Verification Results

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_preview_is_admin_only_and_readonly tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_execute_reuses_physical_delete_contract_and_audits tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_cleanup_run_guards_hash_limits_and_registry_contract` passed.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_removes_expired_local_object_and_marks_deleted tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_registry_is_admin_only_readonly_and_lists_safety_flags` passed.
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff` passed after exporting the additive schema update.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export` passed.
- Frontend build was not run because no frontend files changed.

## Rollback

- Remove `app/domains/files/cleanup_execution.py`.
- Remove cleanup-run schemas and routes.
- Restore `file_retention.automated_cleanup_execute` registry entry to unavailable.
- Remove tests/docs/OpenAPI updates.

## Non-execution Reminder

Do not add a scheduler loop, real S3 delete, provider cancellation, alert delivery, MinerU recovery, pdf-mineru parsing, real translation providers, or Word generation.
