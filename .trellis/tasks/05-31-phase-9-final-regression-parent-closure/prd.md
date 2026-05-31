---
doc_type: prd
task: 05-31-phase-9-final-regression-parent-closure
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 9 narrow core and eliminate central schemas

## Goal

Finish the remaining structure gap after Phase 1-8 by narrowing `app/core/` to
true cross-domain infrastructure primitives and eliminating the remaining
central API schema module.

## Requirements

- Preserve runtime behavior and HTTP contracts. Phase 9 is a module ownership
  cleanup, not a product behavior change.
- Move auth user context models out of `app/core/` into the auth service
  boundary.
- Move Document IR records out of `app/core/` into the Document IR service
  boundary.
- Move renderer template config records out of `app/core/` into the renderer
  service boundary.
- Split `app/api/v1/schemas.py` into route-specific auth/health schema
  companion modules under `app/api/v1/routers/`, then delete the central file.
- Update imports, tests, Trellis spec, CodeStable architecture, and API docs
  that refer to the old central modules.
- Respect the existing dirty worktree from completed Phase 1-8 work. Do not
  revert or normalize unrelated prior-phase edits.
- Run targeted tests, stale-import scans, and release validation. If a command
  fails because of a real current issue, make the smallest behavior-preserving
  fix and rerun the relevant command.
- Record command evidence, results, changes, and residual risks in
  `acceptance.md`.
- Update the parent PRD notes to mention Phase 9 completion.

## Acceptance Criteria

- [x] `app/core/` contains only infrastructure primitives such as config,
      logging, errors, runtime, and package metadata.
- [x] No active code imports `app.core.auth_models`,
      `app.core.document_ir_models`, or `app.core.template_config_models`.
- [x] `app/api/v1/schemas.py` is removed and no active code imports
      `app.api.v1.schemas`.
- [x] Auth/health API models remain Pydantic response/request models with the
      same external fields.
- [x] Trellis spec, CodeStable architecture, and API docs reflect the new
      module ownership.
- [x] Targeted tests and stale-import scans pass, or the exact blocker and root
      cause are recorded.
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`
      passes, or the exact blocker and root cause are recorded.
- [x] The parent PRD notes mention Phase 9 completion.
- [x] `acceptance.md` records the validation commands, results, changes, and
      residual risks.
