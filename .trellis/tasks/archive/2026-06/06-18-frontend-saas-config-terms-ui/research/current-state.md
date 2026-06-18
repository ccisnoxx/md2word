# Current State And Fourth Round Context

## Sources Inspected

- Trellis workflow and context:
  - `python3 ./.trellis/scripts/get_context.py`
  - `python3 ./.trellis/scripts/get_context.py --mode phase`
  - `python3 ./.trellis/scripts/get_context.py --mode packages`
- Frontend guidelines:
  - `.trellis/spec/frontend/index.md`
  - `.trellis/spec/frontend/ui-system-guidelines.md`
- Previous frontend productization tasks:
  - `.trellis/tasks/archive/2026-06/06-18-frontend-saas-main-flow-ui/prd.md`
  - `.trellis/tasks/archive/2026-06/06-18-frontend-saas-qa-settings-ui/prd.md`
  - `.trellis/tasks/archive/2026-06/06-18-frontend-saas-ops-ui/prd.md`
  - `.trellis/tasks/archive/2026-06/06-18-frontend-saas-ops-ui/research/current-state.md`
- Current fourth-round target files:
  - `frontend/src/pages/TemplateListPage.vue`
  - `frontend/src/pages/TemplateDetailPage.vue`
  - `frontend/src/pages/WordPageStyleListPage.vue`
  - `frontend/src/pages/WordPageStyleDetailPage.vue`
  - `frontend/src/pages/TermRuleSetPage.vue`
  - `frontend/src/pages/TermRuleWorkbenchPage.vue`
  - `frontend/src/pages/TranslationProfilesPage.vue`
  - `frontend/src/pages/TranslationTermSetPage.vue`
  - `frontend/src/pages/TermProposalsPage.vue`
  - `frontend/src/components/TermPreview.vue`
  - `frontend/src/components/TermProposalTable.vue`
  - `frontend/src/components/TermSegmentEditor.vue`
  - `frontend/src/components/TerminologyWorkbenchNav.vue`
  - `frontend/src/components/TranslationTermProposalTable.vue`
  - `frontend/src/router/index.ts`
  - `frontend/src/styles/main.scss`
  - `frontend/package.json`

## Third Round Acceptance Evidence

Acceptance conclusion: the third round is complete enough to serve as the baseline for the fourth round.

Evidence:

- Archived task `.trellis/tasks/archive/2026-06/06-18-frontend-saas-ops-ui/` is marked `completed` in `task.json`.
- Implementation commit `06d5b541 feat: polish ops admin UI` changed the intended operations pages and shared UI system files:
  - `frontend/src/pages/SystemStatusPage.vue`
  - `frontend/src/pages/OpsDashboardPage.vue`
  - `frontend/src/pages/AuditLogPage.vue`
  - `frontend/src/pages/FileRetentionPage.vue`
  - `frontend/src/styles/main.scss`
  - `.trellis/spec/frontend/ui-system-guidelines.md`
- Archive commit `973290e5 chore(task): archive 06-18-frontend-saas-ops-ui` persisted the third-round PRD and research artifacts.
- The third-round PRD required preserving operations behavior and safety gates while migrating the four operations pages to the shared SaaS visual layer.
- Current HEAD passes the frontend build/type gate.

Build command:

```bash
cd frontend && npm run build
```

Observed result:

- `vue-tsc --noEmit` passed.
- `vite build` passed.
- Known warnings remain:
  - two third-party `/* #__PURE__ */` annotation warnings from `@vueuse/core`;
  - one Vite chunk-size warning for the main JS bundle.

## Third Round Residual Issues

- Browser/manual smoke was not rerun during this fourth-round planning pass. Previous frontend productization rounds noted local headless Chrome failures before page assertions, so browser visual coverage is weaker than build/type evidence.
- The third round intentionally excluded configuration and terminology deep pages. Those pages still carry older local visual structures and should be the fourth-round scope.
- The operations helper vocabulary added in round three is available in `frontend/src/styles/main.scss`, but the fourth-round pages have not yet adopted it.

## Fourth Round Current-State Findings

