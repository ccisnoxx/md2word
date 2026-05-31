---
doc_type: design
task: 05-31-phase-2-files-domain-sample
status: approved
parent: 05-31-project-directory-restructure
scope: files domain-first sample under app/domains/files
---

# Phase 2 files domain sample design

## 1. Scope

This phase moves the `files` resource from technical-layer packages into one
owning domain package. It is a behavior-preserving refactor and a sample for
the later domain-first migration.

In scope:

- files API router implementation
- files API request/response schemas
- document file metadata model
- file upload service
- PDF upload validation helper
- document file retention planner
- document file repository protocol
- imports in callers that already depend on files behavior
- API v1 route aggregation
- focused docs/spec references for the sample pattern

Out of scope:

- moving `document_jobs` code into a domain
- moving legacy jobs code into a domain
- splitting file/sqlite/mysql repository adapters
- changing database schemas or persisted JSON shape
- changing API paths, request/response fields, auth, status codes, or audit
  event behavior
- deleting `app/schemas/api_v1.py` or central non-files schemas

## 2. Target package shape

```text
app/domains/files/
├── __init__.py
├── models.py
├── repository.py
├── router.py
├── schemas.py
├── service.py
├── retention.py
└── validation.py
```

Ownership:

- `models.py`: `DocumentFileRecord`, `DocumentFileType`,
  `DocumentFileStatus`, `DocumentFileStorageProvider`.
- `repository.py`: `DocumentFileRepositoryProtocol`.
- `schemas.py`: `FileUploadUrlRequest`, `DocumentFileResponse`,
  `FileUploadUrlResponse`, `FileUploadResponse`.
- `router.py`: `/files` API router and router-local response/actor/url helpers.
- `service.py`: `FileUploadAuthorization`, `FileUploadService`, object-key
  helpers, and S3/local-object file operations.
- `retention.py`: document file retention plan, candidates, and planner.
- `validation.py`: PDF metadata/content validation and page-count estimate.
- `__init__.py`: domain public exports for services and retention types used by
  composition/runtime code.

## 3. Moves

Direct moves:

- `app/core/file_models.py` -> `app/domains/files/models.py`
- `app/schemas/files.py` -> `app/domains/files/schemas.py`
- `app/api/v1/routers/files.py` -> `app/domains/files/router.py`
- `app/services/files/upload_service.py` -> `app/domains/files/service.py`
- `app/services/files/retention.py` -> `app/domains/files/retention.py`
- `app/services/files/pdf_validation.py` -> `app/domains/files/validation.py`
- `DocumentFileRepositoryProtocol` from `app/repositories/protocols.py` ->
  `app/domains/files/repository.py`

Remove after imports are updated:

- `app/core/file_models.py`
- `app/schemas/files.py`
- `app/api/v1/routers/files.py`
- `app/services/files/`

No old-path compatibility modules should remain.

## 4. Import strategy

Expected active import changes:

- `app.api.v1.router` imports `files_router` from
  `app.domains.files.router`.
- `app.main` imports `FileUploadService` from `app.domains.files`.
- `app.core.runtime` `TYPE_CHECKING` imports `DocumentFileRepositoryProtocol`
  from `app.domains.files.repository`.
- repository adapters import `DocumentFileRecord` from
  `app.domains.files.models`.
- document job services/imports that use file records or repository ports import
  from `app.domains.files.models` / `app.domains.files.repository`.
- jobs ingest imports PDF validation from `app.domains.files.validation`.
- translation audit imports `FileUploadService` from `app.domains.files`.
- `app.schemas.api_v1` may continue as the legacy API v1 facade, but its files
  re-exports must come from `app.domains.files.schemas`.

The central `app/repositories/protocols.py` keeps unrelated repository ports.
It should stop defining or importing the files repository port.

## 5. Behavioral invariants

- `/api/v1/files/upload-url`, `/api/v1/files/{file_id}/content`, and
  `/api/v1/files/{file_id}` remain unchanged.
- `FileUploadUrlRequest`, `DocumentFileResponse`, `FileUploadUrlResponse`, and
  `FileUploadResponse` JSON shapes remain unchanged.
- `DocumentFileRecord` model fields and default values remain unchanged.
- `DocumentFileRepositoryProtocol` method names and signatures remain unchanged.
- Audit actions remain `file.upload_authorize` and `file.upload_content`.
- PDF validation rules remain unchanged.
- Local object/S3 key generation remains unchanged.
- Existing repository adapters remain in place and keep the same storage shape.

## 6. Verification strategy

Primary tests:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_database_job_repository
```

Additional checks:

```bash
rg "app\\.core\\.file_models|app\\.schemas\\.files|app\\.services\\.files|app\\.api\\.v1\\.routers\\.files" app tests scripts
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check
```

If the OpenAPI check fails only because the repository snapshot is already
dirty from prior work, export/compare should be reviewed explicitly before
accepting the phase.

## 7. Risks

- `DocumentFileRepositoryProtocol` is used outside `files`, especially by
  document job services and runtime wiring. Moving the port is intentional, but
  missed imports can break unrelated flows.
- `app/schemas/api_v1.py` is still a central compatibility facade. This phase
  should update its source import but not delete the facade.
- Moving the router can change OpenAPI operation ordering or module metadata.
  Any HTTP path, schema, status-code, or auth change is not acceptable in this
  phase.
- Existing dirty Phase 1 and P0/P1 changes mean verification output should be
  read carefully rather than assuming every diff belongs to Phase 2.
