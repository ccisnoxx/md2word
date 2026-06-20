# Frontend Saved Views Workbench

## Goal

Add system presets and personal saved views across the three high-frequency operations pages so operators can quickly return to their daily working context without repeatedly rebuilding filters.

Target pages:

- Jobs workbench: `frontend/src/pages/JobsPage.vue`
- Translation QA queue: `frontend/src/pages/TranslationQaQueuePage.vue`
- Incident triage queue: `frontend/src/pages/IncidentTriagePage.vue`

This is the fifth frontend operations round after dense job/QA surfaces, the app shell, QA review drawer, and incident triage workbench.

## Current Context

- All three target pages already use URL query state for durable filters and sort.
- `JobsPage.vue` owns filters for job status, active status group, translation QA status, keyword, sort, archive visibility, and created date range.
- `TranslationQaQueuePage.vue` owns filters for translation QA status, job status, keyword, sort, archive visibility, page, and `qa_job_id` drawer state.
- `IncidentTriagePage.vue` owns filters for status, stage, failure type, retryability, retry count, stalled minutes, keyword, sort, page, and `incident_job_id` drawer state.
- The incident page is now implemented through `frontend/src/api/documentJobIncidents.ts` and `app/domains/document_jobs/incidents_router.py`.
- There is no existing `saved_views` or user preference resource.
- Backend metadata persistence supports file, sqlite, and MySQL adapters; new persisted metadata must keep adapter parity.

## Confirmed Decisions

| Question | Decision |
|---|---|
| Fifth-round direction | Operations saved views and quick entry |
| Save scope | System presets plus personal saved views |
| Covered pages | Jobs, Translation QA queue, Incident triage |
| Storage | Backend persistence by authenticated user |
| API/model boundary | New unified `saved_views` resource |
| Core fields | `page_key`, `name`, `filters`, `sort`, `is_default`, `position` |
| Personal capabilities | Save current view, update, rename, delete, reorder, set default |
| UI entry | Compact view strip above each page's filter controls |
| URL behavior | Applying a view writes its filters/sort to the existing URL query |
| Permission boundary | Current user's personal views only; no team sharing |

## Requirements

### R1. Unified Saved Views Resource

Add a lightweight backend `saved_views` resource for personal saved views.

Required persisted fields:

- `view_id`
- `tenant_id`
- `company_id`
- `owner_user_id`
- `page_key`
- `name`
- `filters`
- `sort`
- `is_default`
- `position`
- `created_at`
- `updated_at`

Supported `page_key` values:

- `jobs`
- `translation_qa`
- `incidents`

The resource stores personal views only. System presets are read-only definitions in code for this round unless implementation evidence shows a cleaner read-only backend projection.

### R2. Saved Views API

Add a thin API for the authenticated user.

Suggested endpoints:

- `GET /api/v1/saved-views?page_key=<page_key>`
- `POST /api/v1/saved-views`
- `PATCH /api/v1/saved-views/{view_id}`
- `DELETE /api/v1/saved-views/{view_id}`
- `POST /api/v1/saved-views/reorder`

Behavior:

- List returns only views owned by the current authenticated user.
- Create saves a personal view for one page.
- Patch supports renaming, updating filters/sort, changing default state, and updating position.
- Delete removes only the current user's personal view.
- Reorder updates positions for one page in one request.
- Setting `is_default=true` clears the previous personal default for the same user and page.

### R3. Backend Persistence

Implement persistence with parity across file, sqlite, and MySQL metadata backends.

- Add a domain package such as `app/domains/saved_views/`.
- Add repository protocols in the domain package.
- Add file/sqlite/MySQL adapters under `app/infrastructure/persistence/`.
- Wire the service and router through `app/main.py`, `app/core/runtime.py`, and `app/api/v1/router.py`.
- Add idempotent schema bootstrap for sqlite and MySQL.
- Do not use ORM or one-off SQL outside repository adapters.

### R4. Validation Rules

Validate saved view payloads at the backend boundary.

Common rules:

- `page_key` must be one of the supported pages.
- `name` is trimmed and length-limited.
- Personal view names should be unique per user and page after normalization.
- Limit personal views per page, suggested maximum: 20.
- `filters` must be a JSON object with only allowlisted keys for that page.
- `sort` must be allowed for that page.
- Reject page state that should not be saved.

Do not save:

- selected batch item ids
- current page number
- page size
- scroll position
- temporary batch result strips
- drawer ids such as `qa_job_id` and `incident_job_id`
- form drafts or review notes

### R5. Page-Specific Saved State

Save only the durable filters and sort that define a reusable view.

`jobs` allowlist:

- `status`
- `status_group`
- `translation_qa_status`
- `q`
- `include_archived`
- `created_from`
- `created_to`
- `sort`

`translation_qa` allowlist:

- `translation_qa_status`
- `status`
- `q`
- `include_archived`
- `sort`

`incidents` allowlist:

- `status`
- `stage`
- `failure_type`
- `retryable`
- `retry_count`
- `stalled_minutes`
- `q`
- `sort`

### R6. System Presets

Add read-only system presets for each covered page.

Suggested Jobs presets:

- Active jobs
- Failed jobs
- Pending QA
- Blocked QA

Suggested Translation QA presets:

- Unreviewed
- Needs fix
- Blocked
- Approved

Suggested Incident presets:

- Retryable failures
- Stalled first
- Artifact missing
- Multiple retries

System presets:

- are always available when the user can access the page
- cannot be renamed, deleted, or reordered
- can be applied like personal views
- can be saved as a personal view through "save current view"

### R7. Compact View Strip UI

Add a compact saved-view strip above the filter controls on each covered page.

The strip should include:

- system presets
- personal views ordered by `position`
- active view indicator
- "save current view" action
- overflow menu for personal view actions

