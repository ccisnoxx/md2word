# P1 dashboard and system workbench template

## Goal

Plan a consistent dashboard and system-status visual template across cockpit, system status, ops dashboard, and acceptance center, with clear KPI, alerts, and evidence hierarchy.

## Background

- The repository already contains multiple dashboard-like and system-facing pages, but they differ significantly in first-screen hierarchy and evidence grouping.
- These pages are less frequent than core workbenches, but they are denser and more risk-sensitive; they need a consistent template after P0 foundations stabilize.
- This child task should decide how operational status, advice, evidence, and optional charts fit together.

## Confirmed Facts

- `frontend/src/pages/OperationsCockpitPage.vue` already acts as a personal operator cockpit with saved-view entry and next-step previews.
- `frontend/src/pages/SystemStatusPage.vue` already presents readiness, metrics, and read-only backend/resource status.
- `frontend/src/pages/OpsDashboardPage.vue` is the densest operations page and already mixes KPI cards, alerts, controlled actions, contracts, dry-runs, and evidence panels.
- `frontend/src/pages/AcceptanceCenterPage.vue` already combines overview metrics, tier cards, list selection, and drawer review.
- The current design system should treat charts as optional because these pages are evidence- and action-heavy, not BI dashboards first.

## Requirements

- Define the dashboard information hierarchy for KPI cards, alert stacks, operational advice, evidence panels, and secondary references.
- Keep charts optional and purposeful; prioritize clarity of next actions over visual density for its own sake.
- Preserve freshness, dry-run, and safety semantics already present in system and operations pages.
- Ensure admin dashboards remain data-dense but calm, legible, and accessible.

## Acceptance Criteria

- [ ] Dashboard templates define where KPI cards, alerts, evidence panels, and reference links belong.
- [ ] Critical actions or blockers are visible in the first screenful on desktop layouts.
- [ ] Every data module defines `loading/empty/error/freshness` presentation expectations.
- [ ] Color is not the sole carrier of severity or state meaning.
- [ ] The PRD identifies when charts are warranted and when tables or evidence cards are preferable.

## Out Of Scope

- Replanning core list workbenches or single-job diagnostic drawers.
- Adopting charting dependencies before the hierarchy and need are validated.
- Backend feature additions or operational write-safety redesigns.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
