---
doc_type: implement-plan
task: 05-31-phase-3-persistence-architecture-split
status: draft
parent: 05-31-project-directory-restructure
---

# Phase 3 implementation plan

## Rules

- Do not implement until this child task is reviewed and explicitly approved.
- Do not start parent Phases 4-5.
- Preserve behavior, storage shape, and HTTP contracts.
- Do not keep old all-purpose repository compatibility shims.
- Do not move non-files domains in this phase.
- Use `/Users/sc/miniconda3/envs/md2word/bin/python` for verification.
- Respect the existing dirty worktree; do not revert unrelated Phase 1/2 or
  user changes.

## Step 0: Baseline

Record status and run persistence-relevant baselines:

```bash
git status --short
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
```

If broader tests fail because of unrelated dirty state, record the failure and
continue only with user-approved narrower checks.

## Step 1: Add infrastructure package and factory skeleton

Actions:

- Create `app/infrastructure/__init__.py`.
- Create `app/infrastructure/persistence/__init__.py`.
- Create `app/infrastructure/persistence/factory.py`.
- Define `PersistenceAdapters` without changing runtime wiring yet.
- Add backend package `__init__.py` files for file/sqlite/mysql.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile app/infrastructure/persistence/*.py
```

## Step 2: Split file backend

Actions:

- Extract file backend helpers into `app/infrastructure/persistence/file/backend.py`.
- Move file-backed port methods into:
  - `file/jobs.py`
  - `file/files.py`
  - `file/document_jobs.py`
  - `file/stage_messages.py`
  - `file/audit.py`
- Update file-backend runtime wiring to use per-port file adapters.
- Update tests/scripts that imported `FileJobRepository`.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention
```

Exit signal:

- file backend still passes repository contract tests
- no active imports from `app.repositories.file_job_repository`

## Step 3: Split sqlite backend

Actions:

- Extract sqlite connection helper into `app/infrastructure/persistence/sqlite/backend.py`.
- Extract sqlite schema bootstrap into `app/infrastructure/persistence/sqlite/schema.py`.
- Move sqlite-backed port methods into:
  - `sqlite/jobs.py`
  - `sqlite/files.py`
  - `sqlite/document_jobs.py`
  - `sqlite/stage_messages.py`
  - `sqlite/audit.py`
- Update `jobs_repository_backend="database"` runtime wiring to use per-port
  sqlite adapters.
- Update shadow-copy scripts and sqlite tests to import new classes.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_metadata_shadow_copy
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_local_file_storage_integrity_check
```

Exit signal:

- sqlite schema and contract behavior match baseline
- no active imports from `app.repositories.database_job_repository`

## Step 4: Split mysql backend

Actions:

- Move `MysqlJobRepositoryConfig` semantics to mysql persistence config /
  backend naming.
- Extract MySQL schema statements and initialization into
  `app/infrastructure/persistence/mysql/schema.py`.
- Move MySQL-backed port methods into:
  - `mysql/jobs.py`
  - `mysql/files.py`
  - `mysql/document_jobs.py`
  - `mysql/stage_messages.py`
  - `mysql/audit.py`
  - `mysql/resources.py`
- Update `jobs_repository_backend="mysql"` runtime wiring.
- Update fake-connection tests and MySQL imports.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning
```

Exit signal:

- fake MySQL tests pass
- resource-version behavior remains wired for mysql
- no active imports from `app.repositories.mysql_job_repository`

## Step 5: Remove old all-purpose modules and runtime aggregate usage

Actions:

- Remove old all-purpose repository modules after imports are gone:
  - `app/repositories/file_job_repository.py`
  - `app/repositories/database_job_repository.py`
  - `app/repositories/mysql_job_repository.py`
- Update `AppRuntime` and tests away from all-purpose `runtime.repository`.
- Keep `app/repositories/protocols.py` only for transition ports not yet moved
  to domains.
- Keep `app/repositories/file_term_rule_repository.py` unless a reviewed
  Phase 4 term-rules migration moves it.

Checks:

```bash
rg "FileJobRepository|DatabaseJobRepository|MysqlJobRepository|runtime\\.repository|app\\.repositories\\.file_job_repository|app\\.repositories\\.database_job_repository|app\\.repositories\\.mysql_job_repository" app tests scripts
```

Expected:

- no active all-purpose repository references
- any remaining `app.repositories.protocols` imports are transition ports only

## Step 6: Targeted verification

Commands:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_metadata_shadow_copy
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_shadow_upload
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_local_file_storage_integrity_check
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_resource_versioning
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check
```

Final stale-import audit:

```bash
rg "FileJobRepository|DatabaseJobRepository|MysqlJobRepository|app\\.repositories\\.file_job_repository|app\\.repositories\\.database_job_repository|app\\.repositories\\.mysql_job_repository" app tests scripts
```

Expected final state:

- file/sqlite/mysql metadata adapters are split by backend and port
- runtime services receive explicit adapters
- storage behavior is unchanged
- tests pass
- OpenAPI check reports `changed=False`

## Review gate

Stop after Phase 3 implementation and verification. Do not begin remaining
domain migrations or cleanup without a separate review.
