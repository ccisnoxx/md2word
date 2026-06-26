# Database Guidelines

The backend currently uses explicit metadata adapters, not an ORM. Metadata can be stored in local files, sqlite, or MySQL; artifact binaries are configured separately.

Evidence:

- `app/core/config.py`
- `app/infrastructure/persistence/factory.py`
- `app/infrastructure/persistence/file/backend.py`
- `app/infrastructure/persistence/sqlite/backend.py`
- `app/infrastructure/persistence/sqlite/schema.py`
- `app/infrastructure/persistence/mysql/backend.py`
- `app/infrastructure/persistence/mysql/schema.py`
- `app/infrastructure/persistence/mysql/jobs.py`
- `app/infrastructure/persistence/sqlite/jobs.py`
- `app/infrastructure/persistence/file/jobs.py`
- `docs/runbooks/backend.md`
- `tests/test_database_job_repository.py`

## Metadata Backend Selection

`Settings.jobs_repository_backend` controls metadata storage:

- `file` is the code default and local development backend.
- `database` means sqlite, using `Settings.jobs_metadata_database_file`.
- `mysql` means MySQL through PyMySQL and `MysqlPersistenceConfig`.

`build_persistence_adapters()` in `app/infrastructure/persistence/factory.py` is the single wiring point for backend-specific repositories. Add new repository ports to `PersistenceAdapters`, then implement and wire each supported backend there.

Artifact binaries are not stored in sqlite or MySQL metadata tables. `Settings.jobs_artifact_storage_backend` selects `local_file`, `local_object`, or `s3`, and `app/main.py` wires the matching artifact storage adapter separately.

## Repository Ports And Adapters

Domain code should depend on narrow repository protocols in `app/domains/**/repository.py`. Examples:

- `app/domains/jobs/repository.py` defines `JobSnapshotRepositoryProtocol`, `JobEventRepositoryProtocol`, `JobFileRepositoryProtocol`, and `StageMessageStoreProtocol`.
- `app/infrastructure/persistence/factory.py` returns a concrete `PersistenceAdapters` object containing implementations for the selected backend.
- `app/main.py` passes those adapters into services and stores them on `AppRuntime`.

When adding persistence for a domain, keep the domain protocol in `app/domains/<domain>/repository.py`, and put backend implementations under `app/infrastructure/persistence/file`, `sqlite`, and/or `mysql`.

当前未建立此约定：resource versioning and several governance repositories are only wired for MySQL in `build_mysql_persistence_adapters()`. File and sqlite adapters often return `None` for those optional ports, so services must explicitly guard MySQL-only behavior instead of assuming every backend supports it.

## Schema And Migration State

当前未建立此约定：there is no Alembic or versioned migration directory.

Schema creation is bootstrap SQL in code:

- sqlite statements live in `app/infrastructure/persistence/sqlite/schema.py`.
- MySQL statements live in `app/infrastructure/persistence/mysql/schema.py`.
- `SqlitePersistenceBackend` and `MysqlPersistenceBackend` call `initialize_schema()` during backend initialization.

Do not add ORM migrations or PostgreSQL assumptions inside feature work unless the task explicitly establishes that new convention. `docs/dev/backend-local-setup-and-architecture.md` and `docs/runbooks/backend.md` both state the current production-oriented metadata backend is MySQL, while PostgreSQL is not present.

For metadata backend moves from file to sqlite/MySQL, use the existing shadow-copy scripts documented in `docs/runbooks/backend.md`:

- `scripts/ops/check_local_file_storage_integrity.py`
- `scripts/ops/shadow_copy_metadata_to_database.py`
- `scripts/ops/shadow_copy_metadata_to_mysql.py`

## Storage Shape

The dominant adapter pattern stores Pydantic model payloads as JSON and keeps a small number of indexed columns for lookup/sorting/status:

- `app/infrastructure/persistence/mysql/jobs.py` stores `JobRecord` in `jobs.payload` and events in `job_events.payload`.
- `app/infrastructure/persistence/sqlite/jobs.py` mirrors that pattern with sqlite.
- `app/infrastructure/persistence/file/jobs.py` stores `job.json`, `files.json`, and `events.jsonl`.
- `app/infrastructure/persistence/file/backend.py` writes JSON via a temporary file and `replace()`, and appends JSONL for events.

Use `model_dump(mode="json")`, `model_dump_json()`, and `model_validate_json()` for Pydantic record persistence. Keep compatibility transforms at the persistence boundary when the existing model requires them, as `sync_source_pdf_compatibility_fields()` does for jobs.

## Query And Transaction Patterns

Use parameterized SQL:

- MySQL adapters use `%s` bind markers with tuple parameters.
- sqlite adapters use `?` bind markers with tuple parameters.

Do not format user or request values directly into SQL strings.

Connection helpers define commit behavior:

- `MysqlPersistenceBackend.connect()` commits on success and rolls back on exception.
- `SqlitePersistenceBackend.connect()` commits on successful context exit and closes the connection.

当前未建立此约定：there is no shared query builder, ORM transaction manager, or multi-statement domain transaction abstraction. Existing adapters open a short connection per repository method.

## Stage Message Persistence

`StageMessageStoreProtocol` defines stage spool behavior. Current stores:

- `FileStageMessageStore`
- `SqliteStageMessageStore`
- `MysqlStageMessageStore`

`pending` and `running` are replayable. `failed` preserves diagnostic state and is not automatically replayed. This is documented in `app/domains/jobs/repository.py`, `app/domains/jobs/stage.py`, and `docs/dev/runtime-observability-and-health.md`.

When changing stage messages, update all supported stores and tests. `tests/test_database_job_repository.py` is the main contract test for adapter parity.

## Document Jobs Translation Batches

`DocumentJobTranslationBatchRepositoryProtocol` is part of the `document_jobs` metadata contract. File, sqlite, and MySQL adapters must all support:

- create/get/list by `job_id` and optional `generation`
- unconditional administrative update for local state repair
- compare-and-set update through `update_translation_batch_if_current(batch_id, allowed_statuses, expected_generation, **patch)`

Provider batch worker transitions must use compare-and-set for claim and running-state completion/failure. A stale task, expired lease replay, canceled job, or older generation must not be able to overwrite a batch that has already left `running`.

Translation batch stores follow the existing payload-plus-index pattern:

- file backend stores one JSON payload per batch under `document_job_translation_batches/`
- sqlite/MySQL use `document_job_translation_batches` with indexed `batch_id`, `job_id`, `generation`, `status`, `created_at`, and `updated_at`

When changing batch persistence fields or state transitions, update all three adapters, the schema bootstrap, fake MySQL cursor behavior, and the adapter parity coverage in `tests/test_database_job_repository.py`.
