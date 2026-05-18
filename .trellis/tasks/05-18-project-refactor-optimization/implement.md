# Backend Job Flow Refactor Implementation Plan

## Scope

Implement the approved medium-strength, behavior-preserving refactor for the
backend job flow:

- split jobs routes by responsibility using nearby route modules
- extract shared job response presenters
- separate callback-specific API guards from generic dependencies
- consolidate repeated internal `JobStageService` transition boilerplate

## Ordered Checklist

### 1. Extract shared jobs presenters

Files:

- create `app/api/v1/routers/jobs_presenters.py`
- update `app/api/v1/routers/jobs.py`
- update `app/api/v1/routers/mineru_callbacks.py`

Goals:

- move shared response mapping helpers out of monolithic `jobs.py`
- make callback router depend on presenter helpers instead of another router's
  private function

Validation:

- imports resolve
- `python3 -m unittest tests.test_fastapi_jobs_backend`

Rollback point:

- restore presenter helpers into `jobs.py`

### 2. Split jobs router into ingest / query / ops modules

Files:

- update `app/api/v1/routers/jobs.py` into aggregator
- create `app/api/v1/routers/jobs_ingest.py`
- create `app/api/v1/routers/jobs_query.py`
- create `app/api/v1/routers/jobs_ops.py`
- update `app/api/v1/router.py` only if aggregator wiring requires it

Goals:

- separate upload, query/download, and operations endpoints by responsibility
- keep `/jobs` routes and response contracts unchanged

Validation:

- no duplicate route registrations
- `python3 -m unittest tests.test_fastapi_jobs_backend`

Rollback point:

- revert to monolithic `jobs.py`

### 3. Split callback guards out of generic dependencies

Files:

- update `app/api/dependencies.py`
- create `app/api/mineru_callback_guards.py`
- update `app/api/v1/routers/mineru_callbacks.py`

Goals:

- keep generic runtime/access dependencies stable
- move callback-only normalization and verification helpers next to their
  responsibility domain
- preserve auth, checksum, and payload validation behavior exactly

Validation:

- callback imports resolve
- callback-related backend tests still pass via
  `python3 -m unittest tests.test_fastapi_jobs_backend`

Rollback point:

- move callback helpers back into `app/api/dependencies.py`

### 4. Consolidate `JobStageService` internal transition helpers

Files:

- update `app/services/jobs/stage.py`
- touch `app/services/jobs/command.py` / `app/services/jobs/lifecycle.py` only
  if a tiny supportive API change is needed

Goals:

- reduce repeated `update_job` / `update_stage_message` / `append_event` /
  logger boilerplate
- preserve all existing stage names, statuses, event names, error codes, and
  side-effect order

Validation:

- `python3 -m unittest tests.test_fastapi_jobs_backend`
- inspect for preserved event/error names with
  `rg "conversion_started|job_failed|mineru_submit_failed|mineru_callback_processed|mineru_callback_failed" app/services/jobs/stage.py`

Rollback point:

- inline extracted helpers back into `stage.py`

### 5. Final verification and cleanup

Files:

- `tests/test_fastapi_jobs_backend.py`
- any changed backend job-flow files

Goals:

- ensure no stale router-to-router private imports remain
- ensure no behavior-preserving assumptions were violated during cleanup

Validation:

- `python3 -m unittest tests.test_fastapi_jobs_backend`
- `rg "_detail_response_from_record" app`
- `rg "from app\\.api\\.v1\\.routers\\.jobs import" app`

Rollback point:

- revert the last cleanup-only edits while preserving earlier structural steps

## Risky Files

- `app/api/v1/routers/jobs.py`
- `app/api/v1/routers/mineru_callbacks.py`
- `app/api/dependencies.py`
- `app/services/jobs/stage.py`
- `tests/test_fastapi_jobs_backend.py`

## Review Gates Before `task.py start`

- Confirm the aggregator-plus-companion-module shape for jobs routers is
  acceptable.
- Confirm dependency split stays local to `app/api/` and does not introduce a
  new framework layer.
- Confirm `stage.py` refactor is limited to helper extraction/consolidation, not
  state-machine redesign.
- Confirm the main verification target is
  `python3 -m unittest tests.test_fastapi_jobs_backend`.
