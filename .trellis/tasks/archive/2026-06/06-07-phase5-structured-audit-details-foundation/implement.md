# Phase 5 structured audit details foundation implementation

## Classification

- Type: additive backend audit contract.
- Behavior change: Admin audit API/export can return structured details for newly recorded events.
- Persistence change: additive JSON payload field only; no table migration.
- External side effects: none beyond existing audit writes on already-existing fake/admin flows.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, and `implement.md`.
   - [x] Run `task.py validate`.
   - [x] Run `task.py start`.

2. Audit contract
   - [x] Add optional `details` to `AuditEvent`.
   - [x] Add optional `details` to `AuditEventResponse`.
   - [x] Add `details_json` CSV column with deterministic JSON encoding.
   - [x] Include details in `q` search.
   - [x] Extend `AuditService.record()` to accept normalized details.

3. Ops details writers
   - [x] Add structured details for `ops.alert_delivery_fake`.
   - [x] Add structured details for `ops.provider_cancellation_fake`.
   - [x] Add structured details for `audit_events.export`.

4. Tests/docs
   - [x] Add targeted API tests for list/search/export details.
   - [x] Add targeted fake Ops audit details assertions.
   - [x] Update frontend API type if needed.
   - [x] Refresh OpenAPI snapshot if needed.

5. Verification
   - [x] Run targeted backend tests.
   - [x] Run `npm --prefix frontend run build` if frontend types changed.
   - [x] Run Trellis validate for this task.
   - [x] Run `git diff --check`.
   - [x] Archive this task after verification.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_api_filters_sorts_and_paginates_for_admin \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_is_admin_only_bounded_and_audited \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_audits_dedupes_and_does_not_notify \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_fake_cancel_audits_dedupes_and_does_not_mutate_jobs
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-structured-audit-details-foundation
git diff --check
```

## Non-execution Reminder

Do not call real Slack/email/webhook delivery, real provider cancellation, MinerU recovery query/download, pdf-mineru parsing, real translation providers, Word generation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.

## Implementation Notes

- Added `AuditEvent.details` as optional JSON-safe structured evidence. Old audit events without details still validate.
- `AuditService.record()` now accepts `details` and recursively normalizes JSON-safe values; empty details become `None`, non-finite floats and arbitrary objects are rejected.
- Admin audit list responses include `details`.
- CSV export appends `details_json` with sorted-key compact JSON and preserves existing columns.
- Query `q` now searches serialized details as well as compact audit fields.
- `audit_events.export`, `ops.alert_delivery_fake`, and `ops.provider_cancellation_fake` now write curated details when they write audit events.
- OpenAPI snapshot was refreshed.

## Verification Results

- Passed targeted backend tests:
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_api_filters_sorts_and_paginates_for_admin tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_audit_events_export_api_is_admin_only_bounded_and_audited tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_audits_and_dedupes_without_external_delivery tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_fake_cancel_audits_dedupes_and_does_not_mutate_jobs tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend`
- Passed frontend build:
  - `npm --prefix frontend run build`
- Passed Trellis validate:
  - `python3 ./.trellis/scripts/task.py validate 06-07-phase5-structured-audit-details-foundation`
- Passed whitespace check:
  - `git diff --check`
- Passed OpenAPI export:
  - `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- Also ran `tests.test_database_job_repository` once while narrowing the persistence test target; it passed, but it is broader than this slice and includes local fake conversion/callback coverage.
