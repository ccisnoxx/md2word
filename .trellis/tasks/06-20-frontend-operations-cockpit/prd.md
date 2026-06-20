# Frontend Operations Cockpit

## Goal

Create a personal operations cockpit as the default high-frequency entry point for operators.

The cockpit should answer one question: what should I process next? It should aggregate actionable work from the existing Jobs, Translation QA, Incident triage, and Saved Views surfaces, then route the operator into the right existing page with the right query state.

This is the sixth frontend operations round after dense job/QA workbenches, shell navigation, QA review drawer, incident triage, and saved views.

## Product Positioning

This is an operational command surface, not a BI dashboard and not a marketing home page.

Design priorities:

- density
- speed
- scanability
- low visual noise
- direct entry into existing work queues
- partial failure tolerance

The current `OpsDashboardPage` at `/system-status/ops-dashboard` remains the admin/system-status page. The new cockpit is a personal operator landing page and must not replace system health, worker safety, fake delivery, or admin control-plane concepts.

## Current Context

- Protected app routes currently redirect the authenticated root route to `/jobs`.
- Login success currently routes authenticated users to `/jobs`.
- `JobsPage.vue`, `TranslationQaQueuePage.vue`, and `IncidentTriagePage.vue` already own durable filter and sort state through URL query params.
- Saved views now exist across the high-frequency pages with:
  - `savedViewsApi`
  - `SavedViewStrip.vue`
  - `systemSavedViews`
  - query builders for jobs, translation QA, and incidents
- The saved-view system supports personal defaults per page and system presets.
- `documentJobsApi.list` can provide compact job/QA list data.
- `documentJobIncidentsApi.list` can provide compact incident queue data.
- Frontend layout guidelines require compact workbench surfaces, stable grid rows, existing `--app-*` tokens, no decorative density loss, and desktop/mobile verification.

## Recommended Decisions

| Question | Recommended Choice |
|---|---|
| Sixth-round direction | Build a personal operations cockpit / today workbench |
| Primary user value | Show the next actionable work, then deep-link into existing pages |
| Route | Add `/cockpit` as a protected route |
| Navigation label | Add first processing nav item: `今日工作` |
| Default landing | Redirect protected root and normal post-login landing to `/cockpit` when accessible |
| Implementation model | Prefer a frontend aggregator that reuses existing list and saved-view APIs |
| Backend expansion | Add a read-only aggregate API only if repeated frontend calls become clearly fragile or slow |
| Saved views behavior | Show default personal views and fallback system presets; editing stays on existing target pages |
| Detail handling | Do not add new drawers in cockpit; route to existing Jobs/QA/Incident pages |
| Batch actions | Keep batch operations out of cockpit v1 |
| Visual direction | Dense SaaS operations dashboard: compact bands, tables, status chips, restrained palette |
| Relationship to OpsDashboard | Keep `/system-status/ops-dashboard` as admin/system operations; cockpit is personal work entry |

## Requirements

### R1. Route, Default Landing, And Navigation

Add a new protected cockpit route.

Expected route:

- path: `/cockpit`
- page component: `frontend/src/pages/OperationsCockpitPage.vue` or similarly named page
- route name/id: `cockpit`

Navigation:

- Add a first-level item under the processing group.
- Recommended label: `今日工作`.
- Put it before `任务列表`.
- Use a concise operations icon from the existing icon library.
- Keep `运维看板` under system navigation unchanged.

Default landing:

- Change the protected root redirect from `/jobs` to `/cockpit` when the user can access the cockpit.
- Change the authenticated login redirect from `/jobs` to `/cockpit` when accessible.
- If the user lacks all underlying cockpit page access, fall back to `/jobs` or the first accessible protected route.

### R2. Cockpit Page Purpose

The cockpit should be action-oriented.

It should show:

- urgent incidents
- translation QA work needing review or correction
- active/stale/failed jobs
- personal default saved views
- compact previews of the next work items

It should not show:

- decorative hero content
- broad BI trend charts
- admin-only system controls
- large explanatory copy
- custom dashboard layout editing

### R3. Data Sources

Prefer reusing existing APIs in v1.

Expected sources:

