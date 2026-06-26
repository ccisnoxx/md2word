# Translation Provider Batching And Recovery Phase 2 Design

## Architecture

Phase 2 is a read-only frontend diagnostics layer over the Phase 1 backend contract.

Data flow:

```text
DocumentJobDetail route
  -> documentJobsApi.get(jobId)
  -> documentJobsApi.listEvents(jobId)
  -> documentJobsApi.listFiles(jobId)
  -> documentJobsApi.getCallbackMessageSummary(jobId)
  -> documentJobsApi.listTranslationBatches(jobId)
  -> Job Detail diagnostics tab
```

The backend remains the owner of batch execution state, retryability, finish_reason, error metadata, and AI call log file IDs. The frontend owns only display formatting, grouping, bounded refresh, and redaction-preserving presentation.

## Contracts

Add these frontend types in `frontend/src/api/types.ts` from the current backend schema:

- `DocumentJobTranslationBatchSummaryResponse`
- `DocumentJobTranslationBatchListResponse`

Keep backend field names unchanged. Do not create a parallel frontend-only payload shape that reinterprets batch records.

Add `documentJobsApi.listTranslationBatches(jobId)` in `frontend/src/api/documentJobs.ts`.

The API response is trusted only as the typed backend contract. Rendering helpers should consume the typed response and avoid local `unknown` casts in `JobDetailPage.vue`.

## UI Placement

Use the existing Job Detail “诊断” tab as the MVP surface.

Recommended placement:

1. Keep current diagnostic summary and next-step recommendation at the top.
2. Add a new “Provider 批次” section before event preview or before Word quality evidence.
3. Show a compact summary strip followed by an `el-table`.

The table should be dense and operational:

- `状态`: tag + raw status fallback.
- `页范围`: `page_start-page_end`, single-page label, or `-`.
- `规模`: item_count and optional char_count.
- `尝试`: `attempt_count/max_attempts`.
- `finish_reason`: raw provider value, especially `length`.
- `错误`: `error_code` plus shortened `error_message`.
- `AI 调用日志`: count plus file IDs in mono text / tooltip.
- `更新时间`: formatted timestamp.

Optional secondary fields can be shown in compact metadata text: `split_level`, `parent_batch_id`, `root_batch_id`, `result_file_id`, `provider_call_budget`.

## Display Rules

Status style should make abnormal batches visible without requiring operators to read every column:

- `succeeded`: success.
- `failed`: danger.
- `split`: warning.
- `pending`, `queued`, `running`: info, with running/queued label retained.
- `canceled`: warning or info, depending on existing visual consistency.

Escalate row tone to warning when:

- `truncation_retry` is true.
- `finish_reason === "length"`.
- `retryable` is true and status is not succeeded.

The UI should not infer that a job is retryable from batch fields. Job-level retry remains owned by `job.available_actions.retry`.

## Loading And Refresh

Add independent state:

- `translationBatches`
- `translationBatchesLoading`
- `translationBatchesError`

`loadAll()` should refresh batches for translation-capable jobs. During active-job polling, reuse the existing `smart` secondary refresh cadence instead of adding an unconditional high-frequency request.

If the job is not translation-capable or the API returns no items, show an empty state. If the API fails, show `ApiErrorAlert` scoped to `document_jobs.translation_batches` and keep the rest of the page usable.

## Redaction Boundary

The UI may display:

- Batch IDs.
- File IDs.
- Error code and error message summaries.
- Provider finish_reason and response_id.
- Usage/token summary if already returned by the API.

The UI must not display or fetch:

- Full prompt.
- Full provider response.
- Source text.
- Translated text.
- Debug archive content.

Existing file download behavior remains owned by the document file APIs; this Phase 2 view should not add new content fetches or inline previews for AI logs/debug archives.

## Documentation

Update `docs/api/document-jobs.md` with a `GET /api/v1/document-jobs/{job_id}/translation-batches` section:

- Purpose: read-only provider batch diagnostics for a document job.
- Key fields: status, page range, item/char counts, attempts, split metadata, finish_reason, error summary, AI call log file IDs.
- Redaction: no prompt/response/source/translated text.
- Operations: no retry/cancel/write semantics in this endpoint.

## Trade-offs

Keeping MVP inside Job Detail avoids creating a second operational source of truth. Incident Triage and Operations Cockpit can later deep-link into the same detail section after the single-job experience proves useful.

Not adding batch-level actions keeps permissions and idempotency out of this phase. Phase 1 recovery already owns execution semantics; Phase 2 should first make that state visible.

## Rollback

Frontend rollback is local:

- Remove `listTranslationBatches` wrapper and types.
- Remove Job Detail batch state/rendering.
- Remove helper/tests/docs.

No database, backend worker, provider, or public write API rollback is expected in this phase.
