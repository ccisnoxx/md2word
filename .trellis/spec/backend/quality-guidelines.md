# Quality Guidelines

Backend verification is built around `unittest`, FastAPI `TestClient`, focused repository tests, OpenAPI snapshot checks, and release aggregation scripts.

Evidence:

- `README.md`
- `docs/runbooks/backend.md`
- `scripts/ops/check_release.py`
- `scripts/ops/export_openapi.py`
- `tests/test_fastapi_jobs_backend.py`
- `tests/test_database_job_repository.py`
- `tests/test_backend_logging.py`
- `tests/test_openapi_export.py`
- `tests/test_internal_user_management.py`
- `requirements.txt`

## Test Style

Current tests use Python `unittest`, not pytest fixtures/config:

- Test classes inherit from `unittest.TestCase`.
- API tests use `fastapi.testclient.TestClient`.
- Runtime tests build isolated app instances through `build_test_runtime()` from `tests/test_fastapi_jobs_backend.py`.
- Filesystem state uses `TemporaryDirectory` or temp paths.
- External providers are faked in tests, for example `FakeMinerUClient`, `FakeConversionService`, and fake MySQL connection/cursor classes.

当前未建立此约定：there is no `pytest.ini`, `pyproject.toml`, ruff config, mypy config, or checked-in formatter configuration.

## Which Tests To Add Or Run

Use focused tests matching the touched behavior:

- API/domain workflow changes: add or run targets in `tests/test_fastapi_jobs_backend.py` or the domain-specific test file.
- Metadata persistence changes: update file/sqlite/MySQL parity tests in `tests/test_database_job_repository.py`.
- Logging changes: update `tests/test_backend_logging.py`.
- Auth/user/security-visible changes: update `tests/test_internal_user_management.py`.
- OpenAPI/public response changes: update and check `tests/test_openapi_export.py` plus the OpenAPI snapshot flow.
- Document IR/conversion/rendering behavior: use the existing characterization tests such as `tests/test_document_ir_word_renderer_layout.py`, `tests/test_text_render_characterization.py`, `tests/test_page_layout_characterization.py`, and related runtime characterization tests.

Preferred targeted command shape:

```bash
.venv/bin/python -m unittest tests.test_backend_logging
.venv/bin/python -m unittest tests.test_database_job_repository.PersistenceAdapterTests
.venv/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.<test_name>
```

## Scenario: Frontend Consumption Of Existing API Diagnostics

### 1. Scope / Trigger

- Trigger: adding frontend consumption for an existing backend/OpenAPI read endpoint, especially diagnostics such as document job events, files, callback summaries, translation QA, or translation batches.
- This is cross-layer work even when backend code is unchanged: backend schema -> OpenAPI snapshot -> `frontend/src/api/types.ts` -> API wrapper -> page/helper display.

### 2. Signatures

- Frontend wrapper signature should match the backend path and response model:
  ```typescript
  documentJobsApi.listTranslationBatches(jobId: string): Promise<DocumentJobTranslationBatchListResponse>
  ```
- Page code should call the wrapper, not `apiRequest` directly, unless a local page already owns that narrow API pattern.

### 3. Contracts

- Add or update the response type in `frontend/src/api/types.ts` using the backend schema field names and nullability.
- Add a wrapper in the owning frontend API module, for example `frontend/src/api/documentJobs.ts`.
- Display code should consume typed helpers/projections for status labels, counts, and summaries; do not parse the same raw payload fields in multiple components.
- If the backend contract is redacted or metadata-only, keep that boundary in the UI. Showing file IDs is acceptable; fetching or rendering raw prompt, response, source text, translated text, object keys, or signed URLs is not.

### 4. Validation & Error Matrix

- Wrapper path or method wrong -> focused frontend API unit test must fail.
- Missing frontend type fields -> `npm run build` / `vue-tsc --noEmit` must fail when the page consumes the field.
- Endpoint load failure -> page should show a scoped `ApiErrorAlert` and keep unrelated page sections usable.
- Unsupported/empty data -> page should show a low-noise empty state, not an error.
- Redaction boundary accidentally crossed -> code review and tests must reject raw content fetch/render paths.

