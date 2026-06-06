# Ops alert delivery outbox safety contract implementation

## Classification

- Type: behavior-changing backend Ops feature.
- Risk: low external risk because no real notification delivery is implemented.
- Public contract change: additive Admin-only Ops API endpoints.
- Frontend change: none planned.

## Checklist

1. Planning
   - Fill `prd.md`, `design.md`, `implement.md`.
   - Run `task.py validate`.
   - Run `task.py start`.

2. Backend schemas
   - Add alert delivery request, item, totals/safety, and response models to `app/domains/ops/schemas.py`.
   - Keep field names explicit and OpenAPI-friendly.

3. Backend service
   - Add `app/domains/ops/alert_delivery.py`.
   - Read current alerts from `HealthService.build_ops_alerts_response()`.
   - Validate exact active alert codes, uniqueness, batch cap, channel, reason, confirmation, and dedupe window.
   - Implement preview with no mutation.
   - Implement fake-send with audit-backed outbox and dedupe by recent audit events.

4. Backend routes
   - Add `POST /api/v1/ops/alert-deliveries/preview`.
   - Add `POST /api/v1/ops/alert-deliveries/fake-send`.
   - Keep Admin-only JWT boundary.

5. Recovery action registry
   - Mark `alert.delivery` available for fake/outbox delivery.
   - Preserve real external delivery as a known gap.

6. Tests
   - Admin-only preview and fake-send.
   - Operator forbidden.
   - Empty/duplicate/too-many/unknown alert codes rejected.
   - Fake-send writes exactly one audit event and reports no external delivery.
   - Repeated fake-send within dedupe window returns `deduped` and does not write another delivery audit.
   - Recovery action registry exposes updated `alert.delivery` gates and audit action.

7. Docs/OpenAPI
   - Update `docs/api/ops.md`.
   - Run OpenAPI check.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_preview_is_admin_only_and_readonly tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_audits_and_dedupes_without_external_delivery tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_rejects_invalid_targets_and_updates_action_registry
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff
python3 ./.trellis/scripts/task.py validate 06-07-ops-alert-delivery-outbox-safety-contract
git diff --check
```

Run `npm --prefix frontend run build` only if frontend files change.

## Observed Validation

- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_preview_is_admin_only_and_readonly tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_audits_and_dedupes_without_external_delivery tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_rejects_invalid_targets_and_updates_action_registry`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_registry_is_admin_only_readonly_and_lists_safety_flags tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_preview_reports_document_job_and_legacy_job_eligibility_without_execution tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ops_alerts_is_admin_only_readonly_and_reports_recovery_readiness`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- Frontend build not run because no frontend files changed.

## Implementation Notes

- Added `app/domains/ops/alert_delivery.py` for Admin-only exact-alert preview and fake-send logic.
- Added `POST /api/v1/ops/alert-deliveries/preview` and `/fake-send`.
- Fake-send writes compact `ops.alert_delivery_fake` audit events for non-deduped batches only.
- Dedupe uses recent audit event `dedupe_keys` within the requested window.
- Updated `alert.delivery` recovery action registry entry to represent the fake outbox contract, not real external delivery.

## Rollback

- Remove `app/domains/ops/alert_delivery.py`.
- Remove alert-delivery schemas and routes.
- Restore `alert.delivery` registry entry to unavailable.
- Remove tests/docs/OpenAPI updates.

## Non-execution Reminder

Do not call real alert delivery services, provider cancellation, MinerU recovery, pdf-mineru parsing, real translation providers, Word generation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.