### Shared UI Layer Available

`frontend/src/styles/main.scss` now provides semantic tokens and helpers from the first three rounds, including:

- `--app-*` colors, radius, spacing, shadows, content widths, and font tokens.
- Page and panel helpers: `app-page`, `app-page-shell`, `app-page-shell--wide`, `app-page-shell--narrow`, `app-page-header`, `app-panel`, `app-panel-card`, `app-table-card`.
- Data and operations helpers: `app-metric-grid`, `app-metric-card`, `app-entry-card`, `app-subpanel`, `app-status-card`, `app-alert-stack`, `app-filter-panel`, `app-evidence-panel`, `app-compact-grid`, `app-compact-card`, `app-key-value-list`, `app-key-value-row`, `app-workspace-tab`.
- Shared text and utility helpers: `page-kicker`, `page-title`, `page-description`, `section-title`, `section-subtitle`, `muted`, `mono`, `toolbar`.

### Routes And Permissions

Fourth-round routes are already defined under `AppLayout`:

- `/settings/templates` -> `TemplateListPage`, admin + `settings:read`.
- `/settings/templates/:templateId` -> `TemplateDetailPage`, admin + `settings:read`.
- `/settings/word-page-styles` -> `WordPageStyleListPage`, admin + `settings:read`.
- `/settings/word-page-styles/:templateId` -> `WordPageStyleDetailPage`, admin + `settings:read`.
- `/settings/term-rule-sets` -> `TermRuleSetPage`, `settings:read`.
- `/settings/term-rules` -> `TermRuleWorkbenchPage`, `settings:read`.
- `/settings/translation-profiles` -> `TranslationProfilesPage`, `settings:read`.
- `/settings/translation-term-sets` -> `TranslationTermSetPage`, `settings:read`.
- `/term-proposals` -> `TermProposalsPage`, `term_proposals:read`.

Fourth-round presentation work should not change these routes, roles, permissions, props, or query semantics.

### Target Size And Complexity

Current target files total about 7,594 lines:

- `TemplateListPage.vue`: 96 lines.
- `TemplateDetailPage.vue`: 638 lines.
- `WordPageStyleListPage.vue`: 96 lines.
- `WordPageStyleDetailPage.vue`: 1,016 lines.
- `TermRuleSetPage.vue`: 1,220 lines.
- `TermRuleWorkbenchPage.vue`: 479 lines.
- `TranslationProfilesPage.vue`: 341 lines.
- `TranslationTermSetPage.vue`: 1,287 lines.
- `TermProposalsPage.vue`: 1,882 lines.
- Related terminology components total 539 lines.

`WordPageStyleDetailPage`, `TermRuleSetPage`, `TranslationTermSetPage`, and `TermProposalsPage` are the highest-risk pages because they combine complex forms, version selection, draft/preflight/diff evidence, dialogs, route query context, and admin/operator role boundaries.

### Visual-System Adoption Gap

`rg` found no current adoption of the main shared `app-page`, `app-page-header`, `app-panel`, `app-table-card`, `app-metric-*`, `app-filter-panel`, `app-evidence-panel`, or `app-workspace-tab` helpers in the fourth-round target files.

The same files still heavily use older local conventions such as:

- `page-heading`
- `style-hero`
- `card-flat`
- `section-header`
- `summary-list`
- `summary-metric`
- `toolbar`
- `context-alert`
- `governance-summary-grid`
- `diff-summary`
- local `muted`, `mono`, `row-actions`, `tag-stack`, and related scoped styles.

`rg` also found many page/component-local hardcoded color values and gradients, especially in:

- `WordPageStyleDetailPage.vue`
- `TemplateDetailPage.vue`
- `TranslationTermSetPage.vue`
- `TermRuleWorkbenchPage.vue`
- `TerminologyWorkbenchNav.vue`
- proposal table/editor components.

### Template And Word Style Pages

Observed behavior to preserve:

