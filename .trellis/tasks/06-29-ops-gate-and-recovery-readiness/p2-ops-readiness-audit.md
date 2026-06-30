# P2 ops readiness audit

## Current Status

Status: hostdzire P2 online gate passed on release `a2bf3e1`; Acceptance Center `acceptance_p2_online_gate_current` is synced and approved.

P1 evidence was checked before entering P2. `.trellis/tasks/06-29-p1-translation-beta-formal-sample-gate/formal-sample-gate-audit.md` records `acceptance_p1_translation_current` with upsert HTTP `200`, review HTTP `200`, status `passed`, decision `approved`, and no P1 blockers. The remaining latest-summary blocker was expected because P2 had not yet been recorded.

## P2 Implementation Evidence

Executed locally on 2026-06-30:

| Evidence | Result |
| --- | --- |
| Task | `.trellis/tasks/06-29-ops-gate-and-recovery-readiness/` |
| Primary script | `scripts/ops/run_p2_online_gate.py` |
| Acceptance Center run id | `acceptance_p2_online_gate_current` |
| New sync option | `--sync-acceptance` |
| Optional review option | `--acceptance-review-decision approved --acceptance-review-note '<note>'` |
| Report output | `tests/tmp/p2_online_runs/<run_id>/report.json` and `report.md` |
| Acceptance payload source | P2 report `summary`, deployment identity, runtime readiness, blockers, warnings, and `report.md` path |
| Acceptance stored artifact boundary | summary metadata only; no PDFs, DOCX, signed URLs, object keys, full text, prompts, provider responses, JWTs, passwords, bearer tokens, or binaries |

The P2 sync path posts to `POST /api/v1/acceptance/runs` and can optionally record a separate admin review via `POST /api/v1/acceptance/runs/{run_id}/review`. It does not change Acceptance Center into an execution surface.

## Ops / Recovery Readiness Boundary

Covered as ready or inspectable:

- P2 online gate aggregates live, ready, metrics, ops alerts, public ingress health, release check, P0 preflight, and P1 preflight.
- Incident triage classifies timeout/stalled, artifact-missing, translation-failed, conversion-failed, worker/dispatch-failed, QA-unavailable, and unknown failures.
- Ops recovery registry and preview remain Admin-only and expose safety flags without mutation.
- `document_job.replay_execution` remains the scoped executable recovery path where existing backend contracts allow it.
- File retention cleanup execution remains guarded by preview, reason, confirmation, and audit.

Deferred unless explicitly approved in a later task:

- Real S3 deletion.
- Automatic cleanup scheduler activation.
- Real provider cancellation.
- Real external alert delivery.
- Provider/MinerU/Word-generation side effects from Acceptance Center.

## Local Validation

Command:

```bash
.venv/bin/python -m unittest tests.test_openapi_export.OpenAPIExportTests.test_p2_online_gate_collects_runtime_evidence tests.test_openapi_export.OpenAPIExportTests.test_p2_online_gate_syncs_acceptance_center_when_enabled
```

Result: passed (`Ran 2 tests`, `OK`).

The second test uses a mocked runtime and verifies that a passing P2 gate upserts `acceptance_p2_online_gate_current` with `tier=P2`, `status=passed`, empty blockers, a `report.md` path, and a compact P2 summary, then records optional admin review.

Additional validation after adding legacy `X-Admin-Token` support:

```bash
.venv/bin/python -m unittest tests.test_acceptance_center_api tests.test_openapi_export.OpenAPIExportTests.test_p2_online_gate_summary_tolerates_ops_alert_error_payload tests.test_openapi_export.OpenAPIExportTests.test_p2_online_gate_syncs_acceptance_center_when_enabled tests.test_golden_sample_manifest.GoldenSampleManifestTests.test_preflight_accepts_legacy_admin_token_for_auth_check tests.test_p1_translation_batch_diagnostics.P1TranslationBatchDiagnosticsTests.test_auth_preflight_accepts_legacy_admin_token tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ops_alerts_is_admin_only_readonly_and_reports_recovery_readiness
.venv/bin/python scripts/ops/check_release.py
```

