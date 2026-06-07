# Phase 6 real alert delivery adapter contract implementation

## Checklist

- [x] Add alert delivery adapter contract dataclasses/service and fake adapter result evidence.
- [x] Add API schemas and Admin-only contract route.
- [x] Include adapter evidence in fake preview/fake-send responses and fake-send audit details.
- [x] Update integration control plane safe config without making real delivery ready.
- [x] Add focused backend tests.
- [x] Add frontend API/types and Ops Dashboard contract panel.
- [x] Update docs/OpenAPI.
- [x] Run targeted backend, OpenAPI, frontend, Trellis, and diff checks.

## Validation commands

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_adapter_contract_is_admin_only_readonly_and_blocks_real_send tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_includes_adapter_contract_parity_in_audit`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_preview_is_admin_only_and_readonly tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_audits_and_dedupes_without_external_delivery`
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- `npm --prefix frontend run build`
- `python3 ./.trellis/scripts/task.py validate phase6-real-alert-delivery-adapter-contract`
- `git diff --check`
