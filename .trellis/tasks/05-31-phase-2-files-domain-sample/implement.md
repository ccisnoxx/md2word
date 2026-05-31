---
doc_type: implement-plan
task: 05-31-phase-2-files-domain-sample
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 2 implementation plan

## Rules

- Do not implement until this child task is reviewed and explicitly approved.
- Do not start parent Phases 3-5.
- Preserve behavior and HTTP contracts.
- Do not keep old files module compatibility shims.
- Keep repository adapters under `app/repositories/` in this phase.
- Use `/Users/sc/miniconda3/envs/md2word/bin/python` for verification.
- Respect the existing dirty worktree; do not revert unrelated changes.

## Step 0: Baseline

Record current status before moving files:

```bash
git status --short
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
```

If a broad baseline fails because of unrelated dirty state, record the failure
and continue only with the smallest files-specific import/API checks approved by
the user.

## Step 1: Create domain package and move files-owned modules

Actions:

- Create `app/domains/files/`.
- Move:
  - `app/core/file_models.py` -> `app/domains/files/models.py`
  - `app/schemas/files.py` -> `app/domains/files/schemas.py`
  - `app/api/v1/routers/files.py` -> `app/domains/files/router.py`
  - `app/services/files/upload_service.py` -> `app/domains/files/service.py`
  - `app/services/files/retention.py` -> `app/domains/files/retention.py`
  - `app/services/files/pdf_validation.py` -> `app/domains/files/validation.py`
- Create/update `app/domains/files/__init__.py` to export the domain service
  and retention types currently imported through `app.services.files`.

Checks:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile app/domains/files/*.py
```

## Step 2: Move files repository port

Actions:

- Create `app/domains/files/repository.py`.
- Move `DocumentFileRepositoryProtocol` from `app/repositories/protocols.py`.
- Remove the files model import from `app/repositories/protocols.py` if no
  longer needed.
- Update repository adapters and services to import the port from
  `app.domains.files.repository`.

Checks:

```bash
rg "DocumentFileRepositoryProtocol" app tests scripts
/Users/sc/miniconda3/envs/md2word/bin/python -m py_compile app/repositories/*.py app/core/runtime.py app/main.py
```

## Step 3: Update imports and route aggregation

Actions:

- Update imports from old files paths:
  - `app.core.file_models`
  - `app.schemas.files`
  - `app.services.files`
  - `app.services.files.pdf_validation`
  - `app.api.v1.routers.files`
- Update `app/api/v1/router.py` to include `app.domains.files.router`.
- Update `app/schemas/api_v1.py` to re-export files schemas from
  `app.domains.files.schemas`.
- Update tests to import files models/schemas/services from the new domain
  package.

Checks:

```bash
rg "app\\.core\\.file_models|app\\.schemas\\.files|app\\.services\\.files|app\\.api\\.v1\\.routers\\.files" app tests scripts
```

Expected: no active imports from old files module paths.

## Step 4: Remove old package locations and update docs/spec references

Actions:

- Ensure these old files/directories are gone:
  - `app/core/file_models.py`
  - `app/schemas/files.py`
  - `app/api/v1/routers/files.py`
  - `app/services/files/`
- Update `.trellis/spec/backend/directory-structure.md` to document
  `app/domains/files/` as the current domain-first sample while the rest of the
  app may still be in legacy technical-layer layout.
- Update current docs only if they refer to old files module paths.

Checks:

```bash
rg "file_models\\.py|schemas/files\\.py|services/files|routers/files\\.py|app\\.domains\\.files" docs .trellis/spec app tests scripts
```

Review any docs hits; old code paths should remain only in historical archive or
explicit migration notes.

## Step 5: Targeted verification

Commands:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
```

OpenAPI contract check:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check
```

Final stale-import audit:

```bash
rg "app\\.core\\.file_models|app\\.schemas\\.files|app\\.services\\.files|app\\.api\\.v1\\.routers\\.files" app tests scripts
```

Expected final state:

- no active imports from old files paths
- files router included from `app.domains.files.router`
- repository adapters unchanged in location and behavior
- tests pass
- no unreviewed OpenAPI contract drift

## Review gate

Stop after Phase 2 implementation and verification. Do not begin persistence
architecture work or additional domain migrations without a separate review.
