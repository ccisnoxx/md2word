# Frontend Workbench Table Preferences

## Goal

Add local table preferences for the high-frequency operations workbenches so Chinese-speaking operators can tune table density, visible columns, and page size without changing shared URLs or saved views.

This is the eighth frontend operations round after:

- dense Jobs workbench
- Translation QA queue and review drawer
- app shell/sidebar
- Incident triage workbench
- saved views
- personal operations cockpit
- command palette, shortcut hints, and batch-result feedback

The goal is to make the tables operators stare at all day faster to scan and less noisy, while preserving the existing workflow semantics.

## Product Positioning

This task improves repeated operational use, not one-time onboarding.

Design priorities:

- dense but readable tables
- Chinese visible copy
- low visual interruption
- stable layout
- local personal preference only
- no new backend dependency

The implementation should feel like a quiet table toolbar, not a new settings product.

## Current Context

- `JobTable.vue` owns the Jobs table layout with fixed columns:
  - selection
  - `任务 / 异常`
  - `状态`
  - `QA`
  - `进度`
  - `更新`
  - `操作`
- `JobsPage.vue` currently uses `const pageSize = 20` and passes it into `JobTable`.
- `TranslationQaQueuePage.vue` has an inline table with columns:
  - `任务`
  - `任务状态`
  - `QA 状态`
  - `问题归因`
  - `证据`
  - `复核人`
  - `更新`
  - `操作`
- `TranslationQaQueuePage.vue` currently uses `const pageSize = 20`.
- `IncidentTriagePage.vue` has an inline incident table with columns:
  - selection
  - `任务 / 证据`
  - `状态`
  - `重试`
  - `更新`
  - `操作`
- `IncidentTriagePage.vue` currently uses `const pageSize = 20`.
- Existing local preference examples:
  - `frontend/src/utils/sidebarState.ts`
  - `frontend/src/utils/theme.ts`
- Saved views intentionally store filters and sort, not page number, selected rows, drawer ids, or table UI preferences.
- Frontend layout guidelines require horizontally scrollable tables on mobile instead of forced card rewrites unless the task explicitly asks otherwise.

## Problems And Recommended Choices

| Problem | Options | Recommended Choice |
|---|---|---|
| Eighth-round direction | 1. More copy cleanup; 2. Table preferences; 3. Detail-page diagnostics | Choose 2 |
| Covered pages | 1. Jobs only; 2. Jobs + Translation QA + Incidents; 3. All app tables | Choose 2 |
| Preference storage | 1. `localStorage`; 2. backend user preferences; 3. saved views | Choose 1 |
| Preference scope | 1. density only; 2. column visibility + density + page size; 3. add drag ordering | Choose 2 |
| URL behavior | 1. write page size to URL; 2. keep page size local only; 3. store in saved views | Choose 2 |
| Column order | 1. fixed order; 2. drag reorder; 3. per-page custom layouts | Choose 1 |
| Column width | 1. fixed existing widths; 2. resizable widths; 3. auto-fit algorithm | Choose 1 |
| Chinese copy | 1. new controls only; 2. all preference UI and affected labels Chinese-first | Choose 2 |

## Requirements

### R1. Workbench Table Preference Model

Add a frontend-only preference model for high-frequency workbench tables.

Target pages:

- Jobs workbench
- Translation QA queue
- Incident triage

Required preference fields:

- `density`: `standard` or `compact`
- `visibleColumns`: page-specific list or map of optional column ids
- `pageSize`: one of `20`, `50`, `100`

Preference keys should be page-scoped and stable.

Recommended storage keys:

- `md2word.workbench.jobs.table`
- `md2word.workbench.translation_qa.table`
- `md2word.workbench.incidents.table`

Rules:

- Use `localStorage`.
- Invalid or missing stored values fall back to safe defaults.
- Do not throw runtime errors because of malformed local storage.
- Provide a reset action that restores defaults for the current page.
- Do not persist selected rows, drawer ids, current page number, filters, sort, or search keyword in this model.

