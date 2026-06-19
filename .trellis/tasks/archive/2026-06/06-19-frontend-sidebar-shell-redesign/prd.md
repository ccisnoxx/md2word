# Frontend Sidebar App Shell Redesign

## Goal

Introduce a global md2word operations app shell with a collapsible sidebar, workflow-based navigation groups, and a compact top status bar so the first-round operations pages sit inside a more scalable workbench layout.

This is a second-round frontend redesign task. It should not rework the business content of `JobsPage`, `JobTable`, or `TranslationQaQueuePage` beyond layout integration that is strictly required by the new shell.

## What I Already Know

* The first round redesigned the high-frequency operations surfaces:
  * `frontend/src/pages/JobsPage.vue`
  * `frontend/src/components/JobTable.vue`
  * `frontend/src/pages/TranslationQaQueuePage.vue`
  * shared style tokens in `frontend/src/styles/main.scss`
* The first round is committed in `cd7c77da`.
* Re-run validation on 2026-06-19:
  * `npm run build` passed in `frontend/`.
  * `npm run test:smoke` passed 11/11 after allowing Playwright to launch local Chrome.
* The first-round PRD intentionally left full global sidebar navigation out of scope.
* Current protected shell entry point is `frontend/src/layouts/AppLayout.vue`.
* Existing breadcrumb component is `frontend/src/components/AppBreadcrumb.vue`.
* The app uses permission-filtered navigation through auth store checks and route meta.

## Requirements

### R1. App Shell Scope

Replace the current protected top-navigation shell with a global app shell:

* Left sidebar for brand and primary navigation.
* Top status bar for current page context and global user actions.
* Main content area preserving the first-round dense operations pages.

Do not redesign individual business pages as part of this task.

### R2. Collapsible Sidebar

The sidebar must support two desktop states:

* Expanded: icon + text labels.
* Collapsed: icon-only navigation with tooltips or equivalent accessible labels.

The default desktop state should be expanded.

### R3. Sidebar State Persistence

Persist the desktop collapsed/expanded preference to `localStorage`.

Suggested key:

* `md2word.sidebar.collapsed`

Invalid stored values should fall back to expanded. Mobile drawer state must remain temporary and should not reuse the desktop persisted value.

### R4. Navigation Information Architecture

Group navigation by user workflow rather than raw business domain.

Recommended groups:

* Processing Queue
  * Job workbench
  * Create job
* Quality Governance
  * Translation QA
  * Term proposals
  * Term rules / term sets where available
* Configuration Release
  * Settings
  * Templates
  * Word page styles
  * Translation profiles
* System Operations
  * System status
  * Audit log
  * File retention
  * Ops dashboard where permitted

The implementation should continue to honor existing permissions and must not expose unauthorized links.

### R5. Group Disclosure

Use expandable navigation groups with common entries visible by default.

High-frequency entries should remain easy to reach:

* Job workbench
* Translation QA
* Settings
* System status

Do not create new group landing pages in this round.

### R6. Active Route Mapping

Add a lightweight route ownership mapping for sidebar and topbar display.

It should support:

* Parent group active state.
* Current route item active state.
* Detail route ownership, such as `/jobs/:id` mapping back to Job workbench.
* Topbar current module label.
* Simplified breadcrumb display.

Avoid a full route meta rewrite unless implementation proves it is clearly simpler and lower-risk.

### R7. Top Status Bar

Move page context and global actions into the topbar.

Topbar should include:

* Current module/page context.
* Breadcrumb or simplified breadcrumb.
* Theme toggle.
* User display name.
* User role when available.
* Logout action.
* Optional environment/status slot if existing data is available without new APIs.

The topbar must not duplicate brand identity that already appears in the sidebar.

### R8. Breadcrumb Placement

Merge `AppBreadcrumb` into the topbar or adapt it so breadcrumb information lives in the topbar area.

Avoid a separate breadcrumb row that creates three stacked levels: topbar, breadcrumb, page header.

### R9. Brand Area

Sidebar brand behavior:

* Expanded desktop: brand icon + `md2word` + workbench label.
* Collapsed desktop: centered brand icon only.
* Mobile drawer: full brand display.

The current header brand block should be removed from the topbar.

### R10. Mobile Navigation

Use a hamburger button in the topbar to open a drawer-style sidebar on mobile.

Mobile drawer rules:

* Show full group labels and item text.
* Do not depend on the desktop collapsed state.
* Close after navigation where appropriate.
* Avoid horizontal-scrolling top navigation.

### R11. Visual Tone

Use a lightly branded sidebar:

* Low-saturation indigo/slate background.
* Clear borders and active states.
* Small active accents using indigo/emerald.
* No large gradients, glassmorphism, or decorative background effects.

The design must preserve the first-round operations-workbench density and not reintroduce oversized navigation chrome.

### R12. Badge Schema Only

The sidebar component may support optional `badge` and `tone` fields, but this round must not connect real global exception counts or add new aggregate APIs.

## Acceptance Criteria

* [ ] Protected app shell uses a left sidebar and top status bar on desktop.
* [ ] Sidebar can expand/collapse on desktop.
* [ ] Sidebar collapsed state persists across refreshes through `localStorage`.
* [ ] Mobile uses a hamburger-triggered navigation drawer.
* [ ] Navigation groups follow the workflow-based information architecture.
* [ ] Existing permission checks still hide unauthorized links.
* [ ] Current route and parent group are highlighted correctly for list and detail routes.
* [ ] Breadcrumb/page context appears in the topbar, not as a separate extra row.
* [ ] First-round Jobs and QA pages remain dense and usable inside the new shell.
* [ ] No real global badge API or fake count is introduced.
* [ ] `npm run build` passes in `frontend/`.
* [ ] Playwright/browser screenshots cover expanded sidebar, collapsed sidebar, and mobile drawer at representative widths.

## Definition Of Done

* Implementation keeps scope to the global app shell, sidebar, topbar, route ownership mapping, and required shared styles.
* No business-page content redesign is included unless required to prevent layout breakage.
* Existing smoke tests are updated or extended for the new shell behavior.
* Frontend build passes.
* Browser verification checks desktop expanded, desktop collapsed, and mobile drawer states.
* Any new layout convention that future tasks need is recorded in `.trellis/spec/frontend/`.

## Out Of Scope

* Reworking the first-round Jobs, JobTable, or Translation QA business content.
* Adding global exception count APIs or polling.
* Full route meta redesign across every route.
* Creating group landing pages.
* Replacing Element Plus navigation components globally.
* Full mobile card-list redesign for business tables.

## Technical Notes

Likely files:

* `frontend/src/layouts/AppLayout.vue`
* `frontend/src/components/AppBreadcrumb.vue`
* new `frontend/src/components/AppSidebar.vue`
* optional small helper for route ownership/navigation config
* `frontend/src/styles/main.scss`
* `frontend/tests/smoke/core-flow.spec.ts`
* `.trellis/spec/frontend/layout-guidelines.md` if new app shell rules should be preserved

Implementation should start only after the first-round task is cleanly committed and the user approves this second-round scope.
