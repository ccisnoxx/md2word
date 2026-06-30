# Ops gate and recovery readiness implementation plan

## Steps

1. Confirm P1 Acceptance Center evidence is already synced and approved from Trellis task evidence.
2. Activate this existing P2 task; do not create a new task.
3. Inspect the P2 online gate script, Acceptance Center API contract, ops docs, incident surfaces, and recovery action boundaries.
4. Add the smallest missing implementation needed to register a passing P2 online gate in Acceptance Center.
5. Add or update P2 readiness evidence documentation in this task directory.
6. Run focused local validation:
   - P2 online gate script test.
   - Acceptance Center API test if sync behavior changes.
   - Release/OpenAPI check only if public API contracts change.
7. If hostdzire credentials are available, run the real P2 online gate and sync `acceptance_p2_online_gate_current`; otherwise leave an explicit evidence gap and exact host command.

## Review gates

- No raw secrets or artifact contents in task evidence or Acceptance Center payloads.
- Destructive/external operations remain gated/deferred unless the user explicitly approves a later implementation task.
- P2 `passed` status is derived from the online gate report, not from starter summaries.
