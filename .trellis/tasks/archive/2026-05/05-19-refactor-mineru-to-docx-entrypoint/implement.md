# Refactor `mineru_to_docx.py` Entrypoint Implementation Plan

## Scope

Implement the approved staged refactor in four independently committable
phases. Each phase must preserve behavior and leave the repository in a testable
state.

## Ordered Checklist

### 1. FastAPI Decoupling Commit

Files likely involved:

- `app/conversion/service.py`
- `app/conversion/entrypoint.py`
- one or more new or expanded shared conversion modules
- possibly `mineru_to_docx.py` for re-export/delegation

Goal:

- remove FastAPI's direct import dependency on `mineru_to_docx.py`

Validation:

- `python3 -m unittest tests.test_fastapi_jobs_backend`

Rollback point:

- restore `app/conversion/service.py` to the previous direct import path

### 2. Shared Contracts / Helpers Commit

Files likely involved:

- `mineru_to_docx.py`
- `app/conversion/*`
- possibly `render_config_runtime.py`
- possibly `translation_runtime.py`
- possibly `text_rendering.py`

Goal:

- move root-owned shared contracts and helper logic into stable shared modules
- keep root-script compatibility exports intact

Validation:

- targeted characterization suites for the helpers touched
- import smoke for moved modules

Rollback point:

- re-inline moved helpers into `mineru_to_docx.py` while keeping Stage 1
  decoupling intact

### 3. Characterization Seam Migration Commit

Files likely involved:

- `tests/test_render_table_from_html_characterization.py`
- `tests/test_render_config_characterization.py`
- `tests/test_text_render_characterization.py`
- `tests/test_input_adapter_characterization.py`
- `tests/test_page_layout_characterization.py`
- `tests/test_page_repair_characterization.py`
- potentially shared test loader helpers if introduced

Goal:

- stop relying on the root script as the only test seam where practical
- preserve behavior expectations while moving patch points to intentional module
  boundaries

Validation:

- rerun only the affected characterization suites

Rollback point:

- restore prior test loaders and compatibility exports

### 4. Entrypoint Shrink-Wrap Commit

Files likely involved:

- `mineru_to_docx.py`
- docs and architecture notes about the root script

Goal:

- reduce the root script to CLI / PyCharm wrapper + explicit compatibility
  façade

Validation:

- backend tests
- impacted characterization tests
- import/CLI smoke if practical

Rollback point:

- restore façade exports or root-owned wrapper functions without undoing earlier
  decoupling

## Suggested Commit Messages

1. `refactor(conversion): decouple fastapi from mineru_to_docx entrypoint`
2. `refactor(conversion): extract shared mineru_to_docx contracts and helpers`
3. `test(conversion): migrate characterization seams off root entrypoint`
4. `refactor(cli): shrink mineru_to_docx to entrypoint facade`

## Review Gates Before `task.py start`

- Confirm the four-phase split is acceptable.
- Confirm preserving CLI behavior is more important than immediately removing
  compatibility exports.
- Confirm characterization seam migration is part of this task rather than
  deferred indefinitely.
- Confirm no phase should mix in term-rules/templates feature work.
