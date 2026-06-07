# Phase 5 cleanup run frontend controls implementation

## Classification

- Type: frontend feature over existing backend contract.
- Behavior change: adds an Admin UI path for manual cleanup-run preview and execute.
- Backend change: none planned.
- Risk: potentially destructive local physical-delete execution, mitigated by existing backend preview/hash/reason/confirmation contract and explicit UI gating.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, `implement.md`.
   - [x] Validate task.
   - [x] Start task.

2. API contracts
   - [x] Add cleanup-run request/response types to `frontend/src/api/types.ts`.
   - [x] Add cleanup-run API wrappers to `frontend/src/api/files.ts`.

3. FileRetention UI
   - [x] Track cleanup-run report/loading/dialog state separately from direct physical-delete state.
   - [x] Clear stale cleanup-run preview when selection changes.
   - [x] Add preview and execute buttons in the existing heading action cluster.
   - [x] Render cleanup-run result section with preview hash, safety flags, totals, and per-file outcomes.
   - [x] Add execute dialog with selected file IDs, preview hash, reason, and confirmation phrase.

4. Validation
   - [x] Run `npm --prefix frontend run build`.
   - [x] Run Trellis validate.
   - [x] Run `git diff --check`.
   - [x] Run browser smoke for the File Retention route.

## Verification Commands

```bash
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-cleanup-run-frontend-controls
git diff --check
```

## Verification Results

- `npm --prefix frontend run build` passed. Existing Vite/Rollup pure-annotation and chunk-size warnings were observed.
- `python3 ./.trellis/scripts/task.py validate 06-07-phase5-cleanup-run-frontend-controls` passed.
- `git diff --check` passed.
- Browser smoke opened `http://127.0.0.1:3000/system-status/file-retention`; unauthenticated state redirected to `http://127.0.0.1:3000/login?redirect=/system-status/file-retention`, rendered the login page, and reported no browser console errors.
- Backend tests and OpenAPI export were not run because this task changed only frontend code and Trellis planning docs.
- No pdf-mineru parsing, translation provider call, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loop, real S3 deletion, or autonomous cleanup was run.

## Rollback

- Remove cleanup-run types and filesApi methods.
- Remove cleanup-run state, controls, dialog, and result section from `FileRetentionPage.vue`.

## Non-execution Reminder

Do not run pdf-mineru parsing, translation providers, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, or autonomous destructive cleanup.
