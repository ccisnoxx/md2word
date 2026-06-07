# Phase 6 S3 delete LocalStack fake parity contract implementation plan

## Checklist

- [x] Read current file-retention S3 fake delete, integration control, Ops API/schema, dashboard, tests, and docs.
- [x] Add an Ops S3 delete contract service with LocalStack/fake parity evidence and safety flags.
- [x] Add Pydantic response schemas and Admin-only router endpoint.
- [x] Update integration control plane S3 safe config while keeping real deletion blocked.
- [x] Add frontend API types/wrapper and read-only Ops Dashboard panel.
- [x] Add backend tests for Admin-only read-only behavior, fake parity, and control-plane blocked status.
- [x] Update API docs and OpenAPI snapshot.
- [x] Run focused backend/frontend validation.
- [x] Run Trellis validation and archive.

## Verification Commands

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_s3_delete_adapter_contract_is_admin_only_readonly_and_keeps_real_delete_blocked tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_s3_fake_delete_preview_matches_ops_s3_adapter_contract`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_integration_capabilities_are_admin_only_and_disabled_by_default tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_integration_capabilities_report_enabled_quota_without_external_side_effects tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_integration_capabilities_report_provider_cancellation_semantics_verified_but_blocked`
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- `/Users/sc/miniconda3/envs/md2word/bin/python -c "from scripts.ops.export_openapi import check_openapi_export, format_pretty_report; report = check_openapi_export(include_diff=False); print(format_pretty_report(report)); raise SystemExit(0 if report.ok else 1)"`
- `(cd frontend && npm run build)`
- `python3 ./.trellis/scripts/task.py validate 06-07-phase6-s3-delete-localstack-contract`
- `git diff --check`

## Verification Results

- Backend S3 contract tests: passed, 2 tests.
- Integration control related tests: passed, 3 tests.
- OpenAPI export: passed, snapshot changed and was regenerated.
- OpenAPI current check: passed, `changed=false`.
- Frontend build: passed from `frontend/`; Rollup emitted existing chunk-size and pure-annotation warnings.
- `git diff --check`: passed.
- Trellis validation: passed.
- Full `scripts/ops/check_release.py`: not run; it includes broader database/release targets outside this slice.

## Rollback

Remove the new Ops endpoint, schemas, frontend panel/API wrapper, tests, docs/OpenAPI updates, and the S3 safe-config additions. Existing file-retention S3 fake delete behavior should remain untouched.
