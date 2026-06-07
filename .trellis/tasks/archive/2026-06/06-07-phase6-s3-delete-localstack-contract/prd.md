# Phase 6 S3 delete LocalStack fake parity contract

## Goal

Define the LocalStack/fake parity contract for exact S3 deletion before any real S3 delete work is considered.

## Requirements

- Add an Admin-only read-only Ops API that reports the exact S3 delete adapter contract, LocalStack profile, and current fake parity evidence.
- Tie the report to the existing file-retention S3 fake delete contract version.
- Keep real S3 deletion blocked in the integration control plane even when the capability flag is enabled.
- Do not call AWS, LocalStack, boto3 delete APIs, cleanup execute, scheduler execute, providers, alert delivery, or conversion workflows.
- Expose enough frontend evidence for operators to see contract version, fake mode, LocalStack readiness fields, blocking reasons, and safety flags.
- Update tests and API docs/OpenAPI for the new additive endpoint.

## Acceptance Criteria

- [x] `GET /api/v1/ops/s3-deletions/adapter-contract` is Admin-only and read-only.
- [x] The response proves fake parity for exact bucket/key/version, idempotency, result fields, audit fields, and metadata mutation rules.
- [x] The response records LocalStack as the next external harness target without requiring or executing it at runtime.
- [x] Integration control plane continues to report `s3_deletion` as blocked and includes the new contract/fake parity status.
- [x] Frontend Ops Dashboard loads and renders the S3 delete contract without offering a real delete action.
- [x] Tests prove no audit write, S3 delete, provider call, scheduler execute, cleanup execute, or metadata mutation occurs.
- [x] API docs and OpenAPI snapshot include the new contract.

## Notes

- Scheduler execute stays deferred until after real S3 delete guarded execution.
