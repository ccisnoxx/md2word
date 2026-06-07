# Phase 6 provider cancellation semantics verification implementation

## Checklist

- [x] Add provider cancellation semantics verification module.
- [x] Add schemas and Admin-only route.
- [x] Update integration control plane provider cancellation blocking reasons.
- [x] Add backend tests for report, safety, and control-plane status.
- [x] Add frontend API/types and Ops Dashboard panel.
- [x] Update docs/OpenAPI and roadmap task status.
- [x] Run targeted backend, OpenAPI, frontend, Trellis, and diff checks.

## Validation commands

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_semantics_verification_is_admin_only_readonly_and_blocks_real_cancel tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_integration_capabilities_report_provider_cancellation_semantics_verified_but_blocked`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_preview_is_admin_only_and_metadata_only tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_fake_cancel_audits_dedupes_and_does_not_mutate_jobs`
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- `npm --prefix frontend run build`
- `python3 ./.trellis/scripts/task.py validate phase6-provider-cancellation-semantics-verification`
- `git diff --check`
