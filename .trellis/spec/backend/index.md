# Backend Development Guidelines

> Entry point for FastAPI backend conventions in this repository.

---

## Overview

This layer applies to:

- backend code under `app/`
- FastAPI integration coverage in `tests/test_fastapi_jobs_backend.py`
- backend-facing runtime changes that persist job, artifact, event, or stage
  message state

Read this file first, then open the specific guideline files that match the
change you are making.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | Filled |
| [Error Handling](./error-handling.md) | Error types, handling strategies | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | Filled |

---

## Pre-Development Checklist

- If you are deciding where new code should live, or wiring a new service /
  router / client:
  read [Directory Structure](./directory-structure.md)
- If you are changing persisted JSON shape, job/event/stage storage, path
  layout, or ID generation:
  read [Database Guidelines](./database-guidelines.md)
- If you are adding validation, auth checks, status-code behavior, callback
  guards, or background failure handling:
  read [Error Handling](./error-handling.md)
- If you are touching request tracing, access logs, or background job logs:
  read [Logging Guidelines](./logging-guidelines.md)
- For any backend code change:
  read [Quality Guidelines](./quality-guidelines.md)
- For cross-layer reasoning and reuse checks:
  also read [Thinking Guides](../guides/index.md)

---

## Quality Check

Before considering backend work done, verify:

- the code landed in the correct layer instead of growing `app/main.py` or a
  router into a workflow module
- job lifecycle changes update all affected persisted outputs: job record,
  stage message when applicable, emitted event trail, and returned API shape
- new client-facing failures use the narrowest `HTTPException` status already
  consistent with this API
- any new log or event carries the relevant `trace_id` / `job_id` context
- tests were updated in the narrowest backend module that proves the change
  path, usually `tests.test_fastapi_jobs_backend`
- if the change teaches a new stable convention, this spec layer was updated
  with a real code reference instead of leaving the rule only in chat

---

## Maintenance Notes

These files are now meant to be maintained as a living description of the
current backend. When the codebase changes materially, update the relevant guide
with real examples from the new implementation.

---

**Language**: All documentation should be written in **English**.