- `TemplateListPage` and `WordPageStyleListPage` call `templatesApi.list()` and show template/style navigation links.
- `TemplateDetailPage` manages DOCX template metadata, download, draft upload, validation job creation, publish, set-default, disable, and routing to page style config.
- `WordPageStyleDetailPage` manages template switching, current layout config metadata, category rail, group tabs, typed field editors, local validation errors, dirty summaries, unsaved-change navigation guard, reset, reload, and save-as-draft-version behavior.

Current UI gaps:

- List pages use a minimal local `page-heading` + `card-flat` table shell.
- `TemplateDetailPage` has local document grid, summary/boundary/upload cards, version table, dialogs, and evidence snippets.
- `WordPageStyleDetailPage` uses a custom `style-hero`, status grid, meta strip, category rail, group tabs, editor panel, and change panel that do not share the first-to-third-round helper vocabulary.

### Term Rule Pages

Observed behavior to preserve:

- `TermRuleSetPage` loads rule sets, categories, approved unpublished proposals, draft detail, draft rules, default-vs-draft diff, preflight report, published versions, YAML fallback draft, and proposal governance context from route query.
- Rule mutations only affect draft: create/update/toggle/delete draft rule, save YAML draft, publish draft, set default, rollback.
- Preflight blocking state controls publish availability. Proposal context should position/filter the page but never mutate draft implicitly.
- `TermRuleWorkbenchPage` is readonly against the live runtime store: category overview, rule filtering, detail drawer, and simulation via `termRulesApi.simulate`.
- `TerminologyWorkbenchNav` preserves governance query context while switching between draft/publish and live-rules views.

Current UI gaps:

- Term rule pages and nav still use local `page-heading`, `summary-grid`, `content-grid`, `card-flat`, `toolbar filters`, `diff-summary`, and hardcoded colors.
- Draft, diff, preflight, live inspection, simulation, and technical detail sections are visually close but not consistently grouped by shared evidence/status/action helpers.

### Translation Governance Pages

Observed behavior to preserve:

- `TranslationProfilesPage` lists profiles, reads selected profile via query `profile_id`, loads detail/draft in parallel, validates draft fields, saves draft, publishes and sets default, set-defaults published versions, and rollbacks published versions. Admin-only controls are guarded by `RoleGate` and `isAdmin`.
- `TranslationTermSetPage` lists sets, loads selected set/draft/diff/preflight/proposal compatibility, handles CSV import with dedupe, version export/copy/download, publish, set-default, rollback, draft entry add/edit/disable/delete, route query proposal context, error action hints, and snapshot/draft conflict messages.
- `TermProposalsPage` supports operator term rule proposal creation, translation term proposal creation, mine/all/review tabs, tab/query focus behavior, admin bulk review, approve/reject, approve-and-publish, current-vs-snapshot conflict visibility, governance deep links, and selected-row table state.
- `TermProposalTable` and `TranslationTermProposalTable` intentionally keep selection eligibility in the table component while page state owns review behavior.

Current UI gaps:

- Pages use old local shell and many local panels/tables/forms instead of the shared SaaS helper vocabulary.
- Proposal review details, conflict/snapshot evidence, governance links, bulk review results, CSV import/export, and diff payloads need a unified evidence/action/status language.
- Dense tables and long technical text need consistent controlled horizontal overflow and readable mobile stacking.

## Planning Implications

- The fourth round should continue the first three rounds' approach: shared SCSS helpers and markup/class migration, not a new UI library or a Vue component-system rewrite.
- It is reasonable to add a small set of shared helpers to `main.scss` if they are reused across at least two target areas, such as:
  - version table shells;
  - governance summary grids;
  - form workbench grids;
  - preview/diff/evidence panels;
  - review/detail split panes;
  - action bars;
  - local workbench navigation.
- The highest-risk pages should be migrated section by section with extra diff review for script changes. Ideally most changes are template class/style changes.
- Behavior-sensitive code paths to avoid changing include API payload builders, route query parsing, RoleGate/admin checks, confirmation messages, preflight blockers, snapshot hashes, dirty-change guards, dedupe/export semantics, selected-row logic, and proposal review status gating.
- Browser validation remains desirable after implementation. Per user rule, use an existing local browser/dev server path first and do not run `npx playwright install chromium`.
