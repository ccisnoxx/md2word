# Frontend SaaS UI Fourth Round Config And Terminology Deep Pages

## Third Round Acceptance And Residual Issues

Acceptance conclusion: the third frontend productization round is complete enough to serve as the fourth-round baseline.

Evidence:

- Third-round task `.trellis/tasks/archive/2026-06/06-18-frontend-saas-ops-ui/` is archived with `status=completed`.
- Implementation commit `06d5b541 feat: polish ops admin UI` changed the intended operations pages and shared UI system files:
  - `SystemStatusPage`
  - `OpsDashboardPage`
  - `AuditLogPage`
  - `FileRetentionPage`
  - `frontend/src/styles/main.scss`
  - `.trellis/spec/frontend/ui-system-guidelines.md`
- Current HEAD passes `cd frontend && npm run build`; observed warnings are the existing third-party PURE annotation warnings and Vite's large chunk warning.
- The third round intentionally did not redesign configuration and terminology deep pages.

Residual issues carried into the fourth round:

- Browser/manual smoke was not rerun during this planning pass; build/type evidence is current, but rendered visual evidence for third-round pages remains weaker than browser smoke.
- Configuration and terminology deep pages still use older local shells, cards, tables, forms, status areas, and hardcoded colors instead of the shared `app-*` visual layer.
- Complex governance pages do not yet share one clear information hierarchy for version selection, draft state, preflight/diff evidence, previews, review actions, empty/loading/error states, and destructive or publishing actions.

Full current-state evidence is in `research/current-state.md`.

## Goal

Complete the fourth frontend productization round by bringing configuration center deep pages and terminology governance pages into the same Stripe / Linear-style internal SaaS visual layer established in the first three rounds, while preserving all existing business behavior.

## Scope

Target pages:

- `TemplateListPage`
- `TemplateDetailPage`
- `WordPageStyleListPage`
- `WordPageStyleDetailPage`
- `TermRuleSetPage`
- `TermRuleWorkbenchPage`
- `TranslationProfilesPage`
- `TranslationTermSetPage`
- `TermProposalsPage`

Related components:

- `TerminologyWorkbenchNav`
- `TermPreview`
- `TermSegmentEditor`
- `TermProposalTable`
- `TranslationTermProposalTable`
- Necessary shared SCSS helpers in `frontend/src/styles/main.scss`
- Optional frontend UI guideline update if new shared helpers become part of the local UI system

## What I Already Know

- The project uses Vue 3, Element Plus, Vue Router, Pinia, and SCSS.
- Existing shared visual tokens and helpers live in `frontend/src/styles/main.scss` as `--app-*` values and `app-*` classes.
- The fourth-round target files currently total about 7.6k lines and include several large, behavior-sensitive pages.
- The target routes and permissions already exist in `frontend/src/router/index.ts`; this task should not change route definitions, roles, permissions, props, or query semantics.
- `TemplateListPage`, `TemplateDetailPage`, `WordPageStyleListPage`, `WordPageStyleDetailPage`, `TranslationProfilesPage`, and template/style routes are admin-heavy settings surfaces.
- `TermRuleSetPage`, `TermRuleWorkbenchPage`, `TranslationTermSetPage`, and `TermProposalsPage` contain governance loops that must preserve draft-only edits, snapshot/preflight evidence, proposal context, and review status gates.
- The user requires first-layer validation to prioritize `cd frontend && npm run build`.
- Do not run `npx playwright install chromium`. Browser smoke should use an existing local Chrome/browser route if available.

## Requirements

### Shared Visual Layer

- Reuse the existing `--app-*` tokens and shared helpers from `frontend/src/styles/main.scss`.
- Migrate page roots and headers to the shared page shell: `app-page`, `app-page-shell`, `app-page-shell--wide` or `--narrow`, `app-page-header`, `page-kicker`, `page-title`, and `page-description`.
- Use shared panel/table/data helpers where appropriate:
  - `app-panel-card`
  - `app-table-card`
  - `app-metric-grid`
  - `app-metric-card`
  - `app-filter-panel`
  - `app-evidence-panel`
  - `app-compact-grid`
  - `app-compact-card`
  - `app-key-value-list`
  - `app-key-value-row`
  - `app-workspace-tab`
