# Translation QA Segment Trace Hardening Implementation Plan

## Status

Planning only. Do not run `task.py start` or edit business code until the design boundary is reviewed.

## Proposed Steps

1. Inspect current trace data shape

   - Re-read `TranslationResultQaPage.vue`.
   - Re-read backend QA response construction in `DocumentJobService`.
   - Confirm whether `term_traces.segment_id` is enough for segment grouping.
   - Confirm whether any defensible AI call to segment key exists.

2. Decide frontend-only vs additive backend response

   - Prefer frontend-only grouping if it can produce honest evidence.
   - Add backend fields only when they reduce ambiguity without exposing sensitive content.

3. Implement segment-first UI

   - Add term trace count and source comparison status per segment.
   - Add expandable/selected segment trace area.
   - Group term hits by segment.
   - Keep AI calls as metadata-only global evidence unless a true segment relation exists.

4. Update contracts and docs if needed

   - If API changes, update schemas, OpenAPI, `docs/api/document-jobs.md`, and targeted tests.
   - If API does not change, document the frontend-only grouping decision in the task closeout.

5. Verify

   - Frontend build.
   - Backend QA tests and OpenAPI tests only if API changes.
   - `git diff --check`.

## Explicit Non-actions

- Do not run `pdf-mineru`.
- Do not call translation providers.
- Do not generate Word.
- Do not add browser smoke in this task.
- Do not modify list filtering, task-level QA status persistence, or proposal review flows.
