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
.venv/bin/python scripts/ops/check_release.py
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
- When a new or changed API is consumed by the frontend, extend
  `scripts/ops/check_release.py` frontend-contract checks for the OpenAPI
  path/schema fields and the matching `frontend/src/api/*` wrapper/type needles;
  this catches drift such as request field renames before runtime smoke tests.

#### Scenario: Lightweight Document Job Incident Queue

##### 1. Scope / Trigger

- Trigger: a new operations queue needs cross-layer API contracts for triaging
  `document_jobs` without creating a persistent `Incident` resource.
- Keep the implementation as a read-mostly projection over existing
  `document_jobs`, events, files, and available action rules.

##### 2. Signatures

- `GET /api/v1/document-job-incidents`
- `GET /api/v1/document-job-incidents/{job_id}/diagnostics`
- `POST /api/v1/document-job-incidents/bulk-retry`
- `POST /api/v1/document-job-incidents/bulk-refresh`

##### 3. Contracts

- List filters may include `status`, `stage`, `failure_type`, `retryable`,
  `retry_count`, `stalled_minutes`, `q`, `sort`, `page`, and `page_size`.
- Response items wrap the existing `DocumentJobResponse` plus lightweight
  fields: `failure_type`, `priority`, `is_incident`, `retryable`,
  `retry_disabled_reason`, `stalled`, `stalled_minutes`, `blocked`,
  `suggested_action`, and `evidence_summary`.
- Diagnostics may include compact evidence links, recent event summaries, and
  file summaries, but must not expose storage internals such as object keys,
  buckets, checksums, presigned URLs, or full event payloads.
- Bulk retry must reuse `DocumentJobService.retry_job` and existing
  `build_available_actions` retry semantics; bulk refresh must not mutate state.

##### 4. Validation & Error Matrix

- Unknown `status`, `stage`, `failure_type`, `retry_count`, or `sort` -> `400`
  `invalid_request`.
- Empty, blank, duplicated, or over-limit `job_ids` -> `400 invalid_request`.
- Per-item job visibility/not-found/state failures in bulk operations -> partial
  item result with `ok=false`, `status_code`, `error_code`, and `detail`.
- Non-retryable selected items in bulk retry -> `skipped=true` and
  `error_code="not_retryable"`; do not abort the whole batch.

##### 5. Good/Base/Bad Cases

- Good: failed retryable job is classified, returned as retryable, and bulk
  retry requeues it through the existing retry path.
- Base: blocked QA or stalled active jobs are surfaced as incident projections
  even when the underlying job status is not `failed`.
- Bad: adding an `IncidentRecord`, incident repository, configurable rule store,
  or independent retry permission logic for this lightweight queue.

##### 6. Tests Required

- Backend tests must cover priority ordering, filters, summary counts, invalid
  filter errors, diagnostic privacy, bulk retry partial success/skips, audit
  recording for successful retries, and bulk refresh read-only behavior.
- OpenAPI export/check must be run after changing these schemas or routes.
- Frontend/browser smoke tests should mock this dedicated API rather than
  overloading the generic document job list endpoint.

##### 7. Wrong vs Correct

Wrong:

```python
class IncidentRecord(BaseModel):
    job_id: str
    status: str
```

Correct:

```python
class DocumentJobIncidentQueueItemResponse(BaseModel):
    job: DocumentJobResponse
    failure_type: DocumentJobIncidentFailureType
    retryable: bool = False
    suggested_action: str
```

#### Scenario: Managed Internal User Accounts

##### 1. Scope / Trigger

- Trigger: internal users become a managed product capability rather than a
  startup-only JSON/env configuration source.
- This is cross-layer work: metadata storage, auth service, admin APIs, audit
  events, OpenAPI snapshots, and frontend route/type contracts must move
  together.
- Keep the scope to managed internal `admin` / `operator` users. Do not add SSO,
  OAuth, SAML, LDAP, MFA, self-registration, email/SMS reset, custom
  permissions, user deletion, teams, or org hierarchy in this scenario.

##### 2. Signatures

- DB/file repository port: `InternalUserRepositoryProtocol`
  - `count_internal_users() -> int`
  - `list_internal_users(role=None, status=None) -> list[InternalUserRecord]`
  - `get_internal_user(user_id) -> InternalUserRecord | None`
  - `get_internal_user_by_username(normalized_username) -> InternalUserRecord | None`
  - `save_internal_user(user) -> InternalUserRecord`
- DB schema: sqlite/MySQL table `internal_users` with `user_id`,
  `normalized_username`, `role`, `status`, `payload`, `created_at`, and
  `updated_at`; `normalized_username` is unique.
- APIs:
  - `GET /api/v1/users`
  - `POST /api/v1/users`
  - `PATCH /api/v1/users/{user_id}`
  - `POST /api/v1/users/{user_id}/reset-password`
  - `POST /api/v1/auth/change-password`

##### 3. Contracts

- `InternalUserResponse` must never include `password_hash`, raw passwords,
  bearer tokens, or JWTs.
- The managed repository is the runtime source of truth. `AUTH_INTERNAL_USERS_FILE`
  and `AUTH_INTERNAL_USERS_JSON` are bootstrap inputs only when the repository is
  empty; once any managed user exists, do not auto-merge configured users.
- JWT payloads must include a freshness value such as `token_version`, and bearer
  validation must reload the current repository record.
- Role-derived permissions remain centralized in `permissions_for_role`; add
  route permissions such as `users:manage` there rather than per-user grants.
- Successful lifecycle operations must write audit events with safe details only:
  `auth.login`, `auth.change_password`, `users.create`, `users.update`,
  `users.disable`, `users.enable`, and `users.reset_password`.

