# Translation Term Governance Diff Gap Audit Implementation Plan

## Status

No-code closeout completed after user review and `task.py start`.

No production code has been changed.

## Closeout Result

- User confirmed the audit conclusion.
- Executed `task.py start` only to move the audit through the Trellis lifecycle.
- Reconfirmed that the first-version `translation-term-governance-diff` implementation already exists in current code.
- No backend, frontend, API, persistence, dependency, or test code was changed.
- Recommended follow-up remains `translation-term-governance-diff-browser-smoke`.

## Proposed Execution After Review

The approved no-code closeout pass is:

1. Reconfirm active task and dirty diff.
2. Re-read the audit evidence if files changed after this planning draft.
3. Validate that the audit conclusion still holds:
   - diff/preflight/proposal compatibility already implemented
   - proposal review bulk/linkage already implemented
   - per-row Translation Term CRUD is not needed for first-version diff
4. Run lightweight validation:
   - `python3 ./.trellis/scripts/task.py validate .trellis/tasks/06-06-translation-term-governance-diff-gap-audit`
   - `git diff --check`
5. Archive the audit task.

## Recommended Follow-up Task

Do not create another implementation task for `translation-term-governance-diff` unless code has regressed.

Recommended first follow-up:

`translation-term-governance-diff-browser-smoke`

Scope:

- Browser/front-end smoke only.
- Use mocked Translation Term Set APIs or deterministic test fixture data.
- Validate rendered diff/preflight/proposal-compatibility states.
- Do not run pdf-mineru parsing, translation providers, or Word generation.
- Do not add row-level CRUD, automatic rebase, or new mutation workflows.

## Verification Already Observed From Repository Evidence

Current code contains:

- `GET /api/v1/translation-term-sets/{set_id}/diff`
- `GET /api/v1/translation-term-sets/{set_id}/preflight`
- `GET /api/v1/translation-term-sets/{set_id}/proposal-compatibility`
- `POST /api/v1/translation-term-proposals/bulk-approve`
- `POST /api/v1/translation-term-proposals/bulk-reject`
- Frontend `TranslationTermSetPage.vue` diff/preflight/proposal compatibility UI.
- Frontend `TermProposalsPage.vue` translation review bulk actions and governance deep-link flow.
- Targeted backend tests for diff/preflight/proposal compatibility and translation proposal bulk review.

## Suggested Optional Runtime Checks

Only run these after review if the user wants current runtime verification:

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k translation_term_set_diff`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k translation_term_proposal_bulk`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- `npm --prefix frontend run build`

These checks do not require pdf-mineru parsing, real translation provider calls, or Word generation.

## Review Gate

Before `task.py start`, confirm one of these paths:

- Accept audit conclusion and start only to close/archive the no-code gap audit.
- Request changes to the audit conclusion or first follow-up boundary.
- Reject the conclusion and explicitly ask for a deeper code/test verification pass.
