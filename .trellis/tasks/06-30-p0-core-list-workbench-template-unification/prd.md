# P0 core list workbench template unification

## Goal

Define the shared template for Jobs, Incident Triage, and Translation QA list workbenches, including filters, saved views, table density, bulk actions, and state handling.

## Background

- The three highest-frequency operator pages already share a clear workbench shape, but each page still composes that shape independently.
- These pages are the main day-to-day operator surface, so they should define the primary list-workbench template for the whole redesign.
- The goal is not to erase page-specific behavior, but to turn repeated structure into a stable template contract.

## Confirmed Facts

- `frontend/src/pages/JobsPage.vue`, `IncidentTriagePage.vue`, and `TranslationQaQueuePage.vue` all use command headers, summary strips, filters, and table/list workspaces.
- `frontend/src/components/SavedViewStrip.vue` is already a reusable pattern across multiple workbench pages.
- `frontend/src/components/WorkbenchTableSettings.vue` already exposes density, column visibility, and page-size preferences.
- `JobsPage.vue` and `IncidentTriagePage.vue` already support batch-action bars; `TranslationQaQueuePage.vue` currently uses a processing rail instead of batch actions.
- Existing smoke coverage already asserts responsive overflow and table-preference behavior, so later implementation should extend this protection rather than replace it.

## Requirements

- Normalize the page structure shared by `Jobs`, `Incident Triage`, and `Translation QA`.
- Keep existing domain-specific logic, but converge repetitive UI structure into one workbench template.
- Preserve saved-view, quick-filter, table-settings, and bulk-action behaviors as first-class workbench primitives.
- Make loading, empty, error, permission, and stale-data states visually consistent across the three pages.

## Acceptance Criteria

- [ ] The shared workbench template covers header, summary strip, saved views, filter zone, table zone, and bulk-action zone.
- [ ] Filter forms are required to support reset, route/state rehydration, and non-overlapping action controls.
- [ ] Tables define complete `loading/empty/error/permission` states and responsive behavior.
- [ ] Table settings remain operable and visible within the viewport on small screens.
- [ ] The PRD preserves page-specific exceptions instead of forcing an unrealistic one-size-fits-all layout.

## Out Of Scope

- Token, typography, and shell decisions owned by the shell/token child task.
- Single-job detail or drawer-based evidence interactions owned by the diagnostics child task.
- Dashboard/governance templates and long-tail admin convergence.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
