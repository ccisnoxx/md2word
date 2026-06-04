# Translation Term Governance Diff Implementation Plan

This task was approved, started with
`task.py start 06-04-translation-term-governance-diff`, implemented, and
verified on 2026-06-04. It has not been committed or archived in this turn.

## Classification

- Type: behavior-changing product feature, read-only governance visibility.
- Public contract change: yes, new Translation Term Set read endpoints and
  response schemas.
- Persistence change: no migration expected.
- Main-flow risk: low if implementation stays read-only and preserves existing
  job resource snapshot behavior.

## Ordered Checklist

1. [x] Backend schemas
   - Add response models in `app/domains/translation/schemas.py`:
     - `TranslationTermSetDiffSummaryResponse`
     - `TranslationTermSetDiffEntryResponse`
     - `TranslationTermSetDiffResponse`
     - `TranslationTermSetPreflightResponse`
     - `TranslationTermProposalCompatibilityFindingResponse`
     - `TranslationTermProposalCompatibilityItemResponse`
     - `TranslationTermProposalCompatibilityResponse`
   - Keep schema fields stable and frontend-friendly.

2. [x] Backend service diff/preflight
   - Add pure diff helpers to `TranslationTermSetVersionService`.
   - Resolve default `base_version` and `target_version=draft`.
   - Return added/removed/changed/unchanged counts.
   - Compare payload fields already used by `_entries_payload()`.
   - Build preflight from existing validation plus diff summary.
   - Do not mutate draft, set default, proposal status, or published versions.

3. [x] Backend proposal compatibility preview
   - Add a read-only method to evaluate pending Translation Term Proposals for
     a set.
   - Reuse or extract validation/conflict logic from
     `TranslationTermProposalService` without calling private helpers from the
     router.
   - Return structured findings for stale observed version, missing target,
     changed target, add-existing, update/delete-missing, and validation errors
     where applicable.
   - Do not approve, reject, publish, or update draft entries.

4. [x] Backend router
   - Add routes in `app/domains/translation/sets_router.py`:
     - `GET /{set_id}/diff`
     - `GET /{set_id}/preflight`
     - `GET /{set_id}/proposal-compatibility`
   - Translate `FileNotFoundError` to `404` and `ValueError` to `400`.
   - Preserve existing `503` behavior when MySQL resource service is disabled.

5. [x] Backend tests and docs
   - Add targeted tests in `tests/test_fastapi_jobs_backend.py`:
     - default-vs-draft diff reports added/removed/changed/unchanged.
     - preflight blocks validation errors and reports warnings.
     - missing version returns `404`.
     - non-MySQL runtime returns `503`.
     - proposal compatibility preview reports compatible and conflict items
       without changing proposal status or draft entries.
   - Update `docs/api/translation-term-sets.md`.
   - Regenerate `docs/api/openapi.json`.

6. [x] Frontend API/types
   - Add TypeScript response types in `frontend/src/api/types.ts`.
   - Add wrappers in `frontend/src/api/translationTermSets.ts`:
     - `getDiff(setId, params)`
     - `getPreflight(setId, params)`
     - `getProposalCompatibility(setId, params)`

7. [x] Frontend page
   - Extend `frontend/src/pages/TranslationTermSetPage.vue`.
   - Load diff/preflight/proposal compatibility after the selected set loads.
   - Add summary cards and diff table.
   - Add preflight blocking/warning display.
   - Add proposal compatibility table with links to existing proposal review
     workflow.
   - Do not add row-level CRUD, batch approve/reject, or auto-rebase controls.

8. [x] Verification
   - Backend targeted:
     `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.<new_test_names>`
   - OpenAPI:
     `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
     then inspect `docs/api/openapi.json`.
   - Frontend:
     `npm --prefix frontend run build`
   - Trellis:
     `python3 ./.trellis/scripts/task.py validate 06-04-translation-term-governance-diff`

## Review Gates

- Gate 1: confirm this task remains read-only diff/preflight/preview and does
  not implement batch mutations.
- Gate 2: confirm proposal compatibility response shape before frontend work.
- Gate 3: after backend tests and OpenAPI snapshot pass, wire frontend.

## Implementation Summary

- Added Admin-only read-only endpoints:
  - `GET /api/v1/translation-term-sets/{set_id}/diff`
  - `GET /api/v1/translation-term-sets/{set_id}/preflight`
  - `GET /api/v1/translation-term-sets/{set_id}/proposal-compatibility`
- Added structured response schemas for diff summary/items, preflight, and
  proposal compatibility findings.
- Extended `TranslationTermSetVersionService` with read-only diff/preflight and
  pending proposal compatibility preview methods.
- Extended `TranslationTermSetPage.vue` with diff/preflight and proposal
  compatibility cards.
- Updated `TermProposalsPage.vue` to open translation proposal review tabs from
  query params.
- Updated `docs/api/translation-term-sets.md` and regenerated
  `docs/api/openapi.json`.
- Added targeted backend API tests for diff/preflight success, blocking
  preflight, 403/404/503 boundaries, and read-only proposal compatibility.

## Verification Run

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_set_diff_and_preflight_reports_draft_changes tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_set_preflight_blocks_invalid_draft_and_preserves_error_boundaries tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_set_proposal_compatibility_preview_is_read_only`
  - Result: passed, `Ran 3 tests`.
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
  - Result: passed, `changed: True`.
- `npm --prefix frontend run build`
  - Result: passed.
  - Notes: Vite reported existing Rollup annotation and chunk-size warnings.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend`
  - Result: passed, `Ran 143 tests`.
  - Notes: output includes expected failure-path logs from existing tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
  - Result: passed, `Ran 3 tests`.
- `git diff --check`
  - Result: passed.

Browser smoke was not run because the current tool session did not expose a
Browser control tool and local Node does not have Playwright installed. A Vite
dev server was started and stopped; it emitted one expected `/api/v1/auth/me`
proxy error because no backend was listening on `127.0.0.1:8000`.

## Residual Risk

- Frontend verification is build/typecheck only; no rendered browser screenshot
  was captured.
- Proposal compatibility preview filters pending proposals in service memory.
  This keeps the change small and avoids a known test fake SQL branch issue;
  pagination/filtering can be revisited if proposal volume grows.
- Proposal compatibility is read-only. Batch approve/reject, rebase, and
  conflict-resolution workflows remain future tasks.

## Rollback Points

- If proposal compatibility scope grows, ship only diff + preflight and split
  proposal preview into a child task.
- If frontend layout risk grows, keep API/docs/tests and expose the page section
  behind a narrow conditional.
- If structured conflicts require too much proposal-service refactor, return
  validation-compatible preview first and split conflict normalization.

## Definition of Done

- [x] Planning artifacts approved.
- [x] Task status moved to `in_progress` before code edits.
- [x] New API contracts are documented and covered by targeted tests.
- [x] Frontend build passes after UI changes.
- [x] Existing Translation Term Set import/export/publish/default/rollback tests
  still pass.
- [x] No pdf-mineru parsing, translation provider calls, Word generation, or file
  deletion is executed.
