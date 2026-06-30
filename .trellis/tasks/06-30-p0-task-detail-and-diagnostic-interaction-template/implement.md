# P0 Task Detail And Diagnostic Interaction Template Implementation Plan

## Scope

Finish the planning artifacts for evidence-heavy detail and drawer interactions. Do not refactor Job Detail or drawer code in this task yet.

## Checklist

1. Finalize the PRD.
   - Capture the surfaces in scope, evidence-order goals, and out-of-scope queue concerns.

2. Define the surface split.
   - Record what belongs on the primary detail page versus what belongs in a secondary right drawer.

3. Define the evidence-order contract.
   - Make the summary-to-technical progression explicit.

4. Define the drawer interaction contract.
   - Capture close behavior, focus return, scroll ownership, and compact-screen expectations.

5. Define technical-content styling rules.
   - Record how IDs, logs, file references, and diff-like payloads should read and align across surfaces.

6. Record page-to-page applicability.
   - Map the contract to Job Detail, Incident Triage, and Translation QA review without pretending they are identical.

## Suggested Validation Commands

Planning-only sanity:

```bash
python3 - <<'PY'
from pathlib import Path
for name in ['prd.md', 'design.md', 'implement.md']:
    assert Path('.trellis/tasks/06-30-p0-task-detail-and-diagnostic-interaction-template', name).exists()
print('planning files OK')
PY
```

## Risk Points

- A single contract can become too generic if the drawer and full-detail surfaces are not distinguished clearly.
- Technical evidence can become visually overwhelming if the plan does not separate summary from low-level data.
- Keyboard and focus rules are easy to under-specify for drawers.

## Review Gate Before Start

Before later implementation:

- the primary/detail surface split must be explicit,
- evidence order must be documented,
- drawer focus/scroll rules must be testable,
- the plan must state where page-specific specialization remains allowed.
