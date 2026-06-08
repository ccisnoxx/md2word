# Phase 7 Cleanup Scheduler Controlled Execute Planning Design

## Decision

Keep scheduler controlled execute planning blocked. It cannot be meaningfully accepted until a real S3 delete pilot has evidence, because scheduler execute must reuse that guarded delete path.

## Dependency

Required dependency:

- accepted `phase7-real-s3-delete-guarded-execution`

Current dependency state:

- missing
- exact S3 target values missing
- destructive S3 execution approval missing
- no real S3 delete evidence exists

## Future Planning Contract

When unblocked, planning must require:

- disabled-by-default scheduler execute flag
- dry-run/no-op schedule first
- cleanup lock
- signed plan and preview hash
- bounded batch size
- per-file exact eligibility
- shared guarded delete path
- retry and timeout limits
- durable run history
- operator promotion gate
- rollback by disabling scheduler execute and S3 delete capability

## Hard Stops

- No direct scheduler delete path.
- No prefix/batch delete before manual one-target S3 acceptance.
- No autonomous execution while S3 delete lane is blocked.
