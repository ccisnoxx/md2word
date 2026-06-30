# P1 Dashboard And System Workbench Template Implementation Plan

## Scope

Finish the planning artifacts for the dashboard/system page family. Do not implement dashboard redesigns in this task yet.

## Checklist

1. Finalize the PRD.
   - Capture the page family, evidence-vs-chart philosophy, and first-screen priorities.

2. Define the template zones.
   - KPI zone, alert zone, action/advice zone, evidence modules, and secondary references.

3. Define the surface vocabulary.
   - Record which card/panel types are shared across the family.

4. Define chart policy.
   - Specify when charts are warranted and when evidence panels or tables are better.

5. Define state/freshness expectations.
   - Make `loading/empty/error/freshness/dry-run` handling explicit for later implementation.

6. Record page-family exceptions.
   - Note where Operations Cockpit, System Status, Ops Dashboard, and Acceptance Center legitimately diverge.

## Suggested Validation Commands

Planning-only sanity:

```bash
python3 - <<'PY'
from pathlib import Path
for name in ['prd.md', 'design.md', 'implement.md']:
    assert Path('.trellis/tasks/06-30-p1-dashboard-and-system-workbench-template', name).exists()
print('planning files OK')
PY
```

## Risk Points

- The family can become chart-driven unless evidence-first priorities are recorded explicitly.
- `OpsDashboard` is much denser than the others and can dominate the template unfairly.
- “Dashboard” language can encourage decorative KPI inflation if not constrained.

## Review Gate Before Start

Before later implementation:

- the first-screen hierarchy must be explicit,
- chart policy must be bounded,
- state/freshness expectations must be testable,
- page-family exceptions must be documented.
