# Admin task delete simplification and template config editor

## Goal

Improve admin efficiency in the internal workbench by simplifying document-job deletion and adding an admin-only UI/API for editing the Word layout template configuration currently stored in `resources/template_configs/datasheet_template.yaml`.

## What I already know

- Document-job deletion is admin-only today, but it requires preview, reason input, confirmation phrase input, preview hash, and audit.
- The user wants admin deletion simplified because admin identity is already the permission boundary.
- The user still accepted keeping a preview step before execution.
- File retention cleanup and other destructive ops are separate higher-risk flows and must keep their current stricter gates.
- `resources/template_configs/datasheet_template.yaml` is the effective default layout config for the datasheet template.
- The user wants a full template configuration UI, not only `page_setup`.
- Existing template management already supports versions, verification jobs, publishing, and setting defaults.

## Requirements

- Simplify admin document-job deletion:
  - Keep `delete-preview`.
  - Keep admin-only backend enforcement.
  - Keep terminal-job-only behavior.
  - Keep preview hash validation.
  - Keep audit and `delete_reason` metadata.
  - Remove mandatory reason and confirmation phrase inputs from the new frontend flow.
  - Accept delete execution with `preview_hash` only.
  - Preserve backward compatibility for old clients that still send `reason` and `confirmation`.
  - Use a backend-generated default reason when the client omits one.
- Add admin-only template layout configuration:
  - Add read API for the current template layout YAML as structured data.
  - Add save API that validates structured config and creates a new template draft version using the current DOCX template file.
  - Do not directly mutate the checked-in `resources/template_configs/datasheet_template.yaml`.
  - Keep the existing template publish and default-selection flow for production activation.
  - Expose all runtime layout groups except `sample_content`, which is demonstration-only and not part of production behavior.
  - Preserve unknown but valid YAML keys only if they are part of the supported contract; otherwise reject unexpected groups/fields with explicit validation errors.
- Frontend:
  - Update `/jobs` and `/jobs/:jobId` delete flows to preview then click-confirm only.
  - Add an admin-only layout-config editor to `/settings/templates/:templateId`.
  - Use grouped form controls matching field type: number inputs, switches, selects, color pickers, and text inputs.
  - After saving config, refresh version list and show that a draft version was created.
- Docs:
  - Update document-jobs API docs and internal portal runbook to describe the simplified task delete flow.
  - Document that file retention and cleanup flows still require stricter confirmation.

## Acceptance Criteria

- Admin can delete a terminal document job after preview by confirming once, without typing a reason or confirmation phrase.
- Operator still cannot delete document jobs.
- Delete execution without a matching preview hash still fails.
- Delete audit and job metadata include a non-empty default reason.
- Existing clients sending reason and confirmation continue to work.
- Admin can open template detail and edit layout config groups from the YAML.
- Saving layout config creates a new draft template version rather than editing the repo YAML in place.
- The saved config can be listed through the template versions API and is available for normal validation/publish flow.
- Operator cannot access or execute template config edit APIs.
- OpenAPI, frontend types, unit tests, and docs are updated.

## Out of Scope

- Simplifying file physical delete, cleanup run, S3 delete, provider cancellation, or other ops flows.
- Directly editing checked-in YAML from the browser.
- Online Word editing.
- Segment-level translation edit writeback.
- Multi-tenant/SaaS behavior.
- Reworking template DOCX editing itself.
- Making a saved layout config immediately production default without template publish/default flow.

## Technical Notes

- Relevant specs: `.trellis/spec/backend/index.md`, `.trellis/spec/backend/quality-guidelines.md`, `.trellis/spec/guides/cross-layer-thinking-guide.md`, `.trellis/spec/guides/code-reuse-thinking-guide.md`.
- Relevant backend areas: `app/domains/document_jobs/`, `app/domains/templates/`, `app/infrastructure/persistence/`, `app/domains/resources/`.
- Relevant frontend areas: `frontend/src/pages/JobsPage.vue`, `frontend/src/pages/JobDetailPage.vue`, `frontend/src/pages/TemplateDetailPage.vue`, `frontend/src/api/templates.ts`, `frontend/src/api/types.ts`.
- Relevant docs: `docs/api/document-jobs.md`, `docs/runbooks/internal-portal.md`.

## Validation Plan

- Targeted backend tests for document-job delete contract and template layout config API.
- OpenAPI export/check.
- Frontend typecheck and unit tests for touched helpers/types where applicable.
- Smoke mock updates only if route-level behavior changes require it.
