# Audit log viewer

## Goal

Provide an Admin-only, read-only audit log viewer so internal QA/Ops/Admin users can inspect successful high-risk actions already recorded in `AuditEvent`.

This task implements the smallest useful slice of the roadmap item `audit-log-viewer`: query, filter, inspect, and export visible audit events. It must not change the PDF parsing / translation / Word generation pipeline.

## Requirements

- Add an Admin-only audit event API over the existing `audit_event_repository`.
- Show audit events in the frontend under the existing internal Admin/Ops information architecture.
- Support practical filtering:
  - actor role
  - action
  - target type
  - target id
  - actor id
  - free-text search across stable audit fields
  - created time range
- Support pagination and deterministic sorting by `created_at`.
- Show only fields already present in `AuditEvent`: `audit_id`, actor, action, target, reason, trace id, and timestamp.
- Provide a lightweight CSV export from the frontend for the currently loaded filtered result page.
- Keep the feature read-only. No audit mutation, deletion, retention changes, or operational actions are in scope.
- Keep the implementation independent from document job execution. Tests must seed audit events directly or use already isolated API calls, not rerun MinerU, translation, or Word generation flows.

## Non-goals

- No full operations dashboard.
- No real file deletion or audit retention purge.
- No new audit write points unless needed by existing login during test setup.
- No raw payload, secret, file path, token, request body, or full prompt exposure.
- No complete term rule CRUD workbench.
- No backend-generated export file storage.

## Acceptance Criteria

- [x] Admin can open an audit log viewer page from the Admin-only operations/status area.
- [x] Operator cannot access the backend audit list API and cannot reach the frontend route through normal navigation.
- [x] `GET /api/v1/audit-events` returns paginated audit events ordered deterministically.
- [x] API filters by actor role, action, target type, target id, actor id, free-text query, and created time range.
- [x] The page displays audit id, actor, action, target, reason, trace id, and created time in a scan-friendly table.
- [x] The page can export the currently loaded filtered result page as CSV without creating backend files.
- [x] Empty state, loading state, and API error state are visible.
- [x] No PDF/MinerU/translation/Word main workflow is executed by implementation or verification.
- [x] Minimal backend verification covers success filtering and Admin-only authorization.
- [x] Minimal frontend verification runs type/build checks after implementation.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
