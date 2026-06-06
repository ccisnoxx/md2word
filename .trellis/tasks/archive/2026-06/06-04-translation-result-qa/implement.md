# Translation result QA implementation plan

## Gate

Stay in planning until the user reviews this scope. Do not run `task.py start` or edit business code before approval.

## Closeout Status

2026-06-06 收口复核：本任务描述的第一版 Translation Result QA 已实现并通过 targeted verification。当前代码已有 `GET/PATCH /api/v1/document-jobs/{job_id}/translation-qa`、任务级 QA 字段、QA 详情页、任务详情入口、OpenAPI schema 和后端 targeted tests。Phase 3 后续不应重复实现基础 QA 页面/API，应转入 `translation-qa-visibility-hardening`、段落 trace 关联和浏览器 smoke 加固。

## Step 1: Backend contracts and service

- Add QA status literals and fields to `app/domains/document_jobs/models.py`.
- Add request/response schemas in `app/domains/document_jobs/schemas.py`.
- Add service methods in `app/domains/document_jobs/service.py`:
  - `get_translation_qa(job_id, user, limit)`
  - `update_translation_qa(job_id, user, status, issue_type, note, trace_id)`
- Inject the existing `FileUploadService` into `DocumentJobService` from `app/main.py` and test runtime builders.
- Parse artifacts through existing `file_repository` and `FileUploadService.read_file_content`.
- Append a `translation_qa_updated` event.

Verification:

- Targeted backend tests for unavailable direct jobs, available en2zh evidence, and QA update persistence/event.

## Step 2: Backend router wiring

- Add `GET /document-jobs/{job_id}/translation-qa`.
- Add `PATCH /document-jobs/{job_id}/translation-qa`.
- Keep routers thin and response mapping schema-based.

Verification:

- `tests.test_fastapi_jobs_backend` targeted unittest.
- If OpenAPI changes, run `scripts/ops/export_openapi.py` and check release/openapi diff as needed.

## Step 3: Frontend page and API wrapper

- Add TypeScript contracts in `frontend/src/api/types.ts`.
- Add `getTranslationQa` / `updateTranslationQa` in `frontend/src/api/documentJobs.ts`.
- Add `TranslationResultQaPage.vue` using existing Element Plus style and `ApiErrorAlert`.
- Add route `/jobs/:jobId/translation-qa`.
- Add `JobDetailPage` entry button for `en2zh_pdf_to_word`.

Verification:

- `npm run type-check` or `npm run build` under `frontend/`, depending on available scripts.

## Step 4: Final checks

- Confirm no code path enqueues or reruns document jobs.
- Confirm no file delete behavior was added.
- Confirm no new term rule CRUD surface was added.
- Confirm QA event payload does not include full source, final text, prompt, response, or secrets.

Rollback:

- Revert the new route/page/API wrapper and additive backend QA fields/endpoints.
- Existing jobs are backward-compatible because new fields have defaults.
