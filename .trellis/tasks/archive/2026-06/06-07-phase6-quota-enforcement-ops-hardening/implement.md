# Phase 6 quota enforcement ops hardening implementation

## Checklist

- [x] Add quota ops summary dataclasses and service method.
- [x] Add API schemas and Admin-only route.
- [x] Add backend tests for Admin-only/read-only/rollback and audit replay.
- [x] Add frontend API/types and File Retention UI panel.
- [x] Update files API docs and OpenAPI snapshot.
- [x] Run targeted backend, OpenAPI, frontend, Trellis, and diff checks.

## Validation commands

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_ops_summary_is_admin_only_readonly_and_reports_rollback tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_ops_summary_replays_block_and_override_audits`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_ready_blocks_upload_authorization_and_audits tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_admin_override_allows_upload_and_audits`
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- `npm --prefix frontend run build`
- `python3 ./.trellis/scripts/task.py validate phase6-quota-enforcement-ops-hardening`
- `git diff --check`
