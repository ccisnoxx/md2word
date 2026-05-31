---
doc_type: design
task: 05-31-phase-3-persistence-architecture-split
status: draft
parent: 05-31-project-directory-restructure
scope: persistence infrastructure split for file/sqlite/mysql metadata backends
---

# Phase 3 persistence architecture split design

## 1. Scope

This phase splits persistence infrastructure without changing product behavior.
The current file/sqlite/mysql metadata adapters each implement many ports in one
class. Phase 3 replaces that shape with explicit per-port adapters grouped by
backend.

In scope:

- `app/infrastructure/persistence/` package creation
- file backend split
- sqlite backend split
- mysql backend split
- sqlite/mysql schema bootstrap extraction
- runtime composition updates in `app/main.py`
- `AppRuntime` persistence fields update if needed
- tests and scripts that import or instantiate old repository classes
- stale import audit for old all-purpose repository modules/classes

Out of scope:

- moving jobs, document_jobs, audit, resources, templates, term_rules, or
  translation into domain packages
- moving non-files models out of `app/core/`
- moving non-files schemas out of `app/schemas/`
- deleting `app/repositories/` entirely
- changing persisted JSON payload fields, table names, indexes, or row payload
  encoding
- enabling resource-version behavior for backends where it is not currently
  active
- introducing migrations, Alembic, locking, or transaction orchestration

## 2. Current architecture problem

Current adapters:

- `app/repositories/file_job_repository.py`
- `app/repositories/database_job_repository.py`
- `app/repositories/mysql_job_repository.py`

Each one is named like a jobs repository but owns multiple responsibilities:

- jobs
- job events
- job files / artifact metadata
- document files
- document jobs
- document job events
- stage messages
- audit events
- resource versions in mysql

`app/main.py` currently wires one repository instance into many ports:

```text
job_repository = repository
job_file_repository = repository
job_event_repository = repository
audit_event_repository = repository
document_file_repository = repository
document_job_repository = repository
document_job_event_repository = repository
stage_message_store = repository
```

Phase 3 should end that one-instance-does-everything shape.

## 3. Target package shape

```text
app/infrastructure/
├── __init__.py
└── persistence/
    ├── __init__.py
    ├── factory.py
    ├── file/
    │   ├── __init__.py
    │   ├── audit.py
    │   ├── backend.py
    │   ├── document_jobs.py
    │   ├── files.py
    │   ├── jobs.py
    │   └── stage_messages.py
    ├── sqlite/
    │   ├── __init__.py
    │   ├── audit.py
    │   ├── backend.py
    │   ├── document_jobs.py
    │   ├── files.py
    │   ├── jobs.py
    │   ├── schema.py
    │   └── stage_messages.py
    └── mysql/
        ├── __init__.py
        ├── audit.py
        ├── backend.py
        ├── document_jobs.py
        ├── files.py
        ├── jobs.py
        ├── resources.py
        ├── schema.py
        └── stage_messages.py
```

Notes:

- `backend.py` owns backend connection/path primitives and shared helpers.
- `schema.py` owns backend schema bootstrap for sqlite/mysql.
- `factory.py` owns runtime composition and returns a typed adapter bundle.
- File/sqlite resource-version adapters are not wired unless current behavior
  already supports them. MySQL resource versions remain active.
- `app/repositories/file_term_rule_repository.py` may remain for now because
  term-rules domain ownership is a later phase.

## 4. Adapter names

Use explicit class names that describe both backend and port:

- `FileJobSnapshotRepository`
- `FileJobEventRepository`
- `FileJobFileRepository`
- `FileDocumentFileRepository`
- `FileDocumentJobRepository`
- `FileDocumentJobEventRepository`
- `FileStageMessageStore`
- `FileAuditEventRepository`
- `SqliteJobSnapshotRepository`
- `SqliteJobEventRepository`
- `SqliteJobFileRepository`
- `SqliteDocumentFileRepository`
- `SqliteDocumentJobRepository`
- `SqliteDocumentJobEventRepository`
- `SqliteStageMessageStore`
- `SqliteAuditEventRepository`
- `MysqlJobSnapshotRepository`
- `MysqlJobEventRepository`
- `MysqlJobFileRepository`
- `MysqlDocumentFileRepository`
- `MysqlDocumentJobRepository`
- `MysqlDocumentJobEventRepository`
- `MysqlStageMessageStore`
- `MysqlAuditEventRepository`
- `MysqlResourceVersionRepository`

