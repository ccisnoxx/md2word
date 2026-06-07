# Phase 5 evidence backfill audit details UI

## Goal

Backfill Phase 5 archive evidence for the existing Audit Log structured details UI so Phase 6 audit replay work can depend on an explicit accepted baseline.

## Requirements

- Treat this as evidence backfill for already-present behavior, not a new feature.
- Confirm the Admin audit page exposes structured `details` from audit events.
- Confirm the UI can open a details drawer with top-level fields and stable JSON.
- Confirm current-page CSV export preserves a `details_json` column.
- Confirm backend list/search/export still provides structured details and deterministic CSV details JSON.
- Do not change backend persistence, audit schemas, provider integrations, cleanup, quota behavior, S3 behavior, scheduler behavior, or conversion workflows.

## Acceptance Criteria

- [x] Audit Log page has a details entry point for events with structured `details`.
- [x] Details drawer shows event identity, top-level details fields, and stable sorted JSON.
- [x] Current-page frontend CSV export includes `details_json`.
- [x] Backend Admin list/search/export behavior for `details` has targeted test evidence.
- [x] Frontend build passes.
- [x] Trellis validate passes.
- [x] `git diff --check` passes.

## Notes

- This backfill resolves the Phase 6 gap-audit item for `frontend/src/pages/AuditLogPage.vue`.
- No real external integration or destructive workflow is executed by this evidence task.
