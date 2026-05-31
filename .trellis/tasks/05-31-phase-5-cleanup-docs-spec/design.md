---
doc_type: design
task: 05-31-phase-5-cleanup-docs-spec
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 5 design

## Intent

Phase 5 closes the staged directory restructure by removing transition shells
and making project knowledge match the code now on disk. It is still a
behavior-preserving cleanup: public HTTP routes, payloads, runtime settings,
and conversion behavior stay stable.

## Code cleanup

`app/schemas/` can disappear only after its remaining auth and health models
move. Those endpoints are API/composition resources rather than business
domains, so their request/response models move to `app/api/v1/schemas.py`.
Domain API schemas remain in their owning `app/domains/<domain>/schemas.py`
modules.

`app/repositories/` can disappear because repository ports now live in domains
and concrete adapters live under `app/infrastructure/persistence/`.

`app/services/` is not deleted wholesale in this phase. The old business-domain
subpackages were moved during Phase 4 and can be cleaned up, but active
cross-cutting services stay where they are:

- `app/services/auth`
- `app/services/document_ir`
- `app/services/renderer`
- `app/services/health_service.py`

## Documentation cleanup

The backend directory structure spec becomes the source of truth for the final
layout:

- `app/api/` owns HTTP composition, auth/health routers, and API-only schemas.
- `app/domains/` owns business domains, schemas, services, models, routers, and
  repository ports.
- `app/infrastructure/persistence/` owns file/sqlite/mysql adapters.
- `app/core/` owns only cross-domain primitives.
- `resources/` owns versioned non-code assets.
- `var/` owns ignored mutable runtime state.
- `scripts/dev/` owns PyCharm-friendly local process runners.

CodeStable architecture pages are updated at the same abstraction level:
overall entry page, FastAPI backend page, and conversion pages that mention old
prompt/template path defaults.

## Compatibility strategy

No `app.schemas.api_v1` or `app.repositories.protocols` compatibility facade is
kept. Tests are updated to assert direct imports from the new owning modules
instead of preserving old import paths.

## Validation strategy

Run a stale-import audit first, then targeted API tests. If full test discovery
is too slow or blocked by unrelated local state, record the blocker and keep the
targeted tests as Phase 5 evidence.
