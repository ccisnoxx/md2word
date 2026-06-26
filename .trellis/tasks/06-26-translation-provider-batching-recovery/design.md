# Translation Provider Batching And Recovery Design

## Architecture

The translation stage becomes a fan-out/fan-in workflow:

1. The document job converts MinerU output into source `DocumentIR` and registers it before translation.
2. A deterministic batch planner creates initial provider batches from source `DocumentIR`, profile limits, term snapshot, provider config, and job retry generation.
3. Each provider batch is persisted and enqueued as an independent Celery task.
4. Batch tasks call the provider, validate returned item ids, write audit/result artifacts, and update batch state.
5. A finalizer runs after each batch completion. It advances the document job only when every current leaf batch has succeeded.
6. The finalizer applies all batch results to the source `DocumentIR`, registers the translated `DocumentIR`, and continues rendering/uploading.

The document job remains the user-facing unit of work. Provider batches are internal execution records.

Phase 1 is backend-only: persistence, async batch tasks, concurrency control, failed-batch retry, fan-in merge, audit, and events. Frontend batch visualization and operations-console enhancements are deferred to a later delivery.

## Data Model

Add a translation batch record store for file, sqlite, and mysql metadata backends.

Recommended record fields:

- `batch_id`: stable id derived from job id, generation, parent id, split level, and item range.
- `job_id`, `job_retry_count`, `generation`: fence stale task attempts and retries.
- `root_batch_id`, `parent_batch_id`: represent adaptive splits.
- `status`: `pending`, `queued`, `running`, `succeeded`, `failed`, `split`, `canceled`.
- `page_start`, `page_end`, `item_ids`, `item_count`, `char_count`.
- `split_level`, `attempt_count`, `max_attempts`.
- `lease_owner`, `leased_at`, `lease_expires_at`.
- `result_file_id`, `ai_call_log_file_ids`, `debug_archive_file_ids`.
- `finish_reason`, `usage`, `error_code`, `error_message`.
- `created_at`, `updated_at`.

Batch records store item ids and summary metadata, not full source text. A batch task reconstructs request text from the persisted source `DocumentIR` and the batch item ids.

## Artifacts

Persist two distinct IR artifacts for translation jobs:

- Source DocumentIR: untranslated structure produced from MinerU plus registered image asset refs.
- Translated DocumentIR: source DocumentIR plus translated text replacements after all leaf batches succeed.

Batch result artifacts contain `batch_id`, ordered item translations, provider metadata, and response hash. Full prompt/response remains behind `translation_debug_archive_enabled`.

## Queue Flow

Document job worker responsibilities:

- Convert MinerU result to source `DocumentIR`.
- Register image assets and source `DocumentIR`.
- Build or reuse the deterministic translation batch plan.
- Enqueue runnable pending provider batches up to the configured concurrency limit.
- Leave the job in `running/ir_converting` while batch tasks execute.

Provider batch task responsibilities:

- Claim a batch with compare-and-set from `queued` or retryable `failed` to `running`.
- Reconstruct the provider request from source `DocumentIR`.
- Call provider with batch-level timeout.
- On success, validate exact id order and mark the batch `succeeded`.
- On suspected truncation, split the current batch into child batches if budget remains, mark parent `split`, and enqueue child batches.
- On non-retryable or budget-exhausted failure, mark the batch `failed` with metadata.
- Invoke finalization after state update.

Finalizer responsibilities:

- Ignore stale generations and terminal/canceled jobs.
- If any current leaf batch is running or queued, enqueue more pending work within concurrency limits and return.
- If any current leaf batch is failed and retry budget remains, enqueue only those failed batches.
- If any current leaf batch is terminal failed with no retry budget, fail the document job as `translation_failed`.
- If every current leaf batch succeeded, merge results in deterministic document order, register translated `DocumentIR`, and continue rendering.

## Budgets And Timeouts

Provider call budget:

```text
max_provider_calls = min(200, deterministic_batch_count * 12)
```

Overall translation/job timeout is dynamic:

```text
translation_timeout_seconds =
  max(
    p0_document_job_timeout_seconds,
    max_provider_calls * provider_timeout_seconds + 1800
  )
```

Batch timeout is separate from job timeout and applies only to the current provider batch attempt. A batch timeout marks that batch retryable; it does not invalidate successful batches.

Celery hard limits must be configured so provider batch tasks and the fan-in finalizer can outlive the default 1200 second document job timeout when the dynamic translation timeout is larger.

## Concurrency

Async provider batches need bounded concurrency to avoid provider rate limits and worker starvation.

Recommended default:

- Per job: at most 4 active provider batches.
- Deployment/global: controlled by a dedicated Celery queue/worker concurrency.

The batch scheduler should enqueue only up to the per-job active limit. This avoids dumping all batches at once and allows failed/split child batches to be prioritized without requeueing succeeded work.

This is an accepted product default, not only an implementation suggestion.

## Idempotency

- Every task carries `job_id`, `batch_id`, `job_retry_count`, and `generation`.
- Stale tasks exit without mutation.
- Batch state updates use compare-and-set expected status/generation.
- Finalizer is idempotent and guarded by job stage/status plus generation.
- Translated `DocumentIR` registration happens once after all current leaf batches are succeeded.

## Failure Semantics

- `finish_reason=length` or incomplete JSON shape is treated as suspected truncation and triggers split retry when budget remains.
- `finish_reason=stop` with invalid JSON is not accepted as success; it is retried/split according to policy and then failed explicitly if still invalid.
- The user-facing job can remain `translation_failed`, but batch/audit metadata must identify the exact failed batch, page range, item count, char count, finish reason, and parser error.

## Phase Boundary

Phase 1 should expose enough backend evidence for diagnosis through events, audit artifacts, metadata, and a minimal read API. It should not build the final UI for batch inspection.

## Minimal Read API

Add a backend-only JSON endpoint for job-scoped provider batch diagnostics.

Recommended response fields per batch:

- `batch_id`
- `status`
- `page_range`
- `item_count`
- `char_count`
- `attempt_count`
- `split_level`
- `parent_batch_id`
- `finish_reason`
- `error`
- `ai_call_log_file_ids`
- `debug_archive_file_ids`
- `updated_at`

The endpoint must not return full prompt text, response text, source item text, or translated item text. It is intended for operations diagnostics and future frontend reuse.
