# Frontend Incident Triage Workbench

## Goal

Add an independent incident triage workbench for high-frequency operations users. Operators should be able to find failed, blocked, retryable, and stalled document jobs; understand the likely cause; inspect key evidence; refresh or retry work in batches; and keep enough URL state to return to the same triage context.

This is the fourth frontend operations round after:

- Round 1: dense list, filter, batch action, and QA queue surfaces.
- Round 2: protected app shell with sidebar/topbar navigation.
- Round 3: QA review drawer and shared QA review panel.

The product direction remains a dense, efficient, low-distraction operations workbench.

## Current Context

- Frontend router: `frontend/src/router/index.ts`
- App shell navigation: `frontend/src/navigation/appShell.ts`
- Existing general jobs workbench: `frontend/src/pages/JobsPage.vue`
- Existing ops dashboard: `frontend/src/pages/OpsDashboardPage.vue`
- Existing QA queue drawer pattern: `frontend/src/pages/TranslationQaQueuePage.vue`
- Existing document job API wrapper: `frontend/src/api/documentJobs.ts`
- Existing frontend contracts: `frontend/src/api/types.ts`
- Backend document job router/service/schemas:
  - `app/domains/document_jobs/router.py`
  - `app/domains/document_jobs/service.py`
  - `app/domains/document_jobs/schemas.py`

Useful existing behavior:

- `documentJobsApi.list` supports generic job filtering and sorting.
- `documentJobsApi.retry` and `documentJobsApi.bulkRetry` already exist.
- Backend `DocumentJobResponse` includes status, stage, failed stage, error code, error message, retry count, timeout, timestamps, and `available_actions`.
- Backend `build_available_actions` exposes retry availability and disabled reason.
- `JobsPage.vue` already has batch result handling for failed batch items.
- `OpsDashboardPage.vue` already links users toward failed jobs, but is not a dedicated high-frequency triage surface.

## Requirements

### R1. Independent Incident Queue Page

Create an independent incident/failed-job triage page.

- Add a protected route, suggested path: `/incidents` or `/ops/incidents`.
- Add a sidebar first-level entry, suggested label: `异常处理` or `失败分诊`.
- Keep the page visually consistent with the existing protected app shell and dense operations pages.
- Do not replace `JobsPage.vue`; the incident page is a focused operations surface.

### R2. Incident Coverage

The first version covers:

- failed jobs
- blocked jobs
- retryable failures
- long-running or stalled jobs

The page does not become a full incident management system.

### R3. Dedicated Lightweight Backend API

Add a dedicated lightweight incident queue API instead of overloading the generic jobs list.

The API should support, at minimum:

- incident queue query with pagination
- incident summary counts for the top filter strip
- incident diagnostics for a selected job
- batch retry using existing retry semantics
- batch refresh/status lookup if needed by the frontend

The implementation should reuse existing document job service rules where practical, especially retry eligibility and available action semantics.

Do not introduce a full `Incident` or `Error` resource model in this round.

### R4. Lightweight Failure Classification

Add lightweight rule-based incident classification.

Suggested initial failure types:

- `conversion_failed`
- `translation_failed`
- `qa_unavailable`
- `artifact_missing`
- `timeout_or_stalled`
- `worker_or_dispatch_failed`
- `unknown`

Classification may use existing job status, stage, failed stage, error code/message, missing artifacts, timeout fields, and available action state.

Do not add configurable classification rules in this round.

### R5. Operations Triage Filters

The incident queue should include filters oriented around operator triage:

- status
- stage or failed stage
- failure type
- retryable
- retry count
- updated time or stalled duration
- keyword search

Do not build saved views or an advanced filter builder in this round.

### R6. Default Priority Sort

Default sort should prioritize the next most useful operator action:

1. stalled or blocked items
2. retryable failures
3. non-retryable failures
4. other incidents

Within the same priority group, use the current queue sort order, normally most recently updated first.

Keep table header sorting where it fits the existing table pattern.

### R7. Diagnostic Drawer

Use a right-side diagnostic drawer with summary plus key evidence.

The drawer should show:

- job id, filename/source reference when available, status, stage, failed stage
- failure type and retryability
- error code and recent error message
- retry count and relevant timestamps
- key evidence links or summaries:
  - task detail page
  - events or logs if already available
  - files/artifacts if already available
  - QA page/diagnostics if relevant
- suggested next action

Do not move a full log viewer or full detail page into the drawer.

### R8. Lightweight Suggestions

Show lightweight suggestions in the list row and drawer.

Examples:

- `可直接重试`
- `缺少产物，先打开详情检查`
- `多次失败，建议查看事件日志`
- `长时间未更新，先刷新状态`

Suggestions should derive from lightweight failure classification and existing action availability. Do not build a full runbook system.

### R9. Single And Batch Actions

Support:

- single retry
- batch retry
- batch refresh/status refresh
- open diagnostic drawer
- open job detail

Safety behavior:

- Single retry can execute directly when the item is retryable.
- Batch retry must show a lightweight confirmation with selected count, retryable count, non-retryable count, and expected impact.
- Do not add batch cancel or manual resolution marking in this round.

### R10. Batch Result Feedback

After a batch operation, show a result strip above the list.

The result strip should include:

- succeeded count
- failed count
- skipped count when applicable
- expandable failed item details with reason
- quick actions such as refresh and reselect failed items where practical

Do not create a persistent batch operation history center.

### R11. URL State

Sync only durable triage state to URL query.

Include:

- major filters such as status, failure type, retryable, stage, keyword
- current diagnostic drawer item, suggested key: `incident_job_id`

Do not sync:

- selected batch items
- scroll position
- temporary batch result strip
- unsaved UI-only draft state

