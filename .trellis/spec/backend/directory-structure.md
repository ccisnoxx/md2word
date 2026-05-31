# Directory Structure

> How backend code is organized in this project.

---

## Overview

The FastAPI backend lives under `app/`. Business resources use a domain-first
layout under `app/domains/`; concrete persistence adapters live under
`app/infrastructure/persistence/`; versioned non-code assets live under
`resources/`; ignored mutable runtime state lives under `var/`.

`app/main.py` is the composition root. It builds settings, persistence
adapters, services, middleware, and the top-level `AppRuntime`.

---

## Repository Layout

```text
.
├── app/
├── deploy/
│   ├── env/
│   ├── hosts/
│   └── nginx/
├── docker/
├── docs/
│   ├── api/
│   ├── archive/
│   ├── deploy/
│   ├── dev/
│   ├── runbooks/
│   └── testing/
├── resources/
│   ├── prompts/
│   ├── template_configs/
│   ├── templates/
│   └── term_rules/
├── scripts/
│   ├── dev/
│   └── ops/
├── tests/
│   ├── fixtures/
│   └── tmp/
└── var/
    ├── config/
    ├── jobs/
    ├── object_artifacts/
    ├── stage_messages/
    └── tmp/
```

Tool-required dot directories such as `.trellis/`, `.codestable/`, `.idea/`,
and VCS/config dotfiles stay at the repository root.

---

## App Layout

```text
app/
├── api/
│   ├── dependencies.py
│   ├── errors.py
│   ├── mineru_callback_guards.py
│   └── v1/
│       ├── router.py
│       ├── routers/
│       │   ├── auth.py
│       │   ├── auth_schemas.py
│       │   ├── health.py
│       │   └── health_schemas.py
├── clients/
├── conversion/
├── core/
├── domains/
│   ├── audit/
│   ├── document_jobs/
│   ├── files/
│   ├── jobs/
│   ├── resources/
│   ├── templates/
│   ├── term_rules/
│   └── translation/
├── infrastructure/
│   └── persistence/
│       ├── file/
│       ├── mysql/
│       └── sqlite/
├── services/
│   ├── auth/
│   ├── document_ir/
│   ├── renderer/
│   └── health_service.py
└── workers/
```

There is no central `app/schemas/` package, no central API v1 schema module,
and no central `app/repositories/` package. Domain API models live with their
domain; auth/health API-only models live beside their routers; repository ports
live with their domain; concrete adapters live under infrastructure.

---

## Module Ownership

- `app/api/`
  - FastAPI composition only: shared dependencies, error mapping, callback
    guards, version router aggregation, auth/health routes, and router-local
    auth/health schemas.
  - `app/api/v1/router.py` only includes sub-routers. Business routers are
    imported from `app.domains.<domain>`.
- `app/domains/<domain>/`
  - Owns business models, API schemas, router implementation, services,
    validation helpers, file codecs, and repository ports for that domain.
  - Large domains may split companion modules beside a resource-level router
    aggregator, such as `jobs_ingest.py`, `jobs_query.py`, and `jobs_ops.py`.
- `app/infrastructure/persistence/`
  - Owns concrete metadata adapters grouped first by backend (`file`, `sqlite`,
    `mysql`) and then by domain or port responsibility.
  - `factory.py` composes a `PersistenceAdapters` bundle for `app/main.py`.
- `app/core/`
  - Cross-domain primitives only: settings, logging, base API errors, and the
    runtime container.
  - Do not add business-domain records here.
- `app/conversion/`
  - Conversion engine/library boundary for MinerU package to DOCX processing.
  - Runtime configuration for conversion belongs here, not at repository root.
- `app/services/`
  - Active cross-cutting services that are not part of the migrated business
    domain packages: auth, health readiness/metrics, Document IR conversion,
    and Word rendering.
  - Auth user records belong in `app/services/auth/models.py`; Document IR
    records belong in `app/services/document_ir/models.py`; renderer template
    config records belong in `app/services/renderer/template_config.py`.
  - Do not add new business-resource services here; use `app/domains/<domain>/`.
- `app/clients/`
  - Outbound integration clients, such as MinerU HTTP protocol details.
- `app/workers/`
  - Process and queue composition. Workers call domain services; they do not
    own business logic.

---

## Placement Rules

- New business HTTP endpoint:
  - put the router and request/response models in `app/domains/<domain>/`
  - include the router from `app/api/v1/router.py`
  - keep orchestration and validation in the same domain package
  - put repository ports in the domain package
  - put backend-specific persistence in `app/infrastructure/persistence/<backend>/`
- New auth or health API-only contract:
  - put request/response models in the route-specific schema companion module
    under `app/api/v1/routers/`
  - keep router logic in `app/api/v1/routers/`
- New persisted field:
  - update the owning domain model and repository port
  - update each concrete adapter that persists the field
  - update API schemas only if the field is part of the HTTP contract
- New third-party integration:
  - put protocol/transport details in `app/clients/`
  - inject it through `app/main.py` or service wiring
- New independent local process runner:
  - put the PyCharm-friendly direct-run script under `scripts/dev/`
  - put reusable loop code under `app/workers/`
- New versioned seed resource:
  - put source-controlled assets under `resources/`
  - put mutable runtime truth under `var/`
  - never add fallback support for old root-level resource directories

---

## Naming Conventions

- Modules and packages use `snake_case`.
- Domain routers are resource-oriented and plural where they expose
  collections: `jobs.py`, `templates.py`, `term_rules.py`.
- Service classes are explicit about responsibility:
  `JobCommandService`, `JobQueryService`, `JobLifecycleService`,
  `JobStageService`, `TemplateReadService`.
- Avoid generic `utils.py`; use names that expose ownership, such as
  `artifact_integrity.py`, `resource_snapshots.py`, or `yaml_codec.py`.

---

## Examples

- Composition root: `app/main.py`
- API router aggregation: `app/api/v1/router.py`
- Auth API-only schemas: `app/api/v1/routers/auth_schemas.py`
- Health API-only schemas: `app/api/v1/routers/health_schemas.py`
- Domain package: `app/domains/jobs/`
- Domain repository port: `app/domains/jobs/repository.py`
- File persistence adapter: `app/infrastructure/persistence/file/jobs.py`
- MySQL schema bootstrap: `app/infrastructure/persistence/mysql/schema.py`
- Conversion runtime config: `app/conversion/runtime_config.py`
- Local API runner: `scripts/dev/run_api.py`
- Versioned template manifest: `resources/template_configs/templates_manifest.yaml`
- Mutable runtime config: `var/config/`

Avoid these mismatches:

- Do not put business logic directly into `app/api/v1/router.py`; it is only
  for including routers.
- Do not add central business schemas under `app/api/` or `app/core/`.
- Do not recreate central schemas or repositories.
- Do not write files directly from routers when a domain service or persistence
  adapter owns the storage rule.
- Do not add new root-level `run_*.py`, resource, or runtime-state directories.
