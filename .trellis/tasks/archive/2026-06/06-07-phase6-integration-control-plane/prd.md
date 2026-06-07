# Phase 6 integration control plane

## Goal

Add an Admin-only integration control plane that reports whether real external or destructive capabilities are enabled, blocked, dry-run-only, or killed, with every real capability disabled by default.

## Requirements

- Expose a read-only Ops API for real integration capabilities:
  - alert delivery;
  - provider cancellation;
  - S3 deletion;
  - cleanup scheduler execution;
  - quota enforcement.
- Add settings for enablement, dry-run-only where relevant, and kill switches.
- Defaults must keep all real external/destructive capabilities blocked.
- The response must include blocking reasons, required future gates, safe config summary, and safety metadata.
- The API must be Admin-only and must not call providers, S3, schedulers, alert destinations, cleanup execution, conversion workflows, or audit writes.
- Add a frontend Ops Dashboard read-only panel for the control-plane status.
- Update API docs/OpenAPI and targeted tests.

## Acceptance Criteria

- [ ] Admin can read `GET /api/v1/ops/integration-capabilities`.
- [ ] Operator/non-admin users are rejected.
- [ ] Default settings report every real capability as `blocked`.
- [ ] Safety metadata proves no provider, S3, scheduler, alert delivery, cleanup, conversion workflow, audit write, or secret exposure occurred.
- [ ] Frontend Ops Dashboard displays the capability summary without execution controls.
- [ ] Targeted backend tests pass.
- [ ] Frontend build passes.
- [ ] OpenAPI snapshot is updated and OpenAPI export tests pass.
- [ ] Trellis validate and `git diff --check` pass.

## Notes

- Do not enable real Slack/email/webhook delivery, real provider cancellation, real S3 deletion, autonomous scheduler execution, or new conversion workflow execution.
