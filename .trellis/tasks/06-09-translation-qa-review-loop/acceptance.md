# Translation QA Review Loop Acceptance

## Result

Accepted for the implemented scope. The task adds a `/translation-qa` reviewer queue, keeps `/jobs/:jobId/translation-qa` as the single-task evidence page, and routes terminology feedback into the existing translation term proposal page. No translation QA summary API, standalone translation result page, online translation editing, or edited-translation Word regeneration path was added.

## Implementation Covered

- `/translation-qa` route and authenticated navigation entry.
- QA queue page backed by `documentJobsApi.list()` / `GET /api/v1/document-jobs`.
- Queue filters for QA status, document job status, keyword, sort, archive inclusion, and pagination.
- Default queue state canonicalized into route query:
  - `translation_qa_status=unreviewed`
  - `sort=updated_at_desc`
  - `include_archived=false`
  - `page=1`
- Queue row actions:
  - `复核` to `/jobs/:jobId/translation-qa` with queue context query.
  - `任务详情` to `/jobs/:jobId`.
- Single-task QA page actions:
  - `返回 QA 队列`
  - `任务详情`
  - `提交翻译术语建议`
- Term proposal deep link fields:
  - `tab=translation-new`
  - `source_job_id`
  - `source_file_id`
  - `observed_translation_term_set_id`
  - `observed_translation_term_version`

## Verification Commands

Passed:

```bash
cd frontend
npm run build
```

Build completed. Vite emitted existing warnings about Rollup comment annotations in `@vueuse/core` and large chunks over 500 kB.

Passed:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_list_supports_workbench_filters_without_running_worker \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_reads_existing_artifacts_and_updates_review_state \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review
```

Result: `Ran 3 tests ... OK`.

Passed:

```bash
git diff --check
/Users/sc/miniconda3/envs/md2word/bin/python .trellis/scripts/task.py validate 06-09-translation-qa-review-loop
```

Boundary scan:

```bash
rg -n "translation-qa/summary|translationQaSummary|translation result|TranslationResultPage|regen|regenerate|重新生成|编辑译文" \
  frontend/src app .trellis/tasks/06-09-translation-qa-review-loop
```

Only task documentation / PRD references were found for the forbidden items; no code path for a summary API, standalone translation result page, edited-translation regeneration, or translation editing UI was found.

## Browser Acceptance

Local services used for acceptance:

- Frontend: Vite on `http://127.0.0.1:3000/`.
- API: `scripts/dev/run_api.py` on `http://127.0.0.1:8000/`.
- API was run with:
  - `JOBS_REPOSITORY_BACKEND=file`
  - `JOBS_WORKER_MODE=external`
  - `DOCUMENT_JOBS_WORKER_BACKEND=disabled`
  - temporary internal auth users from the existing test fixture

No PDF-MinerU parsing, translation provider call, worker execution, clone/rerun execution, or Word generation was run.

For complete page acceptance, a temporary file-backend data directory was seeded at:

```text
/private/tmp/md2word_translation_qa_acceptance_var
```

Seeded fixture:

- Job: `qa_acceptance_job_001`
- Mode: `en2zh_pdf_to_word`
- Status/stage: `succeeded` / `completed`
- QA status before save: `unreviewed`
- Existing evidence files: source PDF metadata, DocumentIR, AI call log, AI debug archive, dummy generated Word metadata.

Browser checks passed:

- `/translation-qa` redirects unauthenticated users to `/login?redirect=/translation-qa`.
- After login, `/translation-qa` canonicalizes to default query.
- Direct query filters render expected labels and state, including `translation_qa_status=all`, `status=succeeded`, `sort=created_at_desc`, `include_archived=true`, and `q`.
- Queue renders the seeded job with `复核` and `任务详情` actions.
- Clicking `复核` opens `/jobs/qa_acceptance_job_001/translation-qa` with queue context query.
- QA page shows:
  - `返回 QA 队列`
  - `任务详情`
  - `提交翻译术语建议`
  - segment evidence
  - term trace for `input offset voltage`
  - AI call metadata for the fixture provider
- `保存复核` issued the existing PATCH endpoint. Changing status to `approved` saved successfully and displayed `最近复核：user_operator`.
- `返回 QA 队列` preserved the original queue context query.
- `提交翻译术语建议` opened:

```text
/term-proposals?tab=translation-new&source_job_id=qa_acceptance_job_001&source_file_id=...&observed_translation_term_set_id=translation_terms&observed_translation_term_version=2026-acceptance
```

- Queue `任务详情` opened `/jobs/qa_acceptance_job_001`.
- Browser console error log checks for the accepted pages returned no errors.

One browser-tool limitation was observed: after restarting Vite, the browser automation runtime could not fill text inputs through its virtual clipboard. This was a tooling limitation, not an app error. The filter route state was still verified through direct query URLs, API logs, and build/typecheck.

## Boundary Confirmation

- No new `/api/v1/translation-qa/summary` or frontend summary wrapper was added.
- `/jobs/:jobId/translation-qa` remains the single-task evidence page.
- No independent translation result route/page was added.
- No online translation editing UI was added.
- No flow for regenerating Word from human-edited translation was added.
- Queue metrics are scoped to current filter/page data and do not present `DocumentJobListResponse.summary` as QA totals.

## Pending Commit File List

Recommended files for this task:

- `.trellis/tasks/06-09-translation-qa-review-loop/design.md`
- `.trellis/tasks/06-09-translation-qa-review-loop/implement.md`
- `.trellis/tasks/06-09-translation-qa-review-loop/acceptance.md`
- `frontend/src/pages/TranslationQaQueuePage.vue`
- `frontend/src/router/index.ts`
- `frontend/src/pages/TranslationResultQaPage.vue`
- `frontend/src/components/AppBreadcrumb.vue`
- `frontend/src/layouts/AppLayout.vue`

Staging caution:

- `frontend/src/layouts/AppLayout.vue` also contains pre-existing breadcrumb-shell changes; the task-specific hunk is the `翻译 QA` nav item.
- `frontend/src/components/AppBreadcrumb.vue` was already untracked before implementation; it now includes QA breadcrumb behavior and should be reviewed as a whole before staging.
- The worktree has unrelated dirty files under backend, API docs, other frontend pages/components, `.codex/`, `.codestable/`, and other Trellis tasks. Do not bulk stage the repository for this task.

Temporary acceptance data is not part of the commit:

- `/private/tmp/md2word_translation_qa_acceptance_var`
