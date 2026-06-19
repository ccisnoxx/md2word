# Logging Guidelines

> Backend logging channels, format, levels, and sensitive-data rules.

---

## Overview

The backend uses Python standard `logging`, configured in
`app/core/logging.py`. Although `loguru` is present in `requirements.txt`, the
FastAPI backend convention is the stdlib logging setup installed by
`configure_logging()`.

`build_runtime()` calls:

```python
configure_logging(resolved_settings.app_env, resolved_settings.log_format)
```

The three project logger channels are:

| Logger | Purpose | Typical source |
| --- | --- | --- |
| `access` | HTTP request access logs | `trace_logging_middleware` |
| `business` | job/stage/workflow events with business context | stage dispatch, retry, cleanup |
| `system` | runtime, library, and unexpected exception logs | uvicorn, httpx, startup, exception stacks |

---

## Format

Default `LOG_FORMAT=text`:

```text
{time} | {logger_name} | {level} | {message}
```

`LOG_FORMAT=json` emits a single-line JSON record:

```json
{"time":"...","logger":"access","level":"INFO","message":"..."}
```

The JSON formatter preserves non-standard log record fields and includes
`exc_info`/`stack_info` when present. `tests/test_backend_logging.py` is the
minimal contract for JSON logging behavior.

---

## Log Levels

`configure_logging()` sets the base level by environment:

- `DEBUG` for `dev`, `local`, and `test`
- `INFO` for other environments

Use levels this way:

- `debug`: local-only diagnostic details that are not needed for normal
  operations.
- `info`: expected lifecycle events, request access logs, successful stage
  transitions, dry-run summaries.
- `warning`: degraded but recoverable states, skipped optional checks, replay
  candidates that need attention.
- `error`/`exception`: failed operations, unexpected exceptions, provider
  failures, and blocked release/readiness conditions.

Do not rely on logger level changes to hide sensitive data. Sensitive values
must not be logged at any level.

---

## Structured Message Pattern

Use stable `key=value` fields inside the log message so text and JSON logs carry
the same searchable contract.

Access logs currently use:

```python
access_logger.info(
    "[trace_id=%s method=%s path=%s status_code=%s duration_ms=%.1f]",
    trace_id,
    request.method,
    request.url.path,
    response.status_code,
    duration_ms,
)
```

Business logs should include the relevant job/stage context when available:

```text
[trace_id=... job_id=... stage=convert_package message_id=... status=completed]
```

For document jobs, include stable identifiers such as `job_id`, `file_id`,
`stage`, `status`, `message_id`, and `trace_id`; avoid full request payloads.

---

## What To Log

Log events that help operators and tests understand state transitions:

- HTTP method/path/status/duration through the access middleware.
- Stage dispatch start/completion/failure and replay decisions.
- Document job creation, retry, cancel, archive, and recovery outcomes.
- File retention cleanup preview/execute results.
- Integration dry-run versus real execution outcomes.
- Readiness blockers and warnings when an ops script or health path reports
  them.

When a user action has audit significance, record it through `AuditService` in
addition to logging. Logs are operational evidence; audit events are product
records.

---

## What Not To Log

Never log:

- `Authorization`, bearer tokens, admin/jobs tokens, JWTs, passwords, API keys,
  webhook URLs, or resolved secret values.
- Full uploaded documents, raw PDF contents, OCR payloads, full AI prompt/output
  archives, or translation debug full text.
- Presigned URLs or S3 credentials.
- Complete third-party provider responses when they can include customer
  content or credentials.

Prefer IDs and counts over payloads. If a path or object key is necessary for a
backend diagnostic, keep it out of API responses and avoid including customer
filenames unless the existing operation explicitly requires them for local-only
debugging.

---

## Examples

Logging setup:

```python
for logger_name in ("access", "business", "system"):
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(level)
    logger.addHandler(handler)
```

Unexpected exception logging:

```python
system_logger.exception(
    "[trace_id=%s method=%s path=%s status=exception duration_ms=%.1f]",
    trace_id,
    request.method,
    request.url.path,
    duration_ms,
)
```

JSON log contract test:

```python
payload = json.loads(formatter.format(record))
self.assertEqual(payload["logger"], "access")
self.assertEqual(payload["level"], "INFO")
```

---

## Common Mistakes

- Creating new logger channels when `access`, `business`, or `system` already
  fit.
- Using `print()` in backend runtime code instead of stdlib logging.
- Logging whole request/response bodies for convenience.
- Logging secret references and resolved secret values together.
- Adding log messages without stable keys, making them hard to grep or parse.
- Reconfiguring logging outside `app/core/logging.py` or `build_runtime()`.
