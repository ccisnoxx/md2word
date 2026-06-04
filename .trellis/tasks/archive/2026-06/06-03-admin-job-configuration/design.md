# Admin Job Configuration Design

## Current State

The product-roadmap parent task defines `admin-job-configuration` as the Phase 1 slice for role-based job configuration. Current frontend upload and retry flows are simpler than that target:

- `frontend/src/components/PdfUploadPanel.vue` uploads a PDF and creates a document job with defaults. It always sends `debug_full_text=false` and does not expose resource version selectors.
- `frontend/src/pages/JobDetailPage.vue` retry dialog only accepts a reason. It calls `documentJobsApi.retry()` with no configuration strategy.
- `frontend/src/api/types.ts` already has create/retry fields for template, term rule set, and translation term set, but it does not expose Translation Profile fields for `document-jobs`.
- `frontend/src/api/translationProfiles.ts`, `templates.ts`, and `termRuleSets.ts` can list versioned resources; there is no frontend API wrapper for read-only Translation Term Set list/detail because the backend currently only exposes import/export for that resource.
- `app/domains/document_jobs/schemas.py` and `router.py` accept create/retry resource fields for template and term assets, but not `translation_profile_id` or `translation_profile_version`.
- `app/domains/document_jobs/service.py` blocks non-admin explicit term asset selection, but it does not block operator template selection or Translation Profile selection because those fields are not part of the contract yet.
- `JobResourceSnapshotService` already knows how to bind Template, Term Rule Set, Translation Term Set, and Translation Profile snapshots, but the `document_jobs` service currently does not pass Template or Translation Profile selection through its resource snapshot path.

There is a backend spec layer under `.trellis/spec/backend/`. No frontend `.trellis/spec` layer exists, so frontend work should follow existing Vue 3 + Element Plus patterns in the current files.

## Scope

In scope:

- Add one small, read-only document-job configuration summary/options contract for upload/retry UI.
- Extend `document-jobs` create/retry contracts only as needed for resource-version selection.
- Add frontend UI for Operator read-only summary and Admin advanced selectors.
- Add frontend retry strategy UI in the existing detail retry dialog.
- Add targeted tests for API permission/snapshot behavior and frontend type/build verification.

Out of scope:

- Full Term Rule CRUD workbench.
- Translation Term Set import/export/rollback UI.
- Physical file deletion or file-management pages.
- Re-running pdf-mineru parsing, translation, or Word generation as verification.
- New bulk job endpoints.
- Online runtime environment editing or worker operations.

## API Changes

### New Endpoint

`GET /api/v1/document-jobs/config-summary`

Purpose: return the effective defaults and selectable published versions needed by the job create/retry UI.

Auth: Bearer JWT via `require_current_user`.

Response shape, planned:

```json
{
  "role": "operator",
  "resource_mode": "versioned",
  "defaults": {
    "template": { "id": "default", "version": "1", "label": "default@1", "available": true },
    "term_rule_set": { "id": "electronics-default", "version": "1", "label": "electronics-default@1", "available": true },
    "translation_term_set": { "id": "translation-terms-en2zh", "version": "v1", "label": "translation-terms-en2zh@v1", "available": true },
    "translation_profile": { "id": "electronics-en2zh", "version": "1", "label": "electronics-en2zh@1", "available": true }
  },
  "options": {
    "templates": [],
    "term_rule_sets": [],
    "translation_term_sets": [],
    "translation_profiles": []
  },
  "readiness": {
    "en2zh_available": true,
    "warnings": []
  }
}
```

For Operator, `options` can be empty because the UI only needs defaults. For Admin, return published selectable versions. If a backend lacks MySQL resource services, the endpoint should still return a useful summary with unavailable flags/warnings instead of forcing frontend aggregation to understand every backend mode.

### Existing Endpoint Extensions

`POST /api/v1/document-jobs`

- Add optional `translation_profile_id`.
- Add optional `translation_profile_version`.
- Enforce that non-admin users cannot pass any explicit version-selection field, including `template_version_id`, term assets, translation term assets, or translation profile fields.
- Preserve current behavior when no explicit fields are supplied.
- Ensure Template and Translation Profile selections are included in `request_snapshot.resources`.

`POST /api/v1/document-jobs/{job_id}/retry`

- Preserve current no-payload / reason-only behavior.
- Keep retry rebinding scoped to term assets for the first implementation unless backend snapshot support for Translation Profile retry can be kept small and isolated.
- Enforce non-admin cannot pass explicit retry selection or `use_latest_term_assets`.

The retry scope intentionally avoids changing template selection during retry because current backend retry semantics are term-asset specific and the roadmap asks for a small Phase 1 slice.

## Page Changes

### `PdfUploadPanel`

- Load document-job configuration summary on mount.
- Show a compact default configuration summary to all roles.
- For Admin only, show an advanced section with selectors:
  - Template Version
  - Term Rule Set Version
  - Translation Term Set Version only when mode is `en2zh_pdf_to_word`
  - Translation Profile Version only when mode is `en2zh_pdf_to_word`
- Submit explicit fields only for Admin and only when the selector has a value.
- Keep Operator request payload default-only.

### `JobDetailPage`

- Expand the retry dialog with a strategy selector:
  - keep original
  - use latest term assets
  - Admin selected term/translation assets
- Load the same configuration summary only when the retry dialog opens and admin options are needed.
- Keep the existing reason field.

### `JobDetailPage` Configuration Snapshot

No new page is needed. Existing detail snapshot labels should be extended only if necessary to show Template and Translation Profile labels from `request_snapshot.resources`.

## Involved Files

Expected backend files:

- `app/domains/document_jobs/schemas.py`
- `app/domains/document_jobs/router.py`
- `app/domains/document_jobs/service.py`
- Optional small helper module under `app/domains/document_jobs/` if config-summary mapping would otherwise make `router.py` too large
- `docs/api/document-jobs.md`
- `docs/api/openapi.json` only if release check requires regenerating after intentional OpenAPI changes
- `tests/test_fastapi_jobs_backend.py`

Expected frontend files:

- `frontend/src/api/types.ts`
- `frontend/src/api/documentJobs.ts`
- `frontend/src/components/PdfUploadPanel.vue`
- `frontend/src/pages/JobDetailPage.vue`
- Optional small shared component such as `frontend/src/components/JobConfigurationSummary.vue` if reuse keeps the upload and retry UI smaller

Expected Trellis files:

- `.trellis/tasks/06-03-admin-job-configuration/prd.md`
- `.trellis/tasks/06-03-admin-job-configuration/design.md`
- `.trellis/tasks/06-03-admin-job-configuration/implement.md`

## Risks And Tradeoffs

- A config-summary endpoint is narrower than adding a full Translation Term Set read-only API. It fits this task because the UI only needs job-creation options, not a management workbench.
- Retry will not change Template Version in the first slice. That keeps retry aligned with the existing backend term-asset rebinding contract and avoids changing artifact/template lifecycle semantics.
- If explicit Translation Profile retry support is required later, it should be a separate backend contract change because current retry helper is named and shaped around term assets.

