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

### Scenario: Datasheet TOC Rendering Semantics

- Trigger: changing TOC recognition, translation text replacement, list rendering, DOCX quality flags, or DocumentIR Word rendering.
- Contract: explicit dot/ellipsis leaders plus a trailing page number are the TOC signal even when translation removes English numbering, Appendix, Table, or Figure prefixes. Examples such as `Features .... 1`, `特性 .... 1`, and `目录 .... 3` must render through the TOC paragraph path with a right-aligned dot leader tab.
- Guardrail: whitespace-only page suffixes remain stricter and should still require a known TOC-style title prefix, so ordinary body text ending in a number is not promoted to TOC.
- Tests required: add or update `tests/test_document_ir_word_renderer_layout.py` for rendered `w:leader="dot"` evidence, `tests/test_text_render_characterization.py` for shared legacy text rendering behavior, and DOCX quality tests so unformatted translated TOC entries still become `docx_plain_toc_entries:{count}`.
- Entry check: when debugging local/online generation, include a worker or renderer assertion that portrait source pages with wide tables remain portrait unless the source page dimensions are actually landscape.

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

## Scenario: P1 Formal Sample Manifest Gate

### 1. Scope / Trigger

- Trigger: changing `tests/fixtures/p1_translation_samples/manifest.yaml`, P1 sample documentation, or release evidence for `P1_TRANSLATION_FORMAL=1`.
- The formal gate is for `mode=en2zh_pdf_to_word` English datasheets. Russian or other-language samples belong to separate language-direction evidence and must not be counted toward the en2zh formal sample target.

### 2. Signatures

- Formal preflight command:
  ```bash
  P1_TRANSLATION_FORMAL=1 .venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight
  ```
- Formal regression command:
  ```bash
  P1_TRANSLATION_FORMAL=1 .venv/bin/python scripts/ops/run_p1_translation_regression.py
  ```
- Manifest contract: `tests/fixtures/p1_translation_samples/manifest.yaml` with `target_sample_count: 3`, `default_mode: en2zh_pdf_to_word`, and `source_status: available` for every formal sample.

### 3. Contracts

- Formal samples must be real English technical datasheet PDFs under a versioned fixture path or a private manifest passed through `P1_TRANSLATION_MANIFEST`.
- `sample_root` may reference another versioned fixture directory when reusing existing real datasheets; do not copy binaries just to satisfy the P1 folder layout.
- The committed default manifest must keep filenames basename-only because the P1 manifest test and report output use sample filenames as stable evidence labels.
- `P1_TRANSLATION_FORMAL=1` changes the required sample count from smoke mode to `target_sample_count`.

### 4. Validation & Error Matrix

- Fewer available samples than `target_sample_count` -> `p1_available_sample_count_below_required`.
- `source_status=available` but the PDF file is missing -> `p1_available_pdf_missing`.
- Manifest check passes but no credential is provided -> `p1_auth_missing`; this does not invalidate sample readiness.
- Runtime cannot be reached/authenticated -> `p1_runtime_unreachable`; rerun on hostdzire or staging with admin credentials.
- Russian/ru2zh sample offered for this gate -> document it as out of scope for en2zh, not as a substitute formal sample.
- Job remains `running` / `ir_converting` with translation batches stuck in `queued` -> verify the deployed worker command consumes `document_jobs_translation_batch_celery_queue` in addition to `document_jobs_celery_queue`.
- Missing or blank `document_jobs_translation_batch_celery_queue` in Celery mode -> readiness/preflight must surface `document_jobs_translation_batch_celery_queue_missing`, not only a generic health failure.

### 5. Good/Base/Bad Cases

- Good: manifest exposes 3 available real English datasheet PDFs, formal preflight manifest check passes, then hostdzire regression records jobs, DOCX outputs, QA, batch diagnostics, and admin manual signoff.
- Base: local formal preflight has no credentials, manifest check passes, and the report explicitly leaves auth/runtime as remaining blockers.
- Bad: marking P1 beta ready from one smoke PDF, counting ru2zh evidence toward en2zh, hiding sample-count or queue-readiness failure behind a generic runtime blocker, or running only the document-job Celery queue when translation batches route to a separate queue.

### 6. Tests Required

