# Directory Structure

> Backend code organization conventions for this project.

---

## Overview

The backend is a FastAPI application with a domain-oriented structure. Keep new
backend work inside the existing `app/` layers, and treat `app/main.py` as the
composition root that wires repositories, services, workers, health checks, and
routers together.

The current backend architecture is documented in
`docs/dev/backend-local-setup-and-architecture.md`; this Trellis spec captures
the conventions that future code changes should follow.

---

## Directory Layout

```text
app/
  main.py                         # FastAPI app factory and runtime composition root
  core/
    config.py                     # Settings, environment variables, derived paths
    errors.py                     # API error codes and ApiError
    logging.py                    # access/business/system logging setup
    runtime.py                    # AppRuntime dependency container
  api/
    dependencies.py               # FastAPI runtime, trace, auth, and actor dependencies
    errors.py                     # exception handler registration and error response shape
    v1/
      router.py                   # /api/v1 route aggregator
      routers/                    # API-owned health/auth routers
  domains/
    <domain>/
      router.py                   # domain HTTP endpoints
      schemas.py                  # request/response Pydantic models
      models.py                   # domain records and value types
      service.py                  # business/application service
      repository.py               # repository Protocol ports, when the domain persists data
      workflow.py                 # workflow policies/state transitions, when applicable
  infrastructure/
    persistence/
      factory.py                  # selects file/sqlite/mysql adapter sets
      file/                       # local JSON/JSONL metadata backend
      sqlite/                     # sqlite metadata backend
      mysql/                      # MySQL metadata backend
  conversion/                     # conversion library and stable FastAPI-facing facade
  workers/                        # stage/document worker process integrations
scripts/
  dev/                            # local entrypoints for API and workers
  ops/                            # release gates, OpenAPI export, shadow copy tools
resources/                        # versioned templates, term rules, prompts
tests/                            # unittest-based backend and conversion tests
var/                              # runtime data, not versioned application assets
```

Examples in the current tree:

- `app/domains/document_jobs/router.py` owns `/api/v1/document-jobs`.
- `app/domains/files/service.py` owns file upload and file metadata business rules.
- `app/infrastructure/persistence/factory.py` creates explicit adapter sets for
  `file`, `database` (sqlite), and `mysql`.
- `app/conversion/runtime_facade.py` is the stable import surface used by the
  FastAPI side; avoid direct imports of legacy/root conversion scripts.

---

## Module Organization

### Composition Root

`app/main.py` is where runtime dependencies are assembled. The current
`build_runtime()` flow starts by resolving settings, configuring logging, and
selecting persistence adapters:

```python
resolved_settings = settings or Settings()
configure_logging(resolved_settings.app_env, resolved_settings.log_format)
persistence_adapters = build_persistence_adapters(resolved_settings)
repository_backend = persistence_adapters.backend_name
```

Do not construct a parallel runtime container in routers, services, or tests.
If a new service/repository is needed at request time, add it to
`build_runtime()` and `AppRuntime`.

### API Routing

The route tree is aggregated under `app/api/v1/router.py`:

```python
router = APIRouter(prefix="/api/v1")
router.include_router(document_jobs_router)
router.include_router(files_router)
router.include_router(health_router)
```

Domain-owned endpoints live beside their domain code, not in
`app/api/v1/routers/`, unless the endpoint is truly API-shell-owned like auth or
health.

### Router Responsibilities

Routers should stay thin:

- Declare FastAPI routes, dependencies, query/body constraints, and response models.
- Read `runtime: AppRuntime = Depends(get_runtime)` and actor dependencies from
  `app/api/dependencies.py`.
- Call domain/application services.
- Build response models through local `_build_*_response` helpers.
- Record audit events at the API boundary when the operation represents a user action.

`app/domains/document_jobs/router.py` is the best current example:

