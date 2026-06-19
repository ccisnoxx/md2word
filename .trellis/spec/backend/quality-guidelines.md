# Quality Guidelines

> Backend code quality, testing, and review standards for this project.

---

## Overview

The backend quality bar is pragmatic: preserve existing FastAPI/domain
boundaries, keep metadata backends behaviorally aligned, expose errors and
readiness failures explicitly, and validate changes with focused `unittest` or
release-gate checks.

The local backend release check documented in `README.md` is:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Use narrower targeted tests first when working on a small area, then use the
release check when the change touches API contracts, metadata persistence,
health/readiness, or release behavior.

---

## Required Patterns

### Runtime And Configuration

- Put environment-driven settings in `app/core/config.py`.
- Read settings through `Settings` or `runtime.settings`; do not scatter direct
  `os.environ` reads across domain code.
- Wire new services/repositories in `app/main.py` and `app/core/runtime.py`.
- Keep production-like guardrails explicit, as in `_validate_runtime_guardrails()`.

### API Boundaries

- Use Pydantic schemas for API requests and responses.
- Use `app/api/dependencies.py` for runtime, trace, JWT, token, admin, and actor
  dependencies.
- Use `ApiError` for known API failures with stable status/code/message.
- Update `docs/api/openapi.json` when API contracts change.

### Domain Boundaries

- Keep business rules in services/workflow modules, not only in routers.
- Use repository Protocols from domain packages and concrete adapters from
  `app/infrastructure/persistence/`.
- Use explicit value types and `Literal` aliases for closed sets such as status,
  mode, worker backend, and log format.
- Prefer dataclasses with `frozen=True`/`slots=True` for immutable result records
  when that matches existing code.

### External Systems

- Use fake providers, fake connections, or adapter injection in local tests.
- Do not require real MinerU, OpenAI-compatible providers, MySQL, Redis/Celery,
  S3, Slack, or browsers for ordinary local backend validation.
- Keep dry-run/kill-switch behavior explicit for ops integrations.

---

## Forbidden Patterns

- Silent fallback behavior that makes a failed provider, missing schema, or
  invalid configuration look successful.
- Broad `except Exception` blocks that return empty/default data. If broad catch
  is needed in an ops gate, report the failure as a failed check.
- Direct SQL string interpolation.
- Adding a metadata feature to file/sqlite/MySQL unevenly.
- Creating a second source of truth for settings, routing, workflow states, or
  persistence adapter selection.
- Logging secrets, tokens, full document payloads, presigned URLs, or provider
  request bodies.
- Committing runtime/generated data from `var/`, `data/`, or test output
  directories.
- Starting local dev servers or real external services as a hidden side effect
  of unit tests.

---

## Testing Requirements

### Test Style

Backend tests currently use `unittest.TestCase`, `fastapi.testclient.TestClient`,
`TemporaryDirectory`, and fake service/provider classes.

Examples:

- `tests/test_fastapi_jobs_backend.py` builds full `AppRuntime` objects with
  fake providers and local temp directories.
- `tests/test_database_job_repository.py` validates file/sqlite/MySQL adapter
  parity, including a fake MySQL connection.
- `tests/test_backend_logging.py` covers the JSON logging formatter contract.
- `tests/test_metadata_shadow_copy.py` covers file -> sqlite/MySQL shadow-copy
  behavior.

Follow this pattern for new backend tests:

```python
class BackendLoggingTests(TestCase):
    def test_settings_accepts_json_log_format(self) -> None:
        settings = Settings(_env_file=None, log_format="json")
        self.assertEqual(settings.log_format, "json")
```

### What To Run

Choose the smallest useful validation:

- Single test module:
  `python -m unittest tests.test_backend_logging`
- Focused test class or method:
  `python -m unittest tests.test_database_job_repository.PersistenceAdapterTests`
- Release gate for backend/API contract changes:
  `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py`

`scripts/ops/check_release.py` checks OpenAPI freshness, frontend contract
needles, smoke mock contract needles, and a curated backend unittest target set.

### Online And Golden Sample Validation

Local code changes should not automatically run online validation. Production or
quasi-production validation follows the deployment docs and may include:

- `scripts/ops/check_release.py --runtime-url <api-base-url> --golden-sample-preflight`
- Golden Sample real regression on the four OPA228 PDFs under
  `tests/fixtures/golden_samples/pdfs/`
- P1 translation regression through `scripts/ops/run_p1_translation_regression.py`
- P2 online gate through `scripts/ops/run_p2_online_gate.py`

Only run these when the task explicitly requires online/runtime evidence or the
release process calls for it.

---

## Code Review Checklist

Before finishing backend work, check:

- Does the change stay in the correct layer: router, service/domain,
  infrastructure adapter, conversion library, or ops script?
- Are settings centralized in `Settings` and runtime wiring centralized in
  `build_runtime()`?
- Are API errors stable and handled by `app/api/errors.py`?
- Are auth/admin/actor requirements declared through dependencies?
- Are file/sqlite/MySQL adapters still behaviorally aligned?
- Are SQL statements parameterized?
- Are logs structured and free of secrets/customer payloads?
- Does the change update OpenAPI/frontend contract artifacts when API behavior
  changes?
- Do tests use fakes/temp directories instead of real external services?
- Does the validation run match the risk and scope of the change?

---

## Common Mistakes

- Treating the file backend as a test-only stub and forgetting it is the local
  default.
- Changing API response fields without updating `docs/api/openapi.json` and the
  release contract checks.
- Adding a new environment variable in a script or service instead of
  `Settings`.
- Hiding readiness blockers behind optional behavior.
- Broadly refactoring conversion/runtime code while making an API-only change.
- Forgetting to keep tests deterministic by isolating state under
  `TemporaryDirectory`.
