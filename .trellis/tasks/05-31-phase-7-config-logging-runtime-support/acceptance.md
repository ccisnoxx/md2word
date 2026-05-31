---
doc_type: acceptance
task: 05-31-phase-7-config-logging-runtime-support
status: completed
parent: 05-31-project-directory-restructure
completed_at: 2026-05-31
---

# Phase 7 acceptance

## Summary

Phase 7 closed the configuration, logging, and runtime support slice. No
tracked runtime code changes were required: the current implementation already
has centralized logging, text/JSON log formatting, readiness required/non-
blocking classification, stage-spool observations, and release-check coverage.

The only implementation fix was in the ignored local `.env`: it still pointed
several path settings at the pre-restructure `data/`, `template_configs/`, and
`tests/golden_samples/` locations. Those non-secret path values were updated to
`var/`, `resources/`, `tests/fixtures/`, and `tests/tmp/`.

## Changes

- Created Phase 7 Trellis planning artifacts and linked the task under
  `05-31-project-directory-restructure`.
- Updated ignored local `.env` non-secret paths:
  - `DATA_DIR=data` -> `DATA_DIR=var`
  - `JOBS_METADATA_DATABASE_PATH=data/metadata.sqlite3` ->
    `JOBS_METADATA_DATABASE_PATH=var/metadata.sqlite3`
  - old `/app/data/...` runtime paths -> `var/...`
  - old `template_configs/...` resource paths -> `resources/...`
  - old `tests/golden_samples/...` paths ->
    `tests/fixtures/golden_samples/...` and `tests/tmp/...`

No token, password, API key, or JWT secret value was changed.

## Audit Results

Command:

```bash
rg -n "LOG_FORMAT|log_format|JsonLogFormatter|configure_logging|readiness_required_checks|readiness_non_blocking_checks|deployment_init_ready|translation_available|pdf_submission_available|stage_spool_observation_status|MINERU_API_TOKEN|DEFAULT_TRANSLATION_MODE" app tests docs .env.example .trellis/spec/backend
```

Result: current code, docs, tests, and specs all describe the Phase 7 logging
and readiness support surface.

Command:

```bash
rg -n "MD2WORD_API_BIND|JOBS_WORKER_MODE|STAGE_MESSAGE_LEASE_SECONDS|TRANSLATION_PROVIDER_BACKEND|TRANSLATION_DEBUG_ARCHIVE|TRANSLATION_TERMS_PATH|TERM_RULES_" .env.example docs app/core/config.py
```

Result: `.env.example`, docs, and `Settings` are aligned for worker mode, stage
lease, term-rule paths, and translation provider/debug options.

Command:

```bash
rg -n "^(DATA_DIR|JOBS_METADATA_DATABASE_PATH|JOBS_ARTIFACT_OBJECT_STORE_PATH|TEMPLATES_MANIFEST_PATH|TEMPLATES_STORAGE_PATH|TEMPLATE_STATE_PATH|TERM_RULES_SEED_PATH|TERM_RULES_STORE_PATH|TERM_RULES_RUNTIME_YAML_PATH|TRANSLATION_TERMS_PATH|GOLDEN_SAMPLE_MANIFEST|GOLDEN_SAMPLE_RUNS_DIR)=" .env
```

Result after fix: local `.env` path entries point to the new `var/`,
`resources/`, `tests/fixtures/`, and `tests/tmp/` layout.

## Validation

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_backend_logging
```

Result: passed, 3 tests.

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_stage_spool_status_counts \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_when_default_translation_mode_requires_missing_client
```

Result: passed, 3 tests.

Command:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Result: passed. OpenAPI snapshot is current, with 58 paths and 87 schemas; the
targeted release unittest group passed 28 tests.

Startup smoke:

```bash
JOBS_REPOSITORY_BACKEND=file JOBS_ARTIFACT_STORAGE_BACKEND=local_file \
JOBS_WORKER_MODE=in_process DOCUMENT_JOBS_WORKER_BACKEND=disabled \
DEFAULT_TRANSLATION_MODE=direct TRANSLATION_PROVIDER_BACKEND=disabled \
OPENAI_API_KEY= OPENAI_BASE_URL= MINERU_API_TOKEN= \
/Users/sc/miniconda3/envs/md2word/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 18087

curl -sS http://127.0.0.1:18087/api/v1/health/ready
```

Result: `/api/v1/health/ready` returned HTTP 200 with
`deployment_init_ready=true`, no `readiness_blockers`, `jobs_dir` under
`/Users/sc/PycharmProjects/md2word/var/jobs`, and expected non-blocking
warnings for missing MinerU/OpenAI credentials. The access log emitted one-line
JSON because the local `.env` has `LOG_FORMAT=json`. The temporary server was
stopped after the smoke.

## Residual Risk

- The root `.env` is ignored local configuration, so the path fix will not show
  in normal git status or travel with a commit. Tracked `.env.example` already
  contains the current Phase 7 paths.
- The current local `.env` still selects MySQL metadata, external stage worker,
  and Celery document worker by default. The startup smoke intentionally
  overrode those to the documented local `file` / `in_process` / `disabled`
  mode so the check did not depend on local MySQL or Redis being available.