- `tests.test_p1_translation_sample_manifest` must assert the formal manifest has exactly `target_sample_count` samples, all formal samples are `available`, filenames are unique basenames, and the referenced PDFs exist.
- If the P1 regression script changes, keep `tests.test_p1_translation_batch_diagnostics` passing and add focused tests for any changed preflight/report projection behavior.
- If the worker entrypoint or health readiness changes, keep `tests.test_document_worker_entrypoint` and the targeted health readiness tests passing.
- Do not require local API, worker, MySQL, Redis/Celery, MinerU, browser, or real provider access for manifest-level validation.
- Hostdzire/staging formal runs must record whether `document-translation-batches` is being consumed. If a temporary worker is used to complete evidence, record that as an operations follow-up rather than treating it as normal release posture. The expected durable fix is `scripts/dev/run_document_worker.py` subscribing to both configured queues, or a documented dedicated batch worker.

### 7. Wrong vs Correct

#### Wrong

```yaml
samples:
  - id: p1-en-003
    filename: diode-ru.pdf
    source_status: available
```

#### Correct

```yaml
sample_root: tests/fixtures/golden_samples/pdfs
target_sample_count: 3
samples:
  - id: p1-en-003
    filename: OPA228_P7.pdf
    source_status: available
```

## Scenario: P1 Translation Batch Diagnostics Evidence

### 1. Scope / Trigger

- Trigger: changing P1 translation regression reporting, provider batch diagnostics evidence, or release/acceptance proof for long PDF translation recovery.
- The P1 script is an ops evidence contract: it is consumed by humans, runbooks, and Acceptance Center summaries, even though it is not a public API.

### 2. Signatures

- Command: `.venv/bin/python scripts/ops/run_p1_translation_regression.py`
- Private long-PDF override: `P1_TRANSLATION_MANIFEST=/path/to/private-manifest.yaml`
- Diagnostics read: `GET /api/v1/document-jobs/{job_id}/translation-batches`
- Report outputs: `tests/tmp/p1_translation_runs/<run_id>/report.json` and `report.md`

### 3. Contracts

- The script should collect translation batch diagnostics after terminal job state for every translation sample with a `job_id`, including failed jobs.
- `P1SampleResult` may include:
  - `translation_batch_diagnostics_available`
  - `translation_batch_diagnostics_error`
  - `translation_batch_generation`
  - `translation_batch_summary`
  - `translation_batches`
  - `translation_batch_warnings`
- Batch report rows may include status, page range, item/char count, attempts, split/root/parent ids, `finish_reason`, `retryable`, `truncation_retry`, provider call budget, shortened error summary, result file id, and AI call log file count.
- Report rows must not include full prompt, provider response body, source text, translated text, debug archive content, signed URLs, object storage locations, secrets, or AI call log file contents.
- AI call log file ids are safe for the Job Detail UI, but P1 report rows should prefer counts over copying ids when cross-job evidence is enough.

### 4. Validation & Error Matrix

- Diagnostics endpoint succeeds with batch items -> summarize status counts, leaf counts, budget, truncation observation, and sanitized batch rows.
- Diagnostics endpoint succeeds with no items for a translation job -> report `translation_batches_empty` / `translation_batch_diagnostics_empty`.
- Diagnostics endpoint is unavailable -> keep the sample terminal result visible and record `translation_batch_diagnostics_unavailable`.
- Any batch is `failed` -> report `translation_batches_failed` as an evidence blocker.
- No live truncation is observed -> report a warning such as `translation_batch_truncation_not_observed`; cite existing automated split tests as complementary evidence.

### 5. Good/Base/Bad Cases

- Good: a private long PDF succeeds with multiple bounded batches, all current leaf batches succeeded, and the report shows generation, budget, batch counts, page ranges, attempts, and AI log counts.
- Base: a small P1 smoke PDF succeeds with one provider batch and still records diagnostics.
- Bad: the report marks the job succeeded but omits translation batch diagnostics, stores full AI call logs, or hides diagnostics endpoint failure behind a generic sample failure.

### 6. Tests Required

- Unit test the pure diagnostics projection from representative `translation-batches` payloads.
- Assert split parent/child batches produce correct leaf counts and truncation observation.
- Assert failed batches become report blockers and long error messages are shortened.
- Assert Markdown/JSON report rendering does not include AI call log file ids when only counts are required.
- Keep tests local and mocked; do not require API, worker, MySQL, Redis/Celery, MinerU, browser, or real provider access.

### 7. Wrong vs Correct

#### Wrong

```python
payload = response.json()
result.translation_batches = payload["items"]
```

This copies every backend field into release evidence, including fields that may become unsafe later.

#### Correct

```python
diagnostics = build_translation_batch_diagnostics(response.json())
result.translation_batch_summary = diagnostics["summary"]
result.translation_batches = diagnostics["items"]
```

The report owns a sanitized projection and can enforce the redaction boundary in one place.

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
