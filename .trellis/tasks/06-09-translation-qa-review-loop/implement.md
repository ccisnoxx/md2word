# Translation QA Review Loop Implementation Plan

## Classification

Frontend-led feature implementation completed after user confirmation. Backend contracts were preserved; no document conversion main flow was executed.

## Preconditions

- User approved `design.md` and this `implement.md`.
- Trellis task was started after approval.
- Current dirty worktree is reviewed before editing; unrelated existing changes are not reverted.
- No PDF-MinerU parsing, translation provider call, worker execution, clone/rerun execution, or Word generation is run.

## Checklist

### 1. Route And Navigation

- [x] Add `TranslationQaQueuePage.vue`.
- [x] Register `/translation-qa` in `frontend/src/router/index.ts`.
- [x] Add `翻译 QA` navigation item in `frontend/src/layouts/AppLayout.vue`.
- [x] Add breadcrumb support in `frontend/src/components/AppBreadcrumb.vue`.
- [x] Preserve the existing `/jobs/:jobId/translation-qa` route.

### 2. Queue Page

- [x] Implement page state for `page`, `pageSize`, `translation_qa_status`, `status`, `q`, `sort`, and `include_archived`.
- [x] Normalize route query values before calling `documentJobsApi.list()`.
- [x] Default to `translation_qa_status=unreviewed` and `sort=updated_at_desc`.
- [x] Render a QA-focused table using `DocumentJobResponse`.
- [x] Route primary row action to `{ name: "job-translation-qa", params: { jobId }, query: queueReturnQuery }`.
- [x] Route secondary row action to `{ name: "job-detail", params: { jobId } }`.
- [x] Use `translationQaStatusText`, `translationQaStatusTagType`, `jobStatusText`, `formatDateTime`, and `getJobSourceFilename` instead of duplicating display logic where practical.
- [x] Use `ApiErrorAlert` for API failures.
- [x] Do not add upload, batch retry, batch cancel, batch archive, or independent task-operation semantics to this page.

### 3. Single-Task QA Page

- [x] Add a `返回 QA 队列` link when `route.query.from === "translation-qa"`.
- [x] Add a `任务详情` link for the current job.
- [x] Add `提交翻译术语建议` action that deep-links to `term-proposals` with existing query fields.
- [x] Resolve observed translation term set/version from `request_snapshot.resources.translation_term_set`, then `request_snapshot.term_assets`, then `term_version_id` as version fallback.
- [x] Keep existing QA save behavior through `PATCH /document-jobs/{job_id}/translation-qa`.
- [x] Keep AI call display metadata-only.
- [x] Do not add per-term URL prefill unless separately approved.

### 4. Tests And Verification

- [x] Add or update frontend tests only if a local frontend test pattern exists; otherwise rely on typecheck/build.
- [x] Run frontend build:
  - `cd frontend`
  - `npm run build`
- [x] Run targeted backend tests that prove reused contracts still hold:
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_list_supports_workbench_filters_without_running_worker`
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_reads_existing_artifacts_and_updates_review_state tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review`
- [x] If frontend changes require browser verification, start only the Vite dev server and inspect `/translation-qa`; do not start workers or conversion flows.
- [x] Confirm no new `/translation-qa/summary` route or API wrapper was added.
- [x] Confirm no independent translation result route was added.
- [x] Confirm no UI allows editing translated text or regenerating Word from edited text.

## Rollback Points

- If queue data fields are insufficient, stop before backend changes and record the exact missing field in this task or a follow-up backend contract task.
- If true QA status totals are required, stop and propose a summary API in a separate design update.
- If route/breadcrumb changes conflict with broader navigation work, keep `/translation-qa` route but defer global breadcrumb refinements to the navigation child task.
- If build fails due unrelated dirty worktree changes, report the conflict and do not revert user changes.

## Review Gate Before Implementation

Implementation began only after the user confirmed:

- `/translation-qa` queue should be a dedicated page, not just a saved `/jobs` view.
- Queue should reuse `GET /api/v1/document-jobs` for the first release.
- Single-job evidence page remains `/jobs/:jobId/translation-qa`.
- Proposal integration should use the existing `term-proposals?tab=translation-new` deep link.
- No translation editing or Word regeneration belongs in this child task.
