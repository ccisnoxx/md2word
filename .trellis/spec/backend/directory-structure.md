# Directory Structure

> How backend code is organized in this project.

---

## Overview

The FastAPI backend lives under `app/` and is organized by delivery layer first,
then by feature. `app/main.py` is the composition root; routers stay thin and
delegate to services; persistence lives behind repository objects and path
helpers.

---

## Directory Layout

```
app/
├── api/
│   ├── dependencies.py
│   └── v1/
│       ├── router.py
│       └── routers/
├── clients/
├── conversion/
├── core/
├── repositories/
├── schemas/
└── services/
    ├── jobs/
    └── templates/

tests/
├── test_fastapi_jobs_backend.py
└── test_*_characterization.py
```

---

## Module Organization

- `app/main.py`
  - Build `Settings`, repositories, services, middleware, and the top-level
    `AppRuntime`.
  - Do not place request validation or job lifecycle logic here.
- `app/core/`
  - Shared runtime-level primitives: settings, logging, domain records,
    filesystem path helpers, and pure validation helpers.
  - Examples: `app/core/config.py`, `app/core/job_models.py`,
    `app/core/job_paths.py`, `app/core/mineru_callback.py`.
- `app/api/`
  - FastAPI-only wiring: dependencies, auth guards, request extraction, and
    router registration.
  - `app/api/v1/router.py` only includes sub-routers; feature routes live in
    `app/api/v1/routers/*.py`.
  - When one resource router grows too large, keep the resource-level aggregator
    file and split companion route modules beside it instead of moving logic far
    away. Current example: `jobs.py` aggregating `jobs_ingest.py`,
    `jobs_query.py`, `jobs_ops.py`, plus shared `jobs_presenters.py`.
- `app/schemas/`
  - API response contracts built with Pydantic.
  - Keep HTTP response shapes here instead of defining ad hoc dictionaries in
    router functions.
- `app/services/`
  - Business workflows and orchestration.
  - Job flow is split by responsibility instead of one large service:
    `command.py` (create/enqueue), `query.py` (read/list),
    `lifecycle.py` (retry/cancel/cleanup), `stage.py` (background execution),
    `artifacts.py` (artifact metadata).
- `app/repositories/`
  - Persistence adapters and repository protocols.
  - Current backend is file-based: `file_job_repository.py`.
- `app/clients/`
  - Outbound integrations. `app/clients/mineru_client.py` owns MinerU HTTP
    protocol details so services do not build raw requests inline.
- `app/conversion/`
  - Conversion contracts and entrypoint wiring for the DOCX pipeline.
- `tests/`
  - `test_fastapi_jobs_backend.py` covers the HTTP API and background-job flow.
  - `test_*_characterization.py` pins behavior of legacy conversion modules.

---

## Placement Rules

- New HTTP endpoint:
  - add the route in `app/api/v1/routers/<resource>.py`
  - add/extend response models in `app/schemas/api_v1.py`
  - put orchestration in a service under `app/services/`
  - only touch `app/api/dependencies.py` when the validation/auth rule is
    shared by multiple endpoints
  - if a single resource accumulates several responsibility clusters, prefer
    companion modules like `<resource>_ingest.py`, `<resource>_query.py`,
    `<resource>_ops.py` under the same directory and keep `<resource>.py` as the
    prefix-owning aggregator
- New persisted job/artifact/event/stage field:
  - update `app/core/job_models.py`
  - update repository read/write logic in `app/repositories/`
  - update any mapping code that returns API responses
- New third-party integration:
  - put transport/protocol logic in `app/clients/`
  - inject or construct it from `app/main.py` / service wiring instead of from
    a router
- New shared path or filesystem rule:
  - prefer `app/core/job_paths.py` or the relevant artifact helper instead of
    recomputing paths inside services and routers

Current edge cases to be aware of:

- `app/api/v1/routers/mineru_callbacks.py` should consume shared presenter
  helpers from `jobs_presenters.py`, not private helpers from another router.
- `app/services/jobs/stage.py` depends on `FileJobRepository` directly, while
  `query.py` and `lifecycle.py` use repository protocols. When adding new
  services, prefer the narrower protocol unless the code truly needs the
  file-backed stage spool methods.
- `app/api/dependencies.py` is for generic runtime and access dependencies.
  Callback-only normalization and verification helpers belong in a nearby
  callback-specific module such as `app/api/mineru_callback_guards.py`.

---

## Naming Conventions

- Modules and packages use `snake_case`.
- Router files are resource-oriented and plural when they expose a collection:
  `jobs.py`, `templates.py`, `mineru_callbacks.py`.
- Service classes are explicit about responsibility:
  `JobCommandService`, `JobQueryService`, `JobLifecycleService`,
  `JobStageService`, `TemplateReadService`.
- Shared record types live in `app/core/job_models.py` and use singular
  Pydantic model names such as `JobRecord`, `JobFile`, `JobEvent`.
- Runtime path and artifact helpers use descriptive names instead of generic
  `utils.py`; examples: `job_paths.py`, `artifacts.py`.

---

## Examples

- Composition root example: `app/main.py`
- Thin router + service delegation example: `app/api/v1/routers/jobs.py`
- Companion route split example: `app/api/v1/routers/jobs_ingest.py`,
  `app/api/v1/routers/jobs_query.py`, `app/api/v1/routers/jobs_ops.py`,
  `app/api/v1/routers/jobs_presenters.py`
- Shared dependency/auth helpers example: `app/api/dependencies.py`
- Callback-specific API guard example: `app/api/mineru_callback_guards.py`
- Filesystem-backed repository example: `app/repositories/file_job_repository.py`
- Feature-oriented service split example: `app/services/jobs/`

Avoid these mismatches:

- Do not put business logic directly into `app/api/v1/router.py`; it is only
  for including routers.
- Do not write files directly from routers when repository/path helpers already
  own the storage layout.
- Do not add generic `utils.py` buckets when the code fits an existing feature
  module or `app/core/` helper.
