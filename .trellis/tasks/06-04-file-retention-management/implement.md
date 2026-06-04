# File retention management implementation plan

This task is still in planning. Do not execute this checklist until the user
approves the scope and `task.py start` is run.

## Classification

- Type: behavior-changing product feature, metadata-only.
- Public contract change: yes, two Admin-only Files API endpoints and one Admin
  frontend route.
- Storage behavior: metadata status update only; no physical deletion.

## Ordered Checklist

1. Backend schemas
   - Add file retention candidate/plan/mark-expired response schemas in
     `app/domains/files/schemas.py`.
   - Include concise Chinese class comments as required by project
     instructions.

2. Backend routes
   - Add `GET /api/v1/files/retention/plan` before `/{file_id}` in
     `app/domains/files/router.py`.
   - Add `POST /api/v1/files/retention/mark-expired` before `/{file_id}`.
   - Use `require_admin_user`, `get_runtime`, and `get_trace_id`.
   - Reuse `DocumentFileRetentionPlanner`; do not add direct repository
     scanning in the router beyond what the planner owns.
   - Record audit only for the POST action.

3. Backend docs/tests
   - Update `docs/api/files.md`.
   - Add tests to `tests/test_fastapi_jobs_backend.py`:
     - Admin can read plan.
     - Operator receives `403 role_forbidden`.
     - POST marks eligible metadata expired while the stored object remains on
       disk.
   - Re-run `tests.test_artifact_retention` to protect existing planner
     behavior.

4. Frontend API/types
   - Add response types in `frontend/src/api/types.ts`.
   - Add wrappers in `frontend/src/api/files.ts`.

5. Frontend route/page
   - Add `FileRetentionPage.vue`.
   - Register Admin route `/system-status/file-retention`.
   - Link from `SystemStatusPage.vue` storage section.
   - Use existing `ApiErrorAlert`, `formatDateTime`, and `formatBytes`.
   - No file download/delete/policy edit controls.

6. Verification
   - Backend:
     `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention`
   - Backend API:
     `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.<new_test_name>`
     or the narrow class/module target if multiple tests are added.
   - Frontend:
     `cd frontend && npm run build`

## Rollback Points

- If route ordering conflicts with `/files/{file_id}`, remove the retention
  routes and restore `files` router behavior.
- If metadata marking has unexpected side effects on downloads, keep only the
  GET dry-run endpoint and defer POST.
- If frontend build risk grows, ship backend API plus docs first and leave the
  page behind the planning gate.

## Definition of Done

- Planning artifacts approved.
- Task status moved to `in_progress` before code edits.
- Code implements only this task.
- Minimal tests/build actually run and results reported.
- No pdf-mineru parsing, translation, or Word generation flow is executed.
