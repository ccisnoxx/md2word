# Translation QA Segment Trace Hardening Implementation Plan

## Status

Implemented with frontend-only grouping. No backend API shape changed.

## Completed Work

- Reviewed the design boundary and tightened wording to avoid implying a fake segment-to-call relationship.
- Kept implementation frontend-only because `term_traces.segment_id` supports segment-to-term grouping, but current `ai_calls` do not expose a defensible segment-to-call key.
- Updated `TranslationResultQaPage.vue` to use a segment-first table.
- Added per-segment evidence status and term trace counts.
- Added expandable segment trace detail with matching term traces.
- Kept AI calls visible as call-level metadata-only evidence instead of segment-level evidence.

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

## Verification

- [x] `npm --prefix frontend run build`
- [x] `git diff --check`

Notes:

- Build passed with existing Rollup pure annotation warnings from `@vueuse/core` and existing large chunk warning.
- Backend targeted tests and OpenAPI tests were not run because no backend contract changed.
