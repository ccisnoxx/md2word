# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

This backend does not use a relational database yet. Persistence is currently a
filesystem-backed repository implemented in
`app/repositories/file_job_repository.py`, with health reporting in
`app/services/health_service.py` exposing both configured and effective backend
as `"file"`.

Current storage layout:

- `data/jobs/<job_id>/job.json` for the primary job record
- `data/jobs/<job_id>/files.json` for registered artifacts
- `data/jobs/<job_id>/events.jsonl` for append-only events
- `data/stage_messages/<message_id>.json` for background stage spool messages

---

## Query Patterns

- Repository methods return typed Pydantic models, not raw dictionaries.
  Examples: `JobRecord.model_validate(...)`, `JobEvent.model_validate_json(...)`.
- Reads are intentionally simple and in-memory:
  - `FileJobRepository.list_jobs()` scans `jobs/*/job.json`
  - `JobQueryService.list_jobs()` applies filtering, sorting, and pagination in
    Python after loading the records
- Writes go through repository methods instead of ad hoc JSON access:
  - `create_job()` writes `job.json`
  - `update_job()` reads, patches via `model_copy(update=...)`, then writes
  - `append_event()` appends one JSON line per event
  - `upsert_file()` replaces existing entries by `file_type`
- Use `build_job_paths()` / `ensure_job_dirs()` for path layout instead of
  recomputing `data/jobs/...` paths inline.
- Crash safety is best-effort file based:
  `_write_json()` writes to `*.tmp` and then replaces the target atomically.

Because there is no transaction manager, multi-step workflows rely on ordered
repository writes plus replayable stage messages. `JobStageService.replay_pending()`
is the recovery path after process restart.

Current dependency boundaries are mixed on purpose:

- `JobQueryService` and `JobLifecycleService` depend on repository protocols.
- `JobStageService` depends on `FileJobRepository` directly because it needs
  both job persistence and stage-spool operations together.

When adding a new service, default to the protocol boundary first. Only bind to
`FileJobRepository` directly if the service truly needs file-repository-specific
behavior that is not already expressed in `JobRepositoryProtocol` /
`StageMessageRepositoryProtocol`.

---

## Migrations

- There is no Alembic, Django migration system, or SQL schema migration flow in
  this repo.
- Schema evolution currently happens by updating Pydantic models and the file
  repository together.
- When storage shape changes, update all of these in the same change:
  - `app/core/job_models.py`
  - `app/repositories/file_job_repository.py`
  - any path helpers in `app/core/job_paths.py`
  - tests that read/write the affected records
- Favor additive changes to JSON payloads where possible so old files continue
  to validate. If a breaking on-disk change is unavoidable, document the manual
  backfill/cleanup step in the task that introduces it.

---

## Naming Conventions

- IDs are string-based and prefixed by type:
  - jobs: `job_<12 hex chars>`
  - stage messages: `msg_<12 hex chars>`
- JSON filenames are semantic and stable:
  - `job.json`
  - `files.json`
  - `events.jsonl`
- Model fields use `snake_case` and are mirrored directly into JSON via
  `model_dump(mode="json")`.
- Enum-like states stay as explicit string literals in models rather than
  lookup tables:
  - job status: `uploaded`, `queued`, `submitting`, `parsing`, `parsed`,
    `converting`, `completed`, `failed`, `canceled`
  - stage names: `convert_package`, `submit_to_mineru`, `process_callback`

---

## Common Mistakes

- Do not assume SQL features such as joins, transactions, or row-level locking;
  current code reads and writes files directly.
- Do not bypass `FileJobRepository` to edit `job.json` or `files.json`
  manually from routers/services.
- Do not invent a second storage layout for a new feature when `build_job_paths()`
  can be extended consistently.
- Do not forget companion writes when mutating job state; current workflows
  usually update the job record, append an event, and sometimes mutate a stage
  message together.
- Do not change job/event schema without checking the response mappers in
  `app/api/v1/routers/jobs.py`; persisted shape and returned shape are coupled.
