# Phase 5 provider cancellation frontend controls implementation

## Classification

- Type: frontend-only Ops usability feature.
- Behavior change: adds a UI path to existing provider cancellation preview/fake-cancel endpoint.
- Backend/API change: none.
- External side effects: fake-cancel may write existing compact audit event only; it does not call real provider cancellation or mutate local jobs.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, and `implement.md`.
   - [x] Run `task.py validate`.
   - [x] Run `task.py start`.

2. Frontend API contracts
   - [x] Add provider cancellation types to `frontend/src/api/types.ts`.
   - [x] Add `frontend/src/api/opsProviderCancellations.ts`.

3. Ops dashboard UI
   - [x] Import provider cancellation API/types.
   - [x] Add exact target form state.
   - [x] Add preview/fake-cancel controls.
   - [x] Add confirmation dialog.
   - [x] Add result summary, target summary, provider operation, missing gates, and safety metadata.
   - [x] Disable fake-cancel when the current target no longer matches the preview.

4. Verification
   - [x] Run `npm --prefix frontend run build`.
   - [x] Run Trellis validate for this task.
   - [x] Run `git diff --check`.
   - [x] Browser-smoke local frontend load; admin dashboard redirected to login because no backend/admin session was running.
   - [x] Archive this task after verification.

## Verification Commands

```bash
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-06-07-phase5-provider-cancellation-frontend-controls
git diff --check
```

No backend tests or OpenAPI export are expected because this slice does not change backend code.

## Implementation Notes

- Added typed frontend wrappers for existing Admin-only provider cancellation preview and fake-cancel endpoints.
- Added an Ops Dashboard fake-control panel with exact target type/id, fixed `provider=mineru`, and bounded dedupe window.
- Preview shows eligibility, outcome, missing gates, target summary, provider operation metadata, dedupe key, audit status, and safety metadata.
- Fake-cancel is gated by preview match, backend-reported eligibility, reason, and exact confirmation phrase.
- UI copy explicitly states fake cancellation does not call MinerU/provider cancellation, mutate local jobs, mutate queues, delete files, or run conversion workflow.

## Verification Results

- `npm --prefix frontend run build`: passed. Vite emitted existing bundle-size and dependency annotation warnings.
- `python3 ./.trellis/scripts/task.py validate 06-07-06-07-phase5-provider-cancellation-frontend-controls`: passed.
- `git diff --check`: passed.
- Browser smoke: `http://127.0.0.1:3000/system-status/ops-dashboard` loaded the frontend and redirected to `/login?redirect=/system-status/ops-dashboard`; no console errors were observed. Deeper dashboard rendering was not verified because local backend/admin session was not available.

## Non-execution Reminder

Do not call real provider cancellation, MinerU recovery query/download, alert delivery fake-send, pdf-mineru parsing, real translation providers, Word generation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.
