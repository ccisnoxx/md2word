---
doc_type: implement-plan
task: 05-31-phase-7-config-logging-runtime-support
status: approved
parent: 05-31-project-directory-restructure
---

# Phase 7 implementation plan

## Step 0: Recheck task and tree state

Commands:

```bash
git status --short
python3 .trellis/scripts/task.py current --source
```

Expected:

- Existing dirty worktree reflects completed prior phases.
- Phase 7 is the current task after planning and `task.py start`.

## Step 1: Audit Phase 7 surfaces

Commands:

```bash
rg -n "LOG_FORMAT|log_format|JsonLogFormatter|configure_logging|readiness_required_checks|readiness_non_blocking_checks|deployment_init_ready|translation_available|pdf_submission_available|stage_spool_observation_status|MINERU_API_TOKEN|DEFAULT_TRANSLATION_MODE" app tests docs .env.example .trellis/spec/backend
rg -n "MD2WORD_API_BIND|JOBS_WORKER_MODE|STAGE_MESSAGE_LEASE_SECONDS|TRANSLATION_PROVIDER_BACKEND|TRANSLATION_DEBUG_ARCHIVE|TRANSLATION_TERMS_PATH|TERM_RULES_" .env.example docs app/core/config.py
```

Expected:

- Settings, `.env.example`, docs, tests, and specs describe the same support
  surface.
- Any stale reference is fixed in the smallest owning file.

## Step 2: Patch only real drift

Actions:

- Update current docs/specs if they describe stale readiness, logging, or env
  behavior.
- Update targeted tests only if the current behavior is correct but unguarded.
- Avoid changing API behavior or broad startup semantics.

## Step 3: Validate

Commands:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_backend_logging
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_runtime_dependencies \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_reports_stage_spool_status_counts \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_when_default_translation_mode_requires_missing_client
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py
```

Optional local startup smoke:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_api.py
curl http://127.0.0.1:8000/api/v1/health/ready
```

The startup smoke may be skipped if port `8000` is already occupied or the
targeted test/release checks provide sufficient evidence for this support slice.

## Step 4: Record acceptance

Actions:

- Add `acceptance.md` with audit commands, validation commands, results, and
  residual risks.
- Update PRD checkboxes after evidence is collected.