Personal view actions:

- apply
- update this view from current filters
- rename
- delete
- move/reorder
- set as default

Use dense workbench styling:

- compact buttons or segmented chips
- stable height
- no nested cards
- no large explanatory blocks
- clear focus and hover states

### R8. Default View Behavior

Each page can have at most one personal default view.

Behavior:

- If the user opens a page with explicit filter/sort query params, do not override the URL.
- If the user opens a page without meaningful filter/sort query params, apply the user's default personal view for that page when one exists.
- If no personal default exists, use the page's existing default behavior and keep system presets available.
- Applying a default view should replace the route query with the view's filters/sort so the state is visible and recoverable.

### R9. URL Behavior

The URL remains the source of durable page state.

- Applying a saved view writes the view's filters/sort into the existing page query format.
- Do not require a `view_id` query param for correctness.
- If a view is later renamed or deleted, previously shared URLs with equivalent filters should still work.
- Drawer query params are preserved only when explicitly unrelated to applying a view; saving a view must not capture them.

### R10. Frontend Reuse

Create reusable frontend building blocks where they remove real duplication.

Expected candidates:

- `savedViewsApi` wrapper
- `SavedViewStrip.vue` or similarly scoped shared component
- page-specific adapter functions that map route/query/filter state to saved view payloads
- validation/type helpers for page keys and allowlisted query state

Keep page-specific filters owned by their existing pages. Do not centralize all page filtering into a global store in this round.

### R11. Permissions And Access

Saved views are personal and scoped to the authenticated user.

- Users can list and mutate only their own personal views.
- Users should not save views for pages they cannot access.
- System presets should be filtered by the same page access expectations as the underlying route.
- Do not add team-shared views, role-based edit rights, or admin management in this round.

### R12. Empty, Loading, And Error States

The view strip should handle:

- loading saved views
- failed saved-view API calls
- no personal views yet
- saving/updating/deleting in progress
- duplicate/invalid names
- stale view data after deletion or reorder

Errors should not block the underlying list page from loading. If saved views fail, show a compact inline error or notification and keep the normal filters usable.

## Acceptance Criteria

- Jobs, Translation QA, and Incident pages show a compact saved-view strip.
- Each page exposes system presets and can apply them to the page filters.
- Users can save the current filters/sort as a personal view.
- Users can update, rename, delete, reorder, and set a personal default view.
- Saved personal views persist through backend storage and are scoped to the current user.
- Applying a saved view updates the existing URL query format for the page.
- Page reload restores explicit URL query state and does not incorrectly override it with a default view.
- Opening a page without explicit query state applies the user's personal default when one exists.
- Saved views never store drawer ids, page number, selected rows, scroll state, temporary results, or form drafts.
- Backend rejects unsupported page keys, unsupported filters, unsupported sort values, duplicate names, and excessive saved views per page.
- Existing Jobs, Translation QA, Incident, QA drawer, and Incident drawer behavior remains functional.

## Definition Of Done

- Backend service, router, repository, and schema changes have targeted tests.
- File, sqlite, and MySQL persistence adapter behavior remains compatible.
- Frontend saved-view mapping helpers and component behavior have targeted tests where practical.
- `npm run build` passes in `frontend/`.
- Relevant backend tests pass for saved views and persistence parity.
- Browser smoke checks cover the saved-view strip on desktop and mobile for all three pages.
- Documentation/spec updates are considered if the saved-view resource becomes a reusable project contract.

## Technical Approach

Backend:

- Add a `saved_views` domain with thin router, service, schemas, model, and repository protocol.
- Add concrete repositories for file, sqlite, and MySQL backends.
- Use current authenticated user, tenant, and company data as ownership scope.
- Keep built-in presets out of persistence in this round.
- Keep routes thin and business rules in service code.

Frontend:

- Add `frontend/src/api/savedViews.ts` and corresponding types.
- Add shared saved-view UI and page-specific adapters.
- Integrate the view strip into `JobsPage.vue`, `TranslationQaQueuePage.vue`, and `IncidentTriagePage.vue`.
- Keep each page's existing filter state and route-sync logic as the source of truth.
- Apply views by setting existing filter refs and reusing each page's existing route-sync/load path.

## Decision (ADR-lite)

**Context**: The operations workbench now has multiple high-frequency pages. Operators need fast return paths to repeated filters, but a full workspace preference system or team-shared view model would expand scope too far.

**Decision**: Implement a unified personal `saved_views` resource plus read-only system presets across Jobs, Translation QA, and Incident pages.

**Consequences**: This adds a small persisted backend resource and shared frontend component, but keeps the feature focused on reusable triage filters and avoids broader workspace preference management.

## Out Of Scope

- Team-shared saved views.
- View ownership transfer or role-based edit permissions.
- Full workspace preference system.
- Column visibility, column order, column width, density, theme, or shortcut preferences.
- Saving selected rows, scroll position, page number, drawer state, or temporary batch results.
- Saved views for configuration, term, audit, file retention, or settings pages.
- Backend-managed system preset authoring UI.
- Import/export of saved views.

## Technical Notes

- Frontend layout spec: `.trellis/spec/frontend/index.md` and `.trellis/spec/frontend/layout-guidelines.md`.
- Backend specs: `.trellis/spec/backend/index.md`, especially directory structure, database, error handling, and quality guidelines.
- Current query-state functions in the target pages should guide the page-specific saved-view adapters.
- Existing fourth-round incident files are part of the target surface:
  - `frontend/src/pages/IncidentTriagePage.vue`
  - `frontend/src/api/documentJobIncidents.ts`
  - `app/domains/document_jobs/incidents_router.py`
- Codex manual was checked for current `/plan` and `/goal` guidance; use `/plan` to shape implementation before starting a persistent `/goal`.