The old class names should not remain as compatibility aliases.

## 5. Shared backend primitives

File backend:

- A small `FilePersistenceBackend` owns:
  - root `data_path`
  - jobs/document_files/document_jobs/stage_messages/tmp/audit paths
  - directory creation
  - atomic JSON write helper
  - JSON read helper
  - JSONL append/read helpers
- Per-port repositories receive this backend object and own only their port
  methods.

Sqlite backend:

- `SqlitePersistenceBackend` owns:
  - `database_path`
  - short-lived connection context manager
  - schema initialization call
- `sqlite/schema.py` owns `initialize_schema(connection)` and schema SQL.
- Per-port repositories receive the backend and open short-lived connections
  for each method, preserving current commit behavior.

MySQL backend:

- `MysqlPersistenceConfig` and `MysqlPersistenceBackend` own:
  - connection settings
  - optional injected connection factory used by tests
  - schema initialization call
  - cursor/connection helper behavior
- `mysql/schema.py` owns MySQL schema statements and initialization.
- Per-port repositories receive the backend and preserve current commit /
  rollback behavior.

## 6. Runtime composition

Create a dataclass in `app/infrastructure/persistence/factory.py`:

```python
@dataclass(frozen=True, slots=True)
class PersistenceAdapters:
    backend_name: str
    job_repository: JobSnapshotRepositoryProtocol
    job_file_repository: JobFileRepositoryProtocol
    job_event_repository: JobEventRepositoryProtocol
    audit_event_repository: AuditEventRepositoryProtocol
    document_file_repository: DocumentFileRepositoryProtocol
    document_job_repository: DocumentJobRepositoryProtocol
    document_job_event_repository: DocumentJobEventRepositoryProtocol
    stage_message_store: StageMessageStoreProtocol
    resource_version_repository: ResourceVersionRepositoryProtocol | None
```

`build_runtime()` should call one persistence factory and assign services from
this bundle.

`AppRuntime.repository` is a transition smell because tests currently use it as
an all-purpose repository. Phase 3 should remove it or replace it with a
non-method persistence bundle, then update tests to use the specific runtime
port they are asserting.

## 7. Port ownership

Current transition state:

- `DocumentFileRepositoryProtocol` already lives in `app.domains.files`.
- Other repository protocols remain in `app/repositories/protocols.py` until
  their domains move in Phase 4.

This is intentional. Moving the remaining ports to domain packages in Phase 3
would mix persistence split with Phase 4 domain migration.

## 8. Behavior invariants

- File backend on-disk paths and payloads remain byte-compatible except for
  harmless JSON formatting already present in current helpers.
- Sqlite table names, payload columns, indexes, and update semantics remain the
  same.
- MySQL table names, payload columns, indexes, and update semantics remain the
  same.
- `jobs_repository_backend` values remain `file`, `database`, and `mysql`.
- `database` continues to mean sqlite.
- Stage message replayability and health readiness behavior remain unchanged.
- Resource version service remains enabled only for the same backend(s) as
  before this phase.
- Audit event ordering and payloads remain unchanged.
- Artifact binary storage remains controlled by artifact storage adapters, not
  metadata repository adapters.

## 9. Verification strategy

Primary tests:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_metadata_shadow_copy
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_shadow_upload
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_local_file_storage_integrity_check
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

Additional checks:

```bash
rg "FileJobRepository|DatabaseJobRepository|MysqlJobRepository|app\\.repositories\\.file_job_repository|app\\.repositories\\.database_job_repository|app\\.repositories\\.mysql_job_repository" app tests scripts
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check
```

Expected result: no active old all-purpose adapter imports, tests pass, and
OpenAPI is unchanged.

## 10. Risks

- This is the highest-risk phase because the split touches every backend and
  many tests use `runtime.repository` as a convenient all-purpose handle.
- Splitting sqlite/mysql schema bootstrap can accidentally alter initialization
  order or fake-connection test assumptions.
- MySQL resource versions are implemented in the current all-purpose adapter;
  missed wiring can silently disable template, term-rule-set, or translation
  profile version behavior.
- The file backend has path and JSON helper behavior that multiple ports share;
  helper extraction must not create a second storage layout.
- Because Phase 1 and Phase 2 are already dirty in the working tree, verification
  output must distinguish Phase 3 failures from earlier uncommitted changes.
