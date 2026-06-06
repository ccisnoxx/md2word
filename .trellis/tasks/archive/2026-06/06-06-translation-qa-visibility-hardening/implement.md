# Translation QA Visibility Hardening Implementation Plan

## Status

Implemented. Awaiting user review before optional `task.py finish` / archive.

## Completed Work

- Added backend `translation_qa_status` list filtering for `en2zh_pdf_to_word` jobs only.
- Added Jobs workbench QA status filter and QA status column.
- Added compact Translation QA summary to job detail.
- Updated `docs/api/document-jobs.md` and regenerated `docs/api/openapi.json`.
- Added archived `translation-result-qa` closeout note.
- Added backend list filtering coverage and kept existing Translation QA tests passing.

## Proposed Work Items

1. Update API documentation

   - Add Translation QA section to `docs/api/document-jobs.md`.
   - Align endpoint descriptions with `docs/api/openapi.json`.

2. Correct archive/acceptance record

   - Add a concise closeout note to the archived `translation-result-qa` task or parent roadmap acceptance.
   - State that first-slice endpoints/page/tests are complete and that Phase 3 continues with visibility hardening.

3. Implement job detail QA summary

   - Add compact display in `frontend/src/pages/JobDetailPage.vue`.
   - Reuse existing fields from `DocumentJobResponse`.
   - Keep direct jobs and unsupported modes non-misleading.

4. Implement Jobs workbench QA status

   - Add QA status display in `frontend/src/components/JobTable.vue`.
   - Add filter UI in `frontend/src/pages/JobsPage.vue`.
   - Prefer backend-supported filtering via task list query to avoid paginated current-page filtering.

5. Add verification

   - Backend list filtering tests if backend query support is added.
   - Existing Translation QA backend tests.
   - OpenAPI export test if API shape changes.
   - Frontend build.

## Suggested Verification Commands

- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k "document_job_list_supports_workbench_filters_without_running_worker"`
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k translation_qa`
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- [x] `npm --prefix frontend run build`

## Verification Notes

- Frontend build passed with existing Rollup pure annotation warnings from `@vueuse/core` and existing large chunk warning.
- No PDF parsing, translation provider call, or Word generation main flow was run.

## Out of Scope

- Segment/term/AI call trace correlation.
- Browser smoke coverage as a standalone hardening pass.
- Any real PDF parsing, translation provider call, or Word generation run.
