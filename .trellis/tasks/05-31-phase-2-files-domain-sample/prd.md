# Phase 2 files domain sample

## Goal

Implement the second directory-restructure slice as a domain-first sample for
the `files` resource, proving the target `app/domains/<domain>/` package shape
without changing HTTP behavior or persistence architecture.

## Requirements

- Move the `files` domain implementation into `app/domains/files/`.
- Keep the external API contract stable:
  - existing `/api/v1/files/*` paths
  - request and response schemas
  - auth requirements
  - status codes and error semantics
  - audit event behavior
- Keep `app/api/v1/router.py` as the API v1 aggregation layer; it should include
  the files domain router directly.
- Keep existing repository adapters under `app/repositories/` in this phase.
  Do not split file/sqlite/mysql persistence adapters; that is parent Phase 3.
- Move the files-owned repository port into the files domain, while updating
  non-files callers to import that port from the owning domain.
- Do not migrate other domains in this phase:
  - document jobs
  - jobs
  - audit
  - templates
  - term rules
  - translation
  - resource versions
- Do not keep compatibility shims for old files module paths. Update imports
  directly.
- Preserve product behavior: no OpenAPI contract change beyond harmless
  generation ordering, no runtime process semantic change, and no persistence
  data-shape change.
- Update docs/specs only where they describe the files package location or the
  domain-first sample pattern.

## Acceptance Criteria

- [ ] `app/domains/files/` exists with the agreed module shape.
- [ ] Files-owned modules move to the domain package:
      `models.py`, `schemas.py`, `router.py`, `service.py`, `retention.py`,
      `validation.py`, and `repository.py`.
- [ ] Old files module paths are removed rather than kept as re-export shims:
      `app/core/file_models.py`, `app/schemas/files.py`,
      `app/api/v1/routers/files.py`, and `app/services/files/`.
- [ ] Active code imports files types, schemas, services, validation, retention,
      and repository port from `app.domains.files.*`.
- [ ] `app/api/v1/router.py` includes `app.domains.files.router`.
- [ ] File/sqlite/mysql repository adapters still compile and satisfy the
      moved files repository port.
- [ ] Targeted tests for files API, document-job usage of files, retention, and
      database repository behavior pass.
- [ ] OpenAPI export/check shows no behavioral API contract drift.
- [ ] Stale import check shows no active references to old files module paths.

## Notes

- Parent task: `.trellis/tasks/05-31-project-directory-restructure`.
- Implements parent Phase 2 and CodeStable scan item #7 only.
- Later phases require separate review before implementation.
