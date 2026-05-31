# Phase 1 root resources runtime layout

## Goal

Implement the first directory-restructure slice: clean the repository root,
move versioned resources and runtime state into explicit homes, and update
local development/documentation paths without changing product behavior.

## Requirements

- Move local process entrypoints from the repository root to `scripts/dev/`.
- Move conversion-only runtime configuration from root-level `config.py` to the
  `app/conversion/` package.
- Consolidate versioned non-code assets under `resources/`.
- Change the local mutable runtime root from `data/` to `var/`.
- Move test sample assets under `tests/fixtures/` and use `tests/tmp/` for test
  scratch files.
- Reorganize docs so current runbooks and historical planning drafts are
  separated.
- Keep container assets under `docker/` and host/environment deployment assets
  under `deploy/`.
- Do not add old-path compatibility shims. Update code, tests, docs, config
  defaults, and examples to the new paths directly.
- Do not move business packages into `app/domains/` in this phase. Domain-first
  migration is a later child task.
- Preserve product behavior: HTTP API contract, conversion output, and worker
  process semantics must not change.

## Acceptance Criteria

- [ ] Repository root no longer contains `run_api.py`, `run_worker.py`,
      `run_document_worker.py`, `config.py`, `template/`, `template_configs/`,
      or `prompt/`.
- [ ] New direct-run entrypoints exist under `scripts/dev/` and remain
      PyCharm-friendly without required CLI arguments.
- [ ] Versioned resources live under `resources/` and all code/test references
      point to the new paths.
- [ ] Runtime state defaults point to `var/`, with `var/` ignored by git.
- [ ] Test fixture paths point to `tests/fixtures/`, and scratch paths point to
      `tests/tmp/`.
- [ ] Current docs and examples describe the new paths; historical planning
      files are archived under `docs/archive/planning/`.
- [ ] Targeted tests for conversion config, render config, fixture manifests,
      backend config/logging, and path-dependent scripts pass.
- [ ] `rg` checks show no stale old-path references outside historical archive
      content or explicitly intentional migration notes.

## Notes

- Parent task: `.trellis/tasks/05-31-project-directory-restructure`.
- This child covers only Phase 1 from the parent design. Later phases require
  separate review before implementation.
