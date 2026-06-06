# Ops recovery action safety registry implementation

## Checklist

1. Planning
   - Fill `prd.md`, `design.md`, `implement.md`.
   - Curate `implement.jsonl` and `check.jsonl`.
   - Run `task.py validate`.
   - Run `git diff --check`.
   - Run `task.py start`.

2. Backend contracts
   - Add `app/domains/ops/schemas.py`.
   - Add request/response models for action list and preview.

3. Backend service
   - Add `app/domains/ops/recovery_actions.py`.
   - Define static action registry.
   - Implement read-only target preview for `document_job`, `legacy_job`, and candidate-only action families.

4. Backend route
   - Add `app/domains/ops/router.py`.
   - Add Admin-only `GET /api/v1/ops/recovery-actions`.
   - Add Admin-only `POST /api/v1/ops/recovery-actions/preview`.
   - Include router in `app/api/v1/router.py`.

5. Frontend read-only integration
   - Add TypeScript contracts and API wrapper.
   - Add read-only section to Ops Dashboard.
   - Do not add execution controls.

6. Docs and OpenAPI
   - Add/update API docs for ops recovery actions.
   - Regenerate OpenAPI snapshot.

7. Tests
   - Add targeted backend tests.
   - Run OpenAPI tests.
   - Run frontend build if frontend changed.

8. Close implementation docs
   - Update acceptance criteria and observed validation.
   - Run `task.py validate`.
   - Run `git diff --check`.

## Validation Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_registry_is_admin_only_readonly_and_lists_safety_flags
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_preview_reports_document_job_and_legacy_job_eligibility_without_execution
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-ops-recovery-action-safety-registry
git diff --check
```

## Observed Validation

- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_registry_is_admin_only_readonly_and_lists_safety_flags tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_recovery_action_preview_reports_document_job_and_legacy_job_eligibility_without_execution`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- Passed with existing Vite/Rollup size warnings: `npm --prefix frontend run build`
- Passed: `python3 ./.trellis/scripts/task.py validate 06-07-ops-recovery-action-safety-registry`
- Passed: `git diff --check`

## Implementation Notes

- Added `app/domains/ops/` for schema-backed, read-only registry and preview service.
- Included the ops router under `/api/v1/ops/recovery-actions`.
- Added TypeScript contracts and an Ops Dashboard registry table without execution controls.
- Added `docs/api/ops.md` and refreshed `docs/api/openapi.json`.
- Did not implement or run provider cancellation, alert delivery, automated cleanup execution, MinerU recovery calls, pdf-mineru parsing, translation providers, or Word generation.

## Non-Execution Reminder

Do not run provider cancellation, alert delivery, scheduler loops, automated cleanup execution, physical deletion, S3 deletion, MinerU recovery calls, pdf-mineru parsing, real translation providers, or Word generation.

## Rollback

- Remove `app/domains/ops/`.
- Remove the ops router include.
- Remove frontend read-only action safety integration.
- Remove OpenAPI/doc/test changes.
