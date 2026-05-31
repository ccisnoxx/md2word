# Project directory restructure

## Goal

Restructure the local project directory layout so it is easier to navigate and
matches the repository's documented coding rules, while preserving current
runtime behavior.

## Requirements

- Preserve product behavior: no HTTP API contract changes, no conversion output
  changes, and no worker/API process semantics changes. Directory paths,
  configuration defaults, and documented commands may change when required by
  the new structure.
- Treat this as a behavior-preserving refactor. Any desired behavior change,
  architecture redesign, or new capability must become a separate task.
- Keep the plan compatible with the existing Trellis and CodeStable project
  knowledge under `.trellis/` and `.codestable/`.
- Keep `app/` as the primary Python application package. Do not migrate the
  project to a `src/md2word/` package layout in this refactor.
- Prioritize cleanup of the repository root and non-code resource/runtime
  boundaries, but include `app/` internal restructuring when a code-structure
  scan shows that business packages violate the target rules.
- Keep external product behavior stable, but allow internal module boundaries,
  package ownership, and architecture-facing code organization to change when
  needed to reach a clean structure.
- Evaluate a domain-first internal `app/` structure as the main target
  candidate. Candidate domains include jobs, document jobs, files, templates,
  term rules, translation, and resource versions.
- If the domain-first internal structure is selected, implement it in staged
  slices rather than moving every technical layer at once.
- Use the `files` domain as the first sample slice if the design approves a
  domain-first migration.
- Preserve `app/api/` as the HTTP composition and version aggregation layer.
  Domain routers may move into `app/domains/<domain>/`, with `app/api/v1/router.py`
  including them.
- Include persistence architecture restructuring in this task as an explicit
  later phase. Do not mix the repository rewrite into the first domain sample
  migration unless the design proves that coupling is required.
- Target persistence structure should separate domain repository ports from
  backend-specific infrastructure adapters. Prefer an
  `app/infrastructure/persistence/` tree grouped by storage backend and split
  by domain responsibility inside each backend.
- Narrow `app/core/` to true cross-domain infrastructure primitives. Move
  business-domain models out of `app/core/*_models.py` into their owning
  domain packages during the staged internal restructure.
- Treat audit and resource versioning as first-class domains rather than loose
  core/service modules.
- Keep `app/conversion/` as a top-level conversion engine/library package,
  separate from `app/domains/`.
- Move API request/response schemas into owning domain packages. The target
  structure should not keep `app/schemas/` as a long-term central schema
  package.
- Keep `app/workers/` as a top-level process/queue composition layer. Worker
  modules should call domain services rather than own business logic.
- Keep `app/clients/` as a top-level outbound integration layer for external
  service protocol clients. Clarify that HTTP/protocol details for external
  systems belong there rather than inside domain services.
- Directory rules may be updated when the current documentation preserves a
  legacy messy layout. Existing docs are evidence of current behavior, not an
  unquestionable target state.
- Existing configuration defaults and documentation references are not target
  constraints for this restructure when they mainly reflect the old messy
  layout. Update them to match the new directory rules.
- Preserve PyCharm-friendly direct execution for local entrypoints, but the
  entrypoint files may move out of the repository root if the new layout keeps
  a clear compatibility and documentation path.
- Move local process entrypoints out of the repository root into a clearer
  scripts namespace, with `scripts/dev/` as the target location for direct
  development runners.
- Move legacy conversion-only root configuration out of root-level `config.py`
  into the `app/conversion/` package. Do not keep root-level re-export shims.
- Move versioned non-code assets out of scattered root directories into a
  unified `resources/` tree. Target buckets are templates, template config,
  term rules/translation terms, and prompts.
- Move local mutable runtime state out of root-level `data/` into root-level
  `var/`, so versioned resources, test fixtures, and runtime state have clear
  separate homes.
- Move test fixture assets under `tests/fixtures/` and use a visible
  `tests/tmp/` scratch directory instead of hidden fixture/runtime directories.
- Reorganize `docs/` so current operational/developer/API documentation is
  separate from historical planning drafts and implementation notes.
- Formalize deployment file ownership: keep container build/compose assets under
  `docker/`, and keep host/environment/reverse-proxy deployment material under
  `deploy/`.
- Keep tool-required hidden directories such as `.claude/`, `.cursor/`,
  `.trellis/`, `.codestable/`, `.idea/`, and VCS/config dotfiles at the
  repository root when their tools expect that location.
- Because the project is still in development and not production-stable, prefer
  direct migration to the new paths over compatibility fallbacks or duplicate
  old-path support.
- Keep all nine scan findings in the overall task scope, but approve
  implementation one phase at a time. Phase 1 is the first implementation slice
  to prepare; later phases require separate review before code moves.

## Acceptance Criteria

- [x] A target directory layout is documented before implementation starts.
- [x] The implementation plan lists each move/rename and its import or
      compatibility impact.
