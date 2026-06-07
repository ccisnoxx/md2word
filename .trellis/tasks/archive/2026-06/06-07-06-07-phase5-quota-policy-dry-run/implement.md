# Phase 5 quota policy dry run implementation

## Classification

- Type: additive backend API + frontend Admin UI.
- Behavior change: adds read-only dry-run only.
- Risk: future operators may confuse dry-run with real enforcement; response safety flags and UI wording must be explicit.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, `implement.md`.
   - [x] Validate task.
   - [x] Start task.

2. Backend contract
   - [x] Add quota policy settings.
   - [x] Add quota policy dry-run service.
   - [x] Add request/response schemas.
   - [x] Add Admin-only router endpoint.
   - [x] Ensure `upload-url` remains unchanged.
   - [x] Update docs/OpenAPI.

3. Frontend
   - [x] Add TS contracts.
   - [x] Add files API wrapper.
   - [x] Add File Retention quota dry-run panel.

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
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_dry_run_reports_would_block_without_side_effects tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_dry_run_is_admin_only_and_upload_url_unchanged
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-06-07-phase5-quota-policy-dry-run
git diff --check
```

## Non-execution Reminder

Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, or autonomous destructive cleanup.

## Results

- Added staged quota policy settings with disabled-by-default behavior.
- Added Admin-only `POST /api/v1/files/quota-policy/dry-run`.
- Added a read-only quota policy service that sums non-deleted `document_files` metadata bytes and reports projected quota outcome.
- Added response safety flags proving no upload authorization, upload content write, blocking execution, metadata mutation, audit write, provider call, delete, or conversion workflow occurred.
- Kept real `POST /api/v1/files/upload-url` behavior unchanged; tests prove a staged `would_block=true` dry-run does not block current upload authorization.
- Added File Retention page quota dry-run controls and result/safety display.
- Updated `docs/api/files.md`, `docs/api/manifest.yaml`, and `docs/api/openapi.json`.

## Verification Results

- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_dry_run_reports_would_block_without_side_effects tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_dry_run_is_admin_only_and_upload_url_unchanged`
- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- PASS: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- PASS: `npm --prefix frontend run build`
- PASS: browser smoke on unauthenticated `/system-status/file-retention` route; redirected to login and console errors were empty.
- PASS: `python3 ./.trellis/scripts/task.py validate 06-07-06-07-phase5-quota-policy-dry-run`
- PASS: `git diff --check`
