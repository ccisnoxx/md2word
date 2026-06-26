# Translation Provider Batching And Recovery Phase 3 Design

## Architecture

Phase 3 is an operational validation layer over Phase 1 backend recovery and Phase 2 read-only diagnostics.

It has three deliverables:

1. A release/staging validation report that records provider batch diagnostics for long PDF en2zh jobs.
2. A backend runbook section that teaches operators how to interpret Job Detail provider batch diagnostics.
3. A lightweight operations-entry evaluation that decides whether existing Incident Triage / Operations Cockpit deep links are enough, or whether a later aggregation surface is warranted.

The provider batch execution core remains owned by Phase 1. Job Detail batch visualization remains owned by Phase 2. Phase 3 should not create a second execution path or a second UI source of truth.

## Validation Report Flow

Use the existing `scripts/ops/run_p1_translation_regression.py` flow as the primary reporting hook because it already:

- authenticates against the runtime,
- uploads P1 en2zh PDF samples,
- creates document jobs,
- waits for terminal job state,
- reads translation QA evidence,
- downloads generated DOCX when requested,
- writes `report.json` and `report.md`.

Phase 3 extends that flow to collect batch diagnostics:

```text
P1 sample job terminal
  -> GET /api/v1/document-jobs/{job_id}/translation-batches
  -> sanitize + summarize batch records
  -> attach batch diagnostics to P1SampleResult
  -> render report.json and report.md evidence
```

The diagnostics request should run for translation jobs whether the job succeeds or fails. Failed jobs are the cases where batch-level status is most useful.

## Batch Diagnostics Contract

The report may store these fields:

- job-level: `job_id`, terminal status, failed stage, error code/message, elapsed seconds.
- list-level: `generation`, batch count, status counts, attention counts.
- batch-level: `batch_id`, `status`, `page_start`, `page_end`, `item_count`, `char_count`, `attempt_count`, `max_attempts`, `split_level`, `parent_batch_id`, `root_batch_id`, `finish_reason`, `retryable`, `truncation_retry`, `provider_call_budget`, `error_code`, shortened `error_message`, `result_file_id`, AI call log file id count.

The report must not fetch or store:

- full prompt,
- provider response body,
- source text,
- translated text,
- debug archive content,
- PDF contents,
- object storage locations,
- signed URLs,
- secret values.

When long private samples are used through `P1_TRANSLATION_MANIFEST`, the report should identify them by manifest sample id, filename, page count if available, and environment. It must not commit the PDF.

## Runbook Content

Add a provider batch diagnostics section to `docs/runbooks/backend.md`.

The runbook should explain:

- where to open the diagnostics: `/jobs/:jobId` -> “诊断” -> “Provider 批次”;
- how to identify normal success: all current leaf batches `succeeded`, job `succeeded`, result file present;
- how to identify truncation recovery: parent `split`, `finish_reason=length` or `truncation_retry=true`, child batches later `succeeded`;
- how to identify exhausted retry: `failed`, `retryable=false`, `attempt_count=max_attempts`, error summary present;
- how to identify active/stuck work: `queued`/`running` with old `updated_at` or expired lease symptoms, job still in `ir_converting`;
- how to identify fan-in risk: every leaf batch succeeded but job did not advance to render/result;
- how to use AI call log file ids as correlation handles without reading full prompt/response from this view;
- what actions are allowed now: task-level retry/cancel/archive/clone according to `available_actions`;
- what actions are not available now: batch-level retry/cancel/requeue/finalizer writes.

## Operations Entry Evaluation

Create a short planning artifact under the task directory, for example `operations-entry-evaluation.md`.

The evaluation should inspect existing entry points:

- Incident Triage already groups failed/stalled translation jobs and links to Job Detail.
- Operations Cockpit already previews incidents, QA work, and failed/active jobs.
- Job Detail already owns single-job provider batch diagnostics.

The expected MVP conclusion is likely: keep Job Detail as the authoritative diagnostics surface and use existing deep links for now. A future aggregation should be triggered only if validation finds operators need cross-job batch health, such as many jobs stuck in provider batches, repeated `finish_reason=length`, or fan-in stalls across jobs.

## Batch-Level Write Operation Design Boundary

If validation or runbook review exposes a need for batch-level writes, Phase 3 may document a future design only.

That design must cover:

- permissions and roles,
- exact endpoint shape,
- target identity and generation fencing,
- idempotency key / duplicate submission behavior,
- audit event shape,
- queue mutation semantics,
- stale task and finalizer safety,
- confirmation and dry-run/preview behavior,
- rollback and kill-switch behavior,
- redaction boundaries.

No endpoint, button, queue mutation, metadata mutation, or provider call should be implemented in Phase 3 for these actions.

## Acceptance Evidence

The validation report should be suitable for manual Acceptance Center registration:

- report path,
- environment,
- source/deployment id,
- summary,
- blockers,
- warnings.

If the real long PDF does not trigger truncation, the report should say so directly and cite existing automated truncation/split coverage as complementary evidence. That is acceptable for Phase 3 as long as the long PDF succeeds and batch diagnostics prove the request was bounded.

## Rollback

Rollback is documentation/reporting only unless the P1 script is extended:

- Remove added report fields from `scripts/ops/run_p1_translation_regression.py`.
- Remove or revert the runbook provider batch diagnostics section.
- Remove task-local evaluation artifacts.

No database, provider protocol, worker, backend execution service, or frontend Job Detail rollback is expected.
