# Term Rule Governance UI Implementation Plan

## Gate

This child task is frontend-focused. Do not modify backend API behavior unless a compile-time type mismatch proves the existing contract unusable and the user approves the backend change.

Do not run pdf-mineru parsing, translation, Word generation, or any real file deletion.

## Checklist

1. [x] Add frontend API types
   - File: `frontend/src/api/types.ts`
   - Add draft rule CRUD request/response types.
   - Add diff/preflight response types.
   - Keep names aligned with backend Pydantic models.

2. [x] Add Term Rule Set API wrappers
   - File: `frontend/src/api/termRuleSets.ts`
   - Add list/get/create/update/delete draft rule methods.
   - Add diff and preflight methods.
   - Preserve existing YAML draft update and publish/default/rollback wrappers.

3. [x] Extend `TermRuleSetPage`
   - File: `frontend/src/pages/TermRuleSetPage.vue`
   - Add draft rule filters and table.
   - Add rule create/edit dialog using `TermSegmentEditor` and `TermPreview`.
   - Add enable/disable quick action.
   - Add delete action with confirmation.
   - Add diff summary and changed items table.
   - Add preflight summary and finding list.
   - Add publish dialog preflight report and blocking disable behavior.
   - Keep YAML fallback.

4. [x] Optionally adjust shared components only if needed
   - File: `frontend/src/components/TermSegmentEditor.vue`
   - Only touch if page integration exposes layout or typing friction.
   - Do not change proposal form semantics.

5. [x] Preserve read-only workbench
   - File: `frontend/src/pages/TermRuleWorkbenchPage.vue`
   - Prefer no changes.
   - If touched, only add navigation or explanatory read-only note.
   - Do not add edit/delete/import/export/publish controls.

6. [x] Frontend validation
   - Run `cd frontend && npm run build`.
   - If a dev server is needed for manual smoke, start it only after implementation and report URL.

## Verification Results

- `cd frontend && npm run build`: passed.
- `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-governance-ui`: passed.
- `git diff --check` on Child 3 files: passed.
- Frontend dev server started at `http://127.0.0.1:3000/`.

## Review Checks

- `TermRuleWorkbenchPage` remains read-only.
- `TermRuleSetPage` is the only governance editing surface.
- No backend contract changes.
- No pdf-mineru / translation / Word generation command.
- No real file deletion.
- UI handles `503` resource service unavailable state.
- Publish disabled when `preflight.blocking=true`.
- YAML fallback remains available.

## Rollback Point

Remove the new Draft Rules, Diff and Preflight UI sections plus new frontend API wrappers/types. Existing `TermRuleSetPage` YAML fallback, published versions, approved proposals, publish/default/rollback remain intact.
