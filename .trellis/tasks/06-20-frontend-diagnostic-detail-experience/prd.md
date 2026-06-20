# Frontend Diagnostic Detail Experience

## Goal

Improve the diagnostic detail experience for high-frequency operations workflows so Chinese-speaking operators can understand failures, evidence, and next steps faster after they open a failed job, an incident diagnostic drawer, or a QA review panel.

This is the ninth frontend operations round after:

- dense Jobs workbench
- Translation QA queue and review drawer
- app shell/sidebar
- Incident triage workbench
- saved views
- personal operations cockpit
- command palette, shortcut hints, and batch-result feedback
- workbench table preferences

The goal is not to show more raw fields. The goal is to reduce judgment cost: what happened, what evidence exists, what should the operator do next, and where should they go.

## Product Positioning

This task improves failure analysis and evidence reading for operations staff.

Design priorities:

- Chinese visible copy
- clear diagnostic summary
- evidence-first structure
- explicit recovery paths
- reuse existing APIs and action flows
- no automated repair logic
- low visual noise

The implementation should feel like a structured operations diagnostic surface, not a developer log viewer or an AI assistant.

## Current Context

- `JobDetailPage.vue` already has:
  - top `任务处置` card
  - `诊断` tab
  - quality evidence card
  - callback summary card
  - failed job card
  - event tab using `JobEventTimeline`
  - retry/clone/cancel/archive/delete dialogs and actions
- `IncidentTriagePage.vue` already has:
  - incident queue
  - `incident_job_id` deep-link drawer state
  - diagnostic drawer with summary, evidence, recent events, files, and retry/open-detail actions
  - `append-to-body` drawer behavior
- `TranslationQaReviewPanel.vue` already has:
  - QA summary strip
  - segment comparison
  - evidence summary
  - review status and issue type controls
- `ApiErrorAlert.vue` already provides normalized error copy, diagnostic metadata, operator hints, and copy-diagnostic behavior.
- `JobEventTimeline.vue` already renders document job events.
- The frontend layout spec requires compact protected workbench pages, document-level drawers, stable URL query behavior, and desktop/mobile checks.

## Problems And Recommended Choices

| Problem | Options | Recommended Choice |
|---|---|---|
| Ninth-round direction | 1. More table tuning; 2. Diagnostic detail experience; 3. System ops page cleanup | Choose 2 |
| Covered surfaces | 1. JobDetail only; 2. JobDetail + Incident drawer + QA panel; 3. all detail pages | Choose 2 |
| Primary goal | 1. Show more raw data; 2. reduce diagnostic judgment cost; 3. add automated repair | Choose 2 |
| Data source | 1. Reuse existing APIs; 2. add backend aggregate endpoint; 3. add persisted diagnostic resource | Choose 1 |
| Action safety | 1. read-only guidance + existing actions; 2. new direct recovery buttons; 3. automated retry/repair | Choose 1 |
| Event presentation | 1. raw event list only; 2. evidence timeline with important events highlighted; 3. full log explorer | Choose 2 |
| QA evidence | 1. keep current layout; 2. add clearer status/evidence grouping; 3. rebuild QA review flow | Choose 2 |
| Chinese copy | 1. new labels only; 2. diagnostic visible copy Chinese-first; 3. full app scan | Choose 2 |

## Requirements

### R1. Job Detail Diagnostic Summary

Improve the `JobDetailPage.vue` diagnostic structure without rewriting the whole page.

The page should make these questions easy to answer:

- What is the current outcome?
- Where did the job stop or fail?
- What evidence is available?
- What is the recommended next step?
- Which existing action should the operator use?

Expected additions or refinements:

- A compact diagnostic summary for failed, stalled, canceled, completed, and active states.
- A clear "下一步建议" area based on existing job status, stage, available actions, recent error event, files, and callback summary.
- Evidence cards that distinguish:
  - source file
  - generated result
  - DocumentIR
  - callback/problem messages
  - latest error event
- A compact event preview in the diagnostic area, linking or guiding users to the full event tab.

Rules:

