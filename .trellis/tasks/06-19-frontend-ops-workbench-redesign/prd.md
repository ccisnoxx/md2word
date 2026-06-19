# Frontend Operations Workbench Redesign Planning

## Goal

Redesign the md2word frontend's highest-frequency operations surfaces so internal operators can triage exceptions, filter work, process batches, and review QA queues with less visual noise and fewer navigation steps.

This task is planning-only for now: produce a lightweight design system and PRD. It must not implement frontend changes until a later execution session starts the Trellis task.

## What I Already Know

* The product is an internal PDF to DOCX delivery and QA workbench, not a generic SaaS landing page.
* The frontend stack is Vue 3, Vite, TypeScript, Element Plus, Pinia, and Vue Router.
* The current workbench already has global design tokens under `frontend/src/styles/main.scss`.
* The current protected layout is in `frontend/src/layouts/AppLayout.vue`.
* The first redesign pass should focus on:
  * `frontend/src/pages/JobsPage.vue`
  * `frontend/src/components/JobTable.vue`
  * `frontend/src/pages/TranslationQaQueuePage.vue`
* The user chose a high-frequency operations workbench direction:
  * balanced high density
  * exception-first page hierarchy
  * reduced visual noise
  * Jobs and QA queue as the first page-level targets

## Requirements

### R1. Lightweight Design System

Create and use a lightweight design system for the operations workbench redesign.

The design system must define:

* Product positioning.
* Visual tone.
* Color usage.
* Density expectations.
* Page layout patterns.
* Table and filtering patterns.
* Batch action behavior.
* QA inbox target model.
* Empty/error state rules.
* Accessibility and responsive expectations.

Current artifact:

* `design-system.md`

### R2. Jobs Page Target Structure

`JobsPage` should move away from large hero/metric-card emphasis and toward a compact operations layout:

* Compact command header.
* Work queue strip for failed, stale, pending QA, and blocked work.
* Basic filters always visible.
* Advanced filters in popover/drawer.
* Active filter chips.
* Table placed high enough to remain a first-screen focus on desktop.

### R3. Job Table Information Architecture

`JobTable` should use a main-column-first architecture:

* Main column combines file/job identity and failure summary.
* Status, QA, progress, updated time, and actions remain scannable.
* Low-frequency metadata moves to tooltip, expanded row, or detail page.
* Per-row actions use "primary action plus more menu".

### R4. Batch Operations

Selected jobs should reveal a bottom sticky action bar.

It must show:

* selected count
* actionable subgroup counts
* batch retry
* batch cancel
* batch archive
* clear selection

Dangerous or irreversible operations must still require explicit confirmation.

### R5. Translation QA Queue Target Structure

`TranslationQaQueuePage` should move toward a task inbox model:

* Work queue summary for pending review, needs fix, blocked, and cleared states.
* Compact QA queue table.
* Primary action to enter review/QA.
* First-pass structural placeholder for a future right-side processing drawer.

Full segment-level drawer implementation can be deferred if it would broaden the task too much.

### R6. Global Navigation Target

The target global layout is a left compact sidebar plus a top status bar.

This should be treated as a follow-up phase unless explicitly pulled into scope later. It affects global layout, permission-filtered navigation, responsive behavior, and every page width.

### R7. Responsive And Theme Behavior

* Desktop is the primary operating target.
* Mobile must remain usable and avoid uncontrolled horizontal overflow.
* Light mode is the primary visual target.
* Dark mode must remain readable and should receive matching noise reduction where token changes affect it.

### R8. Empty And Error States

Empty and error states should be actionable, compact, and operational:

* No jobs: create job.
* Filter has no result: clear filters.
* Load failure: retry and show diagnostic context.
* QA queue empty: show queue is clear and provide view-all or processed-state navigation.

## Acceptance Criteria

Planning acceptance:

* [x] Trellis task exists and remains in `planning` status.
* [x] Lightweight design system exists at `design-system.md`.
* [x] PRD documents the first-pass scope and out-of-scope boundaries.
* [x] The plan records that frontend implementation should not start in this session.
* [x] The plan records how `/plan` and `/goal` should be used in a future session.

Implementation acceptance for a later session:

* [ ] `npm run build` passes in `frontend/`.
* [ ] Playwright or equivalent browser screenshots cover `JobsPage`, `TranslationQaQueuePage`, and the protected layout/login entry at 1440px and 375px.
* [ ] No obvious overlap, uncontrolled horizontal overflow, hidden sticky controls, or broken light/dark contrast is visible in checked screenshots.
* [ ] `JobsPage` uses compact command header, work queue strip, two-tier filters, and high-priority table placement.
* [ ] `JobTable` uses main-column-first information architecture and "primary action plus more menu".
* [ ] Selected jobs show a bottom sticky bulk action bar without hiding pagination.
* [ ] `TranslationQaQueuePage` presents a QA inbox model and reserves a clear path for a right-side processing drawer.

## Definition Of Done

Planning phase:

* Design decisions are written to task files.
* Open implementation scope is explicit.
* No frontend code is changed.
* Task is left in planning status.

Implementation phase:

* Code follows existing Vue, TypeScript, Element Plus, and app token patterns.
* Build and targeted visual verification are run or explicitly documented as blocked.
* Comments/docs are updated only where behavior or non-obvious UI patterns change.
* The implementation does not introduce parallel design-token sources of truth.

## Recommended Execution Flow

Use `/plan` first in a new Codex session to turn this PRD into a concrete implementation plan. Then use `/goal` only after the plan is agreed.

Recommended sequence:

1. Open a new Codex session in `/Users/sc/PycharmProjects/md2word`.
2. Start with `/plan` and ask Codex to inspect this task's `prd.md` and `design-system.md`, then produce a staged implementation plan.
3. Confirm or edit the plan.
4. Start `/goal` with the refined implementation objective.
5. Let Codex run the Trellis execution path, including `trellis-before-dev`, implementation, `trellis-check`, and verification.

Codex manual notes used:

* `/plan` switches the conversation into plan mode for multi-step planning.
* `/goal` sets a persistent objective and the manual recommends using `/plan` first to shape it.
* If `/goal` is unavailable, enable `features.goals` in `config.toml` or run `codex features enable goals`.

## Suggested New Session Prompt

```text
/plan
We are in /Users/sc/PycharmProjects/md2word. Continue the Trellis task at .trellis/tasks/06-19-frontend-ops-workbench-redesign.

Do not implement yet. Read:
- .trellis/tasks/06-19-frontend-ops-workbench-redesign/prd.md
- .trellis/tasks/06-19-frontend-ops-workbench-redesign/design-system.md
- relevant Trellis workflow/spec guidance

Then produce a staged implementation plan for the first pass only:
1. JobsPage compact operations layout
2. JobTable main-column-first + primary-action/more-menu actions
3. bottom sticky bulk action bar
4. TranslationQaQueuePage inbox-style structure
5. build + Playwright screenshot verification

Keep global sidebar navigation as a follow-up phase unless you find it is required.
```

After approving the plan, use:

```text
/goal Implement the first-pass md2word operations workbench redesign from .trellis/tasks/06-19-frontend-ops-workbench-redesign/prd.md and design-system.md. Keep scope to JobsPage, JobTable, TranslationQaQueuePage, and required shared styling. Run frontend build and targeted Playwright screenshot checks. Do not implement the global sidebar phase.
```

## Out Of Scope

* Implementing any frontend changes in this planning session.
* Full global sidebar migration in the first page-level redesign pass.
* Full mobile card-list redesign.
* Full segment-level QA drawer workflow if it expands backend/API or state-management scope.
* New font dependency unless justified in the implementation plan.
* Full design-token rewrite or complete component-library replacement.

## Technical Notes

Relevant files observed:

* `frontend/package.json`
* `frontend/src/styles/main.scss`
* `frontend/src/layouts/AppLayout.vue`
* `frontend/src/pages/JobsPage.vue`
* `frontend/src/components/JobTable.vue`
* `frontend/src/pages/TranslationQaQueuePage.vue`

Design research:

* `ui-ux-pro-max` matched the product most closely to a data-dense dashboard pattern.
* Relevant UX checks from `ui-ux-pro-max`: bulk actions, table handling, loading feedback, success/error feedback, and destructive-action confirmation.
* The broader generated conversion/landing-page pattern is intentionally rejected because this project is an internal operations workbench.

Codex workflow reference:

* Fresh Codex manual was fetched on 2026-06-19 through `openai-docs`.
* Manual path during this session: `/var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/openai-docs-cache/codex-manual.md`.
* Relevant manual sections: Codex app commands and slash commands for `/plan` and `/goal`.