- Add only small semantic helpers when repeated patterns across target pages justify them, such as version tables, governance summary strips, preview/diff payload panels, review detail panes, action bars, workbench navigation, or form workbench grids.
- Keep Element Plus as the component library. Do not add a UI library, icon library, chart library, font import, or replacement theme system.
- Reduce page-local hardcoded colors, borders, shadows, and radii; use `var(--app-*)` unless a local state truly needs a distinct semantic helper.

### Configuration Deep Pages

- `TemplateListPage` and `WordPageStyleListPage`:
  - Use the shared page shell and table card style.
  - Keep template/style cross-links, refresh behavior, loading/error states, empty text, default tags, and route targets unchanged.

- `TemplateDetailPage`:
  - Unify template summary, responsibility boundary, upload draft card, version table, verification evidence, row actions, and dialogs.
  - Preserve `templatesApi` calls, template download, draft upload, validation job creation, publish, set-default, disable, RoleGate behavior, confirmation dialogs, and validation/upload file constraints.
  - Keep template document and page style responsibilities visually distinct without changing their lifecycle.

- `WordPageStyleDetailPage`:
  - Unify the top action area, template switcher, status metrics, config metadata, category rail, group tabs, field groups, dirty summary, validation errors, and empty/loading/error states.
  - Preserve template switching, reload confirmation, unsaved-change route guard, dirty field calculation, field validation, reset, save-as-draft-version, and `layoutConfig` schema-driven control selection.
  - Keep typed controls: switches for booleans, input numbers for numeric fields, segmented controls for alignment/status-like fields, color picker plus text input for colors, and text inputs for strings.

### Term Rule Governance

- `TerminologyWorkbenchNav`:
  - Use shared workbench/tab helper styling.
  - Preserve query context forwarding for proposal governance fields.

- `TermRuleSetPage`:
  - Unify rule set selection, draft summary, preflight summary, draft rule filters, rule table, diff summary/table, preflight finding table, versions table, YAML fallback, rule dialog, and publish dialog.
  - Preserve all draft-only behavior: create/update/toggle/delete draft rule, save YAML draft, refresh after draft mutation, preflight blocker handling, publish, set-default, rollback, approved unpublished proposal loading, and proposal-context return links.
  - Proposal context may position/filter the page, but must not mutate draft implicitly.

- `TermRuleWorkbenchPage`:
  - Unify readonly live-store summary, category table, rule filters/table, simulation panel, simulation result preview, and detail drawer.
  - Preserve `termRulesApi.listCategories`, `listRules`, `getRule`, and `simulate` behavior.
  - Keep HTML preview shown as escaped text, not rendered HTML.

### Translation Governance

- `TranslationProfilesPage`:
  - Unify profile list, selected draft form, snapshot/hash display, unavailable state, versions table, and admin actions.
  - Preserve route query `profile_id`, `translationProfilesApi` calls, draft validation rules, save draft, publish-and-default, set-default confirmation, rollback confirmation, admin gating, and 503 unavailable handling.

- `TranslationTermSetPage`:
  - Unify set list, draft summary, CSV import report, validation findings, diff/preflight, proposal compatibility, published versions, draft entries, import/edit/publish/export dialogs, and error-action hints.
  - Preserve route query proposal context, `translationTermSetsApi` calls, dedupe options and hints, CSV import/export/copy/download semantics, draft entry add/edit/disable/delete, snapshot conflict guidance, preflight blockers, publish, set-default, rollback, and admin gating.

