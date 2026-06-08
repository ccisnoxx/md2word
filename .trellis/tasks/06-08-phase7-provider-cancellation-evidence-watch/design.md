# Phase 7 Provider Cancellation Evidence Watch Design

## Decision

Keep real provider cancellation blocked. The current repository evidence says provider cancellation is `unsupported_by_public_docs`.

This watch task records what evidence would be required to reopen; it does not perform provider cancellation and does not implement an adapter.

## Evidence Required To Reopen

- Primary provider documentation or approved private contract.
- Explicit cancellation endpoint or operation.
- Required operation id field.
- Valid target states and terminal states.
- Idempotency model.
- Timeout and retry semantics.
- Error taxonomy.
- Provider request id or audit evidence contract.
- Statement on whether cancellation mutates local job state or only upstream provider state.

## Hard Stops

- No provider evidence change.
- Ambiguous docs.
- Only local cancellation semantics available.
- No operation id.
- No idempotency model.
- No terminal-state contract.

## Handoff

If evidence changes, create a new task for provider cancellation semantics/design before any implementation.