Result: passed. `check_release.py` reported OpenAPI current, frontend contract ok, frontend smoke mock ok, and 36 targeted unittests passed.

## Live Hostdzire Gate Status

The local environment initially had no `P2_ONLINE_*` variables configured:

| Variable | Status |
| --- | --- |
| `P2_ONLINE_BASE_URL` | unset |
| `P2_ONLINE_PUBLIC_URL` | unset |
| `P2_ONLINE_USERNAME` | unset |
| `P2_ONLINE_PASSWORD` | unset |
| `P2_ONLINE_BEARER_TOKEN` | unset |

The user pointed to `deploy/p0.env`, which contains the legacy `ADMIN_TOKEN` and `AUTH_JWT_SECRET_KEY` material. Two live attempts were made against `https://md2word.962850.xyz`:

1. `P2_ONLINE_ADMIN_TOKEN="${ADMIN_TOKEN}"` was rejected by the current deployed `/api/v1/health/ops-alerts` with HTTP `401`, because the deployed version still requires admin Bearer JWT on that endpoint.
2. A short-lived admin JWT was generated locally from `AUTH_JWT_SECRET_KEY` and `deploy/auth_internal_users.json`, but the deployed `/api/v1/auth/me` also returned HTTP `401`. This indicates the live runtime's JWT secret, managed user record, or token version no longer matches the local deploy bootstrap files.

Latest generated report before deploying the `X-Admin-Token` compatibility changes:

| Field | Result |
| --- | --- |
| Run dir | `tests/tmp/p2_online_runs/20260630T020038Z` |
| `p2_online_gate_ready` | `false` |
| Live check | passed |
| Ready check | passed |
| Metrics check | passed |
| Runtime readiness | passed: MySQL metadata, Celery worker, `document-jobs`, `document-translation-batches`, no readiness blockers |
| Ops alerts | blocked: `ops_alerts_http_401` |
| P0 preflight | blocked: `golden_sample_auth_unavailable` |
| P1 preflight | blocked: `p1_auth_unavailable`, `en2zh_not_available` |
| Acceptance sync | blocked: `acceptance_sync_http_401` |

The report also surfaced a script bug where a non-200 ops-alerts payload without an `alerts` list could raise `TypeError`; this was fixed locally and covered by `test_p2_online_gate_summary_tolerates_ops_alert_error_payload`.

After deploying release `a2bf3e1`, the P2 gate was rerun on hostdzire with the production Docker image as a one-shot runner. The runner mounted an empty `/app/.env` for `check_release.py`, passed only the needed `P2_ONLINE_*` values, and used `P2_ONLINE_ADMIN_TOKEN` from the hostdzire `.env`.

Final evidence:

| Field | Result |
| --- | --- |
| Release dir | `/root/md2word-releases/a2bf3e1` |
| Deployment id | `hostdzire-20260630T022658Z-a2bf3e1` |
| Dry-run report | `/app/tests/tmp/p2_online_runs/20260630T022829Z/report.json` |
| Synced report | `/app/tests/tmp/p2_online_runs/20260630T023020Z/report.json` |
| `p2_online_gate_ready` | `true` |
| Blockers | none |
| Warnings | `document_jobs_failed_present` |
| Live / ready / metrics / ops-alerts | passed |
| Public ingress | passed |
| Release check | passed |
| P0 preflight | passed |
| P1 preflight | passed |
| Acceptance sync | `ok=true`, run id `acceptance_p2_online_gate_current` |
| Acceptance detail | `status=passed`, `decision=approved`, reviewer `admin`, blockers none |
| Latest summary | P2 `status=passed`, P2 `decision=approved`, overall blocker count `0`; overall status remains `needs_attention` because warnings are still present |

The remaining `document_jobs_failed_present` warning reflects existing failed job history surfaced by ops alerts. It is not a P2 blocker and did not prevent Acceptance Center from recording the P2 evidence as passed.
