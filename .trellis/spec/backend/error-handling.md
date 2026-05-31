# Error Handling

> How errors are handled in this project.

---

## Overview

This backend uses layered error translation rather than one global custom error
framework. Pure helpers raise Python exceptions, HTTP-facing code raises
`HTTPException`, and background stage execution persists failure state before it
returns.

---

## Error Types

- `HTTPException`
  - Used for request validation, permission checks, missing resources, and
    business-state conflicts that are already at the HTTP boundary.
  - Examples: `app/api/dependencies.py`, `app/domains/jobs/query.py`,
    `app/domains/jobs/lifecycle.py`.
- `ValueError`
  - Used by pure validation/path helpers and then translated to HTTP 400 near
    the router boundary.
  - Examples: `app/domains/jobs/mineru_callback.py`,
    `app/domains/jobs/paths.py`.
- `FileNotFoundError`
  - Used by repository/storage lookup code and translated to HTTP 404 where
    needed.
  - Examples: `app/infrastructure/persistence/file/`,
    `app/domains/jobs/command.py`.
- `ConversionFailure`
  - Domain-specific failure type for the conversion pipeline.
  - `JobStageService` catches it, updates job + stage state, appends failure
    events, and logs the exception.

---

## Error Handling Patterns

- Validate early and close to the boundary.
  - Auth and callback verification live in `app/api/dependencies.py`.
  - Upload shape/content checks stay in router-local helpers such as
    `_save_upload_to_temp()` and `_save_pdf_upload_to_temp()`.
- Translate local exceptions once, at the layer boundary that understands the
  target contract.
  - `app/domains/jobs/mineru_callbacks_router.py` converts `FileNotFoundError` to
    404 and `ValueError` to 400.
  - When translating, preserve chaining with `raise ... from exc`.
- For background workflows, never fail silently.
  - `JobStageService` records `error_code`, `error_message`, and `JobEvent`
    entries before returning from known failure paths.
- Broad `except Exception` blocks are reserved for final guards or cleanup
  paths only.
  - Request middleware in `app/main.py` logs and re-raises.
  - `JobStageService` has a final guard that logs unexpected failures and
    re-raises instead of swallowing them.
- For configuration-gated features, current code prefers an explicit 503 that
  names the missing capability or setting, for example `OPENAI_API_KEY`,
  `MINERU_API_TOKEN`, or `ADMIN_TOKEN`.

---

## API Error Responses

- The API uses FastAPI's default error body shape: `{"detail": ...}`.
- There is no project-specific top-level error envelope yet.
- Error detail strings are currently written in Chinese and usually name the
  offending field, state, artifact, or missing environment-backed setting.
- Choose the narrowest status code that matches current behavior:
  - `400` for malformed payloads, unsupported options, invalid artifact paths
  - `403` for token or checksum failures
  - `404` for missing jobs, stage messages, or artifacts
  - `409` for invalid job-state transitions such as retry/cancel/result access
  - `413` for oversized uploads
  - `503` for disabled capabilities caused by missing runtime configuration

Representative examples:

- `require_jobs_access()` returns 503 when token mode is enabled but no token is
  configured, and 403 when the supplied token is wrong.
- `get_job_result()` returns 409 until the job has reached `completed`.
- `download_artifact()` returns 404 for unknown/missing artifacts and 400 when
  a resolved path fails local validation.
- `receive_mineru_callback()` preserves `HTTPException`, translates
  `FileNotFoundError` to 404, and translates `ValueError` to 400 before
  enqueuing background processing.

---

## Common Mistakes

- Do not raise raw `ValueError` or `FileNotFoundError` from a router without
  translating it to an HTTP status.
- Do not catch `HTTPException` and replace it with a generic 500; preserve the
  explicit client-facing status code.
- Do not mark a background job failed without also writing the corresponding
  event and stage-message state.
- Do not add new broad `except Exception` blocks unless they are true top-level
  guards that log and re-raise.
