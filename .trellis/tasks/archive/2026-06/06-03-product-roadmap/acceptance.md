# md2word Product Roadmap Acceptance

## Phase 2 Overall Acceptance Closeout

Closeout date: 2026-06-05.

Verdict: Phase 2 `Configuration Governance` can be closed. The current archived task set and source code cover the roadmap's Term Rule governance, Translation Term Set governance, and proposal review queue governance linkage. This closeout did not implement new features and did not run pdf-mineru parsing, translation provider calls, or Word generation.

## Inputs Reviewed

- `AGENTS.md`
- `.trellis/workflow.md`
- `.trellis/tasks/archive/2026-06/06-03-product-roadmap/{prd.md,design.md,implement.md}`
- Phase 2 related Trellis tasks under `.trellis/tasks/archive/2026-06/`
- Current backend/frontend code for Term Rules, Translation Term Sets, and proposal review
- Current API docs and tests for the same areas

## Coverage Matrix

| Phase 2 target | Evidence | Acceptance result |
|---|---|---|
| Term Rule read-only inspection and simulation | `term-rule-workbench` | Covered. Admin-only inspection/simulation page remains read-only and did not become the editing surface. |
| Term Rule draft CRUD | `term-rule-draft-crud-contract`; current `/api/v1/term-rule-sets/{set_id}/draft/rules` endpoints | Covered. Structured draft rule list/get/create/update/delete exists and mutates draft only. |
| Term Rule Set diff and preflight | `term-rule-set-diff-preflight`; current diff/preflight endpoints and publish gate | Covered. Diff and preflight are exposed, and blocking preflight prevents publish. |
| Term Rule governance UI | `term-rule-governance-ui`; `TermRuleSetPage.vue` | Covered. Admin can edit draft rules, inspect diff/preflight, publish through the governed flow, and keep YAML fallback. |
| Term Rule proposal conflicts and linkage | `term-rule-proposal-boundary-conflicts`; `term-rule-proposal-review-governance-linkage`; MySQL E2E smoke | Covered. Structured conflicts, bulk approve/reject, governance CTA/return, and draft-category source consistency are covered. |
| Translation Term Set management | `translation-term-set-management`; `translation-term-set-governance-hardening` | Covered. Admin list/detail/draft/import/export/publish/default/rollback exists, with CSV and default/rollback semantics hardened. |
| Translation Term Set diff/preflight/proposal compatibility | `translation-term-governance-diff` | Covered. Read-only diff, preflight, and pending proposal compatibility preview exist. |
| Translation proposal review linkage | `translation-term-proposal-review-governance-linkage`; MySQL E2E smoke | Covered. Bulk approve/reject, structured conflict display, governance CTA/return, and compatibility focus are covered. |
| Shared proposal review shell | `proposal-review-queue-shared-shell`; `proposal-review-queue-enhancement` | Covered. Deep-link, focus/fallback, selected-row state, and shared review shell are in place. |

## Current Verification Run

Run on 2026-06-05 in this closeout:

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k term_rule`: passed, 23 tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k translation_term`: passed, 14 tests.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`: passed, 3 tests.
- `npm --prefix frontend run build`: passed.
- `python3 ./.trellis/scripts/task.py validate .trellis/tasks/archive/2026-06/06-03-product-roadmap`: passed.
- `python3 ./.trellis/scripts/task.py validate .trellis/tasks/archive/2026-06/06-04-term-rule-governance-phase2`: passed.
- `python3 ./.trellis/scripts/task.py validate .trellis/tasks/archive/2026-06/06-04-proposal-review-queue-enhancement`: passed.

Observed non-blocking warnings:

- Starlette/FastAPI HTTP status deprecation warnings.
- Vite/Rollup third-party pure annotation warning.
- Vite chunk-size warning.

Not run in this closeout:

- pdf-mineru parsing.
- Translation provider calls.
- Word generation.
- Production deploy or production browser smoke. The latest production/MySQL smoke evidence remains in `06-05-proposal-review-queue-mysql-e2e-smoke`.

## Unfinished Or Risk Items

- Row-level Translation Term CRUD remains intentionally out of scope. Current editing path is CSV import plus governance diff/preflight.
- Bulk `approve-and-publish`, automatic rebase, force approve, and automatic conflict resolution remain intentionally out of scope.
- Frontend automated component tests are still absent; current confidence comes from build/typecheck, task smoke records, and backend/API tests.
- This closeout observed `resources/term_rules/term_rules.v2.yaml` being modified by targeted term-rule tests and restored it to `HEAD`. The test side-effect risk should be isolated in a future cleanup if this test group is run frequently.
- Phase 2 acceptance is based on current local code plus archived smoke records; production state was not revalidated in this closeout turn.

## Finish / Archive Recommendation

No active Trellis task remains. These Phase 2 related tasks are already in archive with `task.json.status=completed` and can stay archived:

- `term-rule-workbench`
- `term-rule-governance-phase2`
- `term-rule-draft-crud-contract`
- `term-rule-set-diff-preflight`
- `term-rule-governance-ui`
- `term-rule-proposal-boundary-conflicts`
- `translation-term-set-management`
- `translation-term-set-governance-hardening`
- `translation-term-governance-diff`
- `proposal-review-queue-enhancement`
- `proposal-review-queue-shared-shell`
- `term-rule-proposal-review-governance-linkage`
- `translation-term-proposal-review-governance-linkage`
- `proposal-review-queue-mysql-e2e-smoke`

Do not use the following as Phase 2 blockers:

- `translation-result-qa`: belongs to Phase 3.
- `file-retention-management`, `audit-log-viewer`, `ops-dashboard`, `document-job-bulk-apis`: belong to operations / Phase 4 or cross-stage hardening.

## Recommended Phase 3 Order

1. Start with a Phase 3 gap audit against the existing `translation-result-qa` task and current code, because part of the Result QA direction already has an archived slice.
2. Confirm the smallest Phase 3 MVP around task-level QA status, result evidence display, and issue attribution before adding new UI.
3. Add traceability next: paragraph/source-vs-translation evidence, term hit trace, AI call log/debug archive links where data is actually available.
4. Integrate QA status back into job detail and list filters after the evidence surface is stable.
5. Defer retention, audit export, worker monitoring, and alerting to Phase 4 unless Phase 3 evidence work directly depends on them.
