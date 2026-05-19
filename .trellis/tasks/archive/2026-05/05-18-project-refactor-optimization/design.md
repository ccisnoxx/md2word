# Backend Job Flow Refactor Design

## Summary

This refactor keeps all existing HTTP contracts, persisted job semantics, and
test-observed behavior intact while reducing complexity in the FastAPI job flow.
The work will split the monolithic jobs router into nearby route modules, move
callback-only API guards out of generic dependencies, and consolidate repeated
`JobStageService` transition/event/logging code through internal helpers without
changing stage-machine semantics.

## Scope

In scope:

- `app/api/v1/routers/jobs.py`
- `app/api/v1/routers/mineru_callbacks.py`
- `app/api/dependencies.py`
- `app/services/jobs/stage.py`
- small supporting updates in `app/api/v1/router.py`,
  `app/services/jobs/command.py`, and `app/services/jobs/lifecycle.py` when
  required by the refactor
- `tests/test_fastapi_jobs_backend.py`

Out of scope:

- any HTTP route path, method, response schema, or error-detail change
- any job status or stage semantic change
- file repository redesign
- CLI/runtime conversion pipeline refactors outside the backend job flow

## Design Goals

1. Make the jobs HTTP surface readable by responsibility.
2. Remove router-to-router helper reuse.
3. Keep callback-specific API guards local to callback handling.
4. Reduce repeated `update_job` / `update_stage_message` / `append_event` /
   logging sequences in `JobStageService`.
5. Preserve current behavior under `tests/test_fastapi_jobs_backend.py`.

## Proposed Module Shape

### API Router Layer

Keep `app/api/v1/routers/jobs.py` as a thin aggregator mounted at `/jobs`, and
introduce nearby companion modules:

- `app/api/v1/routers/jobs_ingest.py`
  - `POST /jobs`
  - `POST /jobs/pdf`
  - ingest-only helpers such as conversion-option building and temp upload save
- `app/api/v1/routers/jobs_query.py`
  - `GET /jobs`
  - `GET /jobs/{job_id}`
  - `GET /jobs/{job_id}/files`
  - `GET /jobs/{job_id}/events`
  - `GET /jobs/{job_id}/result`
  - `GET /jobs/{job_id}/download/{artifact_alias}`
- `app/api/v1/routers/jobs_ops.py`
  - `POST /jobs/{job_id}/retry`
  - `POST /jobs/{job_id}/cancel`
  - `POST /jobs/{job_id}/cleanup-local-files`
- `app/api/v1/routers/jobs_presenters.py`
  - shared response mapping helpers currently embedded in `jobs.py`
  - becomes the stable import target for `mineru_callbacks.py`

Why keep `jobs.py` as an aggregator instead of deleting it:

- preserves the current import point used by `app/api/v1/router.py`
- keeps `/jobs` prefix ownership obvious
- limits churn while still splitting the real responsibilities

### API Dependency Layer

Split current mixed concerns into:

- `app/api/dependencies.py`
  - keep `get_runtime`, `get_trace_id`
  - keep jobs/admin access guards
- `app/api/mineru_callback_guards.py` (new)
  - move `verify_mineru_callback_identity`
  - move callback payload normalization / checksum / result-url / job-state
    guards

This is a local API-layer cleanup only. Pure URL-host validation remains in
`app/core/mineru_callback.py`.

### Stage Service Layer

Keep `JobStageService` in `app/services/jobs/stage.py`, but reduce internal
duplication by introducing private helper methods. The goal is to centralize
common transition patterns without changing public behavior or stage semantics.

Expected helper clusters:

- stage-message running/failure bookkeeping
- job failure bookkeeping
- event append helpers
- success/failure logging helpers
- repeated callback/update payload handling helpers where behavior is identical

The dispatch surface remains the same:

- `enqueue_conversion()`
- `enqueue_mineru_submission()`
- `enqueue_process_callback()`
- `dispatch_message()`
- `replay_pending()`

The stage names and legal status transitions remain unchanged.

## Data-Flow and Contract Preservation

### Jobs HTTP Flow

- `POST /jobs` and `POST /jobs/pdf` still:
  - normalize the same form inputs
  - perform the same translation-availability and MinerU-token checks
  - save uploads to temp the same way
  - call the same command service methods
  - enqueue background work through `BackgroundTasks`

### Query and Ops Flow

- query/download endpoints keep using `runtime.query_service`,
  `runtime.artifact_service`, and current schemas
- ops endpoints keep using `runtime.lifecycle_service`
- presenter helpers only move response mapping code; they do not change field
  population logic

### Callback Flow

- callback router still performs the same ordered guard flow before enqueueing:
  identity -> normalize -> result URL -> job lookup -> job-state guard ->
  checksum guard -> enqueue callback
- the only change is module placement, not logic order

### Stage Flow

- `convert_package`, `submit_to_mineru`, and `process_callback` still execute
  the same state changes, event names, and log messages
- helper extraction must not merge distinct failure paths if doing so would
  change emitted `error_code`, `message`, or event ordering

## Compatibility Notes

- Existing imports from `app.api.dependencies` inside non-callback routers stay
  stable.
- `app/api/v1/routers/mineru_callbacks.py` should stop importing a private
  helper from `jobs.py` and instead import from `jobs_presenters.py`.
- Documentation and architecture files do not need a semantic rewrite for this
  milestone; only code and tests need to stay aligned.

## Key Risks

1. Route splitting can accidentally change route registration order or duplicate
   prefixes.
2. Presenter extraction can accidentally drop sorting or field population in
   detail/list responses.
3. Stage helper consolidation can accidentally reorder `append_event()` and
   `update_job()` side effects.
4. Callback-guard relocation can accidentally change import wiring while keeping
   logic textually identical.

## Risk Mitigations

- Keep `jobs.py` as the single `/jobs` prefix owner.
- Move presenter code first, then repoint `jobs_query.py`, `jobs_ops.py`, and
  `mineru_callbacks.py` to the shared presenter module.
- Refactor `stage.py` with extraction-first discipline:
  preserve statements, then wrap them; do not redesign the state machine.
- Re-run `tests/test_fastapi_jobs_backend.py` after each major step.

## Rollback Strategy

- Router split can be reverted independently by restoring the old monolithic
  `jobs.py` and removing companion modules.
- Dependency split can be reverted independently by moving callback helpers back
  into `app/api/dependencies.py`.
- Stage helper consolidation can be reverted independently by inlining helpers
  back into `stage.py`.

## Success Criteria

- `jobs.py` no longer directly contains all route implementations and response
  mappers.
- callback router no longer imports a private helper from another router.
- `app/api/dependencies.py` no longer mixes callback-only guards with generic
  runtime/jobs access helpers.
- `JobStageService` contains visibly less repeated transition boilerplate while
  preserving all current stage semantics.
- backend API tests still pass unchanged except for import/setup adjustments
  required by the refactor.