### R2. Shared Table Preference Controls

Add a reusable control surface where it removes duplication.

Expected UI:

- compact toolbar entry, recommended label: `表格设置`
- density segmented control or radio group:
  - `标准`
  - `紧凑`
- column visibility checklist
- page size selector:
  - `20 条/页`
  - `50 条/页`
  - `100 条/页`
- reset action:
  - `恢复默认`

Placement:

- In each target workbench near the table header or table command area.
- Do not add a separate full settings page.
- Do not place cards inside cards.

All visible copy must be Chinese.

### R3. Column Visibility

Each target table must define a page-specific column registry.

Column definitions should include:

- stable column id
- Chinese label
- whether the column is required
- default visible state

Required columns cannot be hidden.

Recommended required columns:

- Jobs:
  - selection column when batch selection is available
  - `任务 / 异常`
  - `状态`
  - `操作`
- Translation QA:
  - `任务`
  - `QA 状态`
  - `操作`
- Incidents:
  - selection column
  - `任务 / 证据`
  - `状态`
  - `操作`

Recommended optional columns:

- Jobs:
  - `QA`
  - `进度`
  - `更新`
- Translation QA:
  - `任务状态`
  - `问题归因`
  - `证据`
  - `复核人`
  - `更新`
- Incidents:
  - `重试`
  - `更新`

Rules:

- Hidden columns must not leave empty table gaps.
- Column order remains fixed in this round.
- Fixed action-column behavior should remain stable on desktop and mobile.
- If all optional columns are hidden, the table must still remain usable.

### R4. Density Modes

Add two density modes.

`standard`:

- preserves current table spacing as closely as practical
- should be the default for existing users

`compact`:

- reduces row padding and secondary text spacing
- keeps text readable
- does not truncate the main identity column into unusable output
- does not break row actions or batch selection

Rules:

- Density should be applied through page/table classes or a shared helper pattern.
- Do not use viewport-width font scaling.
- Respect existing `--app-*` spacing, radius, border, and color tokens.
- Avoid layout shift on hover.

### R5. Page Size Preference

Add page-size selection for each target workbench.

Behavior:

- Supported sizes: `20`, `50`, `100`.
- Default remains `20`.
- Preference is local per page.
- Changing page size resets the current page to `1`.
- List API calls use the selected `pageSize`.
- Existing filter/sort query behavior remains unchanged.
- Page size is not written into saved views.
- Page size is not required in the route query.

If implementation discovers the existing route sync strongly assumes a constant page size, prefer the smallest local adjustment that keeps current URL semantics stable.

### R6. Saved Views Boundary

Do not expand saved views in this round.

Saved views remain responsible for:

- filters
- sort
- page-specific durable query state already supported by saved views

Table preferences remain responsible for:

- density
- visible columns
- page size

Rules:

- Applying a saved view must not overwrite table preferences.
- Resetting table preferences must not clear filters or saved views.
- Saving or updating a saved view must not capture table preferences.

### R7. Accessibility And Keyboard Behavior

Preference controls must be keyboard accessible.

Requirements:

- `表格设置` trigger is reachable by keyboard.
- Density and page-size controls have visible labels.
- Column checkboxes have Chinese accessible names.
- Required columns communicate why they cannot be hidden.
- Reset action is discoverable and keyboard reachable.
- Popover/dialog close behavior is predictable.
- Error or fallback states are not visual-only.

### R8. Responsive And Layout Constraints

Tables should continue to behave as data tables on mobile.

Requirements:

- Keep horizontal table scrolling where needed.
- Do not force a card-list rewrite in this round.
- No uncontrolled document/body horizontal overflow.
- Preference controls must fit at `375px`.
- Fixed/sticky or bottom bulk-action bars must still fit after density/column changes.
- Page root grid rows must remain compact per layout guidelines.

## Acceptance Criteria

