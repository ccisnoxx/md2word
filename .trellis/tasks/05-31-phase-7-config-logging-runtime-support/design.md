---
doc_type: design
task: 05-31-phase-7-config-logging-runtime-support
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 7 design

## Summary

Phase 7 is a post-restructure support slice for configuration, logging, and
runtime readiness. It does not introduce a new backend feature. It reconciles
the existing implementation and current docs around:

- environment variables and local/deployment startup guidance
- `/api/v1/health/ready` blocking checks, warnings, and runtime observations
- text and JSON logging behavior for `access`, `business`, and `system` logs
- release-check coverage for readiness and logging

## Boundaries

In scope:

- `app/core/config.py`
- `app/core/logging.py`
- `app/services/health_service.py`
- `app/main.py`
- `tests/test_backend_logging.py`
- health readiness coverage in `tests/test_fastapi_jobs_backend.py`
- `.env.example`
- `docs/dev/backend-local-minimal-env-and-commands.md`
- `docs/dev/runtime-observability-and-health.md`
- `docs/runbooks/backend.md`
- `.trellis/spec/backend/logging-guidelines.md`

Out of scope:

- API contract changes
- new health endpoints or metrics formats
- new logging frameworks, OpenTelemetry, or Prometheus
- changing worker/process architecture
- broad directory restructure cleanup unrelated to Phase 7

## Current Target Shape

The current implementation already has the intended support structure:

- `Settings.log_format` accepts `text` or `json`
- `app/main.py` calls `configure_logging()` during runtime construction
- `JsonLogFormatter` emits one-line JSON records for container/cloud log
  collectors
- readiness separates required checks from non-blocking warnings
- release checks include targeted health and logging tests

Phase 7 therefore proceeds as an audit-and-fix pass. If the audit finds no
missing implementation, the code work is limited to task/acceptance artifacts
and validation evidence.

## Risks

- Readiness can become misleading if required checks and non-blocking warnings
  drift between code and docs.
- Logging docs can overpromise structured fields if the code only keeps them in
  the message body.
- `.env.example` can drift from `Settings`, leaving new deployments with
  undocumented required values or stale variables.

## Validation Strategy

- Run logging unit coverage directly.
- Run targeted readiness tests directly.
- Run `scripts/ops/check_release.py` to verify the release-facing aggregation,
  including OpenAPI snapshot freshness and JSON logging coverage.
- Optionally smoke the documented local API startup if a port is available; if
  skipped, record the reason in `acceptance.md`.
