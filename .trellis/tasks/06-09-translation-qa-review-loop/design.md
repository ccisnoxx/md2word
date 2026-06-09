# Translation QA Review Loop Design

## Decision

Add a first-class `/translation-qa` frontend queue for reviewers, backed by the existing `GET /api/v1/document-jobs` list contract. Keep `/jobs/:jobId/translation-qa` as the single-task evidence review page. Do not add a translation QA summary API, a separate translation result page, inline translation editing, or human-edited Word regeneration in this task.

This task is frontend-led. Backend work is limited to regression coverage or small contract fixes if implementation proves the current fields are insufficient.

## Existing Evidence

- `frontend/src/router/index.ts` already routes `/jobs/:jobId/translation-qa` to `TranslationResultQaPage.vue`; `/translation-qa` does not exist yet.
- `frontend/src/api/documentJobs.ts` already exposes `documentJobsApi.list()` with `translation_qa_status`, `status`, `q`, `sort`, `include_archived`, and created date filters.
- `frontend/src/api/types.ts` already defines `DocumentJobResponse.translation_qa_*`, `TranslationQaStatus`, `TranslationQaIssueType`, and `DocumentJobTranslationQaResponse`.
- `app/domains/document_jobs/router.py` already exposes:
  - `GET /api/v1/document-jobs`
  - `GET /api/v1/document-jobs/{job_id}/translation-qa`
  - `PATCH /api/v1/document-jobs/{job_id}/translation-qa`
- `app/domains/document_jobs/service.py` already filters list results by `translation_qa_status` and only matches `en2zh_pdf_to_word` jobs when that filter is present.
- `DocumentJobService.get_translation_qa()` only reads existing artifact files; it does not enqueue parsing, translation, or Word generation.
- `frontend/src/pages/TermProposalsPage.vue` already supports deep links to `tab=translation-new` with `source_job_id`, `source_file_id`, `observed_translation_term_set_id`, and `observed_translation_term_version`.
- Existing backend tests cover translation QA list filtering and single-job QA read/update in `tests/test_fastapi_jobs_backend.py`.

## Scope

In scope:

- Add `/translation-qa` route and page.
- Add a main navigation entry for the QA queue.
- Use `documentJobsApi.list()` for the queue; no new backend endpoint by default.
- Let reviewers filter queue items by QA status, document job status, search keyword, archive inclusion, and sort order.
- Default the queue to unreviewed translation QA jobs, newest updated first.
- Link each queue row to `/jobs/:jobId/translation-qa`.
- Preserve access to the normal job detail page from the queue.
- Keep single-job QA evidence page as the review surface for status, issue type, note, segment evidence, term trace, and AI call metadata.
- Add or improve single-job QA page affordances for returning to the QA queue and opening a translation term proposal with job/version context.

Out of scope:

- No `/api/v1/translation-qa/summary` or equivalent queue API.
- No independent translation result page.
- No online editing of translated text.
- No regenerating Word from human-edited translation.
- No PDF-MinerU parsing, translation provider calls, worker execution, clone/rerun execution, or Word generation during planning or validation.
- No new RBAC model. The queue follows current authenticated-user visibility: admin sees company-visible jobs, operator sees own jobs.

## Route And Navigation

Add route:

- path: `/translation-qa`
- name: `translation-qa`
- component: `TranslationQaQueuePage.vue`
- auth: same authenticated layout as `/jobs`; no admin-only meta.

Navigation:

- `AppLayout.vue` adds a top-level QA item, for example `翻译 QA`, visible to authenticated users.
- `AppBreadcrumb.vue` adds:
  - `translation-qa`: `翻译 QA`
  - `job-translation-qa`: if `route.query.from === "translation-qa"`, prefer `翻译 QA -> {jobId}`; otherwise keep `任务工作台 -> 任务详情 -> 翻译 QA`.

The queue should pass query context when opening a task QA page:

- `from=translation-qa`
- current queue filters when useful: `translation_qa_status`, `status`, `sort`, `include_archived`, `q`

The single-job QA page can use those query values to build a stable "返回 QA 队列" link without relying on browser history.

## Queue Page Design

Create `frontend/src/pages/TranslationQaQueuePage.vue`.

The page should feel like a focused review queue, not a duplicate upload workbench:

- No upload panel.
- No batch retry, batch cancel, or batch archive controls.
- No broad task operation toolbar.
- Primary action per row: `复核`, routed to `job-translation-qa`.
- Secondary action per row: `任务详情`, routed to `job-detail`.
- Optional result download may be shown only if it reuses existing `available_actions.download`; it must not redefine download availability.

Default query:

- `translation_qa_status=unreviewed`
- `sort=updated_at_desc`
- `include_archived=false`
- `page=1`, `page_size=20`

Filters:

- QA status: `unreviewed`, `approved`, `needs_fix`, `blocked`, or all.
- Job status: all, `succeeded`, `failed`, plus existing statuses if the UI keeps a full select.
- Search keyword: pass as `q`.
- Sort: existing `DocumentJobListSort`, with updated-time options first.
- Include archived: pass as `include_archived`.
- Created range may be reused from `/jobs` only if implementation stays simple; do not add an updated-range API in this task.

