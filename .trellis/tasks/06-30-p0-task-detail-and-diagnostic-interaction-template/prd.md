# P0 task detail and diagnostic interaction template

## Goal

Plan a unified task detail, diagnostic evidence, and right-drawer interaction template for job diagnostics, incident drawers, and translation QA review flows.

## Background

- The frontend already has one full detail page and at least two drawer-based evidence/review surfaces.
- These are not generic “details”; they are operator evidence surfaces where ordering, copyability, and keyboard handling matter more than decorative consistency.
- This child task should define how evidence-heavy surfaces read and behave before later page-level implementation.

## Confirmed Facts

- `frontend/src/pages/JobDetailPage.vue` already separates overview, diagnostics, files, events, and configuration evidence.
- `frontend/src/pages/IncidentTriagePage.vue` already uses a right drawer for diagnostic triage and quick action.
- `frontend/src/components/TranslationQaReviewPanel.vue` already provides a dense QA review drawer with segment navigation, evidence summary, and keyboard hints.
- The current project already exposes technical IDs, file IDs, event summaries, and diff-like payloads that operators need to read and copy.
- Existing patterns already use loading skeletons, empty states, and `ApiErrorAlert`, but the information hierarchy differs between the page and drawer variants.

## Requirements

- Define a consistent evidence-reading order for task detail and drawer-based diagnostics.
- Preserve keyboard-driven workflows, segment navigation, and evidence copyability for operators.
- Separate executive summary, recommended action, critical evidence, and low-level technical detail.
- Standardize drawer, tab, and detail-panel behavior without flattening job-specific business logic.

## Acceptance Criteria

- [ ] The detail template defines a stable sequence such as status, recommended action, evidence summary, technical traces, and supporting history.
- [ ] Right drawers specify close behavior, focus return, keyboard access, and small-screen width constraints.
- [ ] Technical IDs, logs, and diff-like payloads have a consistent visual treatment and remain copy-friendly.
- [ ] Job detail page and drawer diagnostics both define `loading/empty/error` presentation rules.
- [ ] The PRD distinguishes what belongs in the primary detail surface versus the secondary drawer surface.

## Out Of Scope

- The list-workbench template for queue pages.
- Token and shell decisions.
- Dashboard/governance pages that are not centered on single-item diagnostics.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
