# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

This backend supports two jobs metadata backends:

- `file`, implemented by `app/repositories/file_job_repository.py`
- `database`, implemented by `app/repositories/database_job_repository.py`

`file` remains the code default and is the local-development backend.
`database` is the sqlite metadata backend for staging-like single-instance
deployments. It stores jobs, job files, events, and stage messages in one
sqlite file, but it does not move artifact binaries by itself. Artifact
binaries are controlled separately by `JOBS_ARTIFACT_STORAGE_BACKEND`.

Health reporting in `app/services/health_service.py` exposes both the
configured backend and the effective backend through
`configured_repository_backend` and `effective_repository_backend`.

Current file-backend storage layout:

- `data/jobs/<job_id>/job.json` for the primary job record
- `data/jobs/<job_id>/files.json` for registered artifacts
- `data/jobs/<job_id>/events.jsonl` for append-only events
- `data/stage_messages/<message_id>.json` for background stage spool messages
- `data/config/term_rules_store.json` for live runtime term-rule truth
- `data/config/runtime_subscripts_dictionary.yaml` for generated conversion
  compatibility YAML
- `data/config/template_state.json` for runtime default-template state

Current database-backend layout:

- `data/metadata.sqlite3` by default, or `JOBS_METADATA_DATABASE_PATH`
- sqlite tables for jobs, job files, job events, and stage messages
- local artifact files stay under `data/jobs/<job_id>/...` unless the artifact
  storage backend is separately switched

Current artifact-storage backends:

- `local_file`, the default, registers job-local logical paths and serves files
  from `data/jobs/<job_id>/...`
- `local_object`, implemented by `ObjectArtifactStorageAdapter`, shadow uploads
  artifacts to a local object directory and serves by `object_key` with a local
  fallback
- `s3`, implemented by `S3ArtifactStorageAdapter`, uploads artifacts through an
  S3-compatible client and resolves downloads as either presigned redirects or
  backend streams

`storage_backend=object` plus `object_key` is the persisted metadata contract
for both local-object and S3 object storage. Retention planning is dry-run first
through `ArtifactRetentionPlanner`; do not delete object artifacts without
reviewing the generated candidates.

---

## Query Patterns

- Repository methods return typed Pydantic models, not raw dictionaries.
  Examples: `JobRecord.model_validate(...)`, `JobEvent.model_validate_json(...)`.
- When one domain needs both a versioned seed and a runtime mutable store, treat
  the runtime store as the live API truth and the versioned file as bootstrap /
  sync material, not as something routers write directly.
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
- Crash safety is adapter-specific:
  - file backend uses `_write_json()` with `*.tmp` replacement
  - sqlite backend commits each repository method call through a short-lived
    connection

Because there is no transaction manager, multi-step workflows rely on ordered
repository writes plus replayable stage messages. `JobStageService.replay_pending()`
is the recovery path after process restart.

Stage message states are intentionally small:

- `pending` and `running` are replayable; `running` means the in-process
  dispatcher claimed the message but may have crashed before deletion.
- `failed` is retained for diagnosis and excluded from automatic replay.
- `lease_owner`, `leased_at`, and `lease_expires_at` are advisory worker-readiness
  fields today. They are not cross-process locking yet, but `/health/ready` uses
  them to report stale running messages.
- `JOBS_WORKER_MODE=external` moves stage consumption to `run_worker.py`, but it
  still uses the same repository and `JobStageService` contracts; API handlers
  should only enqueue stage messages in that mode.

Current dependency boundaries are adapter based:

- `JobQueryService` and `JobLifecycleService` depend on repository protocols.
- `JobStageService` receives both repository protocols and the stage message
  store so it can run against either `file` or `database`.

When adding a new service, default to the protocol boundary first. Only bind to
`FileJobRepository` or `DatabaseJobRepository` directly if the service truly
needs backend-specific behavior that is not already expressed in repository
protocols.

---

## Migrations

- There is no Alembic, Django migration system, or PostgreSQL/MySQL schema
  migration flow in this repo.
- Schema evolution currently happens by updating Pydantic models and the file
  and sqlite repositories together.
- Existing file metadata can be shadow-copied into sqlite with
  `scripts/ops/shadow_copy_metadata_to_database.py` after passing the read-only
  integrity check in `scripts/ops/check_local_file_storage_integrity.py`.
- Some backend domains may use a three-layer file boundary instead of a single
  JSON record:
  - versioned seed file
  - live runtime JSON store
  - generated compatibility/runtime export file
- When storage shape changes, update all of these in the same change:
  - `app/core/job_models.py`
  - `app/repositories/file_job_repository.py`
  - `app/repositories/database_job_repository.py`
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

- Do not assume PostgreSQL/MySQL features such as server-side migrations,
  row-level locking, or cross-process worker leasing; sqlite is only the current
  metadata store.
- Do not bypass repository adapters to edit `job.json`, `files.json`, or sqlite
  rows manually from routers/services.
- Do not invent a second storage layout for a new feature when `build_job_paths()`
  can be extended consistently.
- Do not forget companion writes when mutating job state; current workflows
  usually update the job record, append an event, and sometimes mutate a stage
  message together.
- Do not change job/event schema without checking the response mappers in
  `app/api/v1/routers/jobs.py`; persisted shape and returned shape are coupled.
