# Phase 5 release readiness and commit prep design

## Boundary

This task is a release-prep audit. It should only add Trellis evidence files. It should not change runtime behavior or commit anything.

Excluded from execution:

- pdf-mineru parsing.
- MinerU recovery query/download.
- translation provider calls.
- Word generation.
- real alert delivery.
- real provider cancellation.
- real S3 deletion.
- quota enforcement.
- autonomous destructive scheduler.
- git stage/commit/push.

## Audit Inputs

- `git status --short`
- `git diff --stat`
- `git diff --name-status`
- archived Phase 5 Trellis tasks under `.trellis/tasks/archive/2026-06/`
- existing acceptance reports:
  - `phase5-production-ops-acceptance-closeout`
  - `phase5-s3-deletion-safety-contract-fake-adapter`
- API docs and OpenAPI snapshot:
  - `docs/api/files.md`
  - `docs/api/ops.md`
  - `docs/api/manifest.yaml`
  - `docs/api/openapi.json`
- frontend changed pages/wrappers under `frontend/src/`
- backend changed files under `app/`
- tests under `tests/`
- CodeStable artifacts under `.codestable/`

## Worktree Classification

Use these buckets:

1. Release scope
   - backend Phase 5 runtime/API/persistence/test/docs/frontend changes.
2. Evidence scope
   - Trellis archived task directories.
3. Planning scope
   - `.codestable/features/...`
   - `.codestable/roadmap/...`
4. Local config / review separately
   - `.codex/config.toml`
   - any file not clearly tied to Phase 5 acceptance evidence.

## Verification Plan

Run safe checks only:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_audits_and_dedupes_without_external_delivery \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_fake_cancel_audits_dedupes_and_does_not_mutate_jobs \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_destination_dry_run_is_admin_only_readonly_and_masks_secrets \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_dry_run_reports_would_block_without_side_effects \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_preview_and_execute_records_history \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_signed_plan_blocks_tampering \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_scheduler_dry_run_manual_runner_records_history_and_releases_lock \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_skips_s3_without_mutating_metadata

/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend \
  tests.test_database_job_repository.PersistenceAdapterTests.test_cleanup_lock_service_enforces_fencing_and_expiry

/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-release-readiness-and-commit-prep
git diff --check
```

Do not run full conversion tests or browser flows unless the safe checks expose a frontend integration uncertainty.

## Commit Prep Output

The report should recommend grouping, not execute it. Suggested grouping shape:

1. Backend safety contracts and persistence.
2. Ops/File Retention frontend controls.
3. API docs/OpenAPI/tests.
4. Trellis archive evidence.
5. CodeStable planning artifacts, only if intended for the branch.

## Git Index Lock Handling

Previous Trellis archives reported:

```text
git add failed: fatal: Unable to create '.git/index.lock': Operation not permitted
```

This task should not attempt to force-write `.git`. It may read `.git/index.lock` existence/metadata if allowed and should record that staging/commit must be handled separately or with an approved environment that can write `.git`.
