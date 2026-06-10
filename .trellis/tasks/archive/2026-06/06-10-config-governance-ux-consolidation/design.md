# Configuration Governance UX Consolidation Design

## Decision Summary

Use a conservative frontend-first consolidation.

- Keep current backend APIs and versioned resource semantics.
- Keep existing routes `/settings/term-rule-sets` and `/settings/term-rules` as compatible entry points.
- Do not add `/settings/terminology` in this task; route compatibility is more important than a new canonical URL for the first pass.
- Add a shared terminology-workbench navigation layer so both pages read as one logical workbench:
  - `草稿与发布` -> existing Term Rule Set governance page.
  - `当前生效规则` -> existing live Term Rule Workbench page.
- Keep each page's H1 specific (`术语规则集`, `术语规则检查`) and use the shared tabs plus helper copy to express the umbrella `术语工作台`.
- Update `/settings` from five equal cards into grouped governance areas, without hiding direct access to any current resource page.
- Do not expand `/settings` summary with Translation Term Set statistics in this task; first ship the grouped UX without adding more aggregate requests.
- Align page labels, helper text, disabled reasons, and breadcrumb labels around one resource-state vocabulary.

This avoids extracting the large existing pages into nested panels during the first consolidation pass and preserves proposal deep links.

## Observed Code Surface

Frontend:

- `frontend/src/router/index.ts`
  - Config routes are already admin-only.
  - Current routes include `settings`, `settings/templates`, `settings/templates/:templateId`, `settings/term-rule-sets`, `settings/term-rules`, `settings/translation-profiles`, `settings/translation-term-sets`.
- `frontend/src/components/AppBreadcrumb.vue`
  - Already returns from config children to `/settings`.
  - Needs label refinement for terminology grouping.
- `frontend/src/pages/SettingsHomePage.vue`
  - Current config center is a five-card grid.
  - `ConfigTodoSummary` currently counts templates, term proposals, and translation profile drafts.
- `frontend/src/pages/TermRuleSetPage.vue`
  - Already implements draft rule CRUD, diff, preflight, publish, set-default, rollback, approved proposals, and proposal return context.
- `frontend/src/pages/TermRuleWorkbenchPage.vue`
  - Already implements read-only live categories/rules and simulate.
- `frontend/src/pages/TranslationTermSetPage.vue`
  - Already implements CSV draft import/export, validation, diff/preflight, proposal compatibility, publish, set-default, rollback.
- `frontend/src/pages/TranslationProfilesPage.vue`
  - Already implements draft basics, publish, set-default, rollback and explicitly excludes prompt body editing.
- `frontend/src/pages/TemplateDetailPage.vue`
  - Already requires validation job evidence and reasons around template publish/default.

Backend/docs boundaries:

- `docs/api/term-rule-sets.md`
  - Term Rule Set draft writes do not refresh runtime YAML until publish/default.
  - Publish has blocking preflight and records approved proposal publication.
- `docs/api/term-rules.md`
  - Legacy live writes are rejected in MySQL versioned mode.
  - `/term-rules` remains live read/simulate surface.
- `docs/api/translation-term-sets.md`
  - Diff/preflight/proposal compatibility are read-only and do not mutate draft/proposal/publish state.
- `docs/api/translation-profiles.md`
  - Profile payload excludes secrets and prompt body.
- `docs/api/templates.md`
  - Template publish requires verification job evidence and audit reason.

## UX Architecture

### `/settings` Information Architecture

Replace the flat card list with grouped sections:

1. `术语工作台`
   - Primary action: `草稿与发布` -> `/settings/term-rule-sets`
   - Secondary action: `当前生效规则` -> `/settings/term-rules`
   - Signals:
     - pending review proposals
     - approved but unpublished proposals
     - blocking preflight state when available without excessive calls
   - Copy: production edits happen in draft/publish, live page is inspection/simulation only.

2. `模板与版式`
   - Link: `/settings/templates`
   - Signals:
     - template draft version count
     - missing verification evidence count
   - Copy: publish requires validation job evidence and reason.

3. `翻译治理`
   - Link: `/settings/translation-profiles`
   - Link: `/settings/translation-term-sets`
   - Signals:
     - translation profile draft availability/count
     - Translation Term Set draft/validation/proposal compatibility if added cheaply.
   - Copy: profile controls metadata/batch/model fields only; translation terms remain CSV draft import/export in this phase.

