# Phase 5 alert delivery frontend controls implementation

## Classification

- Type: frontend-only Ops usability feature.
- Behavior change: adds a UI path to existing fake-send endpoint.
- Backend/API change: none.
- External side effects: fake-send may write existing compact audit event only; it sends no external notification.

## Checklist

1. Planning
   - [x] Fill `prd.md`, `design.md`, and `implement.md`.
   - [x] Run `task.py validate`.
   - [x] Run `task.py start`.

2. Frontend API contracts
   - [x] Add alert delivery types to `frontend/src/api/types.ts`.
   - [x] Add `frontend/src/api/opsAlertDeliveries.ts`.

3. Ops dashboard UI
   - [x] Import alert delivery API/types.
   - [x] Add active alert selection state.
   - [x] Add preview/fake-send controls.
   - [x] Add confirmation dialog.
   - [x] Add result summary and per-alert outcome table.
   - [x] Clear selection for alert codes no longer active after refresh.

4. Verification
   - [x] Run `npm --prefix frontend run build`.
   - [x] Run Trellis validate for this task.
   - [x] Run `git diff --check`.
   - [x] Browser-smoke local frontend load; admin dashboard redirected to login because no backend/admin session was running.
   - [x] Archive this task after verification.

## Verification Commands

```bash
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-alert-delivery-frontend-controls
git diff --check
```

No backend tests or OpenAPI export are expected because this slice does not change backend code.

## Implementation Notes

- Added typed frontend wrappers for the existing Admin-only alert delivery preview and fake-send endpoints.
- Added an Ops Dashboard panel that only targets active backend alert codes and never accepts free-form alert IDs.
- Preview and fake-send share a fixed `local_outbox` channel and bounded dedupe window.
- Fake-send is gated by a confirmation dialog with required reason and exact confirmation phrase.
- Result rendering surfaces totals, per-alert outcomes, dedupe keys, audit write status, and backend safety metadata.
- Selection is pruned after dashboard refresh so stale alert codes are not sent.

## Verification Results

- `npm --prefix frontend run build`: passed. Vite emitted existing bundle-size and dependency annotation warnings.
- `python3 ./.trellis/scripts/task.py validate 06-07-phase5-alert-delivery-frontend-controls`: passed.
- `git diff --check`: passed.
- Browser smoke: `http://127.0.0.1:3000/system-status/ops-dashboard` loaded the frontend and redirected to `/login?redirect=/system-status/ops-dashboard`; deeper dashboard rendering was not verified because local backend `127.0.0.1:8000` was not running and no admin session was available.

## Non-execution Reminder

Do not call real Slack/email/webhook delivery, provider cancellation, MinerU recovery, pdf-mineru parsing, real translation providers, Word generation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.
