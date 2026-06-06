# Ops recovery action safety registry

## Goal

Implement the next Phase 4 Operations slice: an Admin-only, read-only recovery action safety registry and exact-target preview contract.

This task must create the safety contract before any new provider cancellation, alert delivery, automated cleanup execution, or Ops recovery execution is implemented.

## Requirements

- Add Admin-only backend endpoints for recovery action governance:
  - list available/candidate Ops recovery actions.
  - preview one exact action against one exact target ID.
- Registry entries must expose stable safety flags:
  - `action_id`
  - `label`
  - `category`
  - `target_type`
  - `available`
  - `requires_admin`
  - `requires_reason`
  - `requires_confirmation`
  - `dry_run_supported`
  - `mutates_metadata`
  - `mutates_queue`
  - `calls_provider`
  - `sends_notification`
  - `deletes_data`
  - `audit_action`
  - `known_gaps`
  - `suggested_route`
- Preview must:
  - accept `action_id`, `target_type`, and exact `target_id`.
  - reject unknown actions or mismatched target types.
  - return eligibility, missing gates, target summary, risk flags, audit action, and safety metadata.
  - not execute any recovery action.
  - not enqueue background work.
  - not call providers.
  - not send notifications.
  - not mutate metadata.
  - not delete local files, object storage, S3 objects, or cleanup outputs.
- Cover existing/candidate action families:
  - document job retry/cancel/archive.
  - legacy job retry/cancel/recover MinerU result/cleanup local files.
  - provider cancellation candidate.
  - alert delivery candidate.
  - automated cleanup execution candidate.
- Frontend may consume the registry on Ops Dashboard as read-only safety information, but must not expose execution buttons.
- Update OpenAPI and TypeScript contracts.

## Non-goals

- No provider cancellation implementation.
- No alert delivery implementation.
- No automated cleanup execution.
- No direct recovery execution from Ops Dashboard.
- No changes to existing retry/cancel/archive/recover/cleanup behavior.
- No scheduler loop.
- No physical delete or S3 delete.
- No real MinerU query/download/submit.
- No real translation provider call or Word generation.

## Acceptance Criteria

- [x] Planning artifacts exist and define the read-only contract.
- [x] `task.py validate` passes before start.
- [x] `task.py start` is run after planning.
- [x] Backend Admin-only registry endpoint is implemented.
- [x] Backend Admin-only preview endpoint is implemented.
- [x] Operator access is rejected.
- [x] Registry includes stable entries for document-job actions, legacy job actions, provider cancellation candidate, alert delivery candidate, and automated cleanup candidate.
- [x] Preview proves exact target lookup for document job and legacy job without mutation.
- [x] Preview reports ineligible terminal or missing targets correctly.
- [x] Preview response includes explicit safety metadata showing no execution/provider/notification/cleanup/delete occurred.
- [x] Frontend consumes registry as read-only Ops Dashboard safety context or documented backend-only rationale is recorded.
- [x] OpenAPI snapshot is regenerated and OpenAPI tests pass.
- [x] Targeted backend tests pass.
- [x] Frontend build passes if frontend code changes.
- [x] `task.py validate` passes after implementation.
- [x] `git diff --check` passes.

## Notes

- The user asked to continue after this toward provider cancellation, alert delivery, or automated cleanup execution. This implementation intentionally stops before those actions because they require the registry/preview evidence first.
- Provider cancellation support is currently unknown in the local `MinerUClient`; any real provider-cancel task must verify provider semantics before implementation.
- Implemented endpoints are:
  - `GET /api/v1/ops/recovery-actions`
  - `POST /api/v1/ops/recovery-actions/preview`
- Candidate execution actions remain `available=false` until a separate execution contract is implemented and reviewed.
