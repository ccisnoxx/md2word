# Phase 3 persistence architecture split

## Goal

Implement the parent task's third slice: split the current all-purpose metadata
repository adapters into backend-specific infrastructure packages and
domain/port-specific adapters, while preserving existing storage behavior,
runtime semantics, and API contracts.

## Requirements

- Create the persistence infrastructure package:
  `app/infrastructure/persistence/`.
- Split the current all-purpose adapters by backend:
  - file backend
  - sqlite backend, currently selected by `jobs_repository_backend="database"`
  - mysql backend
- Within each backend, split persistence responsibilities by current port /
  domain responsibility:
  - job snapshots
  - job events
  - job files / artifact metadata
  - document files
  - document jobs
  - document job events
  - stage messages
  - audit events
  - resource versions where currently supported
- Keep persisted data shape stable:
  - existing file backend paths and JSON / JSONL payloads
  - existing sqlite tables and payload columns
  - existing mysql tables and payload columns
  - existing resource-version mysql behavior
- Move sqlite and mysql schema bootstrap into backend-specific `schema.py`
  modules.
- Update runtime composition in `app/main.py` so services receive explicit
  per-port adapters instead of one all-purpose repository instance.
- Keep the `files` repository port in `app.domains.files.repository`.
- Keep non-files repository ports in their current transition location until
  the later domain migration phase moves their owning domains. Do not start
  Phase 4 domain moves in this task.
- Do not add compatibility shims for old all-purpose repository modules or
  class imports. Update code, tests, and scripts to import the new modules
  directly.
- Do not change HTTP routes, OpenAPI payload schemas, auth behavior, worker
  dispatch semantics, stage replay semantics, audit event content, or artifact
  storage behavior.
- Do not introduce a migration framework, new production dependency, or new
  database feature such as cross-process locks.
- Keep term-rules runtime store migration out of this phase unless implementation
  proves it is required to remove an all-purpose adapter dependency. Term-rules
  domain ownership remains a later phase.

## Acceptance Criteria

- [ ] `app/infrastructure/persistence/` exists with file, sqlite, and mysql
      backend packages.
- [ ] All-purpose repository classes are no longer imported by active code:
      `FileJobRepository`, `DatabaseJobRepository`, `MysqlJobRepository`.
- [ ] Runtime wiring assigns distinct adapters to the relevant `AppRuntime`
      ports instead of assigning one repository instance to every port.
- [ ] File backend behavior is preserved for local development:
      job metadata, job files, job events, document files, document jobs,
      stage messages, and audit events still use the same on-disk layout.
- [ ] Sqlite backend behavior is preserved:
      schema bootstrap, row payload shape, and repository method behavior match
      the current `DatabaseJobRepository` contract.
- [ ] MySQL backend behavior is preserved:
      schema bootstrap, fake-connection tests, metadata methods, and resource
      version methods match the current `MysqlJobRepository` contract.
- [ ] Existing repository and integration tests pass after their imports and
      direct test access are updated to the new per-port adapters.
- [ ] Shadow-copy, artifact storage, resource-versioning, and FastAPI workflow
      tests pass.
- [ ] Stale import audit shows no active imports of old all-purpose repository
      modules/classes.
- [ ] No OpenAPI contract drift is introduced by persistence-only changes.

## Notes

- Parent task: `.trellis/tasks/05-31-project-directory-restructure`.
- Implements parent Phase 3 and CodeStable scan item #8 only.
- Phase 1 and Phase 2 are assumed complete in the working tree.
- Later domain migrations and cleanup phases require separate review.