- Keep raw `error_code`, `trace_id`, event type, file id, and stage visible as evidence.
- Surround raw technical values with Chinese labels and operator-oriented explanation.
- Do not infer retryability beyond existing backend `available_actions`.
- Do not add new backend requests unless current APIs are insufficient for already-displayed data.

### R2. Incident Diagnostic Drawer Refinement

Improve the existing incident diagnostic drawer in `IncidentTriagePage.vue`.

The drawer should have a consistent diagnostic hierarchy:

1. `诊断摘要`
2. `下一步建议`
3. `关键证据`
4. `事件时间线`
5. `文件与入口`
6. `操作`

Expected behavior:

- Keep `incident_job_id` query state.
- Keep `append-to-body`.
- Keep existing close behavior and shortcut behavior.
- Keep existing retry/open-detail actions.
- Add clearer recovery guidance for:
  - retryable incident
  - non-retryable incident
  - artifact missing
  - QA unavailable
  - stalled job
  - multiple retries
- Highlight recent error/warning events without hiding other recent events.

Rules:

- Do not create a second job detail page inside the drawer.
- Do not add new destructive actions.
- Do not make retry automatic.
- If the drawer data load fails, show a clear retry/recovery path.

### R3. Translation QA Evidence Readability

Improve `TranslationQaReviewPanel.vue` evidence readability.

The panel should help operators understand why a QA task is:

- `blocked`
- `needs_fix`
- `unreviewed`
- read-only because evidence is unavailable

Expected refinements:

- A clearer QA status/evidence summary that groups:
  - availability
  - issue type
  - source comparison availability
  - segment count
  - term trace count
  - AI call status
  - quality flags
- More understandable empty/unavailable evidence states.
- A concise "处理建议" line or block where the existing data supports it.

Rules:

- Do not change QA review persistence semantics.
- Do not add auto-approval or auto-rejection.
- Do not alter the saved review form contract.
- Keep segment navigation and existing shortcut hints functional.

### R4. Shared Diagnostic Presentation Helpers

Add shared helpers or components only where they reduce duplication across the target surfaces.

Reasonable candidates:

- diagnostic recommendation helper
- evidence item formatter
- event severity/timeline display helper
- compact diagnostic summary component

Rules:

- Keep page-specific business context close to the owning page.
- Do not introduce a generic diagnostic framework for the whole app.
- Do not duplicate existing `ApiErrorAlert` or `JobEventTimeline` behavior.
- Reuse existing components where possible.

### R5. Error Recovery UX

Errors in diagnostic surfaces should show recovery paths.

Requirements:

- Loading states must be visible.
- Empty states must explain what is missing and what the operator can do.
- Error states should provide a next action when available:
  - refresh diagnostic
  - reload events
  - open job detail
  - copy diagnostic
  - return to list
- Do not rely on color alone for failure/warning/success.
- Use `aria-live` or existing alert semantics for important diagnostic errors where practical.

### R6. Chinese-First Visible Copy

All new or changed visible diagnostic copy must be Chinese-first.

Allowed technical tokens:

- `QA`
- `DOCX`
- `PDF`
- `API`
- `DocumentIR`
- `trace_id`
- raw ids
- event codes
- error codes
- file ids

Rules:

- Technical tokens should be paired with Chinese labels.
- Do not translate code identifiers, route names, test names, API fields, or comments unnecessarily.
- Existing English table headers in diagnostic areas should be translated when they are operator-facing and not raw evidence labels.

### R7. Layout And Responsive Constraints

The diagnostic surfaces must stay dense and usable.

Requirements:

- Use existing `--app-*` tokens.
- Prefer flat or lightly elevated panels.
- No decorative gradients, hero sections, or marketing layout.
- Do not put cards inside cards.
- Job detail diagnostic sections should not become oversized.
- Incident drawer footer actions must remain visible and usable.
- QA panel must remain usable in the drawer and detail contexts.
- Verify desktop around `1440px`.
- Verify mobile around `375px`.
- No uncontrolled document/body horizontal overflow.

## Acceptance Criteria