- [x] All moved Python modules keep imports working through updated references,
      without root-level compatibility shims.
- [x] Documented local commands for API and workers are updated to the new
      script paths.
- [x] The smallest useful test set proves API wiring, worker startup imports,
      and conversion runtime imports after the restructure.

## Notes

- Confirmed on 2026-05-31: scope is strictly behavior-equivalent directory
  restructuring.
- Confirmed on 2026-05-31: keep the existing `app/` package layout instead of
  moving to `src/md2word/`.
- Confirmed on 2026-05-31: root/resource layout cleanup has priority, but
  `app/` internals are in scope if they do not meet the target code structure.
- Confirmed on 2026-05-31: deeper business-package restructuring is acceptable
  even when it approaches architecture rewrite, as long as the external behavior
  preservation contract remains explicit.
- Confirmed on 2026-05-31: use a domain-first `app/domains/` layout as the
  candidate design direction for internal restructuring evaluation, rather than
  assuming the existing technical-layer layout is the target.
- Confirmed on 2026-05-31: any domain-first migration must be split into
  reviewable phases, not one all-at-once package rewrite.
- Confirmed on 2026-05-31: `files` is the first sample domain for evaluating
  and proving the domain-first structure.
- Confirmed on 2026-05-31: keep `app/api/` as a versioned HTTP composition
  layer even if resource router implementations move under domain packages.
- Confirmed on 2026-05-31: the storage/repository architecture may be rewritten
  as part of this restructure, but it must be planned as its own staged phase
  rather than hidden inside the initial domain migration.
- Confirmed on 2026-05-31: persistence target should avoid all-purpose
  `*JobRepository` adapters and instead use domain ports plus backend-specific
  adapters under infrastructure.
- Confirmed on 2026-05-31: `app/core/` should not remain a bucket for business
  domain models; domain models should move into domain packages.
- Confirmed on 2026-05-31: audit and resource versioning should become
  domain-owned packages.
- Confirmed on 2026-05-31: keep conversion as top-level `app/conversion/`, not
  as a jobs/document_jobs domain subpackage.
- Confirmed on 2026-05-31: `app/schemas/` should disappear in the final target
  layout; schemas belong to domains.
- Confirmed on 2026-05-31: keep workers as top-level `app/workers/`.
- Confirmed on 2026-05-31: keep `app/clients/`, but define it specifically as
  the outbound integration client layer.
- Confirmed on 2026-05-31: the refactor may update `.trellis` directory
  structure rules instead of preserving root-level `run_*.py` as the desired
  convention.
- Confirmed on 2026-05-31: target development entrypoints should live under
  `scripts/dev/`, not as new root-level `run_*.py` files.
- Confirmed on 2026-05-31: root-level `config.py` should no longer be the
  target home for conversion runtime configuration; move it under
  `app/conversion/`.
- Confirmed on 2026-05-31: versioned assets currently under `template/`,
  `template_configs/`, and `prompt/` should be consolidated under
  `resources/`.
- Confirmed on 2026-05-31: do not retain old root entrypoint/config/resource
  compatibility shims; update code, tests, and docs to the new paths directly.
- Confirmed on 2026-05-31: prioritize the new code organization rules over
  preserving existing defaults or documentation paths.
- Confirmed on 2026-05-31: target runtime state root is `var/`, not `data/`.
- Confirmed on 2026-05-31: test sample assets should move under
  `tests/fixtures/`.
- Confirmed on 2026-05-31: documentation restructure is in scope; historical
  planning material should move under an archive area rather than sit beside
  current guides.
- Confirmed on 2026-05-31: deployment and container files should be organized
  as `docker/` for image/compose assets and `deploy/` for environment, nginx,
  and host deployment assets.
- Confirmed on 2026-05-31: tool convention hidden directories stay at the root
  and are not a target of this restructure.
- Confirmed on 2026-05-31: all nine scan findings remain in scope for the
  larger restructure, but only Phase 1 should be prepared for initial
  implementation approval. Each later phase needs its own review gate.
- Completed on 2026-05-31: Phase 5 removed transition packages, updated
  Trellis/CodeStable/docs layout knowledge, and passed release/full unittest
  validation.
- Completed on 2026-05-31: Phase 6 added a final integration acceptance child
  task, refreshed stale backend spec references, and passed release validation.
- Completed on 2026-05-31: Phase 7 added a configuration/logging/runtime
  support child task, corrected ignored local `.env` path drift from the old
  layout, smoke-tested readiness startup, and passed release validation.
- Completed on 2026-05-31: Phase 8 added a final handoff-readiness child task,
  verified stale path/package scans, and passed release validation without
  requiring tracked runtime, docs, or spec patches.
- Completed on 2026-05-31: Phase 9 narrowed `app/core/` to infrastructure
  primitives, split the remaining central API schema module into auth/health
  router-local schema companions, and passed targeted, release, stale-import,
  and full unittest validation.