The existing `ConfigTodoSummary` can stay as a top summary, but labels should match the grouped sections.

### Terminology Workbench

Add a small shared component, for example `TerminologyWorkbenchNav.vue`, used at the top of both terminology pages.

Props:

- `active`: `"draft-publish" | "live-rules"`

Behavior:

- Renders two Element Plus tabs or segmented controls:
  - `草稿与发布`
  - `当前生效规则`
- Navigates by route, not local component state:
  - `draft-publish` -> `{ name: "settings-term-rule-sets", query: preservedGovernanceQuery }`
  - `live-rules` -> `{ name: "settings-term-rules" }`
- Preserves governance query only when staying on or returning to the draft/publish route.
- Does not wrap the large pages or duplicate their state.

Page heading changes:

- `TermRuleSetPage`
  - H1 can remain `术语规则集` or become `术语工作台`
  - Add subheading/badge: `草稿与发布`
  - State hint: `结构化编辑只修改 draft；publish / set-default 后才影响后续默认和 runtime 同步。`
- `TermRuleWorkbenchPage`
  - H1 can remain `术语规则检查` or become `术语工作台`
  - Add subheading/badge: `当前生效规则`
  - State hint: `只读检查当前 live runtime store；生产修改请进入草稿与发布。`

### Breadcrumbs

Update `AppBreadcrumb` labels:

- `settings-term-rule-sets`:
  - `配置中心` -> `术语工作台` -> `草稿与发布`
- `settings-term-rules`:
  - `配置中心` -> `术语工作台` -> `当前生效规则`

Keep `/settings` as the parent target.

### Route Compatibility

Do not remove or rename current routes in the first implementation pass.

No additive terminology route is planned for this task.

Avoid making old routes hard redirects until proposal deep-link and browser acceptance are verified, because `TermRuleSetPage` currently reads governance query directly from `useRoute()`.

## Data Contract

No backend contract changes are required for the first pass.

Existing frontend APIs remain authoritative:

- `termRuleSetsApi`
  - list/get/getDraft/listDraftRules/diff/preflight/publish/setDefault/rollback
- `termRulesApi`
  - listCategories/listRules/getRule/simulate
- `translationTermSetsApi`
  - list/get/getDraft/getDiff/getPreflight/getProposalCompatibility/importCsv/exportCsv/publish/setDefault/rollback
- `translationProfilesApi`
  - list/get/getDraft/updateDraft/publish/setDefault/rollback
- `templatesApi`
  - list/get/listVersions/createVersion/publishVersion/setDefaultVersion/disableVersion

If the settings summary is expanded, keep it frontend-aggregated at first and tolerate `503` for resource-service-dependent domains in the same pattern as current `configSummaryApi`.

## State Vocabulary

Use the same vocabulary across pages:

- `draft`: staged editable state; not effective for existing jobs; may be derived from default.
- `published`: immutable version; can be selected by admin for future jobs or made default.
- `default`: published version used when a new job does not explicitly select a version.
- `runtime live`: live store/YAML or manifest state consumed by conversion paths after publish/default synchronization.
- `proposal`: user/admin request that can merge into draft but is not itself production config.
- `rollback`: default pointer switch back to a published version; not history rewrite.

Do not introduce synonyms like "active draft" or "production draft".

## Security And Safety

- Keep all `/settings/**` routes admin-only via router meta.
- Keep operator feedback through `/term-proposals` and QA deep links.
- Do not add live term-rule write actions to `/settings/term-rules`.
- Do not expose prompt bodies, API keys, provider secrets, S3 settings, worker settings, or deployment env editing.
- Preserve backend as authority for blocking preflight, publish validity, set-default/rollback validity, and permission failures.

## Rollout Shape

1. Frontend-only UX consolidation.
2. Browser smoke with admin and operator users.
3. Additive route alias only if useful; no route removals.
4. Backend/API follow-up only if implementation finds missing status fields that cannot be inferred safely.

## Resolved Questions

- `/settings/terminology`: not added in this task.
- Terminology H1s: keep specific page names and show `术语工作台` through shared navigation/context copy.
- `/settings` summary: do not expand Translation Term Set statistics in this task; only regroup the landing page and align existing summary labels.
