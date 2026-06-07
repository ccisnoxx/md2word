# Phase 5 alert destination config dry run implementation

## Classification

- Type: additive backend API + frontend Admin UI.
- Behavior change: adds read-only config dry-run; no external side effects.
- Risk: future integration boundary could be misunderstood as live delivery, mitigated by response safety flags and UI copy.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, `implement.md`.
   - [x] Validate task.
   - [x] Start task.

2. Backend contract
   - [x] Add `ops_alert_destinations_json` setting.
   - [x] Add alert destination dry-run service.
   - [x] Add request/response schemas.
   - [x] Add Admin-only router endpoint.
   - [x] Update docs/OpenAPI.

3. Frontend
   - [x] Add TS contracts.
   - [x] Add API wrapper.
   - [x] Add Ops dashboard config dry-run panel.

4. Tests and verification
   - [x] Add targeted backend tests.
   - [x] Run targeted backend tests.
   - [x] Export/check OpenAPI.
   - [x] Run frontend build.
   - [x] Run browser smoke.
   - [x] Run Trellis validate.
   - [x] Run `git diff --check`.

## Verification Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_destination_dry_run_is_admin_only_readonly_and_masks_secrets tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_destination_dry_run_reports_invalid_config_without_side_effects
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-alert-destination-config-dry-run
git diff --check
```

## Results

- Added an Admin-only, read-only alert destination config dry-run endpoint.
- Added `OPS_ALERT_DESTINATIONS_JSON` as staged destination config input with masked `secret_ref` reporting only.
- Returned destination status, config errors, allowlist matching, missing gates, idempotency key, and safety flags without sending Slack/email/webhook messages.
- Added Ops dashboard controls for config-only dry-run and selected-alert allowlist dry-run.
- Browser smoke: `http://127.0.0.1:3000/system-status/ops-dashboard` redirected to `http://127.0.0.1:3000/login?redirect=/system-status/ops-dashboard`; login page rendered and console errors were empty.

## Verification Results

- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_destination_dry_run_is_admin_only_readonly_and_masks_secrets tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_destination_dry_run_reports_invalid_config_without_side_effects`
- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- PASS: `npm --prefix frontend run build`
- PASS: browser smoke on unauthenticated Ops dashboard route
- PASS: `python3 ./.trellis/scripts/task.py validate 06-07-phase5-alert-destination-config-dry-run`
- PASS: `git diff --check`

## Rollback

- Remove alert destination setting, service, schemas, route, tests, docs, OpenAPI snapshot, frontend wrapper, types, and dashboard panel.

## Non-execution Reminder

Do not run pdf-mineru parsing, translation providers, Word generation, real Slack/email/webhook delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, or autonomous destructive cleanup.
