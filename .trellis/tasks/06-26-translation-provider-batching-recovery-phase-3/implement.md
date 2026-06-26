# Translation Provider Batching And Recovery Phase 3 Implementation Plan

## Scope

Implement the confirmed Phase 3 MVP: batch-aware production/staging validation reporting, provider batch operations runbook, and a lightweight operations-entry evaluation. Do not start implementation until the planning artifacts are reviewed and `task.py start` is approved.

## Checklist

1. Extend validation reporting.
   - Prefer extending `scripts/ops/run_p1_translation_regression.py`.
   - Add sanitized translation batch diagnostics fields to `P1SampleResult`.
   - Fetch `GET /api/v1/document-jobs/{job_id}/translation-batches` after terminal job state for every translation sample.
   - Keep diagnostics collection non-fatal when the endpoint is temporarily unavailable, but record an explicit warning/blocker in the report.
   - Do not fetch AI call log/debug archive contents.

2. Summarize batch diagnostics.
   - Count batch statuses.
   - Track total batches, succeeded, failed, split, active, attention count.
   - Record generation and provider call budget values.
   - Preserve page range, attempt, finish_reason, retryable/truncation flags, error code/message summary, result file id, and AI call log file id count per batch.
   - Shorten long error messages without losing the leading diagnostic code/reason.

3. Render report evidence.
   - Update `report.json` to include the structured diagnostics.
   - Update `report.md` to show a compact per-sample provider batch summary.
   - If no truncation occurred, render that explicitly instead of implying split recovery was tested.
   - Ensure report fields are safe for Acceptance Center manual registration.

4. Add targeted tests for the report helper changes.
   - Cover successful multi-batch diagnostics.
   - Cover failed/truncation-style diagnostics.
   - Cover unavailable diagnostics endpoint warning behavior if helper structure supports it.
   - Avoid network tests; use helper-level or mocked session tests consistent with existing ops script test style.

5. Update provider batch runbook.
   - Add a section in `docs/runbooks/backend.md`.
   - Include normal, truncation split, retry exhausted, stuck running/queued, and fan-in stuck interpretations.
   - Include allowed current actions and explicitly state absent batch-level writes.
   - Preserve the online-first validation boundary: full runtime proof belongs on `hostdzire` or equivalent staging.

6. Write operations-entry evaluation.
   - Add `.trellis/tasks/06-26-translation-provider-batching-recovery-phase-3/operations-entry-evaluation.md`.
   - Compare existing Job Detail, Incident Triage, and Operations Cockpit surfaces.
   - Decide whether MVP needs any new aggregation. Expected answer: no implementation now; keep deep links and define future triggers.
   - If future batch-level writes are mentioned, document permissions, API, audit, idempotency, and safety gates only.

7. Run local validation.
   - Run focused tests for modified ops reporting helpers.
   - Run `git diff --check`.
   - If docs-only parts change, no local full-stack smoke is required.

8. Record staging/hostdzire verification plan or result.
   - If remote validation can be run in this task, record the sanitized report path and summary.
   - If not, record the exact blocker and command/environment variables needed for the operator to run it.

## Suggested Validation Commands

Targeted Python tests, depending on touched test files:

```bash
.venv/bin/python -m unittest tests.test_p1_translation_sample_manifest
```

If new tests are added for `run_p1_translation_regression.py`, run the specific new test module or test cases.

Repository hygiene:

```bash
git diff --check
```

Hostdzire/staging runtime validation is not run locally. Use the existing online-first flow and a private long-PDF manifest through `P1_TRANSLATION_MANIFEST` when the original 32-page sample is not committed to the repo.

## Risk Points

- `run_p1_translation_regression.py` currently treats single-sample exceptions as sample failures; diagnostics endpoint failures should be visible without masking the original job outcome.
- Report data must stay redacted. File ids are allowed; file contents and signed URLs are not.
- The long PDF may succeed without triggering provider truncation. That is still useful evidence for bounded batching, but it does not by itself prove split recovery on a live provider response.
- Incident/Cockpit aggregation can become a larger feature. Keep Phase 3 to evaluation unless the user explicitly reopens scope.
- Batch-level writes are operationally risky because they mutate queues and batch generations. Do not implement them in this task.

## Review Gate Before Start

Before `task.py start`, confirm:

- `prd.md` has no unresolved MVP questions.
- `design.md` and `implement.md` match the confirmed MVP.
- Implementation is limited to reporting, docs, and task-local evaluation.
- No Phase 1/2 archived artifacts will be modified.
