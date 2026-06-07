# Phase 5 production ops acceptance closeout design

## Closeout Boundary

This task is an acceptance audit over the implemented Phase 5 readiness batch. It records evidence and runs verification; it does not extend runtime behavior.

Excluded from the closeout execution path:

- pdf-mineru parsing.
- MinerU recovery query/download.
- translation provider calls.
- Word generation.
- real Slack/email/webhook delivery.
- real provider cancellation.
- real S3 deletion.
- quota enforcement upload blocking.
- autonomous cleanup scheduler loop.

## Accepted Slice Inventory

| Roadmap group | Slice | Acceptance focus |
| --- | --- | --- |
| Planning | `phase5-production-ops-integration-automation-gap-audit` | Roadmap, gap audit, safety plan, and first-batch order. |
| Existing safe contracts UI | `phase5-alert-delivery-frontend-controls` | Ops dashboard fake alert delivery controls; no external notification. |
| Existing safe contracts UI | `phase5-provider-cancellation-frontend-controls` | Ops dashboard fake provider cancellation controls; no real provider call or job mutation. |
| Durable evidence | `phase5-structured-audit-details-foundation` | Audit event `details` contract, query/export support, curated details for high-risk ops fake actions. |
| Existing safe contracts UI | `phase5-cleanup-run-frontend-controls` | Preview-hash gated cleanup-run controls using existing confirmation/reason contract. |
| Integration readiness | `phase5-alert-destination-config-dry-run` | Alert destination config parser and dry-run report; no delivery client. |
| Quota readiness | `phase5-quota-policy-dry-run` | Staged quota dry-run only; upload authorization remains unchanged. |
| Automation readiness | `phase5-cleanup-run-history-foundation` | Durable cleanup run history across file/sqlite/MySQL adapters. |
| Automation readiness | `phase5-signed-cleanup-plan-foundation` | Signed cleanup plan for exact preview hash/file IDs and tamper blocking. |
| Automation readiness | `phase5-cleanup-distributed-lock-foundation` | Metadata cleanup lock/fencing contract, not a scheduler loop. |
| Automation readiness | `phase5-cleanup-scheduler-dry-run-manual-runner` | Admin-only manual dry-run runner with lock and history; no deletion authorization. |
| Automation readiness UI | `phase5-cleanup-scheduler-dry-run-frontend-controls` | File Retention UI for manual scheduler dry-run result, lock evidence, and safety flags. |

## Acceptance Matrix

### API and Docs

Check that Phase 5 routes are represented in `docs/api/openapi.json`, `docs/api/files.md`, `docs/api/ops.md`, and `docs/api/manifest.yaml` where applicable.

Expected Phase 5 routes:

- `POST /api/v1/ops/alert-deliveries/preview`
- `POST /api/v1/ops/alert-deliveries/fake-send`
- `POST /api/v1/ops/provider-cancellations/preview`
- `POST /api/v1/ops/provider-cancellations/fake-cancel`
- `POST /api/v1/ops/alert-destinations/dry-run`
- `POST /api/v1/files/quota-policy/dry-run`
- `POST /api/v1/files/retention/cleanup-runs/preview`
- `POST /api/v1/files/retention/cleanup-runs/execute`
- `POST /api/v1/files/retention/cleanup-runs/scheduler-dry-run`
- `GET /api/v1/files/retention/cleanup-runs/history`
- `GET /api/v1/files/retention/cleanup-runs/history/{run_id}`

### Backend Contracts

Review backend routes and tests for:

- Admin-only gates on ops, audit, quota dry-run, cleanup run, scheduler dry-run, and history endpoints.
- Exact-target requirements for alert codes, provider target type/id, cleanup file IDs, and preview hash execution.
- Safety metadata proving side effects are fake, preview-only, dry-run, or bounded.
- Idempotency evidence where applicable: alert delivery dedupe, provider cancellation dedupe, cleanup run preview hash/signed plan, lock fencing.
- Persistence parity across file/sqlite/MySQL adapters for audit details, cleanup history, and cleanup locks.

### Frontend Controls

Review frontend wrappers and UI pages for:

- TypeScript contracts in `frontend/src/api/types.ts`.
- API wrappers for ops alert deliveries, provider cancellations, alert destinations, and files cleanup/quota routes.
- UI copy clearly identifying fake/dry-run/non-destructive paths before execution.
- Separate state for physical delete, cleanup-run execute, scheduler dry-run, alert fake-send, provider fake-cancel, and destination config dry-run.

### Safety Result

The closeout can accept Phase 5 readiness only if all high-risk capabilities remain staged:

- real alert delivery: deferred.
- real provider cancellation: deferred.
- real S3 delete: deferred.
- autonomous destructive scheduler: deferred.
- quota upload blocking: deferred until a separate enforcement design and approval.

## Verification Plan

Run the smallest broad verification set:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_delivery_fake_send_audits_and_dedupes_without_external_delivery \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_provider_cancellation_fake_cancel_audits_dedupes_and_does_not_mutate_jobs \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_ops_alert_destination_dry_run_is_admin_only_readonly_and_masks_secrets \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_quota_policy_dry_run_reports_would_block_without_side_effects \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_preview_and_execute_records_history \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_run_signed_plan_blocks_tampering \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_cleanup_scheduler_dry_run_manual_runner_records_history_and_releases_lock

/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_database_job_repository.PersistenceAdapterTests.test_metadata_repository_contract_matches_file_backend \
  tests.test_database_job_repository.PersistenceAdapterTests.test_cleanup_lock_service_enforces_fencing_and_expiry

/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-production-ops-acceptance-closeout
git diff --check
```

If a method name has changed, use `rg` to resolve the current targeted test name and document the substitution.

## Follow-up Slice Order

1. `phase5-s3-deletion-safety-contract-fake-adapter`
   - Fake/local contract only. Requires exact bucket/key/version preview and no real delete.
2. `phase5-audit-details-frontend-display`
   - Display curated structured details in Audit Log without leaking secrets or large payloads.
3. `phase5-provider-cancellation-adapter-hardening`
   - Harden fake adapter timeout/error/idempotency semantics before any real provider call.
4. `phase5-quota-enforcement-design`
   - Design upload blocking, admin override, and audit before implementation.

## Residual Risk Criteria

Known residual risks are acceptable for this closeout if they are explicitly deferred and not silently implemented:

- cleanup lock is metadata/fencing based, not database-native distributed locking.
- signed cleanup plan currently uses the local application secret source.
- dry-run history is not deletion authorization.
- alert destination config can say `enabled=true`, but real delivery is still not implemented.
- quota dry-run can report `would_block`, but upload authorization is intentionally unchanged.
