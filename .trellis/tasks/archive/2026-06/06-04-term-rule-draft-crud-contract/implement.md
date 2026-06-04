# Term Rule Draft CRUD Contract Implementation Plan

## Gate

This child task may enter implementation after these planning artifacts are written and validated. Scope is backend contract only. Do not touch frontend pages in this task except generated API docs/OpenAPI if needed.

Do not run pdf-mineru parsing, translation, Word generation, or any real file deletion.

## Checklist

1. [x] Add response schemas
   - File: `app/domains/term_rules/schemas.py`
   - Add mutation response for create/update.
   - Add delete response carrying updated draft metadata.
   - Reuse existing `TermRuleResponse`, `TermRuleCreateRequest`, `TermRuleUpdateRequest`, and `TermRuleListResponse` where practical.

2. [x] Add draft CRUD service methods
   - File: `app/domains/term_rules/versioning_service.py`
   - Add list/get/create/update/delete methods operating on `TermRulesStore` loaded from draft.
   - Keep live runtime store and runtime YAML untouched.
   - Add small helpers for validation and serialization if needed.

3. [x] Add router endpoints
   - File: `app/domains/term_rules/sets_router.py`
   - Add `GET /{set_id}/draft/rules`.
   - Add `GET /{set_id}/draft/rules/{rule_id}`.
   - Add admin-only `POST /{set_id}/draft/rules`.
   - Add admin-only `PATCH /{set_id}/draft/rules/{rule_id}`.
   - Add admin-only `DELETE /{set_id}/draft/rules/{rule_id}`.
   - Preserve existing `PUT /{set_id}/draft/rules` YAML endpoint.

4. [x] Add backend tests
   - File: `tests/test_fastapi_jobs_backend.py`
   - Cover list/get draft rule.
   - Cover create/update/delete only mutates draft.
   - Assert runtime YAML does not change before publish.
   - Cover non-admin write rejection.
   - Cover file backend returns `503`.
   - Cover duplicate source term, unknown category, empty segments, invalid render/apply scope.
   - Ensure legacy write guard test still passes.

5. [x] Update API docs
   - File: `docs/api/term-rule-sets.md`
   - Add draft CRUD endpoints.
   - Add currently existing import/export docs that are missing from the markdown page.

6. [x] Regenerate OpenAPI snapshot
   - File: `docs/api/openapi.json`
   - Use existing export script if schema changed.

7. [x] Validation
   - Run `python -m unittest tests.test_fastapi_jobs_backend -k term_rule_set`.
   - Run `python -m unittest tests.test_openapi_export`.
- Run `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-draft-crud-contract`.

## Verification Results

- `python -m unittest tests.test_fastapi_jobs_backend -k term_rule_set`: passed, 7 tests.
- `python -m unittest tests.test_openapi_export`: passed, 3 tests.
- `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-draft-crud-contract`: passed.

## Review Checks

- No frontend governance UI changes in this child task.
- No changes to pdf-mineru, translation, worker, or Word rendering pipeline.
- No real file deletion.
- No direct use of live `TermRuleService` mutating methods for draft CRUD.
- `TermRuleWorkbenchPage` remains untouched and read-only.
- Published versions remain immutable.

## Rollback Point

If contract shape proves wrong, remove the new endpoints/service methods/schemas and docs/OpenAPI changes. Existing YAML draft update, import/export, publish, default and rollback flows remain intact.
