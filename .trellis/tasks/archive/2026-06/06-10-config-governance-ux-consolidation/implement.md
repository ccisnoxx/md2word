# Configuration Governance UX Consolidation Implementation Plan

This is an implementation plan only. Do not implement until the task is reviewed and started with `python3 ./.trellis/scripts/task.py start 06-10-config-governance-ux-consolidation`.

## Preconditions

- Keep only the current routes; do not add `/settings/terminology`.
- Keep `TermRuleSetPage` / `TermRuleWorkbenchPage` H1s specific and add `术语工作台` through shared tabs/context copy.
- Do not expand Translation Term Set statistics in `/settings` summary in this task.
- Re-check working tree before editing because current repository has unrelated dirty files.

## Step 1 - Terminology Workbench Navigation

- Add a small shared component for terminology navigation, likely under `frontend/src/components/`.
- Use route-based tabs/segmented control:
  - `草稿与发布` -> `settings-term-rule-sets`
  - `当前生效规则` -> `settings-term-rules`
- Preserve Term Rule Set governance query when navigating back to `草稿与发布`.
- Add the component to:
  - `frontend/src/pages/TermRuleSetPage.vue`
  - `frontend/src/pages/TermRuleWorkbenchPage.vue`

Validation:

```bash
cd frontend && npm run build
```

Browser smoke:

- `/settings/term-rule-sets?proposal_id=example&source_term=VIN&target_rule_id=rule_1&return_tab=review` still renders governance context.
- Switching to `当前生效规则` opens live inspection.
- Switching back to `草稿与发布` does not drop required proposal return context if preserved by design.

## Step 2 - Breadcrumb Refinement

- Update `frontend/src/components/AppBreadcrumb.vue` labels:
  - `settings-term-rule-sets`: `配置中心 / 术语工作台 / 草稿与发布`
  - `settings-term-rules`: `配置中心 / 术语工作台 / 当前生效规则`
- Keep `/settings` parent target.
- Keep template, translation profile, translation term set breadcrumbs unchanged unless copy alignment requires small label changes.

Validation:

```bash
cd frontend && npm run build
```

Browser smoke:

- `/settings/term-rule-sets`
- `/settings/term-rules`
- `/settings/templates`
- `/settings/translation-profiles`
- `/settings/translation-term-sets`

## Step 3 - Settings Home Grouping

- Update `frontend/src/pages/SettingsHomePage.vue` from a five-card flat grid into grouped governance sections:
  - `术语工作台`
  - `模板与版式`
  - `翻译治理`
- Keep direct links to all existing pages.
- Keep `ConfigTodoSummary` but align labels/helper text with the new grouping.
- Do not hide links based on transient summary fetch failures.

Validation:

```bash
cd frontend && npm run build
```

Browser smoke:

- Admin sees grouped settings landing.
- Operator remains redirected away from `/settings`.
- All links navigate to existing pages.

## Step 4 - State Copy Alignment

- Update page helper copy only where it reduces ambiguity:
  - Draft does not affect runtime until publish/default.
  - Live rules page is read-only inspection/simulation.
  - Rollback switches default pointer, not history.
  - Translation Profile excludes prompt body/secrets.
  - Translation Term Set CSV import remains the only draft mutation path in this phase.
- Avoid broad CSS refactors and avoid changing API behavior.

Validation:

```bash
cd frontend && npm run build
git diff --check
```

## Step 5 - Summary Boundary Check

- Keep `ConfigTodoSummary` limited to existing signals and align wording only.
- Do not add Translation Term Set aggregate calls.
- Do not add a backend summary endpoint.

## Review Gates

- Confirm route compatibility for:
  - `/settings/term-rule-sets`
  - `/settings/term-rule-sets` with proposal governance query
  - `/settings/term-rules`
  - `/term-proposals` links back to governance pages
- Confirm no new live write action appears on the live rules inspection page.
- Confirm no prompt/secret/system env editing UI was introduced.
- Confirm operator cannot access `/settings/**`.

## Final Verification Target

Minimum expected checks after implementation:

```bash
cd frontend && npm run build
git diff --check
python3 ./.trellis/scripts/task.py validate 06-10-config-governance-ux-consolidation
```

Browser acceptance should cover desktop and mobile widths for:

- `/settings`
- `/settings/term-rule-sets`
- `/settings/term-rules`
- `/settings/translation-term-sets`
- `/settings/translation-profiles`

## Rollback Plan

- If terminology grouping causes navigation or deep-link regressions, remove the shared terminology nav component and keep the previous standalone pages.
- If settings grouping creates layout regressions, revert only `SettingsHomePage.vue` and keep breadcrumb/state-copy improvements.
- If optional summary expansion causes latency or brittle failures, revert the summary expansion and leave grouped links intact.
