# Phase 5 provider cancellation frontend controls

## Goal

Expose the existing Admin-only provider cancellation preview and fake-cancel contract from the Ops Dashboard without adding any real provider cancellation, local job mutation, scheduler, cleanup, or conversion workflow side effect.

## Requirements

- Add frontend TypeScript contracts for the existing `/api/v1/ops/provider-cancellations` response shapes.
- Add a frontend API wrapper for:
  - `POST /api/v1/ops/provider-cancellations/preview`
  - `POST /api/v1/ops/provider-cancellations/fake-cancel`
- Add an Ops Dashboard panel where Admin can enter an exact target:
  - `target_type=document_job|legacy_job`
  - `target_id`
  - `provider=mineru`
  - `dedupe_window_minutes`
- Preview must be available before fake-cancel and must display eligibility, missing gates, provider operation metadata, outcome, dedupe key, and safety flags.
- Fake-cancel must require a non-empty reason and the exact backend confirmation phrase.
- UI copy must clearly state this is fake cancellation only:
  - no real MinerU/provider cancellation.
  - no local job status mutation.
  - no queue mutation.
  - audit may be written only by fake-cancel.
- Do not modify backend code, OpenAPI, persistence, config, worker, scheduler, provider client, or S3 logic.

## Acceptance Criteria

- [ ] Ops Dashboard has a provider cancellation fake-control panel.
- [ ] Preview sends only exact target form values and fixed `provider=mineru`.
- [ ] Fake-cancel is disabled until preview exists, target still matches the preview, reason is non-empty, and confirmation phrase matches.
- [ ] Result view shows target summary, provider operation, missing gates, outcome, audit write status, dedupe key, and safety metadata.
- [ ] `npm --prefix frontend run build` passes.
- [ ] Trellis validate passes.
- [ ] `git diff --check` passes.
- [ ] Task is archived after verification.

## Notes

- Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.
