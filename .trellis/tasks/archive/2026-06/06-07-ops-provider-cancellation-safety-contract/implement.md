# Ops provider cancellation safety contract implementation

## Classification

- Type: behavior-changing backend Ops feature.
- Risk: medium product semantics risk, low external risk because no real provider call is made.
- Public contract change: additive Admin-only Ops API endpoints.
- Frontend change: none planned.

## Checklist

1. Planning
   - Fill `prd.md`, `design.md`, `implement.md`.
   - Run `task.py validate`.
   - Run `task.py start`.

2. Backend schemas
   - Add provider cancellation request/target/operation/safety/response models.

3. Backend service
   - Add `app/domains/ops/provider_cancellation.py`.
   - Resolve exact `document_job` and `legacy_job` targets.
   - Compute MinerU operation IDs from stored metadata only.
   - Implement preview with no mutation and no audit.
   - Implement fake-cancel with reason, confirmation, dedupe, and audit-backed outbox semantics.

4. Backend routes
   - Add `POST /api/v1/ops/provider-cancellations/preview`.
   - Add `POST /api/v1/ops/provider-cancellations/fake-cancel`.
   - Keep Admin-only JWT boundary.

5. Recovery action registry
   - Mark `provider.cancel` available for fake cancellation.
   - Keep real provider cancellation as a known gap.

6. Tests
   - Admin-only preview and fake-cancel.
   - Operator forbidden.
   - Missing batch ID / terminal job / unsupported provider gates.
   - Fake-cancel writes one audit and no job mutation/provider call.
   - Repeated fake-cancel dedupes.
   - Registry exposes updated `provider.cancel` gates and audit action.

7. Docs/OpenAPI
   - Update `docs/api/ops.md`.
   - Run OpenAPI check.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_preview_is_admin_only_and_metadata_only tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_fake_cancel_audits_dedupes_and_does_not_mutate_jobs tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_gates_and_registry_contract
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff
python3 ./.trellis/scripts/task.py validate 06-07-ops-provider-cancellation-safety-contract
git diff --check
```

Run `npm --prefix frontend run build` only if frontend files change.

## Observed Validation

- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_preview_is_admin_only_and_metadata_only tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_fake_cancel_audits_dedupes_and_does_not_mutate_jobs tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_gates_and_registry_contract`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_registry_is_admin_only_readonly_and_lists_safety_flags tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_preview_reports_document_job_and_legacy_job_eligibility_without_execution tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_preview_is_admin_only_and_readonly tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_audits_and_dedupes_without_external_delivery tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_rejects_invalid_targets_and_updates_action_registry`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- Frontend build not run because no frontend files changed.

## Implementation Notes

- Added `app/domains/ops/provider_cancellation.py` for metadata-only preview and audit-backed fake cancellation.
- Added `POST /api/v1/ops/provider-cancellations/preview` and `/fake-cancel`.
- Fake cancellation requires exact target, provider, reason, and confirmation phrase.
- Fake cancellation writes `ops.provider_cancellation_fake` only for non-deduped eligible attempts.
- No local document job, legacy job, queue, provider, cleanup, delete, parsing, translation, or Word workflow was executed.
- Updated `provider.cancel` recovery action registry entry to represent fake cancellation only.

## Rollback

- Remove `app/domains/ops/provider_cancellation.py`.
- Remove provider-cancellation schemas and routes.
- Restore `provider.cancel` registry entry to unavailable.
- Remove tests/docs/OpenAPI updates.

## Non-execution Reminder

Do not call real provider cancellation, MinerU recovery query/download, alert delivery, pdf-mineru parsing, real translation providers, Word generation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.
