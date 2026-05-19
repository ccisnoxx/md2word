# Refactor `mineru_to_docx.py` Entrypoint Design

## Summary

The refactor goal is not “move everything into FastAPI,” but “turn
`mineru_to_docx.py` into a thin entrypoint/compatibility facade and make the
shared conversion core callable from both CLI and FastAPI through stable
library-facing modules.”

This design intentionally keeps the migration incremental:

1. decouple FastAPI from the root script first
2. move shared contracts and orchestration into stable modules
3. migrate characterization seams away from the root-file-as-module-loader
4. shrink the root script last

## Scope

In scope:

- planning a staged refactor around `mineru_to_docx.py`
- the root script's remaining responsibilities
- FastAPI's direct dependency on root-script symbols
- characterization-test seam migration
- stable module boundaries for shared conversion logic

Out of scope:

- changing conversion output semantics
- changing FastAPI API contracts
- term-rules/templates feature work
- removing all runtime indirection in a single pass

## Design Goals

1. Make `app/` depend on reusable conversion modules, not on a local CLI file.
2. Preserve the existing CLI entry surface while migration is underway.
3. Reduce the number of responsibilities that only the root script owns.
4. Preserve testability and characterization coverage during each phase.
5. Keep each stage small enough to commit independently.

## Current Problem Shape

`mineru_to_docx.py` is currently a mixed-responsibility file:

- entrypoint concerns:
  - `parse_args()`
  - `main()`
  - `run_with_pycharm_config()`
  - `resolve_cli_run_options()`
- shared contracts / config helpers:
  - `Block`, `PageData`, `RenderConfig`, etc.
  - template/subscript/layout path resolution
- orchestration:
  - `run_conversion()`
  - translation/config/document-language resolution helpers
- wrapper surface:
  - table/text/layout helper exports used by characterization tests

This creates two concrete problems:

1. FastAPI still imports the root script to reach shared core behavior.
2. Tests still treat the root script as the canonical patch surface for many
   runtime modules.

## Target Shape

### What `mineru_to_docx.py` Should Eventually Keep

- CLI argument parsing
- PyCharm/local fallback behavior
- top-level `main()` wiring
- temporary compatibility re-exports for characterization/tests

### What Should Move Behind Stable Shared Modules

- conversion orchestration entrypoint
- shared conversion contracts and models
- template / terminology / document-language resolution helpers
- runtime callable wrappers that FastAPI needs

### What FastAPI Should Depend On

FastAPI should depend on:

- `app/conversion/` modules
- stable shared contracts
- explicit resolution/orchestration helpers

FastAPI should not depend directly on:

- `mineru_to_docx.py`

## Four-Stage Plan

### Stage 1: FastAPI Decoupling

Goal:

- stop `app/conversion/service.py` from importing the root script directly

Shape:

- introduce or expand a stable shared conversion module under `app/conversion/`
- let FastAPI conversion service import from that shared module instead
- keep `mineru_to_docx.py` re-exporting or delegating to the same logic

Why first:

- it removes the most architecturally awkward dependency with minimal impact on
  the CLI surface

Expected preserved behavior:

- same FastAPI conversion behavior
- same CLI behavior
- same `run_conversion()` semantics

### Stage 2: Shared Contracts And Helper Extraction

Goal:

- move root-owned shared models/helpers to explicit library-facing modules

Likely targets:

- shared dataclasses/models currently still defined in the root script
- template/subscript/layout path resolution helpers
- document language helpers

Why second:

- once FastAPI is no longer importing the root script directly, shared helpers
  can move without creating new cross-surface coupling

Expected preserved behavior:

- root script still exports compatible names
- runtime modules still work with temporary compatibility shims if needed

### Stage 3: Test Seam Migration

Goal:

- migrate characterization suites away from treating `mineru_to_docx.py` as the
  single canonical loaded module

Shape:

- identify which patch points should move to shared runtime modules
- update `_load_module()`-style loaders or test import targets incrementally
- keep compatibility façade exports until all critical tests stop depending on
  root-file implementation details

Why third:

- removing root responsibilities before migrating test seams would make the
  refactor brittle and hard to verify

Expected preserved behavior:

- characterization tests still describe the same behavior
- tests depend on more intentional patch surfaces

### Stage 4: Entrypoint Shrink-Wrap

Goal:

- reduce `mineru_to_docx.py` to a thin CLI/compatibility wrapper

Shape:

- retain only:
  - CLI parsing
  - local run config fallback
  - top-level main wiring
  - explicit re-exports that still must exist
- document the file as an entrypoint façade instead of a core implementation

Why last:

- only safe once FastAPI and tests are no longer structurally anchored to the
  root script

Expected preserved behavior:

- users can still run the local tool the same way
- repository architecture becomes clearer

## Validation Strategy

Stage 1:

- `tests.test_fastapi_jobs_backend`

Stage 2:

- focused characterization suites that cover moved helpers
- `py_compile` or import smoke for shared conversion modules

Stage 3:

- the characterization suites that currently use `_load_module()`:
  - render config
  - text rendering
  - table rendering
  - input adapter
  - page layout / page repair

Stage 4:

- CLI smoke or import smoke
- rerun both backend tests and the affected characterization suites

## Key Risks

1. root-script compatibility exports vanish too early and break tests
2. FastAPI decoupling accidentally changes conversion wiring
3. runtime helper relocation changes patch order or import-time binding behavior
4. removing `bind_runtime()` too early breaks characterization isolation

## Risk Mitigations

- keep `mineru_to_docx.py` as a compatibility façade throughout the migration
- move one class of responsibility at a time
- preserve symbol names until the dependent tests are migrated
- treat `bind_runtime()` removal as a late-stage cleanup, not an initial goal

## Success Criteria

- FastAPI no longer imports `mineru_to_docx.py` directly
- root-script responsibilities are reduced to entrypoint/compatibility concerns
- characterization suites have explicit, intentional import/patch seams
- `mineru_to_docx.py` is small enough to move to `scripts/` later if desired,
  but that move is not required in this task