### R12. Refresh Strategy

Support manual refresh plus lightweight automatic refresh.

- Provide a clear refresh button.
- Periodically refresh queue summary/list.
- Avoid interrupting when a diagnostic drawer is being actively reviewed or a batch operation is running.
- Do not add WebSocket or SSE realtime push in this round.

### R13. Keyboard Shortcuts

Add a small safe shortcut set with visible hints.

Suggested shortcuts:

- `R`: refresh queue
- `Esc`: close drawer
- `Cmd/Ctrl + Enter`: execute the current primary drawer action when safe
- `J` / `K`: move through rows or drawer items where appropriate

Rules:

- Show shortcut hints in the toolbar, drawer footer, or tooltips.
- Do not add dangerous single-key batch retry.
- Do not fire shortcuts while an input, textarea, select, or contenteditable element is focused.

### R14. Visual Design Constraints

Follow the current frontend layout guidelines.

- Use dense command headers, table-first queue layout, compact filter strips, and stable action bars.
- Reuse existing `--app-*` design tokens and Element Plus patterns.
- Avoid nested cards, oversized hero sections, decorative gradients, and low-density marketing layout.
- Make desktop and mobile states explicit; on narrow widths, preserve readability and action reachability.

## Acceptance Criteria

- A new incident triage route is available and protected by appropriate permissions.
- Sidebar navigation exposes the incident page as a first-level operations entry.
- The incident queue lists failed, blocked, retryable, and stalled jobs using the dedicated API.
- Operators can filter by status, stage/failed stage, failure type, retryability, retry count, time/stalled duration, and keyword.
- Default sort follows operations priority, then updated time within a priority group.
- A right-side diagnostic drawer opens from a row and restores from `incident_job_id`.
- URL query restores durable filters and the current drawer item.
- The drawer shows summary, key evidence entries, retryability, and suggested next action.
- Single retry uses existing retry semantics.
- Batch retry requires confirmation and handles partial success/failure.
- Batch refresh/status refresh updates the queue without losing durable filter state.
- Batch result strip shows success/failure/skipped counts and expandable failed details.
- Lightweight auto-refresh does not disrupt active drawer review or batch operations.
- Shortcut hints are visible and shortcuts do not fire while typing.
- Existing Jobs, Ops Dashboard, QA Queue, and QA Detail flows remain functional.

## Definition Of Done

- Backend request/response schemas and service logic are covered by targeted tests.
- Frontend helpers for classification, priority sort, URL state, or shortcuts are tested when extracted.
- `npm run build` passes in `frontend/`.
- Relevant backend test command passes for the touched document job/incident API surface.
- Browser smoke checks cover desktop and mobile incident queue layout, drawer, URL restore, batch retry confirmation, and batch result strip.
- Documentation/spec updates are considered if a new reusable incident queue pattern or backend classification contract emerges.

## Technical Approach

Use a lightweight aggregate API rather than a new persistent incident domain.

Recommended backend shape:

- Keep ownership near document jobs unless implementation evidence points elsewhere.
- Add schemas for incident list item, summary, diagnostics, and batch action results.
- Reuse `DocumentJobService.list_jobs`, retry eligibility, and `build_available_actions` where feasible.
- Keep classification deterministic and local to a service/helper function.
- Ensure retry endpoints continue to enforce true backend eligibility; frontend affordances are advisory only.

Recommended frontend shape:

- Add a new page component, for example `IncidentTriagePage.vue`.
- Add API wrapper/types to `documentJobs.ts` / `types.ts` or a small dedicated incident API module if the backend endpoint is not nested under document jobs.
- Add route and app shell ownership in `router/index.ts` and `navigation/appShell.ts`.
- Reuse table/filter/batch-result/drawer patterns from `JobsPage.vue` and `TranslationQaQueuePage.vue`.
- Keep diagnostic drawer as a focused triage surface, not a duplicate detail page.

## Decision (ADR-lite)

**Context**: The general jobs list and ops dashboard already expose failed-job information, but neither is optimized for high-frequency failure triage and safe batch recovery.

**Decision**: Build an independent incident triage workbench with a dedicated lightweight backend API, rule-based failure classification, right-side diagnostic drawer, batch retry/refresh, durable URL filters, and small safe shortcuts.

**Consequences**: This adds a new frontend page and a small backend API surface, but avoids overloading the generic jobs list and avoids introducing a full incident management domain before the product need is proven.

## Out Of Scope

- Full `Incident` or `Error` resource lifecycle model.
- Configurable classification rules.
- Full log viewer or full diagnostic panel inside the drawer.
- Batch cancel.
- Manual resolution/assignment/status marking.
- Saved filter views or advanced filter builder.
- Persistent batch operation history center.
- WebSocket/SSE realtime updates.
- Full runbook system.
- Global app shell redesign beyond adding the new nav item.

## Technical Notes

- Frontend layout spec: `.trellis/spec/frontend/index.md` and `.trellis/spec/frontend/layout-guidelines.md`.
- Backend specs: `.trellis/spec/backend/index.md`, especially directory structure, error handling, logging, database, and quality guidelines.
- Existing backend bulk retry response already allows partial success through `DocumentJobBulkResponse`.
- Existing backend `DocumentJobResponse.available_actions.retry` already carries retry eligibility and disabled reason.
- Existing `JobsPage.vue` batch result UI can inform the incident result strip, but the incident page should not inherit unrelated archive/cancel/delete behaviors.
- Existing `TranslationQaQueuePage.vue` drawer and URL-state patterns can inform the diagnostic drawer.
- Codex manual was checked for current `/plan` and `/goal` usage guidance; use `/plan` to shape implementation before starting a persistent `/goal`.

