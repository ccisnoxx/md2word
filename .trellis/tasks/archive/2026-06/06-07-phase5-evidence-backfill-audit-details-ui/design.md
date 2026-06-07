# Phase 5 Audit Details UI Evidence Backfill Design

## Decision

Accept the current Audit Log page as the Phase 5 structured audit details UI baseline.

The UI is intentionally read-only:

- It uses the existing Admin-only audit list API.
- It displays structured `details` only when the backend returns them.
- It does not mutate audit events or create server-side export files.
- It keeps CSV export browser-local for the current page and uses the governed backend export for filtered export.

## Evidence Surface

- `frontend/src/pages/AuditLogPage.vue`
  - Adds a `Details` table column.
  - Opens a drawer for events with details.
  - Renders event identity, top-level fields, and stable sorted JSON.
  - Exports current page CSV with `details_json`.
- `frontend/src/api/types.ts`
  - Defines recursive `AuditDetailsValue`, `AuditDetails`, and `AuditEventResponse.details`.
- `app/domains/audit/router.py`
  - Returns `details` in Admin audit list responses.
  - Records structured details for governed exports.
- `app/domains/audit/service.py`
  - Emits deterministic `details_json` for CSV export.

## Safety Boundary

This evidence does not add or enable:

- real Slack/email/webhook delivery;
- real provider cancellation;
- real S3 deletion;
- quota behavior changes;
- cleanup execution or scheduler loops;
- pdf-mineru parsing, translation provider calls, or Word generation.

## Compatibility

Existing audit events without `details` remain displayable because the UI treats `details=null` as no details and the backend model keeps the field optional.