##### 4. Validation & Error Matrix

- Missing/invalid bearer token -> `401 unauthorized` / `401 invalid_token`.
- Non-admin access to `/users` -> `403 role_forbidden`.
- Blank username or blank/weak password -> `400 invalid_request`.
- Duplicate username after case-insensitive normalization -> `409 user_conflict`.
- Unknown user id -> `404 not_found`.
- Disabling or downgrading the last active admin -> `409 last_admin_conflict`.
- Disabled users cannot log in, and disabled users' existing tokens must fail
  validation because the repository record is reloaded.

##### 5. Good/Base/Bad Cases

- Good: config users seed an empty file/sqlite/MySQL repository once, then all
  login and `/auth/me` calls read the repository.
- Base: admin creates an operator, resets their password, disables the account,
  and the old token immediately fails.
- Bad: keeping config JSON as a live fallback after managed users exist, exposing
  `password_hash` in response schemas, or letting MySQL duplicate-key upserts
  overwrite an existing user on username conflict.

##### 6. Tests Required

- Repository parity test for file/sqlite/MySQL covering create/update, lookup by
  normalized username, role/status filtering, and token version persistence.
- API tests for admin-only list/create/update/reset, duplicate username,
  last-active-admin protection, self change-password, disabled login rejection,
  token invalidation, and audit events without password/hash/token content.
- Existing auth compatibility tests for configured-user bootstrap, login, `/me`,
  invalid/expired tokens, and wrong-role access.
- OpenAPI export/check and frontend build must pass after contract changes.

##### 7. Wrong vs Correct

Wrong:

```python
if repository.get_internal_user_by_username(username_key) is None:
    return configured_users_by_username.get(username_key)
```

Correct:

```python
if user_repository.count_internal_users() == 0:
    bootstrap_configured_users_once()
user = user_repository.get_internal_user_by_username(username_key)
```

#### Scenario: Local MinerU Phase-2 Quality Matrix

##### 1. Scope / Trigger

- Trigger: local-only MinerU PDF-to-Word quality hardening needs a repeatable
  command that runs current `mineru_result/` samples, collects DOCX structure
  evidence, and produces manual visual QA artifacts without changing online
  APIs or the formal renderer path.
- Keep this workflow under `scripts/dev/` and `tests/tmp/`; do not commit local
  DOCX, PNG/PDF renders, full translation traces, API keys, or proprietary PDFs.

##### 2. Signatures

- Command:
  `scripts/dev/run_local_mineru_quality_matrix.py`
- Key args:
  `--sample-set phase2-core`, repeated `--sample-id`, repeated `--mode direct|en2zh`,
  `--translation-response-dir`, `--output-dir`, `--no-timestamp`, `--dry-run`,
  and `--allow-blockers`.
- Default output:
  `tests/tmp/local_mineru_quality/<run_id>/report.json`, `report.md`,
  `manual-signoff-template.yaml`, and `docx/<mode>/<sample>.docx`.

##### 3. Contracts

- `phase2-core` must cover `OPA228_P1`, `OPA228_P2`, `OPA228_P6`,
  `OPA228_P7`, and `RS2G04`.
- Direct mode uses the datasheet Word template, datasheet YAML layout config,
  and subscript term rules from `resources/`.
- En2zh mode requires either `OPENAI_API_KEY` or a matching local response file
  under `--translation-response-dir`; it must not silently fall back to direct.
- Reports must include sample metadata, MinerU page/block/image stats, DOCX
  hash/openability, `docx_quality_flags`, P0/P1/P2 issues, standard render
  commands, acceptance layers, and phase-3 entry blockers.

##### 4. Validation & Error Matrix

- Unknown sample id -> `ValueError`.
- Missing local MinerU package -> per-entry `blocked` with
  `sample_input_missing`.
- En2zh without API key or response -> per-entry `blocked` with
  `translation_api_key_missing`.
- Runtime conversion exception -> per-entry `failed` with the exception class
  name as `error_code`.
- DOCX zip not openable -> quality issue `docx_not_openable`.

##### 5. Good/Base/Bad Cases

- Good: `--mode direct --sample-set phase2-core` writes five successful DOCX
  entries and flags P1/P2 quality risks without marking generated outputs for
  commit.
- Base: en2zh without key/response records an environment blocker and does not
  call the conversion runtime.
- Bad: storing a real API key in JSON/report output, committing
  `tests/tmp/local_mineru_quality`, importing the formal renderer as the
  generation path, or treating manual visual QA as automated pass.

##### 6. Tests Required

- Unit tests must assert the `phase2-core` sample ids and P0 membership.
- Unit tests must cover dry-run report generation, MinerU stats extraction,
  en2zh missing-key blocker behavior, and successful DOCX quality extraction.
- When the command or report contract changes, run
  `tests.test_local_mineru_quality_matrix`,
  `tests.test_component_pdf_sample_governance`, and
  `tests.test_conversion_sandbox_dev_tools`.

##### 7. Wrong vs Correct

Wrong:

```bash
.venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config local_en2zh.json || true
```

Correct:

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --mode en2zh \
  --sample-id OPA228_P1 \
  --translation-response-dir tests/tmp/local_mineru_debug/en2zh_responses \
  --allow-blockers
