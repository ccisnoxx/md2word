# Phase 7 config logging runtime support

## Goal

Close the configuration, logging, and runtime support slice after the completed
Phase 1-6 restructure work. Phase 7 verifies that a new local or deployment
environment can follow the current docs, inspect readiness, and collect useful
logs without relying on chat-only knowledge.

## Requirements

- Preserve runtime behavior, HTTP contracts, and the directory layout completed
  by Phases 1-6.
- Treat this as a support/acceptance slice first. Make code or documentation
  edits only where the current implementation and current docs disagree.
- Verify the current `Settings` environment surface, `.env.example`,
  `docs/dev/backend-local-minimal-env-and-commands.md`,
  `docs/dev/runtime-observability-and-health.md`,
  `docs/runbooks/backend.md`, and backend logging spec describe the same
  configuration, readiness, and logging behavior.
- Keep readiness semantics explicit:
  - blocking checks are limited to required runtime directories/assets and
    default translation availability when `DEFAULT_TRANSLATION_MODE=en2zh`
  - MinerU, translation in direct mode, and stage-spool observations remain
    non-blocking warnings
- Keep logging centralized in `app/core/logging.py`, configured from
  `Settings.log_format`, and consumed through the existing `access`,
  `business`, and `system` named loggers.
- Keep validation narrow but sufficient: health readiness tests, logging tests,
  and the release check must pass or record an exact blocker.
- Respect the dirty worktree from previous phases. Do not revert previous
  directory restructure changes.

## Acceptance Criteria

- [x] Planning artifacts (`prd.md`, `design.md`, `implement.md`) exist before
      implementation starts.
- [x] Current code/docs/specs have been audited for Phase 7 configuration,
      readiness, and logging consistency.
- [x] Any discovered stale Phase 7 docs/spec references are updated, or the
      acceptance note records why no edit was required.
- [x] `tests.test_backend_logging` passes.
- [x] Health readiness coverage in `tests.test_fastapi_jobs_backend` passes.
- [x] `scripts/ops/check_release.py` passes, or a blocker is recorded with the
      exact failing command and output.
- [x] `acceptance.md` records the audit, validation commands, results, and
      residual risks.

## Notes

- User stated Phases 1-6 are complete and asked to create Phase 7, finish
  planning, then implement directly.
- The parent task was already marked `completed` before this child was created;
  Phase 7 therefore avoids changing parent lifecycle state unless Trellis
  requires it.
- Completed on 2026-05-31: Phase 7 audited config/logging/readiness support,
  corrected ignored local `.env` path drift from the old layout, smoke-tested
  `/health/ready`, and passed targeted logging/readiness/release validation.
