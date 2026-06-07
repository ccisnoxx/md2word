# Phase 6 Integration Control Plane Implementation

## Checklist

- [x] Create Trellis task artifacts.
- [x] Read backend specs and existing Ops/dashboard code.
- [x] Add backend settings, service, schemas, and route.
- [x] Add targeted backend tests.
- [x] Add frontend API/types and Ops Dashboard panel.
- [x] Update docs/OpenAPI.
- [x] Run targeted backend tests, OpenAPI export/tests, frontend build, Trellis validate, and `git diff --check`.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_integration_capabilities_are_admin_only_and_disabled_by_default \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_integration_capabilities_report_enabled_quota_without_external_side_effects
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate .trellis/tasks/06-07-phase6-integration-control-plane
git diff --check
```

## Non-execution Reminder

Do not call real provider cancellation, MinerU recovery query/download, alert delivery, pdf-mineru parsing, real translation providers, Word generation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.

## Verification Results

- PASS: targeted integration control-plane backend tests.
- PASS: quota enforcement regression tests for ready block and Admin override.
- PASS: OpenAPI export; `path_count=124`, `schema_count=242`.
- PASS: `tests.test_openapi_export`.
- PASS: `npm --prefix frontend run build`.
- PASS: Trellis validate.
- PASS: `git diff --check`.
