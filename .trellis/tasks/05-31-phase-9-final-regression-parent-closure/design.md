---
doc_type: design
task: 05-31-phase-9-final-regression-parent-closure
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 9 design

## Summary

Phase 1-8 removed the old domain-owned `app/core/*_models.py` files and
`app/schemas/`, but a few cross-cutting data records still kept `app/core/`
wider than the target, and `app/api/v1/schemas.py` remained as a central
auth/health schema bucket. Phase 9 closes those leftovers without changing
external behavior.

## Boundaries

In scope:

- `app/core/auth_models.py` -> `app/services/auth/models.py`
- `app/core/document_ir_models.py` -> `app/services/document_ir/models.py`
- `app/core/template_config_models.py` ->
  `app/services/renderer/template_config.py`
- `app/api/v1/schemas.py` -> route-specific
  `app/api/v1/routers/auth_schemas.py` and
  `app/api/v1/routers/health_schemas.py`
- imports, tests, Trellis spec, CodeStable architecture, API docs, and Phase 9
  acceptance notes

Out of scope:

- HTTP route, status code, or payload changes
- conversion output changes
- new domain packages or persistence rewrites
- broad cleanup of the existing dirty worktree
- committing, pushing, or archiving unless the user explicitly asks

## Target Shape

- `app/core/` owns only infrastructure primitives: config, errors, logging,
  runtime, and package metadata.
- Auth user records live with the auth service.
- Document IR records live with the Document IR service.
- Renderer template config records live with the renderer service.
- Auth/health API-only Pydantic models live beside their routers, not in a
  central API schema file.

## Validation Strategy

- Run targeted import/behavior tests for FastAPI contracts and Document IR
  translation.
- Run a stale-import scan for the removed core/API schema modules.
- Run release validation through `scripts/ops/check_release.py`.
- Record all evidence in `acceptance.md` and update parent task notes.
