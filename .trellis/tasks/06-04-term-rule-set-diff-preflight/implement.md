# Term Rule Set Diff Preflight Implementation Plan

## Gate

Scope is backend contract only. Do not implement frontend pages in this child task. Do not run pdf-mineru parsing, translation, Word generation, or any real file deletion.

This task may enter implementation after this PRD/design/implement set validates and `task.py start` is run.

## Checklist

1. [x] Add response schemas
   - File: `app/domains/term_rules/schemas.py`
   - Add version ref, diff summary, diff item, diff response, governance finding, preflight summary and preflight response models.
   - Reuse `TermRuleResponse` for before/after rule snapshots.

2. [x] Add diff service methods
   - File: `app/domains/term_rules/versioning_service.py`
   - Resolve `default`, `draft`, and explicit published versions.
   - Compare stores by `rule.id`.
   - Produce summary and changed items.
   - Support `include_unchanged`.

3. [x] Add preflight service methods
   - File: `app/domains/term_rules/versioning_service.py`
   - Reuse existing YAML/store validation where practical.
   - Add governance checks for duplicate source terms, missing/disabled categories, empty segments and default drift.
   - Include diff summary in the preflight response.

4. [x] Add router endpoints
   - File: `app/domains/term_rules/sets_router.py`
   - Add `GET /{set_id}/diff`.
   - Add `GET /{set_id}/preflight`.
   - Keep router thin and translate domain exceptions consistently.

5. [x] Add publish preflight gate
   - File: `app/domains/term_rules/versioning_service.py`
   - Run preflight before creating published version.
   - Blocking report must prevent publish.
   - Warning-only report must keep existing publish semantics.
   - Preserve runtime YAML sync behavior.

6. [x] Add backend tests
   - File: `tests/test_fastapi_jobs_backend.py`
   - Cover diff summary and changed items.
   - Cover explicit published version diff.
   - Cover `include_unchanged`.
   - Cover preflight warnings and blocking errors.
   - Cover publish blocked by preflight and warning-only publish success.
   - Cover file backend `503`.

7. [x] Update API docs
   - File: `docs/api/term-rule-sets.md`
   - Add diff and preflight endpoints.
   - Document publish preflight failure detail shape.

8. [x] Regenerate OpenAPI snapshot
   - File: `docs/api/openapi.json`
   - Use `scripts/ops/export_openapi.py`.

9. [x] Validation
   - Run `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k term_rule_set`.
   - Run `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`.
   - Run `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-set-diff-preflight`.

## Verification Results

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k term_rule_set`: passed, 9 tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`: passed, 3 tests.
- `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-set-diff-preflight`: passed.
- `git diff --check` on Child 2 files: passed.

## Review Checks

- No frontend governance UI changes in this child task.
- No changes to pdf-mineru, translation, worker, or Word rendering pipeline.
- No real file deletion.
- `TermRuleWorkbenchPage` remains untouched and read-only.
- Child 1 draft CRUD contract remains compatible.
- Published versions remain immutable.

## Rollback Point

If contract shape proves wrong, remove diff/preflight endpoints, schemas, service methods and publish gate. Existing YAML draft update, draft CRUD, import/export, publish, default and rollback flows remain intact.
