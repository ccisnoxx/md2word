# P0 Core List Workbench Template Unification Implementation Plan

## Scope

Complete the planning artifacts for the shared queue/workbench template across Jobs, Incident Triage, and Translation QA. Do not implement page refactors in this task yet.

## Checklist

1. Finalize the PRD.
   - Capture shared goals, current reusable primitives, and page-specific exceptions.

2. Build the template contract.
   - Document the shared zone model for header, summary, saved views, filters, table body, result zone, and action zone.

3. Build the exception matrix.
   - Record what stays different for Jobs, Incident Triage, and Translation QA.
   - Ensure exceptions are intentional and bounded.

4. Define the workbench state model.
   - Standardize required handling for loading, empty, error, permission, stale, and batch-result states.

5. Define responsive behavior.
   - Document expected behavior for filter wraps, settings popovers, summary strips, and mobile/tablet table layouts.

6. Record downstream validation needs.
   - Feed the accessibility/regression child with concrete testable expectations.

## Suggested Validation Commands

Planning-only sanity:

```bash
python3 - <<'PY'
from pathlib import Path
for name in ['prd.md', 'design.md', 'implement.md']:
    assert Path('.trellis/tasks/06-30-p0-core-list-workbench-template-unification', name).exists()
print('planning files OK')
PY
```

## Risk Points

- Over-generalization could erase meaningful operational differences between the three pages.
- Under-generalization would leave the task as page inventory rather than a reusable template.
- Mobile/tablet rules can be missed if planning focuses only on desktop density.

## Review Gate Before Start

Before later implementation:

- the shared zone model must be explicit,
- exception cases must be documented,
- state handling must be testable,
- responsive rules must be concrete enough for smoke validation.