- `documentJobsApi.list` for job summaries and translation QA queue previews
- `documentJobIncidentsApi.list` for incident priority and preview rows
- `savedViewsApi.list` for personal defaults and saved-view launchers
- `systemSavedViews` and saved-view query helpers for fallback quick links

The implementation may add a small frontend service/composable such as `useOperationsCockpit` if that reduces duplication and keeps loading/error state legible.

Add a backend aggregate endpoint only if implementation evidence shows that the frontend needs too many fragile calls or cannot compute the required summaries from existing APIs. If added, it must be read-only and must not introduce new workflow state.

### R4. Priority Work Strip

Add a compact top strip that shows the highest-value queues.

Recommended items:

- retryable incidents
- stalled incidents
- QA blocked
- QA needs fix
- QA unreviewed
- failed jobs
- active or stale running jobs

Each item should include:

- label
- count or compact status
- severity/priority styling
- direct link to the existing target page with the correct query

The strip must stay stable in height and must not reflow into large cards on desktop.

### R5. Saved View Launcher

Add a cockpit section for personal work entry.

Behavior:

- Load saved views for `jobs`, `translation_qa`, and `incidents`.
- Prefer the user's personal default view for each page.
- If a page has no personal default, show relevant system presets as fallback.
- Each saved-view entry routes to the target page with the query generated by existing saved-view helpers.
- Do not implement create, rename, delete, reorder, or set-default actions in the cockpit.
- If no defaults exist, show a compact hint that links to the relevant page where the user can save or set a default view.

### R6. Today Queue Preview

Add a compact preview table or list for the next items to process.

Recommended fields:

- source type: incident, QA, or job
- job id/name
- current status
- age or last updated time
- suggested action
- target page action

Rules:

- Keep identity in the first meaningful column.
- Show only a small number of items per source.
- Do not duplicate full target page tables.
- Row actions should route to existing pages and query/drawer state when appropriate.
- Low-frequency actions stay out of the cockpit.

### R7. URL And Deep-Link Semantics

The cockpit must route into existing pages instead of becoming a second implementation of those pages.

Expected route generation:

- Jobs links use `jobsSavedViewStateToQuery`.
- Translation QA links use `translationQaSavedViewStateToQuery`.
- Incident links use `incidentsSavedViewStateToQuery`.
- If a preview row opens a detail drawer on a target page, use that page's existing query parameter such as `qa_job_id` or `incident_job_id`.

Existing target page URL behavior remains the source of truth.

### R8. Loading, Empty, And Partial Error States

The cockpit must remain useful when one source fails.

Behavior:

- Show an initial compact loading state.
- Let each module load independently where practical.
- A failed incidents module should not block saved views or jobs.
- A failed saved-view call should not block queue preview modules.
- Use compact inline error states with retry affordances.
- Show empty states that point users to the relevant existing page.

No broad silent fallback should hide API failures.

### R9. Permissions And Access

The cockpit must respect existing route/page permissions.

Rules:

- Hide modules for pages the user cannot access.
- Do not fetch saved views or queue data for inaccessible pages.
- If all cockpit sources are unavailable, show a compact no-access or empty-access state and provide a fallback route.
- Do not expose admin/system operations data from `/system-status/ops-dashboard`.

### R10. Responsive Dense Layout

Use the existing protected shell and app tokens.

Design constraints:

- Use `main.app-page`.
- If the page root uses CSS grid, set `align-content: start` and `grid-auto-rows: max-content`.
- Use existing `--app-*` colors, spacing, borders, radius, and shadows.
- Prefer flat or lightly elevated panels.
- Avoid broad gradients, glass effects, decorative backgrounds, and large hero sections.
- Do not place UI cards inside other cards.
- Keep text compact but legible.
- Ensure desktop and mobile do not create uncontrolled horizontal overflow.
- On mobile, preserve priority order: work strip, saved-view launcher, queue preview.

## Acceptance Criteria

