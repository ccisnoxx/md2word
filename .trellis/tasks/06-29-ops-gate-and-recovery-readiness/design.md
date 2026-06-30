# Ops gate and recovery readiness design

## Scope

P2 readiness is an evidence and operations-governance closure over existing runtime surfaces. It does not add SaaS behavior, broaden the PDF scope, or enable destructive/external operations by default.

## Evidence contract

- Primary gate: `scripts/ops/run_p2_online_gate.py`.
- Output: `tests/tmp/p2_online_runs/<run_id>/report.json` and `report.md`.
- Acceptance Center run id: `acceptance_p2_online_gate_current`.
- Passing state: `summary.p2_online_gate_ready=true`, no blockers, and only documented warnings if the user accepts them.

The P2 report must summarize:

- `/health/live`, `/health/ready`, `/health/metrics`, and `/health/ops-alerts`.
- Public ingress health when `P2_ONLINE_PUBLIC_URL` is configured.
- `check_release.py` aggregation.
- P0 Golden Sample preflight.
- P1 translation preflight.
- Deployment identity, worker backend, document job queue, translation batch queue, repository backend, translation availability, readiness blockers, readiness warnings, ops-alert status, and critical alerts.

## Acceptance Center sync

Acceptance Center stores only summary metadata, report path, blockers, warnings, timestamps, and review metadata. It must not store PDFs, DOCX binaries, signed URLs, object storage locations, full extracted text, prompts, provider responses, JWTs, passwords, or bearer tokens.

For P2, sync uses `POST /api/v1/acceptance/runs` with:

- `id=acceptance_p2_online_gate_current`
- `tier=P2`
- `status=passed` only when the online gate report is ready; otherwise `unknown` or `failed`
- `environment=hostdzire`
- `source=manual_import:p2_online_gate`
- `report_path_or_url=<P2 report.md path>`

Admin review through `/api/v1/acceptance/runs/{run_id}/review` remains a separate signoff action.

## Recovery readiness boundaries

Allowed P2 evidence can reference these existing read/preview/replay surfaces:

- Incident triage for failed, stalled, artifact-missing, translation-failed, conversion-failed, and timeout-style jobs.
- Ops recovery action registry and preview.
- The scoped `document_job.replay_execution` execution path where existing backend contracts allow it.
- File retention preview and dry-run / guarded cleanup evidence.

Deferred unless explicitly approved in a later task:

- Real S3 deletion.
- Automatic cleanup scheduler activation.
- Provider cancellation semantics beyond documented gates.
- External alert delivery.
- MinerU/provider/Word-generation side effects from Acceptance Center itself.

## Validation

Local validation should cover pure script/report behavior and Acceptance Center API contracts with mocked runtime or TestClient state. Hostdzire validation requires runtime credentials and must record only redacted evidence.
