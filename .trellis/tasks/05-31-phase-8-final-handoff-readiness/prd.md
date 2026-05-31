---
doc_type: prd
task: 05-31-phase-8-final-handoff-readiness
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 8 final handoff readiness

## Goal

Close a final handoff-readiness slice after completed Phase 1-7 directory
restructure work. Phase 8 verifies that the repository, task tree, current
documentation/spec references, and release validation evidence are coherent
enough for a human reviewer to pick up the large uncommitted restructure diff.

## Requirements

- Preserve runtime behavior and HTTP contracts. Phase 8 is an audit, evidence,
  and handoff slice, not a feature or architecture rewrite.
- Respect the dirty worktree from prior phases. Do not revert or normalize
  earlier restructure edits.
- Treat the completed parent task status as historical state. Link Phase 8 as a
  child and record the extra handoff slice, but do not rely on the parent
  lifecycle status for implementation gating.
- Audit high-risk stale references after the restructure:
  - old root resource/runtime paths such as `template_configs/`, `template/`,
    `prompt/`, `tests/golden_samples/`, `tests/p1_translation_samples/`,
    `tests/.tmp/`, and root `data/`
  - removed central packages such as `app.schemas`, `app.repositories`, and old
    `app.services.<business-domain>` imports
  - old core business model modules such as `app.core.job_models`,
    `app.core.resource_models`, and related moved domain models
- Run release validation with the project interpreter.
- Patch only real drift found by the audit. If the audit finds no tracked code
  or docs drift, limit implementation to Trellis planning/acceptance artifacts
  and parent task notes.
- Record exact commands, results, accepted residual references, and remaining
  risks in `acceptance.md`.

## Acceptance Criteria

- [x] Planning artifacts (`prd.md`, `design.md`, `implement.md`) exist before
      implementation starts.
- [x] Phase 8 is linked under `05-31-project-directory-restructure` and started
      after planning.
- [x] Stale old-path and old-package scans have been run; any remaining matches
      are either fixed or explicitly accepted in `acceptance.md`.
- [x] `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`
      passes, or the exact blocker is recorded.
- [x] The parent PRD notes mention Phase 8 completion.
- [x] `acceptance.md` records the audit, validation commands, results, and
      residual risks.

## Notes

- User stated Phase 1-7 are complete and asked to continue the parent task with
  Phase 8, create the subtask, finish planning, then implement directly.
- There is no predefined Phase 8 in the original parent design. This phase is
  intentionally scoped as a final handoff-readiness pass rather than a new code
  migration.
- Completed on 2026-05-31: Phase 8 verified task linkage, stale path/package
  scans, and release validation; no tracked code or docs drift required a
  patch.
