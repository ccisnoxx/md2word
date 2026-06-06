# File retention scheduled cleanup readonly plan implementation

## Checklist

1. Add domain service
   - Add `app/domains/files/scheduled_cleanup.py`.
   - Generate `readonly_plan` reports from retention planner and storage usage reporter.
   - Keep output serializable and path-safe.
   - Status: done.

2. Add CLI script
   - Add `scripts/ops/run_file_retention_cleanup_readonly.py`.
   - Build runtime without creating app.
   - Print JSON to stdout by default.
   - Optionally write to `--output`.
   - Status: done.

3. Add tests
   - Add targeted tests in `tests/test_fastapi_jobs_backend.py` or a new unittest module.
   - Verify report contents.
   - Verify metadata and local object remain unchanged.
   - Verify optional output file is written.
   - Status: done.

4. Docs/Trellis
   - Update task docs with observed verification.
   - Keep this as implementation-only; no finish/archive/commit until requested.
   - Status: in progress.

## Verification

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_readonly_cleanup_runner_reports_without_mutation
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_readonly_cleanup_runner_reports_without_mutation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_storage_usage_is_admin_only_readonly_and_reports_reclaim_estimates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_plan_is_admin_only_and_reports_dry_run_candidates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate
python3 ./.trellis/scripts/task.py validate 06-06-file-retention-scheduled-cleanup-readonly-plan
git diff --check
```

Observed:

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_readonly_cleanup_runner_reports_without_mutation` passed.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_readonly_cleanup_runner_reports_without_mutation tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_storage_usage_is_admin_only_readonly_and_reports_reclaim_estimates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_plan_is_admin_only_and_reports_dry_run_candidates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate` passed.

## Rollback

- Remove CLI script and domain module if runner semantics become unsafe.
- Keep existing retention API untouched.

## Non-Execution Reminder

Do not run pdf-mineru parsing, real translation providers, Word generation, mark-expired outside tests, physical deletion, S3 deletion, quota enforcement, or scheduler loops.
