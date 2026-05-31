# Phase 4 remaining domain migrations

## Goal

Move the remaining backend business resources into domain-owned packages under
`app/domains/`, after the Phase 2 `files` sample and Phase 3 persistence split,
while preserving external API behavior and runtime semantics.

## Requirements

- Migrate only Phase 4 domains in this order:
  1. `audit`
  2. `resources`
  3. `translation`
  4. `document_jobs`
  5. `templates`
  6. `term_rules`
  7. `jobs`
- Do not do Phase 5 cleanup. In particular, do not delete the remaining
  central packages merely because they become smaller, do not rewrite
  architecture/spec docs beyond this task's planning artifacts, and do not do
  broad final cleanup.
- Preserve HTTP paths, methods, status codes, and response payload contracts.
- Preserve worker/API process behavior and storage behavior.
- Keep `app/api/` as the versioned HTTP composition layer. It should include
  routers from domain packages after each migration.
- Move domain-owned model, schema, service, router, and repository port code
  into the owning `app/domains/<domain>/` package.
- Keep concrete persistence adapters under `app/infrastructure/persistence/`.
  Only update imports to domain-owned models and ports.
- Keep cross-domain primitives in `app/core/` only when they are not owned by a
  Phase 4 domain.
- Avoid compatibility shims for old module paths. Update active imports
  directly.
- Respect the existing dirty worktree and do not revert Phase 1-3 changes.
- Use `/Users/sc/miniconda3/envs/md2word/bin/python` for verification.

## Acceptance Criteria

- [x] `app/domains/audit/` owns audit models, service, and repository port.
- [x] `app/domains/resources/` owns resource-version models, service, and
      repository port.
- [x] `app/domains/translation/` owns translation models, translation provider
      services, translation audit, term-version resolution, translation profile
      schemas/service/router.
- [x] `app/domains/document_jobs/` owns document job models, schemas, service,
      execution queue, router, and repository ports.
- [x] `app/domains/templates/` owns template models, schemas, read/versioning
      service, and router.
- [x] `app/domains/term_rules/` owns term-rule models, schemas, services,
      router modules, file repository, and repository port.
- [x] `app/domains/jobs/` owns job models, path helpers, workflow rules,
      schemas, service modules, router modules, callback helper, and repository
      ports.
- [x] `app/api/v1/router.py` includes migrated routers from their domain
      packages.
- [x] Active imports from migrated old paths are gone in `app/`, `tests/`, and
      `scripts/`.
- [x] Domain-specific tests pass after each migration checkpoint or the failure
      is recorded with a clear blocker.
- [x] OpenAPI check does not show unreviewed contract drift.

## Notes

- User explicitly approved continuing Phase 4 after Phase 1-3 and asked to
  complete planning then implement directly.
- Phase 5 is intentionally out of scope for this task.
