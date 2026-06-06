# Translation QA Segment Trace Hardening Design

## Scope

This Phase 3 slice should make the existing QA evidence easier to inspect by correlating final text segments with term hits and AI call metadata. It should stay inside the existing Translation QA detail experience.

## Current Evidence Model

Existing `GET /api/v1/document-jobs/{job_id}/translation-qa` returns:

- `segments`: final text segments derived from `document_ir`; optional `source_text` and `ai_translation_text` are only present when debug archive evidence is available.
- `term_traces`: glossary / term hit metadata from `ai_call_log`, including `segment_id`, source/target terms, term set/version, match offsets, provider trace ID, and context summary.
- `ai_calls`: metadata-only AI call summaries from `ai_call_log`, including file ID, call ID, provider summary, language pair, item/char counts, duration, status, and error summary.

The current page renders these as separate tables. That is sufficient for availability proof, but weak for QA triage because the user has to mentally join `segment_id`, term rows, and AI calls.

## Target UX

- Segment-first inspection:
  - Main table stays centered on final text segments.
  - Each segment row shows term hit count, source comparison availability, and a short trace affordance.
  - Expanding or selecting a segment reveals matching term traces and related AI call summary.

- Evidence state clarity:
  - `source_text` and `ai_translation_text` missing because of debug archive state should show reason-level copy such as `debug archive missing` / `expired` / `unreadable` / `no text`.
  - Missing term traces should be distinct from missing source comparison.
  - AI call errors should remain metadata-only and not imply full provider transcript availability.

- Trace grouping:
  - Term traces should group by `segment_id`.
  - AI call summaries should be linked conservatively. If the existing response cannot prove a segment-to-call mapping, the UI should say “call-level only” rather than inventing a relation.

## Backend Options

### Option A: Frontend-only grouping

Use existing response fields:

- group `term_traces` by `segment_id`
- compute `term_trace_count` per segment
- show `ai_calls` as global call evidence

Pros: smallest change, no API migration.

Cons: cannot accurately link a segment to an AI call unless existing logs provide a stable key.

### Option B: Additive backend trace summary

Add optional fields to the QA response, for example:

- segment-level `term_trace_count`
- segment-level `term_traces`
- optional `ai_call_refs` only if there is a defensible source in logs
- normalized `source_comparison_reason` at segment/detail level

Pros: cleaner frontend and future-proofed evidence contract.

Cons: requires OpenAPI update and backend tests.

Recommended first implementation: start with Option A unless code review confirms a stable segment-to-call key already exists. Only add Option B fields when the existing response makes the frontend join too fragile.

## Security And Privacy Constraints

- Do not expose raw prompt, raw response, source full text, complete debug archive payload, credentials, headers, API keys, provider secrets, or token values.
- Keep `ai_call_log` semantics as metadata-only.
- Do not store new per-segment QA decisions in this slice.
- Do not trigger new parsing, translation, or Word generation.

## Likely Files

- `frontend/src/pages/TranslationResultQaPage.vue`
- `frontend/src/api/types.ts` only if additive fields are introduced
- `app/domains/document_jobs/schemas.py` only if additive fields are introduced
- `app/domains/document_jobs/service.py` only if additive fields are introduced
- `tests/test_fastapi_jobs_backend.py` only if backend response shape changes
- `docs/api/document-jobs.md` and `docs/api/openapi.json` only if API shape changes

## Verification Plan

- If frontend-only: run `npm --prefix frontend run build`.
- If backend response changes: run targeted `translation_qa` backend tests and `tests.test_openapi_export`.
- Always run `git diff --check`.
- Do not run PDF parsing, translation provider calls, or Word generation.

## Deferred Work

- Browser smoke for QA page interactions.
- Jobs list/filter changes.
- Segment-level persisted annotations.
- Automated quality scoring.