- `TermProposalsPage`:
  - Unify tab layout, proposal forms, context summaries, mine/all/review queues, selected-row tables, bulk review panels, conflict alerts, review detail panes, snapshot/current rule comparison, translation proposal review detail, and governance deep links.
  - Preserve active tab/query/focus behavior, operator proposal submission, translation proposal submission, admin-only tabs, bulk approve/reject, approve, approve-and-publish, reject, selected proposal state, status-based disabled rules, pending-only bulk selection, and post-action reload behavior.

- Proposal table/editor components:
  - Align selected-row highlighting, job links, proposal table wrappers, segment editor controls, and preview boxes with shared tokens.
  - Preserve component contracts, emitted events, `defineExpose({ clearSelection })`, pending-only selection rules, and segment ordering/add/remove/update semantics.

### State Surfaces

- Loading states, empty states, API errors, readonly/unavailable notices, conflict warnings, draft/preflight blockers, dirty-change markers, and bulk result messages must be visually consistent across the target pages.
- Dense tables may use controlled horizontal scrolling on small screens, but text must not overlap, fixed action columns must remain usable, and form buttons must not crush into unreadable controls.
- Target responsive checkpoints: approximately 375px, 768px, 1024px, and 1440px.

### Behavior Preservation

- Do not modify API clients, API payloads, router definitions, route names, route permissions, auth guards, Pinia stores, RoleGate semantics, backend action availability, upload/validation contracts, dirty-change guards, confirmation messages, preflight blockers, snapshot hashes, CSV export/import semantics, proposal status gates, or error normalization.
- Do not add silent fallbacks, hide backend errors, suppress safety evidence, or replace backend-provided availability with frontend guesses.
- If tests need updates because visible structure changes, keep business assertions at least as strong.

## Acceptance Criteria

- [ ] All target pages use the shared page shell and `--app-*` visual tokens rather than page-local shells as the dominant visual layer.
- [ ] Template list/detail pages visually align table, metadata, upload, version, validation, publish, default, disable, loading, empty, and error states while preserving all existing template lifecycle behavior.
- [ ] Word page style list/detail pages visually align template switching, status metrics, schema-driven form controls, dirty summaries, validation errors, change guards, save/reset/reload actions, and metadata surfaces while preserving all existing layout config behavior.
- [ ] Term rule set/workbench pages visually align workbench nav, live/draft summaries, filters, tables, preflight, diff, simulation, detail drawer, YAML fallback, dialogs, and governance context while preserving all term rule API calls and draft-only semantics.
- [ ] Translation profiles page visually aligns list/detail/draft/version/admin-action surfaces while preserving route query selection, validation, unavailable state, publish/default/rollback behavior, and admin gating.
- [ ] Translation term set page visually aligns CSV import/export, draft summary, validation, diff/preflight, proposal compatibility, version tables, draft entry editor, dialogs, and error hints while preserving dedupe, snapshot, publish/default/rollback, route context, and CSV behavior.
- [ ] Term proposals page visually aligns proposal forms, tabbed queues, bulk review, review details, conflict/snapshot evidence, selected-row state, and governance links while preserving operator/admin behavior and proposal status gates.
- [ ] Related proposal/terminology components use shared tokens and remain contract-compatible with their parent pages.
- [ ] No new UI library, icon library, chart library, font import, Element Plus replacement, backend change, API contract change, router/permission change, or data model change is introduced.
- [ ] Target pages remain readable at approximately 375px, 768px, 1024px, and 1440px with no obvious text overlap or crushed actions; controlled table scrolling is acceptable.
- [ ] `cd frontend && npm run build` passes after implementation.
- [ ] Browser smoke uses `npm run dev:smoke` plus an existing local Chrome/browser path if available. If browser tooling is unavailable, the result records the skipped coverage and build/source-inspection fallback.

## Definition Of Done

