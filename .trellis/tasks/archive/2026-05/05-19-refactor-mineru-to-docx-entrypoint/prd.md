# Refactor mineru_to_docx entrypoint

## Goal

Plan a behavior-preserving refactor that shrinks `mineru_to_docx.py` into a
thin CLI / compatibility facade, while moving shared conversion responsibilities
to stable reusable modules that FastAPI and local CLI can both call.

## Confirmed Facts

- The repository currently has two runtime surfaces:
  - CLI / PyCharm flow rooted at `mineru_to_docx.py`
  - FastAPI backend rooted at `app/`
- `app/conversion/service.py` still directly imports
  `run_conversion` and `resolve_document_language` from
  `mineru_to_docx.py`.
- `mineru_to_docx.py` still owns multiple responsibilities at once:
  - CLI argument parsing and PyCharm fallback
  - shared dataclasses and config helpers
  - conversion orchestration
  - thin wrappers around rendering/table helpers
- Multiple characterization suites still load `mineru_to_docx.py` directly and
  patch its top-level symbols, especially through
  `tests/test_render_table_from_html_characterization.py`.
- The repository has already completed several local refactors that split
  runtime logic into:
  - `input_adapter_runtime.py`
  - `page_repair_runtime.py`
  - `render_config_runtime.py`
  - `page_layout_runtime.py`
  - `text_rendering.py`
  but these modules still rely on `bind_runtime()` / `_runtime_value()` and the
  root module as a compatibility container.
- The current architecture document describes the project as “双表面、单内核”:
  FastAPI and CLI share one conversion core rather than maintaining separate
  algorithms.
- The working tree currently contains other in-progress, uncommitted work, so
  this new task should stay planning-only for now and must not implicitly absorb
  unrelated code changes.
- Default refactor assumption is behavior-preserving: conversion behavior, CLI
  usability, and FastAPI contracts should remain stable unless explicitly
  changed in a later task.

## Requirements

- Produce a new Trellis refactor task for `mineru_to_docx.py`收口.
- Split the work into 3 to 5 independently committable stages.
- Keep each stage small enough to validate directly.
- Prioritize removing FastAPI's direct dependency on `mineru_to_docx.py`
  before aggressively shrinking the root file itself.
- Preserve existing CLI entry behavior during the migration.
- Preserve characterization-test coverage and known patch points until a later
  stage explicitly migrates them.
- Avoid mixing this refactor with unrelated feature work.

## Acceptance Criteria

- [ ] PRD records the current role of `mineru_to_docx.py` and why it cannot be
  deleted immediately.
- [ ] The refactor plan is split into 3 to 5 coherent stages.
- [ ] Each stage has a clear preserved-behavior goal and validation path.
- [ ] The plan explicitly distinguishes what stays in the root entrypoint
  facade versus what should move into shared reusable modules.
- [ ] The task has `design.md` and `implement.md` ready for review before any
  implementation starts.

## Likely Out Of Scope

- Rewriting the conversion algorithm itself.
- Feature changes in jobs, term-rules, templates, or callback semantics.
- Removing all `bind_runtime()` seams in one shot.
- Deleting `mineru_to_docx.py` immediately.

## Open Questions

- None at the PRD level. The task is to formalize a staged refactor roadmap,
  not to choose between competing product scopes.

## Notes

- Planning is complete enough to draft `design.md` and `implement.md`.
