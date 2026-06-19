# Database Guidelines

> Persistence, schema, query, and migration conventions for this project.

---

## Overview

This project does not use an ORM. Backend metadata is stored through explicit
repository adapters with three supported backends:

- `file`: local JSON/JSONL metadata under the runtime data directory; this is
  the development default.
- `database`: sqlite metadata, configured by
  `JOBS_REPOSITORY_BACKEND=database`.
- `mysql`: MySQL metadata, configured by `JOBS_REPOSITORY_BACKEND=mysql`.

The backend name `database` means sqlite in this codebase. Do not introduce a
second meaning for it.

Artifacts and customer files are not stored in sqlite/MySQL metadata tables.
Artifact bytes are handled by artifact storage backends such as `local_file`,
`local_object`, or `s3`; metadata repositories only store records, payloads, and
references.

---

## Persistence Architecture

Adapter selection is centralized in
`app/infrastructure/persistence/factory.py`:

```python
if settings.jobs_repository_backend == "database":
    return build_sqlite_persistence_adapters(settings.jobs_metadata_database_file)
if settings.jobs_repository_backend == "mysql":
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    return build_mysql_persistence_adapters(mysql_config, connect_factory=mysql_connect_factory)
return build_file_persistence_adapters(settings.data_path)
```

Every backend must implement the same domain repository ports. For example, job
metadata has parallel adapters in:

- `app/infrastructure/persistence/file/jobs.py`
- `app/infrastructure/persistence/sqlite/jobs.py`
- `app/infrastructure/persistence/mysql/jobs.py`

Keep this parity when adding repository methods. If one backend cannot support a
new method, that is a design problem to resolve explicitly, not a reason to add
silent fallback behavior.

---

## Data Model Pattern

Current sqlite and MySQL metadata tables usually store a small set of indexed
columns plus a serialized Pydantic payload:

```sql
CREATE TABLE IF NOT EXISTS document_jobs (
    job_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

The MySQL equivalent uses `VARCHAR`/`LONGTEXT` and `utf8mb4`:

```sql
CREATE TABLE IF NOT EXISTS document_jobs (
    job_id VARCHAR(128) PRIMARY KEY,
    payload LONGTEXT NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    KEY idx_document_jobs_created_at (created_at, job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
```

Serialize models through the backend helper:

```python
def dump_payload(self, model: Any) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)
```

Deserialize with the model that owns the record:

```python
return JobRecord.model_validate_json(row["payload"])
```

---

## Query Patterns

Use parameterized SQL only.

Sqlite uses `?` placeholders:

```python
row = connection.execute(
    "SELECT payload FROM jobs WHERE job_id = ?",
    (job_id,),
).fetchone()
```

MySQL uses `%s` placeholders through PyMySQL cursors:

```python
cursor.execute(
    "SELECT payload FROM jobs WHERE job_id = %s",
    (job_id,),
)
```

Do not format user-controlled values into SQL strings with f-strings,
`format()`, or concatenation.

Repository methods use short connection scopes. Sqlite commits after the
context manager yields; MySQL commits on success and rolls back on exceptions:

```python
@contextmanager
def connect(self) -> Iterator[Any]:
    connection = self._connect_factory()
    try:
        yield connection
        connection.commit()
    except Exception:
        if hasattr(connection, "rollback"):
            connection.rollback()
        raise
    finally:
        connection.close()
```

Current adapters do not provide cross-repository transactions. If a workflow
updates multiple repositories, the service must handle idempotency and recovery
explicitly.

---

## Schema And Migrations

There is no Alembic or PostgreSQL migration system in this project.

Schemas are bootstrapped at adapter initialization:

- `app/infrastructure/persistence/sqlite/schema.py` owns
  `SQLITE_SCHEMA_STATEMENTS`.
- `app/infrastructure/persistence/mysql/schema.py` owns
  `MYSQL_SCHEMA_STATEMENTS` and `MYSQL_SCHEMA_MAINTENANCE_STATEMENTS`.

Schema statements must be idempotent. Existing code uses
`CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` for sqlite, and
`CREATE TABLE IF NOT EXISTS` plus targeted maintenance statements for MySQL.

When adding persistent fields or a new metadata record type:

1. Update the domain model and repository Protocol.
2. Update file, sqlite, and MySQL adapters together.
3. Add or update schema bootstrap SQL for sqlite and MySQL.
4. Update fake MySQL test support in `tests/test_database_job_repository.py`
   when the MySQL adapter behavior changes.
5. Add shadow-copy or parity tests when metadata must migrate from file to
   sqlite/MySQL.

Do not introduce destructive schema changes as part of routine feature work.
If a data rewrite is unavoidable, create an explicit ops script and validation
path similar to the existing metadata shadow-copy scripts.

---

## Naming Conventions

- Tables and columns use `snake_case`.
- Primary business IDs are named after the entity, for example `job_id`,
  `file_id`, `message_id`, `policy_id`.
- JSON payload columns are named `payload`.
- Timestamps are stored as ISO strings in `created_at` and `updated_at` columns.
- Indexes use descriptive prefixes such as `idx_`, `uq_`, or `uniq_`.
- MySQL tables use `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`.
- MySQL text that requires binary semantics may specify collation explicitly,
  as `term_rules.source_term` currently does.

---

## File Backend

The file backend is not a throwaway mock; it is the local development metadata
backend and must remain behaviorally compatible with sqlite/MySQL.

Current examples:

- Job snapshots: `var/jobs/{job_id}/job.json`
- Job events: `var/jobs/{job_id}/events.jsonl`
- Stage messages: `var/stage_messages/*.json`

Use the file backend for fast local tests and local-only development flows.
Use sqlite/MySQL adapter tests to prove backend parity for metadata behavior.

---

## Common Mistakes

- Treating `database` as a generic database flag instead of the sqlite backend.
- Adding a repository method to only one backend.
- Storing artifact bytes, large customer payloads, or generated documents in
  metadata tables.
- Interpolating SQL with f-strings.
- Adding schema state without updating `scripts/ops/check_release.py`,
  metadata shadow-copy validation, or fake MySQL tests when those contracts are
  affected.
- Assuming file/sqlite/MySQL operations share a transaction boundary when the
  current adapter design does not provide one.
