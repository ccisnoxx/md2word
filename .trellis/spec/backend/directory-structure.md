# Directory Structure

The backend is a single FastAPI application rooted at `app/`. There is no `src/` package wrapper.

Evidence:

- `docs/dev/backend-local-setup-and-architecture.md`
- `app/main.py`
- `app/api/v1/router.py`
- `app/core/runtime.py`
- `app/domains/document_jobs/router.py`
- `app/domains/files/service.py`
- `scripts/dev/run_api.py`
- `scripts/dev/run_stage_worker.py`

## Runtime Composition

`app/main.py` is the composition root. It builds `Settings`, configures logging, builds persistence adapters, wires services, creates `AppRuntime`, registers error handlers, installs middleware, and includes the v1 API router.

Follow this pattern for runtime dependencies:

- Construct shared services and adapters in `build_runtime()`.
- Store shared dependencies on `AppRuntime` in `app/core/runtime.py`.
- Read runtime dependencies in routers through `Depends(get_runtime)` from `app/api/dependencies.py`.
- Avoid constructing repositories, clients, or services directly inside route handlers unless the existing route already owns a narrow local helper.

`create_app()` registers `register_api_error_handlers(app)`, CORS, trace/access logging middleware, startup replay tasks, and `api_v1_router`. `app = LazyDefaultApp()` delays reading `.env` and connecting runtime dependencies until the ASGI app is actually called.

## API Layout

`app/api/v1/router.py` owns the `/api/v1` prefix and aggregates business routers from `app/domains/**/router.py`.

Current pattern:

- API-owned auth/health routers live under `app/api/v1/routers/`.
- Business routers live with their domain, for example `app/domains/document_jobs/router.py`, `app/domains/files/router.py`, `app/domains/saved_views/router.py`, and `app/domains/term_rules/sets_router.py`.
- Router modules convert HTTP inputs to service calls, call FastAPI dependencies, map service results to response schemas, and write audit records for user actions.
- Business request/response schemas usually live in the same domain's `schemas.py`.

When adding a public v1 backend endpoint, add the router in the owning domain and include it from `app/api/v1/router.py`. Do not put new business endpoints under `app/api/v1/routers/` unless they are API shell concerns like current auth/health.

## Domain Layout

Business domains live under `app/domains/<domain>/`. The exact file set varies by domain, but the common local pattern is:

- `models.py` for Pydantic records and state literals.
- `schemas.py` for API request/response models.
- `router.py` or specialized routers such as `sets_router.py`, `review_router.py`, `ops_router.py`.
- `service.py` for application behavior and business validation.
- `repository.py` for `Protocol` ports used by services.
- Focused helpers for workflow, execution, recovery, presenters, validation, or config summaries when a domain has real complexity.

Examples:

- `app/domains/document_jobs/` has `models.py`, `schemas.py`, `router.py`, `service.py`, `repository.py`, `workflow.py`, `execution.py`, `recovery.py`, and incident routers.
- `app/domains/jobs/` has separated command/query/stage/lifecycle/workflow modules for the legacy jobs workflow and stage message processing.
- `app/domains/files/` splits upload service, retention, quota policy, cleanup, validation, repository, schemas, and router.

当前未建立此约定：not every domain has the same file names or all of `model/schema/router/service/repository`. Match the nearest existing domain with the same kind of behavior instead of forcing a uniform template.

## Core, Services, Conversion, And Workers

`app/core/` owns cross-cutting runtime primitives:

- `config.py` defines `Settings` and path derivation.
- `errors.py` defines `ApiError` and stable API error codes.
- `logging.py` configures runtime logging.
- `runtime.py` stores the process-wide `AppRuntime`.

`app/services/` holds shared services that are not cleanly owned by one business domain, such as auth, health, Document IR conversion, and rendering.

`app/conversion/` is the conversion library boundary. `docs/dev/backend-local-setup-and-architecture.md` identifies `app/conversion/runtime_facade.py` and `app/conversion/runtime_runner.py` as the stable backend-facing runtime path. Backend code should use the conversion entrypoint/facade rather than importing historical root scripts.

`app/workers/` owns worker implementations. Script entrypoints under `scripts/dev/` adapt them for local/PyCharm use:

- `scripts/dev/run_api.py` runs `uvicorn` against `app.main:app`.
- `scripts/dev/run_stage_worker.py` builds runtime and runs `StageWorker`.
- `scripts/dev/run_document_worker.py` is the Document Jobs worker entrypoint.

## Infrastructure And Runtime Data

`app/infrastructure/persistence/` owns metadata adapters:

- `file/`
- `sqlite/`
- `mysql/`
- `factory.py`

`resources/` contains versioned seed/config assets such as templates, template configs, prompts, and term rules. `var/` and `data/` are runtime data directories and are not the versioned source of truth.

`docs/dev/backend-local-setup-and-architecture.md` documents the current runtime shape, including `var/jobs/{job_id}/job.json`, `files.json`, `events.jsonl`, `stage_messages/`, `tmp/`, and config state files.

## Tests And Scripts

Backend tests live under `tests/` as `unittest` test modules. Large contract coverage currently sits in `tests/test_fastapi_jobs_backend.py`, with focused tests such as `tests/test_database_job_repository.py`, `tests/test_backend_logging.py`, `tests/test_openapi_export.py`, and domain-specific tests.

Operational and release scripts live under:

- `scripts/dev/` for local development/debug entrypoints.
- `scripts/ops/` for release, migration/shadow copy, Golden Sample, P1, and P2 checks.

当前未建立此约定：there is no `pyproject.toml`, `pytest.ini`, checked-in lint config, or backend package manager metadata beyond `requirements.txt`.
