# Frontend QA Review Drawer

## Goal

Add a right-side QA review drawer to the Translation QA queue so high-frequency operators can inspect source/translation segments, submit a QA decision, and continue to the next queue item without leaving the workbench.

This is the third frontend improvement round after:

- Round 1: dense operations workbench surfaces for lists, filters, batch actions, and QA queue.
- Round 2: protected app shell with sidebar/topbar navigation.

The design priority remains density, speed, clear state, and low distraction for operations work.

## Current Context

- Primary queue page: `frontend/src/pages/TranslationQaQueuePage.vue`
- Existing detail QA page: `frontend/src/pages/TranslationResultQaPage.vue`
- Existing API client:
  - `documentJobsApi.getTranslationQa(jobId, limit = 200)`
  - `documentJobsApi.updateTranslationQa(jobId, payload)`
- Existing QA update payload:
  - `status`
  - `issue_type`
  - `note`
- Existing QA response includes:
  - `available`
  - `availability_reason`
  - `qa`
  - `artifacts`
  - `summary`
  - `segments`
  - `term_traces`
  - `ai_calls`

No backend changes are expected for this round.

## Requirements

### R1. Queue Drawer Entry

Add a right-side drawer on `TranslationQaQueuePage.vue`.

- Open from the existing row QA action instead of navigating away by default.
- Drawer loads QA data for the selected job with the existing `getTranslationQa` API.
- Preserve the current queue context, filters, sort, pagination, and scroll as much as practical.
- Keep a direct detail-page entry available for deep inspection.

### R2. Shared Review Component

Create a shared QA review component, for example `TranslationQaReviewPanel.vue`.

- Use it first inside the queue drawer.
- Structure it so `TranslationResultQaPage.vue` can reuse it later.
- Do not force a full detail-page migration in this round unless the implementation becomes simpler and remains low risk.

### R3. Drawer Layout

Use a dense operations layout, not a marketing/card-heavy layout.

- Width: `min(920px, 92vw)` on desktop.
- Mobile: near-fullscreen drawer or sheet.
- Header shows job id, filename, current QA status, and availability.
- Summary area shows compact chips for segment count, term trace availability, AI call availability, and debug/archive availability.
- Main content prioritizes source/translation segment comparison.
- Sticky footer contains review controls and primary actions.

### R4. Review Form

Support review submission from inside the drawer.

- Status options follow existing QA status semantics:
  - `unreviewed`
  - `approved`
  - `needs_fix`
  - `blocked`
- Issue type and note reuse existing detail-page behavior where applicable.
- Disable form while loading, saving, or when QA is unavailable.
- Show clear success and failure states without noisy page-level disruption.

### R5. Submit And Next

The primary action is submit and move to next.

- Primary button: submit current QA decision, refresh the queue, then open the next eligible item.
- Secondary action: submit only.
- Next item is chosen within the current filtered queue.
- State priority:
  - `blocked`
  - `needs_fix`
  - `unreviewed`
  - other statuses
- If multiple items have the same priority, keep the current queue sort order.
- If no next item exists, show a clear "queue cleared" or equivalent empty state in the drawer and keep the operator in context.

### R6. Query State

Sync only the selected QA job id to the URL query.

- Suggested query key: `qa_job_id`.
- Opening a drawer updates the query.
- Closing a drawer removes that query key.
- Directly visiting the queue with `qa_job_id` restores the drawer.
- Do not sync draft form state, active segment, or scroll position.

### R7. Keyboard Shortcuts

Add a small set of safe shortcuts with visible hints.

- `Esc`: close drawer.
- `Cmd/Ctrl + Enter`: submit primary action.
- `J` / `K`: move between segment/task navigation where appropriate.
- Show shortcut hints in footer, top-right controls, or tooltips.
- Do not support single-key approve/reject shortcuts in this round.
- Do not hijack `J` / `K` while an input, textarea, select, or contenteditable element is focused.

### R8. Evidence Access

Expose summary and key evidence entries without moving the full detail page into the drawer.

- Provide an obvious detail-page entry.
- Surface availability of debug archive, term traces, and AI calls.
- Use existing links or existing route behavior if already available.
- Do not build a second full evidence browser in the drawer.

### R9. Unavailable QA

If QA data is unavailable, still open a read-only diagnostic drawer.

- Show availability reason.
- Show missing or unavailable artifacts if the response exposes them.
- Keep review form disabled.
- Provide next actions such as open detail page and refresh.

### R10. Visual And Interaction Constraints

Follow the existing frontend layout guidelines.

- Use compact command headers, queue strips, dense tables, and existing `--app-*` design tokens.
- Avoid nested cards and decorative surfaces.
- Prefer stable dimensions for drawer header, segment list, and footer so loading/saving states do not shift the layout.
- On mobile, stack segment comparison while keeping actions reachable.

## Out Of Scope

- Backend/API changes.
- Segment-level translation editing.
- Persisting review draft state.
- Moving the entire detail QA page into the drawer.
- Reworking the global sidebar/topbar shell.
- Broad visual redesign outside the Translation QA queue and shared review panel.

## Acceptance Criteria

- Queue row QA action opens the drawer and loads QA data.
- The drawer can also be restored from `?qa_job_id=<id>`.
- Segment comparison is readable on desktop and mobile.
- Review submission works through the existing update API.
- Submit-and-next advances according to current queue filters and the selected priority order.
- Submit-only keeps the drawer on the current job after save.
- Unavailable QA opens a read-only diagnostic drawer.
- Shortcut hints are visible, and shortcuts do not fire while typing in form fields.
- The detail-page entry remains available for deep inspection.
- Existing QA detail route remains functional.

## Verification Plan

- Run the frontend build, typically `npm run build` from the frontend package or project-established command.
- Run targeted unit/component tests if helpers are introduced for next-item selection or shortcut handling.
- Run browser smoke checks for:
  - desktop queue drawer at about 1440px width
  - mobile/narrow drawer at about 375px width
  - URL restore with `qa_job_id`
  - submit-only
  - submit-and-next
  - unavailable read-only state
  - shortcut hints and input-focus guard

## Implementation Notes

- Start with `TranslationQaQueuePage.vue` plus a shared review panel component.
- Reuse status labels/options and payload semantics from `TranslationResultQaPage.vue`.
- Keep backend types/API calls unchanged unless the current frontend type definitions are incomplete.
- Consider extracting a pure helper for next-item selection if the logic becomes non-trivial enough to test directly.
- If a drawer/sheet pattern already exists in the frontend, use that local pattern before adding a new dependency.