- `JobDetailPage.vue` includes a clearer diagnostic summary and next-step guidance using existing job/events/files/callback data.
- Job detail preserves existing actions and dialogs.
- Job detail raw evidence values remain visible with Chinese labels.
- Incident diagnostic drawer uses a clearer hierarchy: summary, next step, evidence, event timeline, files/entry points, actions.
- Incident drawer preserves `incident_job_id` URL behavior and close behavior.
- Incident drawer retry/open-detail actions still use existing flows.
- QA review panel provides clearer evidence/status grouping and unavailable evidence guidance.
- QA review form submission and shortcut behavior remain unchanged.
- Diagnostic loading, empty, and error states include useful recovery paths.
- All new/changed visible diagnostic copy is Chinese-first.
- No new backend endpoint, persistence table, or API contract is required.
- Existing Jobs list, Incident list, QA queue, command palette, saved views, and table preferences remain functional.
- `npm run build` passes in `frontend/`.
- Browser smoke checks cover affected diagnostic surfaces on desktop and mobile.

## Definition Of Done

- Trellis frontend specs are read before implementation.
- Existing detail and drawer patterns are reused.
- New diagnostic helper logic has focused tests where practical.
- Existing tests for incident, QA, job detail, or utilities are updated when behavior changes.
- `npm run build` passes in `frontend/`.
- Browser smoke checks cover:
  - failed job detail diagnostic area
  - incident diagnostic drawer
  - QA review panel evidence area
- Verification checks no uncontrolled horizontal overflow.
- No backend migration or new API contract is introduced.

## Technical Approach

Recommended implementation path:

1. Audit current diagnostic copy and structure in `JobDetailPage.vue`, `IncidentTriagePage.vue`, and `TranslationQaReviewPanel.vue`.
2. Add small utility helpers only for repeated recommendation/evidence formatting.
3. Refine Job Detail diagnostic summary and next-step area.
4. Refine Incident drawer hierarchy and recovery guidance.
5. Refine QA evidence grouping and unavailable evidence states.
6. Translate remaining operator-facing diagnostic labels in the touched surfaces.
7. Add targeted tests for helper behavior and existing surface regressions where practical.
8. Run frontend build and browser smoke checks.

Implementation notes:

- Prefer computed values and existing API response fields over new API requests.
- Keep retryability and action availability driven by backend-provided action state.
- Keep route query contracts unchanged.
- Keep details accessible through existing full pages rather than duplicating full detail content inside drawers.

## Out Of Scope

- AI-generated diagnosis.
- New backend diagnostic aggregate endpoint.
- New persisted diagnostic resource.
- Automated repair, auto retry, or auto approval/rejection.
- Rewriting the entire Job Detail page.
- Rewriting the whole QA review flow.
- Replacing `ApiErrorAlert`.
- Replacing `JobEventTimeline` wholesale.
- System ops dashboard cleanup.
- Full app-wide diagnostic language scan.
- Team assignment or ownership workflows.

## Technical Notes

- Frontend layout spec: `.trellis/spec/frontend/layout-guidelines.md`.
- Target files:
  - `frontend/src/pages/JobDetailPage.vue`
  - `frontend/src/pages/IncidentTriagePage.vue`
  - `frontend/src/components/TranslationQaReviewPanel.vue`
- Existing helper/component files:
  - `frontend/src/components/ApiErrorAlert.vue`
  - `frontend/src/components/JobEventTimeline.vue`
  - `frontend/src/utils/incidents.ts`
  - `frontend/src/utils/translationQa.ts`
- Related features that must remain stable:
  - incident drawer deep links
  - QA drawer behavior
  - command palette
  - saved views
  - table preferences
  - batch result strips

## ADR-lite

**Context**: The frontend now has efficient entry points, table preferences, saved views, and command navigation. Operators can reach failures quickly, but detail surfaces still require reading multiple raw sections to decide what happened and what to do next.

**Decision**: Improve diagnostic detail experience in the existing frontend surfaces by adding clearer diagnostic summaries, evidence hierarchy, event previews, and recovery guidance while reusing current APIs and existing actions.

**Consequences**: Operators get faster failure triage without new backend scope or automated repair risk. The trade-off is that diagnostics remain a frontend presentation layer over existing data; deeper root-cause automation can be considered later if the current evidence proves insufficient.
