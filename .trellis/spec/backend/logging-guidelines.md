# Logging Guidelines

> How logging is done in this project.

---

## Overview

The backend uses the Python standard library `logging` module. Logging is
configured once in `app/core/logging.py`, then consumed through named loggers
such as `access`, `business`, and `system`.

---

## Log Levels

- Default level is environment-sensitive:
  - `DEBUG` in `dev`, `local`, and `test`
  - `INFO` elsewhere
- Current code uses these levels in practice:
  - `INFO` for successful lifecycle transitions and request access logs
  - `WARNING` for ignored-but-not-fatal situations such as callbacks arriving
    for unsupported job status
  - `EXCEPTION` for unexpected failures and handled failure terminal states that
    still deserve stack traces
- There are currently no meaningful project-specific `debug()` call sites. If
  you add one, keep it diagnostic and non-essential.

---

## Structured Logging

- Formatter: `%(asctime)s | %(name)s | %(levelname)s | %(message)s`
- `LOG_FORMAT=text` keeps the formatter above. `LOG_FORMAT=json` switches the
  same records to one-line JSON with top-level `time`, `logger`, `level`, and
  `message` fields.
- Named channels:
  - `access` for per-request timing in `app/main.py`
  - `business` for background job/stage lifecycle in `app/domains/jobs/stage.py`
  - `system` for request-level exceptions and external client activity
- Prefer metadata inside the message body using stable keys. Current messages
  consistently include fields such as:
  - `trace_id`
  - `job_id`
  - `stage`
  - `status`
  - extra identifiers like `batch_id` or result path when useful
- Use `%s` parameterized logging instead of f-strings so the logger owns string
  interpolation.
- Do not add another logger stack locally. Extend `app/core/logging.py` if the
  existing text/JSON switch needs a new field.

Example pattern from the codebase:

```python
self.logger.info(
    "[trace_id=%s job_id=%s stage=%s message_id=%s status=completed] result=%s",
    message.trace_id,
    job.id,
    message.stage,
    message.id,
    job_paths.result_docx,
)
```

---

## What to Log

- Every request should get a trace id and access log entry. `create_app()`
  writes `X-Trace-Id` to the response and logs method, path, status, and
  duration.
- Background stage transitions should log terminal or externally visible state
  changes:
  - conversion completed
  - MinerU submission accepted/failed
  - callback processing accepted/skipped/failed
- External integration logs should focus on operational metadata, not full
  payload dumps. Example: `MinerUClient.upload_files_batch()` logs batch id and
  file count after success.
- When a code path also persists a `JobEvent`, keep the same `trace_id` in the
  event record and the related log lines so request-to-background flow stays
  correlatable.

---

## What NOT to Log

- Do not log secrets from settings or headers:
  - `JOBS_ACCESS_TOKEN`
  - `ADMIN_TOKEN`
  - `MINERU_CALLBACK_TOKEN`
  - callback seeds
- Do not log raw callback payload content or uploaded file bytes.
- Do not log full temporary filesystem contents when a short path or identifier
  is enough.
- Keep current practice of logging metadata-only summaries for request and job
  flow; expanding to full payload dumps would be a regression in signal-to-noise
  and secret handling.
