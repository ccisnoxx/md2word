# Error Handling

> Backend exception, propagation, and API response conventions.

---

## Overview

API-visible errors use a stable JSON shape registered in `app/api/errors.py`.
Domain and application code should raise explicit exceptions and let the API
error boundary convert them to HTTP responses.

Current response content includes both legacy-compatible and structured fields:

```json
{
  "detail": "message",
  "error_code": "invalid_request",
  "request_id": "trace-id",
  "trace_id": "trace-id",
  "error": {
    "code": "invalid_request",
    "message": "message",
    "status_code": 400,
    "request_id": "trace-id",
    "trace_id": "trace-id"
  }
}
```

Keep this shape stable when adding new errors.

---

## Error Types

Use `ApiError` for application-level failures that should have a deliberate HTTP
status and stable error code:

```python
@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: ApiErrorCode
    message: str
```

`ApiErrorCode` is defined in `app/core/errors.py`. Add new error codes there
before using them in services or routers.

Existing domain-specific exceptions are registered at the API boundary when they
have stable HTTP meaning:

- `JobWorkflowViolation` -> `409 job_state_conflict`
- `ConversionFailure` -> `503 conversion_failed`
- `JobResourceSnapshotError` -> its explicit status code with
  `resource_snapshot_error`

FastAPI `HTTPException` is still accepted for older code paths, but
`app/api/errors.py` normalizes it into the same response shape and derives a
standard code from the status when needed.

---

## Raising Errors In Services

Services should raise `ApiError` when the failure is part of the public API
contract. Example from document job readiness:

```python
raise ApiError(
    status.HTTP_503_SERVICE_UNAVAILABLE,
    "document_jobs_not_ready",
    message,
)
```

Use `FileNotFoundError` and `ValueError` for lower-level repository or parser
failures only when the caller is responsible for mapping them. Current helpers
for mapping those errors live in `app/api/errors.py`:

```python
def not_found_http_exception(exc: FileNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

def bad_request_http_exception(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
```

For new API-facing service methods, prefer raising `ApiError` directly instead
of requiring every router to repeat the same mapping.

---

## Router Patterns

Routers normally let `ApiError` propagate to the registered handlers.

Bulk endpoints are the exception: they may catch `ApiError` per item so one bad
item does not abort the whole batch. Current example:

```python
for job_id in job_ids:
    try:
        job = runtime.document_job_service.retry_job(job_id, user=user, reason=payload.reason)
    except ApiError as exc:
        items.append(_build_document_job_bulk_failure(job_id, exc))
        continue
```

If an endpoint catches an exception, it must either return a deliberate partial
failure result or re-raise a mapped exception. Do not swallow failures.

---

## Request Validation

FastAPI/Pydantic validation errors are handled centrally as
`422 validation_error`:

```python
app.add_exception_handler(RequestValidationError, _request_validation_exception_handler)
```

Use Pydantic request models and FastAPI `Query(...)` constraints for request
shape validation. Use service-level checks for business rules that need access
to repositories, runtime settings, or actor context.

---

## Unexpected Exceptions

Unexpected exceptions are logged by the HTTP middleware in `app/main.py` and
then re-raised:

```python
except Exception:
    system_logger.exception(
        "[trace_id=%s method=%s path=%s status=exception duration_ms=%.1f]",
        trace_id,
        request.method,
        request.url.path,
        duration_ms,
    )
    raise
```

Do not convert unexpected exceptions into generic success responses or silent
fallbacks. Let them fail loudly so release checks and logs can expose the issue.

---

## Common Mistakes

- Returning ad hoc dictionaries for errors instead of raising `ApiError` or a
  registered exception.
- Adding a new public error code in a service without adding it to
  `ApiErrorCode`.
- Catching broad `Exception` in services and returning an empty/default result.
- Using `ValueError` for an API contract violation when the status and error
  code are known.
- Losing `trace_id` by building custom `JSONResponse` errors outside the
  central helpers.
- Returning raw exception details from third-party providers when the message
  may include tokens, URLs, customer text, or internal paths.
