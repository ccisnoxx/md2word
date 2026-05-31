# Phase 5 cleanup docs and spec

## Goal

Finish the project-directory restructure after Phases 1-4 by removing obsolete
transition packages and updating the project structure documentation to match
the final domain-first layout.

## Requirements

- Preserve runtime behavior and HTTP contracts. This phase should remove stale
  module locations and documentation drift, not introduce new product behavior.
- Delete transition-only packages and modules after active imports are removed:
  `app/schemas/`, `app/repositories/`, and old domain-owned `app/services/*`
  package shells that now contain no source files.
- Move the remaining non-domain auth/health API schemas out of `app/schemas/`
  into the API v1 layer so `app/schemas/` can disappear without creating a new
  compatibility facade.
- Do not delete `app/services/auth`, `app/services/document_ir`,
  `app/services/renderer`, or `app/services/health_service.py`; those are not
  Phase 4 business-domain packages and are still active runtime services.
- Update `.trellis/spec/backend/directory-structure.md` to describe the
  current target layout: domain-owned business code, backend-specific
  persistence adapters, `resources/`, `var/`, `scripts/dev/`, and no central
  `app/schemas` or `app/repositories` package.
- Update `.codestable/architecture/` pages that describe backend physical
  structure and conversion resource paths so future agents see the new layout.
- Update current API/developer docs that list source paths or local layout
  rules affected by the cleanup. Historical archive content can retain old
  paths.
- Respect the existing dirty worktree from Phases 1-4; do not revert earlier
  moves.
- Use `/Users/sc/miniconda3/envs/md2word/bin/python` for verification.

## Acceptance Criteria

- [x] Active imports under `app/`, `tests/`, and `scripts/` no longer reference
      `app.schemas` or `app.repositories`.
- [x] `app/schemas/` and `app/repositories/` have no tracked source modules.
- [x] Domain-owned docs/specs point to `app/domains/*` and
      `app/infrastructure/persistence/*` instead of old central packages.
- [x] `.trellis/spec/backend/directory-structure.md` reflects the final
      directory structure after the staged migration.
- [x] `.codestable/architecture/ARCHITECTURE.md` and relevant detailed pages
      describe the final backend/resource/runtime layout.
- [x] Targeted tests covering API wiring and health/auth schemas pass, or any
      blocker is recorded with exact command output.

## Notes

- User stated Phases 1-4 are complete and asked to create Phase 5, finish
  planning, then implement directly.
- Phase 4 deliberately left cleanup and documentation updates for this task.
