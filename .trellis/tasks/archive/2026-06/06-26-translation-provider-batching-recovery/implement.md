# Translation Provider Batching And Recovery Implementation Plan

## Scope

Implement Phase 1 backend async provider batch execution for DocumentIR translation jobs.

Phase 1 includes batch persistence, async batch tasks, concurrency control, failed-batch retry, fan-in merge, audit, events, and a minimal read-only JSON API for batch diagnostics. Frontend batch visualization and operations-console enhancements are explicitly deferred to a later delivery.

## Checklist

1. Add translation batch domain models and repository ports.
   - Define batch statuses, batch record fields, generation fencing, lease fields, and result/audit references.
   - Add file/sqlite/mysql persistence adapters and schema bootstrap.
   - Add focused repository tests for create/list/claim/update/finalize-safe reads.

2. Refactor DocumentIR translation planning.
   - Extract text targets with page context from `DocumentIRBlock.page_index` or `block.layout.page_index`.
   - Reuse Translation Profile/settings `max_pages_per_batch` and `max_chars_per_batch`.
   - Build deterministic initial batches by page window, then item/char hard limits.
   - Compute `deterministic_batch_count`, `max_provider_calls`, and dynamic translation timeout.

3. Persist source DocumentIR before translation fan-out.
   - Register untranslated source DocumentIR after MinerU conversion and image asset registration.
   - Track source vs translated DocumentIR artifact roles in metadata.
   - Ensure retry resumes from source DocumentIR and existing batch records where valid.

4. Extend provider result and error contracts.
   - Capture `finish_reason`, usage, response id, content length, parse diagnostics, and provider trace metadata.
   - Add explicit parse/truncation errors that audit can serialize without full prompt/response by default.
   - Preserve exact item id order validation.

5. Add async provider batch task queue.
   - Add `document_jobs.translate_batch` Celery task and queue adapter.
   - Add per-job concurrency scheduler with default limit 4.
   - Use a dedicated translation batch queue/worker configuration for global concurrency.
   - Make task claims and updates idempotent with job retry count and generation.

6. Implement batch execution and adaptive split.
   - Reconstruct provider requests from source DocumentIR and batch item ids.
   - On success, write batch result artifact and audit logs, then mark batch succeeded.
   - On suspected truncation or invalid JSON, split current batch when budget remains and enqueue child batches.
   - On exhausted budget or non-retryable error, mark only that batch failed.

7. Implement fan-in finalizer.
   - After each batch update, inspect current leaf batches for the job/generation.
   - Enqueue more pending work within per-job concurrency.
   - If any final leaf failed, mark job `translation_failed` with batch diagnostics.
   - If all leaf batches succeeded, merge results, register translated DocumentIR, and continue rendering/uploading.

8. Update audit/events/progress.
   - Emit batch-level events for queued/running/succeeded/split/failed summaries.
   - Save one AI call log per provider attempt and link logs to the batch record.
   - Keep debug archives controlled by `translation_debug_archive_enabled`.
   - Report progress from completed leaf batch count without exposing full text.

9. Add minimal read-only batch diagnostics API.
   - Add a job-scoped endpoint that returns provider batch summaries.
   - Include `status`, `page_range`, `item_count`, `attempt_count`, `finish_reason`, `error`, and `ai_call_log_file_ids`.
   - Do not expose source text, translated text, full prompt, or full response.
   - Add router/schema tests for authorization, empty state, success summaries, and failed batch diagnostics.

10. Update retry/cancel/recovery behavior.
   - Job retry should keep source DocumentIR and succeeded batch results when compatible with the same generation inputs, then requeue only failed/pending batches.
   - Cancel should prevent pending/running batch updates from advancing the job.
   - Recovery replay should detect active jobs with stuck/running batches and requeue expired leases.

11. Tests and validation.
    - Unit tests for planner: <=20 pages single batch, >20 page windows, dense page item/char splits.
    - Provider adapter tests for finish reason/usage capture and invalid JSON diagnostics.
    - Batch task tests for success, truncation split, stop+invalid JSON, timeout, stale generation, and idempotent duplicate task.
    - Document job integration tests for async fan-out/fan-in, only failed batch retry, cancellation, and translated IR merge.
    - API tests for minimal batch diagnostics response and redaction.
    - Run targeted `unittest` suites and `git diff --check`.

## Risk Points

- Introducing batch persistence touches file/sqlite/mysql adapters; schema and adapter behavior must stay aligned.
- Async fan-in must be idempotent to avoid double-registering translated DocumentIR or double-rendering.
- Provider concurrency can amplify external rate limits; default per-job concurrency is intentionally 4.
- Existing local draft code that only batches by item/char should be revised rather than treated as final.

## Phase 1 Validation Notes

2026-06-26 validation found and fixed two backend issues before handoff:

- Provider call budget now follows the accepted formula `min(200, deterministic_batch_count * 12)`.
- Running batch success/failure/split/cancel/lease-expiry writes now use generation/status compare-and-set so stale tasks cannot overwrite batches that already left `running`.

Validated targets:

- `.venv/bin/python -m unittest tests.test_document_ir_translation`
- `.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_worker_translates_ir_and_saves_ai_audit_artifacts tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files`
- `.venv/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend tests.test_database_job_repository.PersistenceAdapterTests.test_mysql_schema_bootstrap_includes_resource_versions`
- `.venv/bin/python -m unittest tests.test_openapi_export`
- `git diff --check`

Follow-up validation resolved the residual known failure by migrating the 3 stale legacy `/api/v1/jobs` persistence tests to current `/api/v1/document-jobs` flows and repository assertions. The legacy removal contract remains covered by `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_legacy_jobs_api_paths_are_removed`.

Additional validated target:

- `.venv/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests`
