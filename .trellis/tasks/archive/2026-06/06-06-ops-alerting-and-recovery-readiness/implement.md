# Ops alerting and recovery readiness implementation

## Checklist

1. Backend schemas
   - Add `HealthOpsAlertItem` and `HealthOpsAlertsResponse` to `app/api/v1/routers/health_schemas.py`.
   - Keep schema fields stable and explicit.

2. Backend aggregation
   - Add `HealthService.build_ops_alerts_response()`.
   - Derive alerts from existing readiness, stage spool, and job status counters.
   - Include safety metadata that confirms no recovery or write actions ran.

3. Backend route
   - Add Admin-only `GET /api/v1/health/ops-alerts` to `app/api/v1/routers/health.py`.
   - Do not change existing `/health/ready` or `/health/metrics` auth behavior.

4. Frontend integration
   - Add TypeScript contracts and `healthApi.getOpsAlerts()`.
   - Update `OpsDashboardPage.vue` to render backend-provided status and alerts.
   - Keep existing health/metrics/job sample sections read-only.

5. Tests and docs
   - Add targeted tests in `tests/test_fastapi_jobs_backend.py`.
   - Regenerate `docs/api/openapi.json`.
   - Run OpenAPI snapshot tests and frontend build.

6. Trellis closeout
   - Update task docs with observed verification.
   - Run `task.py validate`.
   - Run `git diff --check`.

## Validation Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ops_alerts_is_admin_only_readonly_and_reports_recovery_readiness
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-06-ops-alerting-and-recovery-readiness
git diff --check
```

## Observed Validation

- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ops_alerts_is_admin_only_readonly_and_reports_recovery_readiness`
- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_metrics_reports_runtime_counters tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_metrics_reports_default_resource_versions_in_mysql_mode tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_stage_spool_status_counts tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_when_default_translation_mode_requires_missing_client tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_when_callback_uid_missing`
- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- PASS: `npm --prefix frontend run build`
- PASS: `python3 ./.trellis/scripts/task.py validate 06-06-ops-alerting-and-recovery-readiness`
- PASS: `git diff --check`
- NOTE: frontend build emitted existing Rollup annotation/chunk-size warnings and npm upgrade notice.

## Non-Execution Reminder

Do not run pdf-mineru parsing, real translation providers, Word generation, physical deletion, S3 deletion, quota enforcement, scheduler loops, provider cancellation, or recovery actions.

## Rollback

- Remove the ops-alerts schemas, service method, route, frontend call, tests, and OpenAPI snapshot changes.
- Existing health ready/metrics and Ops Dashboard read-only sections remain functional.
