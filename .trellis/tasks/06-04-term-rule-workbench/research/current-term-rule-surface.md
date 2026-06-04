# Current term rule surface research

## Inputs Read

- `.trellis/tasks/06-03-product-roadmap/prd.md`
- `.trellis/tasks/06-03-product-roadmap/design.md`
- `.trellis/tasks/06-03-product-roadmap/implement.md`
- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/directory-structure.md`
- `.trellis/spec/backend/quality-guidelines.md`
- `docs/api/term-rules.md`
- `docs/api/term-rule-sets.md`
- `docs/api/term-rule-categories.md`
- `frontend/src/pages/TermRuleSetPage.vue`
- `frontend/src/pages/SettingsHomePage.vue`
- `frontend/src/router/index.ts`
- `frontend/src/api/termRules.ts`
- `frontend/src/api/termRuleSets.ts`
- `frontend/src/api/types.ts`
- `frontend/src/components/TermPreview.vue`
- `app/domains/term_rules/router.py`
- `app/domains/term_rules/sets_router.py`
- `app/domains/term_rules/categories_router.py`

## Findings

- Roadmap Phase 2 describes a full `term-rule-workbench`: CRUD, categories, enable/disable, import/export, simulation, version diff.
- Current turn constraints explicitly exclude a complete CRUD workbench, so the implementable slice should be read-only inspection plus simulation.
- Backend already exposes all needed read/simulate APIs for this slice.
- Frontend already has category/rule list/detail wrappers but lacks a `simulate` wrapper and TypeScript simulation response types.
- Existing `TermRuleSetPage.vue` is a governance page for draft summary, published versions, default switching, rollback, approved proposals, and YAML fallback. A separate `/settings/term-rules` page keeps browse/simulate workbench concerns separate.
- Existing `router/index.ts` supports Admin-only route metadata and can protect the new page the same way as other settings pages.
- Existing `TermPreview.vue` can render rule segments safely without raw HTML.

## Decision

Plan a frontend-only Admin page named `TermRuleWorkbenchPage.vue` at `/settings/term-rules`, with no backend changes and no mutating rule controls.