### 5. Good/Base/Bad Cases

- Good: endpoint response gets a typed frontend model, a wrapper test, shared display helpers with unit tests, scoped loading/error state, and a docs update.
- Base: a small read-only endpoint is exposed through a typed wrapper and rendered directly where no reusable display logic is needed.
- Bad: a page calls `apiRequest` inline, casts `unknown` payload fields locally, duplicates status mapping in multiple places, or fetches artifact contents when the API contract only promised safe file IDs.

### 6. Tests Required

- Frontend API wrapper test: assert URL and HTTP method.
- Helper/reducer test: assert status labels, warning/error classifications, empty/null formatting, and summary counts.
- Build/type check: run `npm run build` for Vue template and TypeScript coverage.
- For backend schema changes, also run `tests.test_openapi_export` and refresh `docs/api/openapi.json` through the export script.

### 7. Wrong vs Correct

#### Wrong

```typescript
const response = await apiRequest<any>({ url: `/api/v1/document-jobs/${jobId}/translation-batches` });
const status = (response.items[0] as { status?: string }).status || "unknown";
```

#### Correct

```typescript
const response = await documentJobsApi.listTranslationBatches(jobId);
const summary = summarizeTranslationBatches(response.items);
```

## Release Check

`scripts/ops/check_release.py` is the local aggregate release gate cited by `README.md`. It checks:

- OpenAPI snapshot freshness.
- Minimum frontend contract fields derived from `docs/api/openapi.json`.
- Frontend mock/smoke contract files.
- A curated set of backend `unittest` targets.
- Optional runtime readiness and Golden Sample preflight when arguments/env are provided.

Use it when a backend change affects release-critical behavior or public contracts:

```bash
.venv/bin/python scripts/ops/check_release.py
```

For API contract changes, keep `docs/api/openapi.json` in sync through `scripts/ops/export_openapi.py` and the checks in `tests/test_openapi_export.py`.

## Local Versus Online Validation

`README.md` and `docs/runbooks/backend.md` define a clear validation boundary:

- Local change work should run checks that do not depend on real services.
- Do not start frontend, backend, MySQL, Redis/Celery, workers, MinerU, or Playwright smoke locally as P0 release evidence.
- Complete API/Worker/MySQL/Redis-Celery/MinerU/Golden Sample evidence is collected on hostdzire through the online-first workflow.

For P1 and P2, use the existing ops scripts when the task explicitly asks for those gates:

- `scripts/ops/run_p1_translation_regression.py`
- `scripts/ops/run_p2_online_gate.py`
- `scripts/ops/run_golden_sample_regression.py`

## Review Checklist

Before finishing backend work, check the touched files against these current project contracts:

- Runtime wiring: shared services are built in `app/main.py`, stored on `AppRuntime`, and consumed through `Depends(get_runtime)` rather than hidden globals.
- API errors: externally visible failures use `ApiError` or a registered exception mapping and return stable `error_code` plus `trace_id`.
- Persistence: domain code depends on repository protocols; backend adapters are wired through `app/infrastructure/persistence/factory.py`; SQL uses parameters.
- Logs/metrics/audit: no secrets, passwords, token values, raw payload bodies, or local artifact absolute paths are exposed.
- Tests: new behavior has targeted `unittest` coverage or an explicit reason why a narrower/manual check is the best available validation.
- Public API: OpenAPI snapshot and frontend contract checks are updated when request/response shapes change.

当前未建立此约定：there is no separate code review bot, lint gate, type-check gate, or formatting gate in the checked-in backend config.

## Legacy API Test Migration

When a legacy API route is intentionally removed, do not make stale tests pass by re-registering the removed route. Keep one explicit removal test that asserts the legacy path returns 404, and migrate any old flow coverage to the current owning API or to a pure service/repository contract test.

For metadata persistence tests, prefer preserving the backend assertion while moving the HTTP path to the current domain. Example: a stale `/api/v1/jobs` sqlite/MySQL flow should become a `/api/v1/document-jobs` flow or a repository parity test, while `test_legacy_jobs_api_paths_are_removed` remains the source of truth for the old route removal.
