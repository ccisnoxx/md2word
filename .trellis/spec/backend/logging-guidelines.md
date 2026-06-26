# Logging Guidelines

The FastAPI backend uses Python standard `logging` configured in `app/core/logging.py`. `loguru` is present in `requirements.txt`, but it is not the FastAPI runtime logging convention.

Evidence:

- `app/core/logging.py`
- `app/main.py`
- `app/domains/jobs/stage.py`
- `app/workers/stage_worker.py`
- `app/clients/mineru_client.py`
- `docs/dev/runtime-observability-and-health.md`
- `docs/runbooks/backend.md`
- `tests/test_backend_logging.py`
- `tests/test_internal_user_management.py`

## Logger Channels

`configure_logging()` configures three named runtime loggers:

- `access` for HTTP request access logs.
- `business` for job, stage, worker, retry, cleanup, and other business-flow logs.
- `system` for unexpected exceptions, third-party libraries, startup/runtime infrastructure, and logs without business context.

`app/main.py` calls `configure_logging()` during `build_runtime()`. Use `logging.getLogger("business")`, `logging.getLogger("system")`, or the existing local logger channel instead of creating unrelated logger naming schemes for backend runtime behavior.

## Format And Levels

`Settings.log_format` accepts `text` or `json`.

Text format:

```text
{time} | {logger_name} | {level} | {message}
```

JSON format is a single JSON object per line with at least:

```json
{"time":"...","logger":"access","level":"INFO","message":"..."}
```

`configure_logging()` sets `DEBUG` for `dev`, `local`, and `test`; otherwise it sets `INFO`. It also lowers noisy third-party logger verbosity for `httpx`, `httpcore`, `asyncio`, `uvicorn`, and `python_multipart`.

当前未建立此约定：there is no per-domain log level map or structured logging library beyond `JsonLogFormatter`.

## Required Context Fields

Messages use stable key/value fragments inside the message string so they can be grepped in text logs and parsed from JSON `message`.

Access logs are emitted by `trace_logging_middleware` in `app/main.py`:

```text
[trace_id=... method=GET path=/api/v1/health/ready status_code=200 duration_ms=1.5]
```

Business stage logs should include the durable workflow identifiers available on that path:

- `trace_id`
- `job_id`
- `stage`
- `message_id`
- `status`
- `reason` or error summary when relevant

`JobStageService._log_stage_failure()` and `_delete_if_stage_already_applied()` are the local examples. `StageWorker.run_forever()` logs `worker_id`, mode, and processed count.

## What To Log

Log durable operational facts, not raw payloads:

- HTTP method/path/status/duration in access logs.
- Stage enqueue, replay, skip, success, and failure context in business logs.
- Worker loop startup and processed count in business logs.
- Unexpected request exceptions in system logs.
- External provider request summaries that do not reveal secret values, such as MinerU batch/file counts in `app/clients/mineru_client.py`.

For long-running job behavior, also record domain events through the owning service/repository. Logs are diagnostic output; `events` and audit records are the durable business history.

## What Not To Log

Do not log secrets, raw tokens, passwords, password hashes, full customer file contents, or full external payload bodies.

Evidence of this boundary:

- `tests/test_internal_user_management.py` asserts user-management responses/audit details do not contain passwords or `pbkdf2_sha256`.
- `docs/dev/runtime-observability-and-health.md` states `/health/metrics` must not expose token, payload, customer filename, or artifact local absolute path.
- `app/api/dependencies.py` raises stable auth errors without logging provided token values.

当前未建立此约定：there is no centralized redaction filter for arbitrary logger calls. Each caller must avoid passing sensitive values to logging or audit details.

## Health And Metrics

Health and metrics are part of observability but not log streams:

- `/api/v1/health/ready` reports readiness checks, backend selection, worker mode, artifact storage, resource versions, deployment identity, and P0 blockers/warnings.
- `/api/v1/health/metrics` returns JSON operational counts and is not Prometheus format.

Follow `docs/dev/runtime-observability-and-health.md` when adding readiness or metrics fields. Keep them non-sensitive and stable enough for scripts such as `scripts/ops/run_p2_online_gate.py`.
