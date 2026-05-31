---
doc_type: design
task: 05-31-phase-8-final-handoff-readiness
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 8 design

## Summary

Phase 8 is a final handoff-readiness pass for the completed directory
restructure. The codebase has already moved through root layout cleanup, domain
migration, persistence split, cleanup/spec updates, integration acceptance, and
configuration/logging/runtime support. This phase verifies that the result is
reviewable and that no obvious stale guidance remains in the tracked current
surface.

## Boundaries

In scope:

- Trellis task artifacts for Phase 8 and parent task notes
- current backend specs under `.trellis/spec/backend/`
- current docs under `docs/api`, `docs/dev`, `docs/deploy`, `docs/runbooks`,
  and `docs/testing`
- tracked code and tests under `app`, `scripts`, and `tests`
- `.env.example`, `.gitignore`, `.dockerignore`, `docker/`, and `deploy/`
- release validation through `scripts/ops/check_release.py`

Out of scope:

- API contract changes
- additional package moves or domain reshaping
- new compatibility shims for old root paths or removed packages
- changing ignored local secrets or environment values except recording
  residual risk when relevant
- committing, pushing, or archiving the task unless the user explicitly asks

## Current Target Shape

The expected result is a coherent handoff state:

- the parent task has eight child phases recorded
- current specs and docs describe the post-restructure layout
- high-risk stale references are absent from current tracked code/docs/specs or
  documented as intentionally historical/negative references
- release validation passes with the project conda interpreter
- the acceptance note gives enough command evidence for a reviewer to evaluate
  the final state without replaying the full conversation

## Risks

- Broad `rg` scans can flag historical archived docs or negative examples. The
  implementation should distinguish true current guidance drift from accepted
  history.
- The worktree contains large uncommitted restructure changes from prior
  phases. Phase 8 must avoid overwriting or reverting that work.
- Release validation can fail for environment reasons. If that happens, record
  the exact command and failure output instead of claiming release readiness.

## Validation Strategy

- Run focused stale-reference scans across current code, tests, scripts, docs,
  deployment files, examples, and backend specs.
- Run the release check with
  `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`.
- If scans reveal real drift, patch the smallest owning file and rerun the
  affected scan.
- Record all evidence in `acceptance.md` and update Phase 8 acceptance
  checkboxes.