- `/cockpit` exists as a protected route.
- The sidebar includes a processing nav item labeled `今日工作` before `任务列表`.
- Authenticated default landing routes to `/cockpit` when accessible, with a safe fallback when not accessible.
- `/system-status/ops-dashboard` remains available and semantically separate.
- The cockpit shows priority work modules for incidents, QA, and jobs when the user can access those pages.
- Priority modules link to existing target pages with correct query params.
- The cockpit shows personal default saved views and system preset fallbacks for jobs, translation QA, and incidents.
- Saved-view launcher links use existing saved-view query helper semantics.
- The cockpit includes a compact queue preview with direct target-page actions.
- Loading, empty, and partial-error states are visible and do not block unrelated modules.
- Permission-restricted modules are hidden and not fetched.
- The page is visually dense, low-noise, and follows the frontend layout guidelines.
- Desktop and mobile layouts have no uncontrolled body/document horizontal overflow.
- Existing Jobs, Translation QA, Incident, Saved Views, QA drawer, Incident drawer, and OpsDashboard behavior remains functional.

## Definition Of Done

- Trellis frontend specs are read before implementation.
- Route/nav/default landing changes are covered by targeted checks where practical.
- Cockpit data-loading helpers or composables have focused tests if non-trivial.
- Saved-view route-generation behavior reuses existing helpers and has targeted coverage if new adapters are introduced.
- `npm run build` passes in `frontend/`.
- A browser smoke check covers `/cockpit` at desktop width around `1440px`.
- A browser smoke check covers `/cockpit` at mobile width around `375px`.
- Verification checks for uncontrolled horizontal overflow.
- If a backend aggregate endpoint is added, backend tests cover permissions, partial data, and read-only behavior.

## Technical Approach

Frontend-first recommended path:

1. Add route and navigation id for the cockpit.
2. Update default protected redirect and authenticated login redirect with fallback behavior.
3. Add `OperationsCockpitPage.vue`.
4. Add a small cockpit data helper/composable only if it keeps API loading and partial errors clear.
5. Reuse `documentJobsApi.list`, `documentJobIncidentsApi.list`, `savedViewsApi.list`, `systemSavedViews`, and saved-view query builders.
6. Build compact modules:
   - priority work strip
   - saved-view launcher
   - today queue preview
7. Keep all detail work on existing target pages.
8. Add targeted tests and run build/browser checks.

Backend path only if required:

- Add a read-only aggregate endpoint that returns cockpit summaries and preview rows.
- Keep ownership, tenant/company scoping, and permissions aligned with existing APIs.
- Do not add new persistent workflow state or duplicate existing queue semantics.

## Out Of Scope

- BI analytics dashboard.
- Charts-heavy reporting.
- Team assignment, ownership queues, or workload balancing.
- Customizable drag/drop homepage.
- Batch operations directly from cockpit.
- Editing saved views inside cockpit.
- Realtime push or websocket updates.
- Replacing `/system-status/ops-dashboard`.
- Admin/system health controls.
- New persistent notification/task-center resource.
- New workflow state beyond existing jobs, QA, incidents, and saved views.

## Technical Notes

- Frontend layout spec: `.trellis/spec/frontend/layout-guidelines.md`.
- Existing route/nav files:
  - `frontend/src/router/index.ts`
  - `frontend/src/navigation/appShell.ts`
- Existing saved-view files:
  - `frontend/src/api/savedViews.ts`
  - `frontend/src/components/SavedViewStrip.vue`
  - `frontend/src/utils/savedViews.ts`
- Existing queue API wrappers:
  - `frontend/src/api/documentJobs.ts`
  - `frontend/src/api/documentJobIncidents.ts`
- Existing pages to preserve:
  - `frontend/src/pages/JobsPage.vue`
  - `frontend/src/pages/TranslationQaQueuePage.vue`
  - `frontend/src/pages/IncidentTriagePage.vue`
  - `frontend/src/pages/OpsDashboardPage.vue`

## ADR-lite

**Context**: Operators now have dense pages for job handling, QA review, incident triage, and saved views, but the default entry remains the job list. That forces users to decide where to start instead of surfacing the most actionable work.

**Decision**: Add a personal operations cockpit as the default protected landing page. The cockpit reuses existing APIs and query semantics, shows compact priority work, and routes users into existing specialized pages for actual handling.

**Consequences**: This adds one new frontend page and route/nav/default landing behavior. It avoids creating a second implementation of job, QA, or incident workflows, and keeps system operations separate from personal operator work.