Data source:

```text
GET /api/v1/document-jobs
  page
  page_size
  translation_qa_status
  status
  q
  sort
  include_archived
  created_from?
  created_to?
```

Important limitation:

- `DocumentJobListResponse.summary` is status summary for visible jobs, not QA status summary. The queue must not present it as QA status totals.
- Any queue metrics should be clearly scoped to the current filtered result or current page unless a future backend summary API is added.

Table columns:

- Job ID and source filename.
- Job status / stage.
- QA status.
- Issue type.
- Reviewed by / reviewed at.
- Updated at.
- Evidence hints from `DocumentJobResponse`: `document_ir_file_id`, `result_file_id`, `debug_full_text_enabled`, `error_code`.
- Actions: `复核`, `任务详情`.

Empty states:

- No matching QA tasks: show filter-aware empty text.
- Invalid query values: normalize client-side and avoid passing invalid enum values to the backend, following `JobsPage.vue`.
- API errors: use `ApiErrorAlert`.

## Single-Task QA Page Integration

Keep `TranslationResultQaPage.vue` as the evidence page. It should continue to:

- Load `documentJobsApi.get(jobId)` and `documentJobsApi.getTranslationQa(jobId)`.
- Save review state through `documentJobsApi.updateTranslationQa()`.
- Show only metadata summaries for AI calls and not full prompt/response bodies.
- Show unavailable states for unsupported mode, missing DocumentIR, unreadable DocumentIR, and debug archive limitations.

Add page links/actions:

- `返回 QA 队列` when opened from `/translation-qa`.
- `任务详情` link for the current job.
- `提交翻译术语建议` link to `term-proposals` with:
  - `tab=translation-new`
  - `source_job_id`
  - `source_file_id`
  - `observed_translation_term_set_id`
  - `observed_translation_term_version`

Observed translation term set/version resolution order:

1. `job.request_snapshot.resources.translation_term_set.set_id/version`
2. `job.request_snapshot.term_assets.translation_term_set_id/translation_term_version`
3. `job.term_version_id` as a version fallback only when no version is present

Do not claim that the proposal form is prefilled with a specific source/target term. The existing proposal page only accepts context query parameters for source job/file and observed version. Per-term prefill would be a later contract change.

Problem feedback:

- Continue using QA `status`, `issue_type`, and `note` as the general issue feedback record.
- For terminology issues, the proposal deep link sends the issue into the existing translation term proposal workflow.
- Non-terminology issues remain review notes for this task; do not create a new issue tracker or problem API.

## API Contract

No new API contract is planned.

Existing contracts to reuse:

- `GET /api/v1/document-jobs`
- `GET /api/v1/document-jobs/{job_id}/translation-qa`
- `PATCH /api/v1/document-jobs/{job_id}/translation-qa`
- `POST /api/v1/translation-term-proposals` indirectly through the existing proposal page

Do not add a QA summary API unless implementation proves one of these blockers:

- The list response lacks fields required to render the queue.
- Current filtering cannot represent the reviewer workflow without misleading UI.
- Performance becomes unacceptable with realistic data size.
- Product needs true QA status counts across the full result set, not current-page approximations.

If a blocker appears, stop and record a follow-up backend contract task rather than silently adding an endpoint in this child task.

## Privacy And Security

- Do not expose raw prompt or raw response text in the queue.
- Keep single-job QA page at metadata-only AI call summaries, matching current implementation.
- Rely on existing document job visibility checks; do not bypass with frontend-only filtering.
- Do not weaken job action availability. If actions are displayed, use `available_actions` through existing helpers.
- Do not log or persist QA note content into event payloads beyond existing `note_length` behavior.

## Compatibility

- Existing `/jobs/:jobId/translation-qa` direct links continue to work.
- Existing `/jobs` QA filter remains valid.
- Existing `TermProposalsPage.vue` deep link contract remains unchanged.
- Backend OpenAPI should not change unless an implementation blocker forces a separate approved contract change.

## Acceptance Plan

Functional acceptance:

- Reviewer can open `/translation-qa` and see only translation QA-relevant jobs when a QA status filter is selected.
- Reviewer can filter unreviewed, approved, needs-fix, and blocked tasks.
- Reviewer can open a row into `/jobs/:jobId/translation-qa`.
- Single-job QA page can save status, issue type, and note through the existing PATCH endpoint.
- Single-job QA page can return to the QA queue with route context.
- Terminology issue feedback can jump to `term-proposals?tab=translation-new` with job/file/version context.

Negative acceptance:

- No new translation QA summary API is added.
- No independent translation result page is added.
- No online translation editing UI is added.
- No human-edited translation regeneration path is added.
- No PDF-MinerU parsing, translation, worker execution, clone/rerun execution, or Word generation is run as part of this task.