```python
@router.post("", response_model=DocumentJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document_job(payload, runtime, user, trace_id):
    _ensure_document_job_creation_ready(runtime)
    job = runtime.document_job_service.create_job(
        user=user,
        source_file_id=payload.source_file_id,
        mode=payload.mode,
        trace_id=trace_id,
    )
    runtime.audit_service.record(
        actor=_actor_from_user(user),
        action="document_job.create",
        target_type="document_job",
        target_id=job.id,
        trace_id=trace_id,
    )
    return DocumentJobCreateResponse(job_id=job.id, status=job.status)
```

### Domain Responsibilities

Domain packages own business rules and workflow invariants. For larger domains,
split by responsibility rather than putting everything into `service.py`.
Existing examples:

- `app/domains/document_jobs/workflow.py` defines document job workflow groups
  and allowed actions.
- `app/domains/jobs/stage.py`, `dispatch.py`, and `lifecycle.py` split stage
  processing, dispatching, and lifecycle operations.
- `app/domains/files/retention_policy.py`, `cleanup_execution.py`, and
  `quota_policy.py` isolate file governance concerns.

### Persistence Boundaries

Repository Protocols live in the domain package, while concrete adapters live
under `app/infrastructure/persistence/<backend>/`.

Examples:

- `app/domains/jobs/repository.py` defines job/stage repository protocols.
- `app/infrastructure/persistence/file/jobs.py`,
  `app/infrastructure/persistence/sqlite/jobs.py`, and
  `app/infrastructure/persistence/mysql/jobs.py` implement the same job ports.
- `app/infrastructure/persistence/factory.py` is the only place that selects
  which adapter set the runtime uses.

---

## Naming Conventions

- Python modules and packages use `snake_case`.
- Domain package names are usually plural when the business area is plural in
  product language: `document_jobs`, `term_rules`, `translation`, `files`.
- Public classes use domain-specific names, for example `DocumentJobService`,
  `FileUploadService`, `MysqlJobSnapshotRepository`.
- Route response helpers use `_build_*_response`.
- Validation/normalization helpers use `_ensure_*`, `_validate_*`, or
  `_normalize_*`.
- Constants that define API/business contracts use uppercase names near the
  module that owns them, for example `DOCUMENT_JOB_BULK_LIMIT`.
- Runtime data belongs under `var/` or `data/`; versioned defaults belong under
  `resources/`.

Most backend files also use explicit module purpose comments. Keep those
comments near the top of new non-trivial Python modules and state the file's
actual responsibility, for example:

```python
# File: app/infrastructure/persistence/factory.py
# Purpose: Select metadata persistence adapters from runtime settings.
```

Follow this pattern for new non-trivial Python modules.

---

## Adding A Backend Feature

1. Put domain logic under `app/domains/<domain>/`.
2. Add or extend `schemas.py` for request/response models.
3. Add repository Protocols in the domain package if persistence is needed.
4. Implement backend-specific adapters under `app/infrastructure/persistence/`.
5. Wire new runtime dependencies in `app/main.py` and `app/core/runtime.py`.
6. Add the domain router to `app/api/v1/router.py`.
7. Add unittest coverage under `tests/`, using fake providers/adapters when
   external systems would otherwise be required.
8. Update `docs/api/openapi.json` when API contracts change.

---

## Forbidden Patterns

- Do not put business rules only in routers when a service/domain boundary
  already exists.
- Do not import concrete persistence adapters directly from domain services.
  Depend on domain repository protocols and let `build_runtime()` inject the
  concrete implementation.
- Do not introduce a second route aggregator outside `app/api/v1/router.py`.
- Do not store generated runtime state or customer artifacts under `resources/`
  or commit files from `var/`.
- Do not start real MySQL, Redis/Celery, MinerU, OpenAI, or browser smoke tests
  as part of ordinary local backend code changes unless the task explicitly
  asks for online/integration validation.

---

## Reference Examples

- Composition root: `app/main.py`
- Runtime container: `app/core/runtime.py`
- API dependency boundary: `app/api/dependencies.py`
- API error boundary: `app/api/errors.py`
- Domain router: `app/domains/document_jobs/router.py`
- Domain service: `app/domains/document_jobs/service.py`
- Persistence factory: `app/infrastructure/persistence/factory.py`
- Backend release gate: `scripts/ops/check_release.py`
