# Phase 6 quota enforcement ops hardening design

## Boundary

The implementation stays inside the existing Files domain and File Retention admin page. It does not create a new rollback executor and does not toggle runtime configuration. Rollback is represented as explicit operator-facing switch advice.

## Backend contract

Add `GET /api/v1/files/quota-policy/ops-summary`.

The endpoint is Admin-only and returns:

- normalized policy config
- current metadata usage snapshot with `proposed_upload_size_bytes=0`
- `enforcement_ready`, which is true only when policy status is `ready`, kill switch is false, and the service would enforce true blocks
- rollback options for disabling policy, forcing dry-run, or enabling kill switch
- recent replay items from persisted audit events with actions `file.quota_policy_block` and `file.quota_policy_override`
- safety flags proving the read did not execute upload authorization, metadata writes, audit writes, provider calls, delete, cleanup, scheduler, or conversion work

The service will use existing `DocumentFileRepositoryProtocol` and `AuditEventRepositoryProtocol` inputs. Router work remains limited to dependency/auth, query limit normalization, and response mapping.

## Frontend contract

Extend `filesApi` and `types.ts`, then show a new section inside the existing quota dry-run panel:

- status tags for readiness, kill switch, and replay count
- summary cards for current usage and true enforcement readiness
- rollback option table with env var, target value, current value, and whether it already matches
- read-only safety tags
- recent audit replay table

## Compatibility

This is additive:

- no existing route changes
- no existing request/response schema changes
- no config writes
- no external side effects

## Risks

Audit details are optional and older events may not carry structured quota details. Replay rows must tolerate missing nested details and keep values nullable.