- Jobs workbench has a Chinese `表格设置` control.
- Translation QA queue has a Chinese `表格设置` control.
- Incident triage has a Chinese `表格设置` control.
- Each target page supports `标准` and `紧凑` density.
- Each target page supports page size `20`, `50`, and `100`.
- Each target page persists table preferences in local storage under a page-specific key.
- Each target page falls back to defaults when local storage is empty or malformed.
- Each target page provides `恢复默认`.
- Required columns cannot be hidden.
- Optional columns can be hidden and shown again without page reload.
- Applying saved views does not alter table preferences.
- Changing table preferences does not alter saved views, filters, sort, or drawer query state.
- Changing page size reloads the list with the selected size and resets current page to `1`.
- Existing batch selection, row actions, QA drawer, incident diagnostics drawer, command palette, and saved-view behavior remain functional.
- Preference controls and resulting tables are usable at desktop width around `1440px`.
- Preference controls and resulting tables are usable at mobile width around `375px`.
- No uncontrolled document/body horizontal overflow is introduced.

## Definition Of Done

- Trellis frontend specs are read before implementation.
- Existing table and local-storage patterns are reused where practical.
- New table preference helper/composable has focused tests.
- Column registry/default/fallback behavior has focused tests.
- Page-size behavior has focused tests where practical.
- `npm run build` passes in `frontend/`.
- Browser smoke checks cover Jobs, Translation QA, and Incident table settings on desktop and mobile.
- Verification checks no uncontrolled horizontal overflow.
- No backend migration or API contract change is introduced.

## Technical Approach

Recommended implementation path:

1. Add a small shared table preference utility, for example `frontend/src/utils/tablePreferences.ts`.
2. Define page ids and preference storage keys for Jobs, Translation QA, and Incidents.
3. Add page-specific column registries.
4. Add a reusable table preference control component, for example `WorkbenchTableSettings.vue`.
5. Integrate preference state into `JobsPage.vue` and `JobTable.vue`.
6. Integrate preference state into `TranslationQaQueuePage.vue`.
7. Integrate preference state into `IncidentTriagePage.vue`.
8. Add tests for storage validation, default fallback, column visibility, and page-size selection.
9. Run build and browser smoke checks.

Implementation notes:

- Prefer explicit page column registries over dynamic introspection of `el-table-column`.
- Keep page-specific render logic close to existing table components/pages.
- Add shared abstractions only for preference storage, validation, and common controls.
- Do not introduce a global table framework.
- Do not introduce a full i18n layer.

## Out Of Scope

- Backend user-preference API.
- Team-shared table layouts.
- Saved-view integration for table preferences.
- Column drag-and-drop ordering.
- Column width resizing.
- Persisting current page number.
- Persisting selected rows.
- Persisting drawer state.
- Full app-wide table preference rollout.
- Rewriting mobile tables into cards.
- New bulk actions.
- Full multilingual i18n framework.

## Technical Notes

- Frontend layout spec: `.trellis/spec/frontend/layout-guidelines.md`.
- Existing local preference examples:
  - `frontend/src/utils/sidebarState.ts`
  - `frontend/src/utils/theme.ts`
- Target table files:
  - `frontend/src/components/JobTable.vue`
  - `frontend/src/pages/JobsPage.vue`
  - `frontend/src/pages/TranslationQaQueuePage.vue`
  - `frontend/src/pages/IncidentTriagePage.vue`
- Related features that must remain stable:
  - saved views
  - command palette
  - batch result strips
  - QA review drawer
  - Incident diagnostics drawer

## ADR-lite

**Context**: Operators now have fast entry points, saved views, and command navigation, but the high-frequency tables still use fixed columns and fixed page size. Different operators need different information density.

**Decision**: Add frontend-only, page-scoped table preferences for Jobs, Translation QA, and Incident workbenches. Preferences include density, optional column visibility, and page size, stored in `localStorage`.

**Consequences**: This improves daily scan efficiency without changing backend contracts, saved-view semantics, or shared URLs. The trade-off is that preferences are local to the browser for this round; cross-device preferences can be revisited later if operators ask for it.
