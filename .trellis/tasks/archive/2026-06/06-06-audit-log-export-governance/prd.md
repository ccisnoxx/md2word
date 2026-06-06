# Audit log export governance

## Goal

Add governed Admin-only audit log export so operators can export the current audit filter set without relying on browser-only current-page CSV.

## Requirements

- Add a backend export endpoint for persisted audit events.
- Export must use the same filters and sort contract as `GET /api/v1/audit-events`.
- Export must be Admin-only; Operator and anonymous users must be rejected by existing auth dependencies.
- Export must be bounded by an explicit `max_rows` query parameter with a hard API cap.
- Export must return a JSON envelope with an export manifest and `csv_text`; it must not create server-side export files.
- Export manifest must include export time, requester identity, sort, selected filters, matched count, exported count, truncation status, max rows, CSV columns, and the audit event id for the export action.
- Export must record an audit event after building the CSV so the export event itself is not included in that CSV.
- CSV must include only stable audit columns: `created_at`, `audit_id`, `actor_role`, `actor_id`, `action`, `target_type`, `target_id`, `reason`, `trace_id`.
- CSV output must escape commas, quotes, and newlines.
- Frontend audit page must offer a full filtered export action using the backend endpoint while preserving the current-page export option.
- OpenAPI snapshot and TypeScript contracts must be updated.

## Acceptance Criteria

- [x] Task exists.
- [x] `prd.md`, `design.md`, and `implement.md` define the export governance boundary.
- [x] `task.py validate` passes before start.
- [x] `task.py start` is run.
- [x] Backend export endpoint is implemented and reuses the existing query service filtering logic.
- [x] Export response is bounded, includes governance manifest, and does not write server-side files.
- [x] Successful export records an `audit_events.export` audit event after CSV generation.
- [x] Tests cover Admin success, CSV escaping/truncation, audit recording, and Operator rejection.
- [x] Frontend API/types/page integrate full filtered export without removing current-page export.
- [x] OpenAPI snapshot is regenerated and OpenAPI tests pass.
- [x] Targeted backend/frontend verification passes.
- [x] `git diff --check` passes.

## Notes

- This task does not add server-side export artifact retention, async export jobs, email delivery, or audit event deletion.
- This task does not run pdf-mineru parsing, real translation providers, or Word generation.
- Observed validation passed on 2026-06-06.