```

#### Scenario: Acceptance Center Latest Evidence Summary

##### 1. Scope / Trigger

- Trigger: admin Acceptance Center exposes cross-layer evidence state consumed by
  the frontend release UI and release checks.
- The summary is a derived view over compact acceptance run metadata. It must not
  become a second persisted source of truth or mutate evidence records.

##### 2. Signatures

- `GET /api/v1/acceptance/runs`
- `POST /api/v1/acceptance/runs`
- `GET /api/v1/acceptance/runs/{run_id}`
- `GET /api/v1/acceptance/runs/latest-summary`
- `POST /api/v1/acceptance/runs/{run_id}/review`

##### 3. Contracts

- `AcceptanceRunRecord` uses tier values `P0`, `P1`, `P2`; status values
  `passed`, `failed`, `unknown`; and review decisions `approved`, `rejected`,
  `needs_changes`.
- `latest-summary` returns `overall_status`, `missing_tiers`, `blocker_count`,
  `warning_count`, `latest_reviewed_run`, `tiers`, and `generated_at`.
- `overall_status` is derived as `incomplete` when any tier is missing,
  `blocked` when latest tier evidence has blockers or failed status,
  `needs_attention` when latest tier evidence has warnings or unknown status,
  and `accepted` only when all latest tier evidence is present and clean.
- Evidence recency follows `finished_at`, then `started_at`, then `updated_at`.
  Review actions may update metadata, but must not make an older evidence run the
  latest run for its tier.
- `POST /acceptance/runs` is an admin evidence-registration API. Creating a new
  run id returns `201`; replacing an existing id returns `200` and clears stale
  `reviewer`, `decision`, `reviewed_at`, and `review_note` so new evidence must
  be reviewed again.
- Review endpoints update `reviewer`, `decision`, `reviewed_at`, and
  `review_note` only. They must not change the evidence `status`, `blockers`, or
  `warnings`.

##### 4. Validation & Error Matrix

- Missing bearer token -> `401 unauthorized`.
- Non-admin access -> `403 role_forbidden`.
- Unknown `run_id` -> `404 not_found`.
- Invalid tier, status, or decision enum -> FastAPI/Pydantic validation error.
- `finished_at` earlier than `started_at` on an upserted run -> `400
  invalid_request`.
- Partial review metadata in storage -> model validation error; review metadata
  must be stored together.

##### 5. Good/Base/Bad Cases

- Good: P0 passed, P1 missing, P2 unknown returns `overall_status=incomplete`,
  includes `P1` in `missing_tiers`, and keeps P2 blockers visible.
- Base: an admin approves an unknown run; the review audit is written, but the
  run status remains `unknown` and the UI still shows warnings/blockers.
- Base: an admin replaces a previously reviewed run with fresh evidence; the old
  review fields are removed and the upsert audit records whether an existing run
  was replaced.
- Bad: deriving acceptance from the latest reviewed run, storing a separate
  overall status record, treating `approved` as equivalent to `passed`, or
  carrying an old review decision onto newly registered evidence.

##### 6. Tests Required

- API tests must cover admin-only access, list/detail/filter, run upsert,
  replacing a reviewed run, invalid run times, `latest-summary`, review
  persistence, audit event details, and missing-run errors.
- Service tests must cover the evidence-time ordering invariant where reviewing
  an older run does not make it the latest tier evidence.
- OpenAPI export/check, frontend contract needles, frontend API wrapper unit
  tests, and Acceptance Center smoke mocks must be updated when fields or paths
  change.

##### 7. Wrong vs Correct

Wrong:

```python
latest = max(runs, key=lambda record: record.updated_at)
overall_status = "accepted" if latest.decision == "approved" else "blocked"
```

Correct:

```python
latest = max(runs, key=lambda record: record.finished_at or record.started_at or record.updated_at)
overall_status = derive_from_latest_tier_status_blockers_and_warnings(tiers)
```

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
  `.venv/bin/python scripts/ops/check_release.py`

`scripts/ops/check_release.py` checks OpenAPI freshness, frontend contract
needles, smoke mock contract needles, and a curated backend unittest target set.
Frontend contract needles should cover every frontend-consumed API surface that
has a stable wrapper, including path availability, required schema fields, and
request body field names that differ from page-local form names.

### Convention: Local MinerU Runtime Layout Tuning

**What**: First-stage PDF-to-DOCX layout tuning for local MinerU samples belongs
in the legacy/local conversion runtime (`app/conversion/runtime_*`,
`app/conversion/runtime_rendering_api.py`, `app/conversion/runtime_helpers.py`,
and local template config/resources) plus focused characterization tests.
Do not change the formal renderer under `app/services/renderer/*` unless the
task explicitly promotes the behavior to the production rendering path.

**Contracts**:

- Page size, margins, header distance, and footer distance must come from
  `resources/template_configs/datasheet_template.yaml` when that YAML provides
  them. PDF `page_size` is source-layout evidence for bbox/ratio estimates only;
  it must not set Word section dimensions or orientation while configured page
  size exists. The DOCX template is only a source for page furniture such as
  header logo/footer decoration; body typography should be controlled by runtime
  config and language overrides.
- Runtime language overrides may choose the default font family for the detected
  output language, but font size, line spacing, paragraph spacing, and table
  sizing must remain controlled by the YAML style groups.
- TOC pages are document front matter. When non-TOC content follows a detected
  TOC page, insert a Word page break even if the final TOC page has enough blank
  space for the next section.
- Pagination is estimated before rendering. Keep the planner conservative:
  title anchors require room for at least two body lines, table anchors require
  caption plus header plus one data row, and figure/table captions and notes
  should move with their visual block when possible.
- Treat tables estimated at more than two rendered pages as long tables. Tables
  estimated at two pages or less should keep the standard editable table path
  and may flow naturally.
- Datasheet tables should render as plain editable tables by default. Header
  text may be bold when the source or style calls for it, but do not add
  decorative header fill unless the YAML table style explicitly opts in.
- Numbered table captions that are actually section headings, such as
  `6.4 Thermal Information: ...`, should use the matching heading style rather
  than the centered `Caption` style.
- Source-positioned two-column regions may be represented with hidden-border
  layout tables when MinerU bboxes already expose left/right columns. Do not
  add post-generation DOCX repair passes to hide pagination mistakes.

**Example**:

```python
flow_plan = build_page_flow_plan(regions, render_config, page_width, usable_width)
for region in regions:
    if flow_plan.should_break_before_region(region):
        insert_page_break(document)
    render_region(region)
```

**Tests Required**: Add or update `unittest` characterization tests for config
loading, configured section sizing independent of source PDF page size,
flow-plan page breaks, TOC/non-TOC separation, TOC/column detection, table
threshold decisions, heading-like table captions, and table style tokens. For
visual acceptance, generate representative local MinerU DOCX files, render them
with the document renderer to PDF/PNG, and inspect page images for orphan
headings, table-caption splits, header-only tables, separated figure captions,
unwanted table header fills, and avoidable large page gaps.

**Bad**: silently shrinking everything after DOCX generation, adding a second
renderer path under `app/services/renderer/*`, or making LibreOffice/rendered
PNG artifacts part of committed runtime resources.

## Scenario: Safe Document File Summaries For Job-Facing APIs

### 1. Scope / Trigger

- Trigger: An API response exposes document file metadata to task detail pages,
  download authorization responses, or other operator-facing surfaces.
- This is cross-layer because the backend schema, OpenAPI snapshot, frontend
  hand-written types, task page quality evidence, and regression tests must stay
  aligned.

### 2. Signatures

- Full internal/admin file metadata schema:
  `DocumentFileResponse`
- Operator/job-facing safe schema:
  `DocumentFileSummaryResponse`
- Job files response:
  `GET /api/v1/document-jobs/{job_id}/files -> DocumentJobFileListResponse`
- Download authorization response:
  `GET /api/v1/document-jobs/{job_id}/download-url -> DocumentJobDownloadUrlResponse`

### 3. Contracts

- `DocumentFileSummaryResponse` may expose:
  `id`, `tenant_id`, `company_id`, `job_id`, `file_type`,
  `storage_provider`, `original_filename`, `mime_type`, `size_bytes`,
  `status`, `expires_at`, `created_by`, `created_at`, `updated_at`, and
  `quality_evidence`.
- It must not expose object location or raw storage metadata:
  `bucket`, `object_key`, `checksum_sha256`, `etag`, raw `metadata`, local
  paths, file bytes, or presigned URLs.
- `quality_evidence` is a whitelist projection for detail-page review only. It
  may include known quality flags, layout counters, renderer/template labels,
  and `docx_quality` counters, but must not pass through arbitrary metadata.

### 4. Validation & Error Matrix

- Missing/invalid Bearer token for document job APIs -> `401 unauthorized` /
  `401 invalid_token`.
- Job/file ownership mismatch -> `403 forbidden`.
- File type is not job-downloadable -> `409 conflict`.
- File status is not `uploaded` -> `409 conflict`.
- `expires_at <= utc_now()` for default result or explicit `file_id` downloads
  -> `409 conflict`.

### 5. Good/Base/Bad Cases

- Good: job detail lists `generated_word` with `quality_evidence.docx_quality`
  and without `object_key`.
- Base: source PDF download authorization returns a safe file summary and a
  short-lived `download_url`.
- Bad: reusing `DocumentFileResponse` in a job-facing response leaks
  `bucket`, `object_key`, `checksum_sha256`, `etag`, or raw `metadata`.

### 6. Tests Required

- Backend API tests must assert job-facing file payloads do not contain
  `bucket`, `object_key`, `checksum_sha256`, `etag`, or raw `metadata`.
- Download tests must cover both explicit `file_id` expiry and default
  generated Word expiry.
- OpenAPI must be regenerated after schema changes.
- Frontend unit/build validation must cover hand-written type changes and
  quality evidence reading.
- `scripts/ops/check_release.py` should pass for cross-layer API contract
  changes.

### 7. Wrong vs Correct

#### Wrong

```python
return DocumentJobFileListResponse(
    job_id=job.id,
    files=[DocumentFileResponse(**file.model_dump(mode="python")) for file in files],
)
```

#### Correct

```python
return DocumentJobFileListResponse(
    job_id=job.id,
    files=[_build_document_file_summary_response(file) for file in files],
)
```

## Scenario: Translation Language Pair Defaults

### 1. Scope / Trigger

- Trigger: a new translation language pair is added to document jobs, for example
  `ru2zh` alongside `en2zh`.
- This is cross-layer work because mode metadata, seed data, MySQL bootstrap,
  resource snapshots, config-summary readiness, frontend display text, and
  release checks must agree before the mode can be selected in the UI.

### 2. Signatures

- Mode registry: `app.domains.translation.modes.TRANSLATION_MODE_SPECS`.
- Translation term seed: `resources/term_rules/translation_terms.csv` with
  `language_pair,source_term,target_term,version`.
- Runtime bootstrap:
  `TermVersionService.bootstrap_repository_from_csv_if_empty()` and
  `TranslationProfileVersionService.bootstrap_default_profiles_if_missing()`.
- API config summary:
  `GET /api/v1/document-jobs/config-summary` returns legacy
  `defaults.translation_term_set` / `defaults.translation_profile` for en2zh
  compatibility and `translation_defaults[language_pair]` for mode-specific
  defaults.
- UI readiness codes may include a language-pair suffix:
  `translation_term_set_default_missing:<language_pair>` and
  `translation_profile_default_missing:<language_pair>`.

### 3. Contracts

- Every supported translation `language_pair` must have a default Translation
  Term Set ID derived from `derive_translation_term_set_id(language_pair)`.
- MySQL startup must import missing default term sets for newly supported
  language pairs from the CSV seed without replacing existing defaults.
- MySQL startup must seed a published/default Translation Profile for every
  supported default profile ID without overwriting an already configured default.
- Config summary marks a translation mode available only when both the default
  Translation Term Set and Translation Profile are present and published.
- Config summary must expose operator-visible defaults per language pair in
  `translation_defaults`; operators cannot select explicit resource versions,
  so the create UI must not infer ru2zh defaults from the legacy en2zh
  `defaults.translation_*` fields.
- `defaults.translation_term_set` and `defaults.translation_profile` remain
  en2zh compatibility fields until legacy frontend/backend clients no longer
  need them.
- Frontend readiness text must parse suffixed codes and display the language
  pair using user-facing copy such as `ru2zh -> 俄译中`.

### 4. Validation & Error Matrix

- Missing Translation Term Set default -> config-summary warning
  `translation_term_set_default_missing:<language_pair>` and the mode is not
  selectable.
- Missing Translation Profile default -> config-summary warning
  `translation_profile_default_missing:<language_pair>` and the mode is not
  selectable.
- Existing published/default en2zh resources -> startup leaves them unchanged.
- Missing CSV rows for a newly supported language pair -> startup cannot create
  that term set, and readiness must stay unavailable rather than silently
  falling back to another language pair.
- Missing `translation_defaults[language_pair]` in an older backend response ->
  frontend may fall back to legacy defaults only for `en2zh`; other language
  pairs must show unconfigured rather than displaying en2zh resources.

### 5. Good/Base/Bad Cases

- Good: deploying a new language pair to a database that already has en2zh
  defaults creates only the missing language pair defaults.
- Base: frontend displays `默认翻译术语集未发布（俄译中）` instead of an unknown
  readiness-code message while the backend remains not ready for that mode.
- Base: operator selects `ru2zh`; the UI shows `translation-terms-ru2zh@...`
  and `electronics-ru2zh@...` from `translation_defaults.ru2zh` while still
  omitting explicit resource-version fields from the create payload.
- Bad: hard-coding ru2zh outside the mode registry, reusing en2zh term sets for
  ru2zh, or treating prompt existence alone as enough to enable the mode.

### 6. Tests Required

- Backend bootstrap regression: start with existing en2zh term/profile defaults,
  add a new language-pair CSV seed, rebuild runtime, and assert the new default
  term set and profile are present.
- Config summary/API tests must assert the mode is available only when both
  translation resources exist for the selected language pair.
- Config summary/API tests must assert operator responses include
  `translation_defaults` for every supported language pair and keep admin-only
  `options` hidden from operators.
- Frontend utility tests must assert suffixed readiness codes map to the correct
  Chinese message and settings route.
- Frontend utility tests must assert selected-mode default resolution uses
  `translation_defaults.ru2zh` instead of legacy en2zh defaults.
- `scripts/ops/check_release.py` and `frontend` build must pass after changing
  mode metadata or readiness display behavior.

### 7. Wrong vs Correct

#### Wrong

```python
if repository.has_version("en2zh", "v1"):
    return
```

#### Correct

```python
for language_pair in TRANSLATION_LANGUAGE_PAIRS:
    if not repository_has_default(language_pair):
        import_seed_entries_for(language_pair)
```

#### Wrong

```typescript
const value = summary.defaults.translation_term_set?.label;
```

#### Correct

```typescript
const value = summary.translation_defaults[translationMode]?.translation_term_set?.label;
```

## Scenario: Runtime AI Provider Configuration

### 1. Scope / Trigger

- Trigger: admins need to change the translation AI provider without editing
  environment files or restarting the API.
- This is cross-layer work because `Settings`, runtime composition, provider
  calls, health readiness, audit events, OpenAPI, frontend wrappers, and the
  protected settings UI must use the same effective provider contract.

### 2. Signatures

- Setting: `AI_PROVIDER_CONFIG_PATH`, defaulting to
  `var/config/ai_provider_config.json`.
- Runtime service: `AiProviderConfigService.get_effective_config()`.
- APIs:
  - `GET /api/v1/ai-provider-config`
  - `PUT /api/v1/ai-provider-config`
- Frontend route: `/settings/ai-provider`, admin-only.

### 3. Contracts

- `AiProviderConfigUpdateRequest` fields:
  `backend`, `base_url`, `model`, `timeout_seconds`, `max_output_tokens`,
  `api_key`, and `clear_api_key`.
- `AiProviderConfigResponse` fields:
  `backend`, `base_url`, `model`, `timeout_seconds`, `max_output_tokens`,
  `api_key_configured`, `api_key_mask`, `source`, `updated_at`, and
  `updated_by`.
- API responses and audit details must never include the raw `api_key`.
- The persisted runtime config is an override over environment `Settings`; when
  no runtime config exists, provider calls and health checks use `Settings`.
- `HealthService.build_dependency_checks()` must report the effective
  `translation_provider_backend`, `openai_model`,
  `openai_api_key_configured`, `openai_base_url_configured`,
  `ai_provider_config_source`, and `ai_provider_config_error`.
- Runtime config files should be written with owner-only permissions where the
  filesystem supports it.

### 4. Validation & Error Matrix

- Missing bearer token -> `401 unauthorized`.
- Non-admin access to the AI config API -> `403 role_forbidden`.
- Invalid request enum/ranges -> FastAPI/Pydantic `422 validation_error`.
- Unreadable JSON or schema-invalid config file -> health dependency check
  `ai_provider_config_error="ai_provider_config_invalid"`.
- `default_translation_mode=en2zh` plus invalid AI config -> readiness blocker
  includes `ai_provider_config_invalid`; direct mode treats it as a warning.

### 5. Good/Base/Bad Cases

- Good: admin saves `openai_compatible` config, response returns a masked key,
  health uses the new model/base URL, and the audit event only records safe
  fields.
- Base: admin leaves `api_key` blank on update, preserving the existing runtime
  secret; `clear_api_key=true` removes the saved runtime secret.
- Base: provider calls resolve effective config at call time, so subsequent UI
  saves affect new translation attempts without rebuilding the process.
- Bad: reading `OPENAI_API_KEY` directly in translation code after runtime
  config exists, exposing raw keys in API/audit/logs, or treating invalid config
  as a silent success.

### 6. Tests Required

- API tests must cover admin update, non-admin rejection, masked response,
  audit details without raw `api_key`, and health checks reading runtime config.
- Health tests must cover schema-invalid config files returning
  `ai_provider_config_invalid`.
- Translation retry/provider tests should use fake providers or temp config
  files and must not call real OpenAI-compatible endpoints.
- OpenAPI export/check, frontend contract needles, and `npm run build` must pass
  after changing this API or frontend wrapper.

### 7. Wrong vs Correct

#### Wrong

```python
client = OpenAI(api_key=settings.openai_api_key)
```

#### Correct

```python
config = ai_provider_config_service.get_effective_config()
client = OpenAI(api_key=config.api_key, base_url=config.base_url or None)
```

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

## Scenario: Formal DocumentIR Renderer Parity Gate

### 1. Scope / Trigger

- Trigger: local MinerU-to-DOCX quality rules are migrated into the formal
  `document_jobs -> DocumentIR -> app/services/renderer/*` path.
- This gate proves implementation readiness locally, then hands off P0 Golden
  Sample release evidence to hostdzire.

### 2. Signatures

- Formal conversion: `MinerUToDocumentIRService.convert_zip(...)`.
- Formal render call:
  `DocumentIRWordRenderer.render_to_bytes(document_ir, template_path, config_path, image_loader, options=DocumentIRRenderOptions(...))`.
- Per-call renderer options: `DocumentIRRenderOptions(subscript_config_path, document_language)`.
- P0 acceptance command: `python scripts/ops/run_golden_sample_regression.py`.

### 3. Contracts

- Shared pure rules that affect both local runtime and formal renderer belong
  under `app/conversion/docx_rules/`; runtime modules may re-export those names
  for compatibility but must not keep duplicate active implementations.
- `DocumentIR` remains the interchange shape; only add fields when source facts
  cannot fit existing page/block/layout/metadata/quality structures.
- `DocumentJobExecutionService` must pass active subscript config and document
  language into the formal renderer.
- Generated Word metadata must continue surfacing `renderer_mode`,
  `layout_quality_flags`, `docx_quality`, and `quality_flags`.
- Golden Sample P0 still means the four canonical OPA228 samples only; do not
  expand sample count as part of this gate.

### 4. Validation & Error Matrix

- Local targeted tests fail -> do not start hostdzire Golden Sample validation.
- `check_release.py` fails locally -> resolve OpenAPI/contract/unit failures
  before deployment.
- Hostdzire preflight fails -> do not run real Golden Sample conversion; fix
  readiness/auth/MySQL/Celery/MinerU blockers first.
- Real Golden Sample succeeds without admin sign-off -> not release ready.
- Admin signs `pass` with `docx_quality_flags` but no notes -> sign-off
  validation must fail.

### 5. Good/Base/Bad Cases

- Good: converter, renderer, document_jobs worker, Golden Sample manifest, and
  local release checks pass before deployment; hostdzire then produces a fresh
  run with `p0_release_ready=true`.
- Base: local checks pass but hostdzire is unavailable; record the external
  gate as pending, not passed.
- Bad: proving quality only through local sandbox output, reusing a historical
  sign-off for a new code revision, or committing generated DOCX/PNG/PDF/key
  evidence.

### 6. Tests Required

- Converter tests for nested v2 pages, legacy flat content, captions,
  footnotes, visual assets, table continuations, and page orientation.
- Renderer tests for heading, Word numbering, TOC tab leaders, formula/symbol
  normalization, subscript config, caption/notes, editable tables, long/wide
  tables, two-column regions, and landscape sections.
- document_jobs tests proving the behavior through worker execution and
  generated Word metadata, not only direct renderer calls.
- Golden Sample manifest/sign-off tests for canonical sample inventory,
  preflight contract, DOCX quality flags, and admin sign-off validation.
- Local `scripts/ops/check_release.py` before deployment; hostdzire
  `check_release.py --runtime-url ... --golden-sample-preflight` before real
  Golden Sample conversion.

### 7. Wrong vs Correct

Wrong:

```python
word_content = local_sandbox_renderer.render(mineru_pages)
```

Correct:

```python
word_content = DocumentIRWordRenderer().render_to_bytes(
    document_ir,
    template_path=template_path,
    config_path=config_path,
    image_loader=image_loader,
    options=DocumentIRRenderOptions(
        subscript_config_path=settings.subscript_config_path,
        document_language=document_ir.metadata.document_language,
    ),
)
```

## Scenario: Local MinerU Conversion Sandbox Tools

### 1. Scope / Trigger

- Trigger: local development needs to run MinerU result directories or zips
  without making `md2word_main` a second source of conversion code.
- The official conversion code source is `app/conversion` in this repository.
  Local CLIs must be thin wrappers over the official runtime.

### 2. Signatures

- `python scripts/dev/run_local_mineru_debug_config.py [--config PATH]`
- `scripts/dev/local_mineru_debug_config.json`
- `python scripts/dev/run_local_mineru_conversion.py [input_path] [--output PATH]`
- `python scripts/dev/audit_conversion_sandbox.py --sandbox-root PATH drift`
- `python scripts/dev/audit_conversion_sandbox.py --sandbox-root PATH samples`
- `python scripts/dev/audit_conversion_sandbox.py --sandbox-root PATH thin`
- `python scripts/dev/migrate_md2word_main_sandbox.py --sandbox-root PATH [--apply]`
- Runtime binding entrypoint: `app.conversion.runtime_runner.ensure_runtime_bound()`

### 3. Contracts

- The local conversion CLI must call
  `app.conversion.runtime_runner.run_conversion`; it must not import or execute
  `md2word_main/mineru_to_docx.py`.
- The PyCharm-friendly default entrypoint is
  `scripts/dev/run_local_mineru_debug_config.py`, which reads
  `scripts/dev/local_mineru_debug_config.json` by default and resolves relative
  paths from the official repository root.
- Absolute config paths may point at `md2word_main/mineru_result` because
  `md2word_main` is now only a historical sample-asset source.
- Local PDF debugging must improve the shared parser/renderer in
  `app/conversion` when a MinerU package exposes a reusable defect. Do not add a
  one-sample debug config to compensate for a broken official conversion path.
- `md2word_main/mineru_to_docx.py` is deprecated. It must print a migration
  message pointing to `run_local_mineru_debug_config.py`, exit non-zero, and
  never proxy into `scripts.dev.run_local_mineru_conversion`.
- `runtime_facade.load_pages()` and `runtime_runner.run_conversion()` must bind
  legacy runtime modules before calling `load_pages` or `build_document`.
- Explicit local `document_language` overrides must preserve all supported
  values (`zh`, `en`, and `ru`) instead of treating non-English languages as
  auto-detect input. Translation modes still render the final document as `zh`.
- MinerU v2 input loading must accept `layout.json` or `*_layout.json` as the
  page metadata source when `middle.json` is absent, including
  `pdf_info[*].page_size` so layout/bbox estimators can use source dimensions.
  Generated Word section size remains governed by configured page setup.
- Multiline table-of-contents paragraphs from `content_list_v2` that mostly
  contain dot-leader lines must be split into list entries and rendered with Word
  dot-leader tab stops, not flattened into one paragraph with literal dots.
- Inline formula nodes collected from captions, footnotes, and paragraph
  fragments must normalize their `content` only. Structural keys such as `type`
  with value `equation_inline` must never become visible Word text, and common
  TeX fragments such as `\overline{A}` or `^{(1)(2)}` must not leak raw syntax.
- Visual footnotes parsed from rich MinerU node lists must merge inline formula,
  punctuation, and connector fragments into the numbered note they belong to,
  while preserving independent unnumbered notes as separate paragraphs.
- Local MinerU table rendering must keep the Word table semantics used by the
  service renderer: repeat the first row as the table header and mark rows with
  `w:cantSplit` so Word moves oversized rows across pages instead of splitting a
  row into unreadable fragments.
- When a source page starts with a top-level numbered section title after a
  dense visual/table page that reaches the page bottom, the renderer should
  start a new Word page for that section. Do not force the break when the
  previous source page already visibly overflows, because the continuation space
  should be reused instead of creating mostly blank pages.
- Drift audits are read-only and compare relative paths such as
  `app/conversion` and `resources`; they report drift instead of copying files.
- Sample inventory audits are read-only and list `test_pdf/*.pdf` plus
  `mineru_result/*` package capabilities.
- Thin-shell audits fail when active duplicate sources such as `app`, `cli_core`,
  or `resources` still exist in `md2word_main`.
- The migration script archives duplicate sources under `_legacy_duplicate_core/`
  and writes only the debug entrypoint, config, README, and thin-shell test.

### 4. Validation & Error Matrix

- Missing local conversion input -> CLI/config entry exits with an explicit
  input-path error.
- Unknown config keys -> config entry exits before calling runtime conversion.
- Running `md2word_main/mineru_to_docx.py` -> deprecated message and non-zero
  exit; no conversion output is produced.
- Sandbox drift present -> drift command exits non-zero unless `--allow-drift`
  is provided.
- Missing sandbox paths -> report one-sided files or empty inventories; do not
  create fallback success.
- Active duplicate sources in a migrated sandbox -> thin-shell audit exits
  non-zero; do not treat archived duplicate code as importable runtime code.
- Missing runtime binding -> regression tests must catch `PageData is not bound`
  or equivalent model-binding failures.
- Missing `middle.json` with present `layout.json` -> local conversion still
  loads page metadata and keeps source page size available for layout estimates;
  do not silently treat source dimensions as unknown.
- TOC-like multiline paragraphs -> list entries with semantic page-number tab
  stops; do not emit a single paragraph of dot-leader text.
- Caption/footnote inline formulas -> normalized formula text only; no visible
  `equation_inline`, `inline_formula`, raw `\overline`, or raw leading `^{...}`
  syntax.

### 5. Good/Base/Bad Cases

- Good: a PyCharm run configuration points at
  `scripts/dev/run_local_mineru_debug_config.py`, uses the project Python 3.11
  interpreter, leaves parameters empty, and edits
  `scripts/dev/local_mineru_debug_config.json` for input/output choices.
- Base: `run_local_mineru_conversion.py` remains available for one-off shell
  commands with explicit arguments.
- Base: `md2word_main` keeps historical sample assets, but its runtime entrypoint
  is deprecated and cannot execute conversion.
- Base: a migrated `md2word_main` keeps `test_pdf/`, `mineru_result/`, and
  `out/`, while copied conversion code is isolated under `_legacy_duplicate_core/`.
- Bad: copying `md2word_main/app/conversion` over this repository, or adding a
  second thick CLI that binds runtime modules independently.
- Bad: regenerating a `md2word_main/mineru_to_docx.py` proxy that calls
  `run_local_mineru_conversion`.
- Bad: adding a local config that special-cases one problematic PDF instead of
  fixing the shared `app/conversion` parsing or rendering contract.

### 6. Tests Required

- Unit tests assert the thin CLI builds `run_conversion` kwargs and can take
  input from `MD2WORD_LOCAL_MINERU_INPUT`.
- Unit tests assert the PyCharm config entry reads JSON, resolves relative paths
  from the official repo root, accepts absolute `md2word_main/mineru_result`
  paths, rejects unknown config keys, and calls the shared runtime runner.
- Unit tests assert drift classification for same, changed, official-only, and
  sandbox-only files.
- Unit tests assert sample inventory detects PDFs and MinerU package evidence.
- Unit tests assert the migration script archives duplicate active paths and
  writes deprecated shell files without deleting sample assets.
- Unit tests assert thin-shell audit blocks active duplicate source paths.
- Unit tests assert `md2word_main/mineru_to_docx.py` does not mention or import
  `run_local_mineru_conversion`.
- Runtime binding tests assert `runtime_facade.load_pages()` works on a minimal
  MinerU v2 package without manual test-side binding.
- Runtime input-adapter tests assert `layout.json` page sizes are loaded,
  TOC-like multiline paragraphs become list entries, and visual metadata
  collection skips structural `type` labels while normalizing inline formulas.
- Text-rendering tests assert TOC page numbers use dot-leader tab stops and
  formula normalization removes raw `\overline{...}` and leading `^{...}` syntax.
- Page-layout tests assert configured page setup is used for Word section size
  while source PDF page sizes remain available only to layout estimates.
- Page-layout and table-rendering tests assert dense visual pages can force a
  new top-level section page without forcing already-overflowing pages, and that
  local MinerU tables emit `w:tblHeader` / `w:cantSplit` pagination semantics.
- A local smoke may run one real sandbox package to DOCX under `tests/tmp/`.

### 7. Wrong vs Correct

Wrong:

```python
from md2word_main.mineru_to_docx import run_conversion
```

Correct:

```python
from app.conversion import runtime_runner

runtime_runner.run_conversion(input_path=input_path, output_path=output_path, ...)
```

## Scenario: Component PDF Regression Sample Governance

### 1. Scope / Trigger

- Trigger: local electronic component PDF work discovers a layout or conversion
  issue that should be preserved as a repeatable regression sample.
- This workflow is for local MinerU package regression and sample governance,
  not for replacing the P0 Golden Sample release gate.

### 2. Signatures

- `tests/fixtures/component_pdf_samples/manifest.yaml`
- `python scripts/dev/manage_component_pdf_samples.py validate`
- `python scripts/dev/manage_component_pdf_samples.py add-mineru-sample ... [--apply]`
- `python scripts/dev/run_component_pdf_regression.py [--sample-id ID]`

### 3. Contracts

- Samples are organized as
  `tests/fixtures/component_pdf_samples/samples/<brand>/<category>/<sample-id>/mineru/`.
- Manifest entries must include `id`, `brand`, `category`, `product`,
  `source_pdf`, `mineru.package_path`, `tags`, `acceptance_focus`, and
  `regression.enabled`.
- The regression runner must call the official `app.conversion.runtime_runner`;
  it must not import or execute `md2word_main/mineru_to_docx.py`.
- Generated DOCX and reports belong under `tests/tmp/component_pdf_regression/`
  or external evidence storage.

### 4. Validation & Error Matrix

- Missing or duplicate sample id -> manifest validation fails.
- Missing brand/category/product/source metadata -> manifest validation fails.
- Missing MinerU `*_content_list_v2.json` or `*_content_list.json` -> manifest
  validation fails and the sample is not runnable.
- Per-sample conversion exception -> regression report item `status=failed`
  and non-zero CLI exit.

### 5. Good/Base/Bad Cases

- Good: a local OPA228 wide-table issue is added under
  `texas-instruments/op-amp/<sample-id>/mineru`, fixed in `app/conversion`,
  and verified with `run_component_pdf_regression.py --sample-id <sample-id>`.
- Base: proprietary PDFs stay outside the repo while a minimized public MinerU
  package and manifest reference are committed.
- Bad: adding a second copied conversion implementation under the sample tree,
  committing generated DOCX outputs, or treating this suite as P0 release
  signoff.

### 6. Tests Required

- Unit tests must validate manifest schema, brand/category path alignment, and
  existence of committed runnable MinerU fixtures.
- Unit tests must cover adding a MinerU sample into a temporary manifest.
- Unit tests must run the minimal local regression entrypoint on at least one
  committed sample and verify an openable DOCX/report is produced.

### 7. Wrong vs Correct

Wrong:

```python
from md2word_main.mineru_to_docx import main
```

Correct:

```python
from app.conversion import runtime_runner

runtime_runner.run_conversion(input_path=package_path, output_path=docx_path)
```

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
