# Term rule workbench design

## Current State

The roadmap currently marks `term-rule-workbench` as a later Phase 2 task covering full CRUD, categories, enable/disable, import/export, simulation, and version diff. This turn intentionally implements only a small, non-CRUD slice because the active constraints exclude a complete workbench.

Backend capabilities already exist:

- `GET /api/v1/term-rule-categories` lists categories and rule counts.
- `GET /api/v1/term-rules` lists rules with `category_id`, `enabled`, and `q` filters.
- `GET /api/v1/term-rules/{rule_id}` returns a single rule.
- `POST /api/v1/term-rules/simulate` returns `original`, `markdown_preview`, and `html_preview`.

Frontend state:

- `TermRuleSetPage.vue` manages rule-set draft summary, published versions, default switching, rollback, approved proposals, and a YAML fallback.
- `SettingsHomePage.vue` links to templates, term rule sets, and translation profiles.
- `router/index.ts` already protects settings pages with `meta.roles = ["admin"]`.
- `termRulesApi` already wraps category and rule list/detail reads, but not simulation.
- `types.ts` already has term rule/category/list contracts, but not simulation request/response contracts.
- `TermPreview.vue` can render term segments without using raw HTML.

## Scope

Implement a frontend-only Admin page:

- New route: `/settings/term-rules`
- New page: `frontend/src/pages/TermRuleWorkbenchPage.vue`
- Config center entry: add a fourth card in `SettingsHomePage.vue`
- API wrapper: add `termRulesApi.simulate`
- Types: add `RuleSimulationRequest` and `RuleSimulationResponse`

No backend endpoint, schema, persistence, worker, job, or document generation code should change.

## Page Changes

### Settings Home

Add an Admin-only config card:

- Title: `术语规则检查`
- Description: browse rules, inspect rendered segments, run a simulation.
- Route: `/settings/term-rules`

The existing `术语规则集` card remains focused on draft/publish/default/rollback governance.

### Term Rule Workbench

Layout:

- Header with title and refresh action.
- Top summary area:
  - category count
  - total rule count
  - enabled rule count
- Filter toolbar:
  - category select
  - enabled select: all / enabled / disabled
  - keyword input
  - search and reset buttons
- Rule table:
  - source term
  - preview via `TermPreview`
  - category
  - apply scope
  - priority
  - enabled status
  - detail action
- Detail drawer:
  - ID
  - category
  - source term
  - scope / case sensitivity / priority / enabled
  - segments
  - custom markdown/html shown as text
  - notes
- Simulation panel:
  - textarea input
  - simulate button
  - result panes for `original`, `markdown_preview`, `html_preview`

Do not render `html_preview` through `v-html`; display it as text to avoid turning the workbench into an unsafe HTML preview surface.

## API Changes

No backend API changes.

Frontend API additions only:

- `frontend/src/api/types.ts`
  - `RuleSimulationRequest`
  - `RuleSimulationResponse`
- `frontend/src/api/termRules.ts`
  - `simulate(payload: RuleSimulationRequest): Promise<RuleSimulationResponse>`

## Involved Files

- `frontend/src/router/index.ts`
  - Import and register `TermRuleWorkbenchPage`.
  - Add admin route `/settings/term-rules`.
- `frontend/src/pages/SettingsHomePage.vue`
  - Add config card entry and icon.
- `frontend/src/pages/TermRuleWorkbenchPage.vue`
  - New focused page.
- `frontend/src/api/termRules.ts`
  - Add simulation wrapper.
- `frontend/src/api/types.ts`
  - Add simulation types.

Expected untouched areas:

- `app/**`
- `tests/test_fastapi_jobs_backend.py`
- `docs/api/openapi.json`
- pdf-mineru / conversion / worker code

## Compatibility

Existing routes and pages remain stable. The new route is Admin-only and uses the same router role guard as other settings pages. The implementation reuses existing backend APIs and does not alter proposal, term-rule-set, or job processing semantics.

## Risks

- In deployments where term-rule APIs are unavailable or return `503`, the page must show an existing `ApiErrorAlert` state instead of masking the error.
- The current backend simulation returns an HTML string; rendering it as raw HTML would create an avoidable frontend safety risk, so this slice intentionally shows it as text.
- This page is not the full Phase 2 workbench. Users may expect editing; acceptance requires no edit/delete/import/export controls in this slice.

## Rollback

Rollback is limited to removing the new route/page/card and the frontend simulation wrapper/types. No persisted data or backend contract is affected.
