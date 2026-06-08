# Phase 7 provider cancellation evidence watch

## Goal

Track whether provider cancellation evidence changes enough to unblock a future real provider cancellation adapter.

Current status: blocked. Existing accepted evidence remains `unsupported_by_public_docs`.

## Requirements

- Do not implement real provider cancellation adapter.
- Do not run real provider cancellation.
- Do not treat local job cancellation as provider cancellation.
- Reopen only if primary provider docs/API evidence or an approved private provider contract supplies:
  - supported cancellation operation
  - operation id field
  - terminal-state semantics
  - idempotency model
  - timeout/error contract
  - provider request id/audit evidence rules
- If evidence changes, create a new design task before implementation.

## Acceptance Criteria

- [x] Evidence-watch task exists and is explicitly blocked.
- [x] Current blocker `unsupported_by_public_docs` is recorded.
- [x] No provider cancellation was run.

## Notes

- This task does not browse provider docs or claim provider evidence changed.
