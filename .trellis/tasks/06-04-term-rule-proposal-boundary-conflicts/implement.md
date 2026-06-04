# Term Rule Proposal Boundary Conflicts Implementation Plan

## Gate

This child task may touch backend proposal contract, frontend proposal review display, API docs, OpenAPI snapshot, and targeted tests only.

Do not run pdf-mineru parsing, translation, Word generation, or any real file deletion. Do not add edit/publish controls to `TermRuleWorkbenchPage`. Do not change Child 1/2/3 contracts unless a direct compile or test failure proves a compatibility issue.

## Checklist

1. [x] Add response schemas
   - File: `app/domains/term_rules/schemas.py`
   - Add `TermRuleProposalConflictItemResponse` and `TermRuleProposalConflictResponse`.
   - Reuse `TermRuleResponse` for current rule payload.
   - Keep field names aligned with frontend type names.

2. [x] Carry structured conflicts through service
   - File: `app/domains/term_rules/proposals_service.py`
   - Update `TermRuleProposalConflictError` to store `conflicts`.
   - Add a small conflict builder for missing target, stale target, and source term segment conflicts.
   - Ensure conflicts are raised before draft mutation, proposal status mutation, publish, and success audit events.

3. [x] Return structured `409` from router
   - File: `app/domains/term_rules/proposals_router.py`
   - Map `TermRuleProposalConflictError` to `detail={"code": "term_rule_proposal_conflict", "message": ..., "conflicts": [...]}`.
   - Add `responses={409: ...}` metadata for approve and approve-and-publish if consistent with local OpenAPI style.
   - Preserve existing `400` / `403` / `404` / `503` behavior.

4. [x] Add backend regression tests
   - File: `tests/test_fastapi_jobs_backend.py`
   - Update existing stale snapshot test to assert structured detail.
   - Add missing target rule conflict coverage.
   - Add create same source term different segments conflict coverage.
   - Add approve-and-publish conflict does not publish coverage.
   - Assert proposal remains `pending_review` and draft is unchanged.

5. [x] Update frontend type contract
   - File: `frontend/src/api/types.ts`
   - Add proposal conflict response types.
   - Do not change proposal success response shape.

6. [x] Render structured conflicts in proposal page
   - File: `frontend/src/pages/TermProposalsPage.vue`
   - Parse `detail.conflicts[]` object items first.
   - Keep string fallback for existing Translation Term Proposal and legacy backend details.
   - Preserve local snapshot warning and current review actions.

7. [x] Update API docs and OpenAPI snapshot
   - File: `docs/api/term-rules.md`
   - File: `docs/api/openapi.json`
   - Document `409` payload and proposal/direct governance boundary.

8. [x] Validation
   - Run `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k term_rule_proposal`。
   - Run `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`。
   - Run `cd frontend && npm run build`。
   - Run `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-proposal-boundary-conflicts`。

## Verification Results

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests -k term_rule_proposal`: passed, 7 tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`: passed, 3 tests. Existing FastAPI status constant deprecation warnings were printed.
- `cd frontend && npm run build`: passed. Existing Rollup pure annotation and chunk size warnings were printed.
- `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-proposal-boundary-conflicts`: passed.

## Review Checks

- Proposal conflict response is structured and stable.
- Conflict does not mutate draft.
- Conflict does not mark proposal approved/published.
- Conflict does not run publish in approve-and-publish path.
- `TermRuleSetPage` direct governance remains unchanged.
- `TermRuleWorkbenchPage` remains read-only.
- Translation Term Proposal conflict display still works.
- No pdf-mineru / translation / Word generation command was run.
- No real file deletion was performed.

## Rollback Point

Revert the structured conflict schemas, service conflict payload, router `409` detail mapping, frontend structured display, docs, and related tests. Existing free-text `409` conflict path can be restored without changing draft CRUD, diff/preflight, governance UI, or workbench read-only behavior.
