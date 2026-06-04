# Job context proposals implementation plan

## Preconditions

- Stay inside Phase 1 `job-context-proposals` scope.
- Do not run pdf-mineru parsing, translation, or Word generation.
- Do not modify proposal backend contracts unless implementation discovers a hard blocker.
- Do not start implementation until this plan is reviewed.

## Checklist

1. [x] Job detail proposal entry
   - Add a focused proposal section to `frontend/src/pages/JobDetailPage.vue`.
   - Build term-rule and translation-term query payloads from current job context.
   - Only show translation proposal entry for `en2zh_pdf_to_word`.
   - Verify no lifecycle action semantics change.

2. [x] Term Rule Proposal context form
   - Extend `TermProposalsPage` form state with `source_file_id`, observed term rule set id/version, optional page/context fields.
   - Read `tab=new` query params and prefill those fields.
   - Add a read-only context summary block when opened from a job.
   - Include context fields in `termProposalsApi.create` payload.

3. [x] Translation Term Proposal create form
   - Add `translation-new` tab in `TermProposalsPage`.
   - Add a one-change form for add/update/delete.
   - Validate add requires source + target; update/delete require source.
   - Read `tab=translation-new` query params and prefill context.
   - Submit through `translationTermProposalsApi.create`.

4. [x] Review source job回链
   - Add source job columns/links to `TermProposalTable` and `TranslationTermProposalTable`.
   - Add source job links in Term Rule and Translation Term review detail panels.
   - Keep empty display as `-` when proposals have no source job.

5. [x] Verification
   - Run `cd frontend && npm run build`.
   - If build passes and dev server is practical, smoke-check the relevant pages in the browser without triggering job processing.
   - Do not run full backend/release checks unless a backend/API contract change is introduced.

## Review Gate Before Start

Implementation can start after confirming:

- Scope is limited to the four frontend files listed in `design.md` unless a type-only adjustment is required.
- API contract remains unchanged.
- Acceptance criteria in `prd.md` are the verification target.

## Implementation Summary

- Updated `frontend/src/pages/JobDetailPage.vue` to expose task-context proposal entries and carry source job/file plus observed term set versions through route query parameters.
- Updated `frontend/src/pages/TermProposalsPage.vue` to prefill context for Term Rule proposals and add a lightweight Translation Term Proposal create tab using existing backend fields.
- Updated `frontend/src/components/TermProposalTable.vue` and `frontend/src/components/TranslationTermProposalTable.vue` to show source job back-links.
- No backend API contract or job processing behavior was changed.

## Verification Results

- `cd frontend && npm run build` passed.
- Browser smoke test passed on `http://127.0.0.1:3000/term-proposals?tab=translation-new&source_job_id=job_demo&source_file_id=file_demo&observed_translation_term_set_id=translation-terms-en2zh&observed_translation_term_version=v1` with mocked `/api/v1/auth/me`; the page rendered the `translation-new` form, locked/prefilled `job_demo`, and displayed `file_demo`, `translation-terms-en2zh`, `v1`, plus a `/jobs/job_demo` source link.
- Browser console after the smoke test had 0 errors. The remaining warnings were existing Element Plus radio `label`-as-value deprecation warnings from the pre-existing Term Rule Proposal form, not from the new Translation Term Proposal form.
- Did not run pdf-mineru parsing, translation, or Word generation.
- Did not run backend/release checks because this subtask did not change backend code or API contracts.

## Spec Update

- No `.trellis/spec` update is needed. This subtask adds a narrow frontend flow over existing proposal APIs and existing Vue/Element Plus page patterns; it does not introduce a new stable cross-project convention, backend contract, persistence rule, or workflow invariant.
