# Phase 6 S3 delete LocalStack fake parity contract design

## Boundary

This slice only fixes the LocalStack/fake parity contract for S3 delete. It must not implement a real S3 delete adapter, run LocalStack, call AWS or boto3 delete APIs, mutate file metadata, execute cleanup, or start scheduler execution.

## Backend Contract

Add `GET /api/v1/ops/s3-deletions/adapter-contract`.

The response includes:

- `contract_version`
- fake adapter id and mode
- existing file-retention fake contract version
- LocalStack profile for the future external harness
- required request/result/audit/safety fields
- parity checks for exact bucket/key/version, idempotency, result shape, audit shape, metadata rules, and no provider call
- blocking reasons that keep real S3 delete disabled
- read-only safety flags

Integration control plane remains blocked for `s3_deletion`, but its safe config states that the LocalStack/fake parity contract exists, the file-retention fake contract version is linked, and the real S3 delete adapter is not implemented.

## Frontend Contract

Extend Ops Dashboard with a read-only S3 delete adapter contract panel. It should show contract version, fake mode, existing fake retention contract version, LocalStack profile, blocking reasons, parity check summary, and safety flags. It must not add any real delete button or scheduler execute affordance.

## Compatibility

All changes are additive:

- existing file-retention preview and cleanup run contracts stay unchanged
- existing fake S3 retention item contract stays `s3-delete-fake-v1`
- real S3 deletion and scheduler execution remain unavailable

## Risks

Future real S3 delete may need provider-specific fields such as delete marker, request id, eTag precondition, and versioned delete semantics. The contract should reserve generic result fields without storing provider payloads, secret values, object bytes, or local paths.
