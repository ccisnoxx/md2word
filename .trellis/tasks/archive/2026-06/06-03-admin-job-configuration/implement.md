# Admin Job Configuration Implementation Plan

This task is in progress. Implementation follows the reviewed design and the active `06-03-admin-job-configuration` scope.

## Success Criteria

- Operator sees but cannot select job configuration.
- Admin can select published job configuration versions during create.
- Admin retry can keep original, use latest term defaults, or explicitly bind term/translation term versions.
- Non-admin explicit selection is rejected by API.
- The implementation does not run or depend on the pdf-mineru / translation / Word generation main flow.

## Checklist

1. Backend contract — done
   - Added document-job config-summary response schemas.
   - Added `GET /api/v1/document-jobs/config-summary`.
   - Extended create request with `translation_profile_id` and `translation_profile_version`.
   - Enforced role checks for all explicit create/retry resource-selection fields.
   - Passed selected Template and Translation Profile values into create resource snapshots.
   - Kept retry template/profile behavior unchanged; retry only rebinds term assets.

2. Backend tests — done
   - Added a targeted test for Operator config summary and Admin options.
   - Added a targeted test that Operator explicit create selection returns `403`.
   - Added a targeted Admin create test that selected published versions appear in `request_snapshot.resources`.
   - Added a targeted Admin retry test for latest/default and explicit term asset behavior on `document-jobs`.

3. Frontend API/types — done
   - Added config-summary types to `frontend/src/api/types.ts`.
   - Added `documentJobsApi.getConfigSummary()`.
   - Added `translation_profile_id` / `translation_profile_version` to document job create types.

4. Upload UI — done
   - Loads and renders the config summary in `PdfUploadPanel`.
   - Gates selectors with current role.
   - Submits explicit fields only for Admin.
   - Keeps Operator payload default-only.

5. Retry UI — done
   - Expanded `JobDetailPage` retry dialog with strategy selection.
   - Submits `use_latest_term_assets` or explicit term asset fields only for Admin strategies.
   - Keeps existing reason-only behavior for default retry.

6. Documentation — done
   - Updated `docs/api/document-jobs.md` for config summary and new create fields.
   - Regenerated `docs/api/openapi.json` after intentional OpenAPI changes.

## Minimal Verification

- Backend:
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
  - If this is too broad after implementation, first run the smallest targeted test names added for this task.
- Frontend:
  - `cd frontend && npm run build`
  - If the project has a narrower typecheck script in `frontend/package.json`, use that first.
- API docs:
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export` if OpenAPI output changes.

## Rollback Points

- If backend config-summary becomes too broad, keep frontend aggregation for Template, Term Rule Set, and Translation Profile, and return only Translation Term Set/default readiness from the new endpoint.
- If Translation Profile create binding requires deeper execution changes, defer only Translation Profile explicit selection and still ship Template + Term Rule Set + Translation Term Set selection.
- If retry config selection becomes risky, keep retry as reason-only plus `use_latest_term_assets` for Admin and document explicit version retry as follow-up.
