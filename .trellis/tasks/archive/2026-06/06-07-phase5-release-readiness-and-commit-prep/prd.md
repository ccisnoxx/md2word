# Phase 5 release readiness and commit prep

## Goal

Prepare the accumulated Phase 5 "Production Ops Integration & Automation" readiness work for a clean review/commit without changing product behavior.

This task audits the current dirty worktree, maps changed files to archived Phase 5 tasks, runs a release-prep verification set that avoids the PDF -> Word main workflow and real external side effects, and writes a commit/PR preparation report.

## Requirements

- Inventory all current modified/untracked files and classify them as:
  - Phase 5 product/runtime changes.
  - Phase 5 Trellis archive evidence.
  - CodeStable planning artifacts.
  - local/private configuration or unrelated changes that should not be committed by default.
- Confirm there are no active Trellis tasks before and after the release-prep task.
- Confirm Phase 5 release scope remains readiness-only:
  - fake/dry-run/preview controls.
  - signed cleanup plan/history/lock evidence.
  - no real alert delivery.
  - no real provider cancellation.
  - no real S3 deletion.
  - no autonomous destructive scheduler.
  - no quota upload blocking.
- Run a broad but safe verification set:
  - targeted Phase 5 FastAPI tests.
  - persistence adapter contract tests.
  - OpenAPI export and snapshot tests.
  - frontend production build.
  - Trellis validation.
  - whitespace diff check.
- Check whether `.git/index.lock` / git staging remains blocked in this environment and record the result.
- Produce commit preparation guidance:
  - recommended commit grouping.
  - files that likely should be excluded or reviewed separately.
  - residual risks.
  - exact verification commands run.

## Out of Scope

- No git stage, commit, branch, push, or PR creation unless separately requested.
- No product code behavior changes.
- No destructive scheduler or cleanup execution outside existing test fixtures.
- No real Slack/email/webhook delivery.
- No real provider cancellation.
- No real S3 deletion.
- No quota enforcement.
- No pdf-mineru parsing, MinerU recovery query/download, translation provider calls, or Word generation.

## Acceptance Criteria

- [x] Current worktree inventory is recorded.
- [x] Phase 5 archive coverage is recorded.
- [x] Verification commands are run or explicitly skipped with reason.
- [x] Commit grouping recommendation is recorded.
- [x] Files requiring separate review/exclusion are identified.
- [x] Git staging/index-lock status is recorded.
- [x] Trellis task validates and is archived.

## Notes

- The worktree is already dirty from prior Phase 5 slices. Do not revert user or prior-agent changes.
- If validation finds a defect, record it as release risk unless the fix is trivial and directly required for truthful release prep.
