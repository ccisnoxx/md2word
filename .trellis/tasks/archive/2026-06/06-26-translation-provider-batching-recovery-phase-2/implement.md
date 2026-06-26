# Translation Provider Batching And Recovery Phase 2 Implementation Plan

## Scope

Implement a read-only provider batch diagnostics view in Job Detail using the Phase 1 backend API. The MVP scope was confirmed on 2026-06-26; do not start implementation until the planning artifacts are reviewed and `task.py start` is approved.

## Checklist

1. Add frontend API contract.
   - Add `DocumentJobTranslationBatchSummaryResponse`.
   - Add `DocumentJobTranslationBatchListResponse`.
   - Keep field names aligned with `app/domains/document_jobs/schemas.py`.

2. Add API wrapper.
   - Add `documentJobsApi.listTranslationBatches(jobId)`.
   - Add a focused unit test proving the request uses `GET /api/v1/document-jobs/{jobId}/translation-batches`.

3. Add shared display helpers.
   - Create a helper module such as `frontend/src/utils/translationBatches.ts`.
   - Centralize status label, tag type, page range label, attempt label, AI log summary, error summary, and batch summary counts.
   - Add unit tests for failed, split/truncated, running, succeeded, empty page range, and missing AI log cases.

4. Integrate Job Detail data loading.
   - Add translation batch state, loading, and error refs.
   - Add `loadTranslationBatches`.
   - Include it in manual diagnostic refresh.
   - Include it in active-job smart polling only for translation-capable jobs.
   - Reset batch state when the job is not translation-capable or when the route job id changes.

5. Render the diagnostics section.
   - Add a “Provider 批次” section inside the existing “诊断” tab.
   - Show summary counts and generation.
   - Render table columns for status, page range, size, attempts, finish_reason, error summary, AI call log file IDs, and updated_at.
   - Add clear visual distinction for failed/split/truncation/retryable/running states.
   - Use overflow-safe styles for long IDs and error messages.

6. Preserve the redaction boundary.
   - Do not request AI log file content.
   - Do not display prompt/response/source/translated text.
   - Keep debug archive IDs out of MVP unless needed as a count-only secondary metadata field.

7. Update docs.
   - Add `translation-batches` endpoint documentation to `docs/api/document-jobs.md`.
   - Mention read-only behavior and sensitive content exclusion.

8. Review the diff before validation.
   - Check for duplicate status mapping logic.
   - Check no raw payload field parsing is duplicated in the page.
   - Check no write operation or retry/cancel UI slipped into the batch section.
   - Check no unrelated `.agents`, `.codex`, or `.trellis` churn is included.

## Validation

Targeted first:

```bash
cd frontend
npm run test:unit -- src/api/documentJobs.test.ts src/utils/translationBatches.test.ts
```

Then type/build:

```bash
cd frontend
npm run build
```

Repository hygiene:

```bash
git diff --check
```

If backend docs or OpenAPI expectations appear inconsistent during implementation, run the existing backend check that covers API export:

```bash
.venv/bin/python -m unittest tests.test_openapi_export
```

## Risk Points

- Frontend `types.ts` is currently behind OpenAPI for translation batch schemas; manual type additions must match backend optional/null fields.
- Job Detail is already a large component; keep new logic factored through helpers to avoid local duplicated status interpretation.
- Smart polling must not add excessive API pressure for active jobs.
- AI call log/debug archive identifiers are useful evidence, but content fetch/rendering is out of scope for the MVP.
