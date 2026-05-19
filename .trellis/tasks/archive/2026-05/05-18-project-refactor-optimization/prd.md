# Project Refactor Optimization

## Goal

Plan a behavior-preserving refactor for the most valuable part of this project,
with clear scope, constraints, and acceptance criteria before any code edits.

## Confirmed Facts

- The repository contains a FastAPI backend under `app/` plus legacy
  conversion/runtime modules covered by characterization tests under `tests/`.
- The first refactor milestone is now explicitly scoped to the backend job flow:
  `app/api/v1/routers/jobs.py`, `app/services/jobs/stage.py`,
  `app/services/jobs/command.py`, `app/services/jobs/lifecycle.py`, and
  `app/api/dependencies.py`.
- The user has approved a medium-strength structural refactor for this
  milestone, not just cosmetic cleanup.
- The first milestone should cover both:
  - router-boundary cleanup in `app/api/v1/routers/jobs.py`
  - internal helper extraction and repeated state-flow consolidation in
    `app/services/jobs/stage.py`
- The stage refactor must not change job-state-machine semantics.
- The user allows introducing nearby new files/modules for the split, as long
  as the work stays within the current directory neighborhoods and avoids a
  large-scale move.
- The current session already has unrelated in-progress work in the working
  tree, so refactor changes must stay narrowly scoped and must not overwrite
  existing user edits.
- The biggest backend hotspots by size are:
  - `app/api/v1/routers/jobs.py` (522 lines)
  - `app/services/jobs/stage.py` (497 lines)
  - `app/services/jobs/lifecycle.py` (193 lines)
  - `app/api/dependencies.py` (185 lines)
  - `app/services/jobs/command.py` (157 lines)
- The backend currently mixes several concerns around the job flow:
  - HTTP request parsing and response mapping in routers
  - job orchestration across `command`, `stage`, and `lifecycle` services
  - file-backed persistence in `FileJobRepository`
  - callback/auth/validation logic in `app/api/dependencies.py`
- `app/api/dependencies.py` currently mixes:
  - generic FastAPI runtime/request dependencies (`get_runtime`, `get_trace_id`)
  - jobs access guards (`require_jobs_access`, `require_job_ops_access`)
  - MinerU callback-specific normalization and verification helpers used only by
    `app/api/v1/routers/mineru_callbacks.py`
- The user wants the same milestone to locally split `app/api/dependencies.py`
  so generic request/job-access helpers and callback-specific guards are no
  longer mixed, while keeping all auth/validation behavior unchanged.
- There is at least one current layering smell worth considering during design:
  `app/api/v1/routers/mineru_callbacks.py` imports
  `_detail_response_from_record` from `app/api/v1/routers/jobs.py`.
- Existing architecture notes already predicted that once `jobs.py` kept growing
  past ~500 lines, a future refactor should consider splitting “upload entry /
  query download / ops actions” into separate routers.
- Existing backend behavior is covered mainly by
  `tests/test_fastapi_jobs_backend.py`; legacy conversion behavior is pinned by
  multiple `test_*_characterization.py` modules.
- Default refactor assumption is behavior-preserving unless the user explicitly
  asks for behavior changes.

## Requirements

- Produce a refactor plan before implementation.
- Keep behavior unchanged unless a later explicit decision says otherwise.
- Base the plan on repository evidence, not generic cleanup advice.
- Identify the smallest high-value refactor scope that can be verified safely.
- Preserve existing public API contracts, persisted job state semantics, and
  current test-observed behavior within the chosen scope.
- Prefer meaningful complexity reduction over cosmetic cleanup.
- Allow internal module and helper boundary changes inside the backend job flow
  as long as HTTP contracts, job status semantics, and repository behavior stay
  unchanged.
- For `stage.py`, allow helper extraction and duplicated transition/log/event
  flow consolidation, but do not redefine the dispatch stages or legal status
  transitions in this milestone.
- New companion modules are allowed near `app/api/v1/routers/` and
  `app/services/jobs/`, but the milestone should avoid package-wide relocation
  or a new top-level abstraction layer.
- New companion modules may also be introduced under `app/api/` when needed to
  separate generic request dependencies from callback-specific guards, but this
  should remain a local cleanup rather than a new framework layer.

## Acceptance Criteria

- [ ] Refactor target scope is explicitly chosen.
- [ ] The first milestone is bounded within the backend job flow files listed
  above.
- [ ] The allowed depth is medium-strength structural split, not full
  architectural rewrite.
- [ ] The first milestone covers both API-router boundary cleanup and `stage.py`
  internal helper consolidation.
- [ ] New files/modules, if introduced, remain close to the current router/jobs
  directories and do not trigger a large-scale move.
- [ ] Any `app/api/dependencies.py` cleanup remains behavior-preserving and
  stays local to the existing API package.
- [ ] PRD records confirmed facts, constraints, and out-of-scope areas.
- [ ] For the chosen scope, the plan identifies the main code smells, intended
  preserved behavior, and verification path.
- [ ] If the scope is complex, follow-up `design.md` and `implement.md` will be
  required before any code changes start.

## Likely Out Of Scope

- Broad whole-repo cleanup across backend and all conversion/runtime modules in
  one pass.
- Behavior-changing feature work disguised as refactor.
- Rewriting the legacy conversion pipeline without first narrowing the target.
- Replacing the file repository abstraction or changing HTTP route contracts in
  this milestone.
- Changing dispatch stage names, job status semantics, or callback state-machine
  rules in `JobStageService`.

## Open Questions

- None at the PRD level. Remaining work is to draft and review `design.md` and
  `implement.md`.

## Notes

- Planning is in progress via `trellis-brainstorm`.
