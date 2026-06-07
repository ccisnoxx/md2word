# Phase 5 structured audit details foundation

## Goal

Add an additive structured `details` field to audit events so high-risk Ops fake/execution contracts have machine-readable compliance evidence while preserving the existing compact `reason` field, existing filters, and existing CSV/export behavior.

## Requirements

- Extend persisted `AuditEvent` with optional structured `details`.
- Preserve compatibility with existing audit JSONL/sqlite/mysql payloads that do not contain `details`.
- Expose safe `details` in Admin audit list API.
- Preserve existing `reason` and existing CSV columns.
- Add a JSON details column to CSV export using compact, deterministic JSON when details are present.
- Make search `q` include safe details values.
- Write structured details for:
  - `ops.alert_delivery_fake`
  - `ops.provider_cancellation_fake`
  - `audit_events.export`
- Do not store secrets, tokens, callback seed, local filesystem paths, object bodies, prompt text, provider payloads, provider credentials, or file bytes in details.
- Do not change persistence table schemas because audit events are stored as JSON payloads.
- Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.

## Acceptance Criteria

- [ ] Existing audit events without `details` still deserialize and list/export correctly.
- [ ] New audit events can persist structured `details` through file/sqlite/mysql JSON payload adapters.
- [ ] Admin audit list responses include `details`.
- [ ] CSV export includes a deterministic `details_json` column without removing existing columns.
- [ ] `ops.alert_delivery_fake` audit includes structured delivery details.
- [ ] `ops.provider_cancellation_fake` audit includes structured fake cancellation details.
- [ ] Targeted backend tests pass.
- [ ] Trellis validate passes.
- [ ] `git diff --check` passes.
- [ ] Task is archived after verification.

## Notes

- This is a backend foundation slice. Frontend display of structured details can remain a later task unless a small type update is required by build checks.
