# Phase 6 final integration acceptance

## Goal

Close the project-directory restructure with a final integration acceptance
pass after Phases 1-5. This phase validates that code, current documentation,
Trellis specs, and CodeStable architecture all describe the same final
domain-first layout and runtime paths.

## Requirements

- Preserve runtime behavior and HTTP contracts. Phase 6 is a verification and
  documentation/spec consistency pass, not a new restructure phase.
- Keep the parent task scope unchanged: `app/` remains the primary package,
  business code stays domain-owned, persistence stays under
  `app/infrastructure/persistence/`, versioned assets stay under `resources/`,
  and mutable runtime state stays under `var/`.
- Audit active code, tests, scripts, current docs, `.trellis/spec/backend/`,
  and `.codestable/architecture/` for stale references to old paths and old
  packages introduced before Phases 1-5.
- Fix stale current documentation/spec references when they conflict with the
  final implemented layout. Historical archive documents may keep old paths.
- Run the smallest global validation that proves the staged restructure is
  integrated: stale-reference audits, targeted backend tests, and the release
  check.
- Respect the existing dirty worktree from Phases 1-5. Do not revert previous
  moves or unrelated local files.
- Use `/Users/sc/miniconda3/envs/md2word/bin/python` for verification.

## Acceptance Criteria

- [x] Parent-task acceptance criteria are rechecked against the current tree.
- [x] Active code/tests/scripts have no stale imports for removed
      `app.schemas`, `app.repositories`, old business `app.services.*`, or old
      `app.core.*_models` modules.
- [x] Current specs and architecture docs do not describe old root `data/`,
      `template_configs/`, `template/`, `prompt/`, `app/schemas/`, or
      `app/repositories/` locations as the current target.
- [x] Any stale current docs/specs found during the audit are updated to the
      final layout.
- [x] Targeted backend tests and `scripts/ops/check_release.py` pass, or a
      blocker is recorded with exact command output.
- [x] A Phase 6 acceptance note records the validation commands, results, and
      residual risks.

## Notes

- User stated Phases 1-5 are complete and asked to create Phase 6, finish
  planning, then implement directly.
- The parent task was already marked `completed` before this child was created;
  Phase 6 therefore avoids changing parent lifecycle state unless Trellis
  requires it.
- Completed on 2026-05-31: Phase 6 updated stale backend spec references and
  passed final integration validation.
