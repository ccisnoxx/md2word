# Translation QA Visibility Hardening Design

## Scope

This task is the first Phase 3 implementation slice after the gap audit. It should make existing QA state visible where operators already triage jobs, and close documentation drift around the already-implemented Translation QA endpoints.

## Recommended Approach

1. Documentation first

   Update `docs/api/document-jobs.md` to document:

   - `GET /api/v1/document-jobs/{job_id}/translation-qa`
   - `PATCH /api/v1/document-jobs/{job_id}/translation-qa`
   - supported mode: `en2zh_pdf_to_word`
   - QA status enum and nullable legacy state
   - evidence sources and debug archive limitations
   - non-sensitive event/audit behavior

2. Archive status correction

   Add an explicit acceptance/closeout note to the archived `translation-result-qa` task or related roadmap acceptance material. The goal is to prevent future agents from reopening the already implemented basic QA slice.

3. Job detail visibility

   Use the fields already present on `DocumentJobResponse`:

   - `translation_qa_status`
   - `translation_qa_note`
   - `translation_qa_reviewed_by`
   - `translation_qa_reviewed_at`

   Show a compact QA summary near the existing `翻译 QA` action. For non-`en2zh_pdf_to_word` jobs, hide the summary or show a clear “not applicable” state only if the surrounding UI already uses that pattern.

4. Jobs list visibility and filtering

   Add a QA status column for PDF translation jobs. For reliable filtering across pagination, use an additive backend query parameter `translation_qa_status` rather than a front-end-only current-page filter.

   If backend filtering is added, update:

   - backend router/service list query handling
   - API schemas or query parsing if needed
   - `frontend/src/api/documentJobs.ts`
   - `frontend/src/api/types.ts`
   - `frontend/src/pages/JobsPage.vue`
   - relevant tests and OpenAPI export

## Key Constraints

- Do not alter PDF parsing, translation, AI calls, or Word generation.
- Do not change Translation QA persistence semantics unless needed for the list query.
- Do not expose raw prompt/output content in the Jobs list; keep deep evidence on the QA detail page.
- Preserve compatibility for legacy jobs where QA fields are null.

## Testing Plan

- Backend unit test for list filtering if `translation_qa_status` query is introduced.
- Existing Translation QA tests should continue to pass.
- OpenAPI export test if query/schema docs are updated.
- Frontend build after UI changes.
- Optional browser smoke for task detail/list QA state visibility if local app can be run without invoking main flows.

## Risks

- A front-end-only filter would be misleading with paginated jobs; avoid it unless explicitly labeled.
- Displaying notes in the list can leak too much context; keep notes on details page and use only status in list.
- Existing old jobs can have null QA fields; UI should not treat null as failed.