- User confirms this PRD before implementation begins.
- Task remains in Trellis planning until confirmation.
- Before `task.py start`, Phase 1.3 context is curated in `implement.jsonl` and `check.jsonl` with frontend specs and this research artifact.
- Implementation reads this PRD, `research/current-state.md`, `.trellis/spec/frontend/index.md`, and `.trellis/spec/frontend/ui-system-guidelines.md`.
- Code changes stay scoped to target pages/components, necessary shared SCSS helpers, and optional UI guideline updates.
- First validation gate is `cd frontend && npm run build`.
- Do not run `npx playwright install chromium`.
- If an existing local browser is available, start `cd frontend && npm run dev:smoke` and smoke representative pages/interactions through Chrome/devtools/browser tooling.
- Final implementation report states validation run, browser smoke coverage or blocker, residual risk, and whether docs/comments/specs were updated.

## Technical Approach

Recommended direction: continue the first three rounds' lightweight shared CSS/helper migration. Do not introduce a new Vue layout abstraction or component library first.

Implementation order:

1. Shared helper pass:
   - Inventory repeated local patterns across target pages.
   - Add only reusable helper classes to `main.scss` where at least two target areas benefit.
   - Update frontend UI guidelines if a helper becomes part of the project UI vocabulary.
2. Template and Word page style pages:
   - Migrate list pages first as low-risk table-shell baselines.
   - Migrate `TemplateDetailPage` version/action/dialog surfaces.
   - Migrate `WordPageStyleDetailPage` workbench layout, form groups, dirty summary, and validation surfaces.
3. Term rule governance:
   - Migrate `TerminologyWorkbenchNav`.
   - Migrate `TermRuleWorkbenchPage` readonly surfaces.
   - Migrate `TermRuleSetPage` draft/diff/preflight/dialog surfaces with careful review of any script changes.
4. Translation governance:
   - Migrate `TranslationProfilesPage`.
   - Migrate `TranslationTermSetPage`.
   - Migrate `TermProposalsPage` and proposal table/editor components.
5. Verification:
   - Run `cd frontend && npm run build`.
   - Inspect the diff for accidental API/router/permission/payload/guard changes.
   - Start `npm run dev:smoke` and smoke representative pages with an existing local browser if available.

## Decision (ADR-lite)

**Context**: The first three frontend rounds established a light internal SaaS visual system for the main job flow, Translation QA/settings entry, and operations pages. The remaining configuration and terminology deep pages are feature-rich but still visually fragmented.

**Decision**: The fourth round will reuse the existing `--app-*` token system and shared `app-*` helpers, adding only small semantic helpers for repeated deep-page governance patterns. The work is presentation and information hierarchy only.

**Consequences**: This keeps the implementation compatible with Element Plus and reduces behavior regression risk. The tradeoff is that very large pages may still retain page-local structure after migration, but their visible hierarchy, status language, action bars, version tables, previews, and state surfaces should align with the rest of the product.

## Research References

- `research/current-state.md` - third-round acceptance evidence, current fourth-round page findings, route/permission inventory, shared helper inventory, and implementation risks.

## Out Of Scope

- No new UI library, icon library, chart library, font import, or Element Plus replacement.
- No backend, API client, router, permission, auth, Pinia, or data model changes.
- No changes to publish/default/rollback semantics, preflight blockers, confirmation messages, snapshot hashes, dirty-change guards, CSV import/export semantics, proposal review status gates, or RoleGate behavior.
- No prompt editor, full translation platform redesign, online Word editing, template DOCX content editor, or segment-level human translation writeback beyond existing forms.
- No redesign of main job flow, Translation QA pages, operations pages, login page, or backend runbooks except passive global style effects.
- No dark-mode project, theme switcher, animation system, marketing/landing treatment, white-label system, or charting system.

## Open Questions

- 请确认本 PRD 是否可以作为第四轮实现依据。推荐确认当前范围：一次覆盖上述配置与术语治理深层页及相关组件；若你希望降低单轮风险，可以把第四轮拆成 4A（Template/Word Page Style）和 4B（Term/Translation Governance）。
