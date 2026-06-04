# Term rule workbench implementation plan

## Gate

Do not run `task.py start` or edit application code until this plan is reviewed.

## Preconditions

- Stay inside the narrowed `term-rule-workbench` slice defined in `prd.md`.
- Do not implement full term rule CRUD, import/export, file deletion, version diff, or proposal workflow changes.
- Do not run pdf-mineru parsing, translation, or Word generation.
- Preserve existing routes and Admin role guard behavior.

## Checklist

1. [x] Add frontend simulation contract
   - File: `frontend/src/api/types.ts`
   - Add `RuleSimulationRequest` and `RuleSimulationResponse`.
   - File: `frontend/src/api/termRules.ts`
   - Add `termRulesApi.simulate`.

2. [x] Add workbench route
   - File: `frontend/src/router/index.ts`
   - Import `TermRuleWorkbenchPage`.
   - Register `/settings/term-rules` with `meta.roles = ["admin"]`.

3. [x] Add config center entry
   - File: `frontend/src/pages/SettingsHomePage.vue`
   - Add one card linking to `/settings/term-rules`.
   - Keep existing term rule set card for draft/publish governance.

4. [x] Build focused page
   - File: `frontend/src/pages/TermRuleWorkbenchPage.vue`
   - Load categories and rules on mount.
   - Add filters for category, enabled state, and keyword.
   - Render category summary and read-only rules table.
   - Use `TermPreview` for segment preview.
   - Add a read-only detail drawer.
   - Add simulation panel that displays returned previews as text.

5. [x] Verification
   - Run `cd frontend && npm run build`.
   - Run `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-workbench`.
   - Do not run pdf-mineru main workflow.

## Review Checks

- Confirm no backend files changed.
- Confirm no rule create/update/delete/import/export buttons were introduced.
- Confirm `/settings/term-rules` is Admin-only via existing route metadata.
- Confirm HTML simulation output is not rendered with raw `v-html`.
- Confirm build succeeds.

## Rollback Point

If the page grows beyond the focused read-only/simulation slice, revert the page/card/route changes before adding more behavior. Full CRUD, import/export, and version diff must become separate reviewed tasks.

## Implementation Summary

- Added `/settings/term-rules` as an Admin-only frontend route.
- Added a configuration-center card for the focused term rule inspection page.
- Added `RuleSimulationRequest` / `RuleSimulationResponse` and `termRulesApi.simulate`.
- Added `TermRuleWorkbenchPage.vue` with category summary, rule filters, read-only rule list/detail drawer, and text-only simulation result display.
- No backend endpoint, persistence, document job, worker, pdf-mineru, translation, or Word generation code was changed.

## Verification Results

- `cd frontend && npm run build` passed.
- `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-workbench` passed.
- Static grep confirmed the new page/API wrapper does not use `v-html` and does not call rule import/export/sync, PATCH, PUT, or DELETE APIs.
- Playwright smoke with mocked Admin/API responses passed on `http://127.0.0.1:3000/settings/term-rules`: page rendered category summary, rule list, subscript segment preview, detail drawer, and simulate results with HTML preview shown as text.
- Playwright smoke with mocked Operator response passed: direct visit to `/settings/term-rules` redirected to `/jobs`, and Operator navigation did not show Admin-only entries.
- Did not run pdf-mineru parsing, translation, or Word generation.

## Spec Update

- No `.trellis/spec` update is needed. This task adds a narrow frontend page over existing APIs and existing route-guard/component patterns; it does not introduce a new backend contract, persistence rule, or reusable engineering convention.
