# Frontend Workbench UI Design System And Beautification Planning Implementation Plan

## Scope

Complete the parent planning artifacts and prepare the task tree for later child-task planning and implementation. Do not start frontend implementation from this parent task.

## Checklist

1. Finalize the parent PRD.
   - Record the overall goal, confirmed facts, shared requirements, acceptance criteria, task map, and out-of-scope boundaries.
   - Make the parent PRD useful as a planning entry point, not a duplicate of every child PRD.

2. Finalize the parent design artifact.
   - Define the parent task as a planning coordinator.
   - Record the design-system decision frame and the child-task topology.
   - Document why the rollout order is structured around reusable UI concerns rather than page-by-page edits.

3. Finalize the parent implementation-plan artifact.
   - Capture the intended planning and rollout order.
   - State explicitly that later implementation should happen through child tasks.
   - Record review gates before any child moves toward `task.py start`.

4. Review the child PRD skeletons against the parent invariants.
   - Ensure every child scope aligns with the parent task map.
   - Ensure no child silently contradicts the parent decision that `form-table` is evaluated before adoption.
   - Ensure child acceptance skeletons remain testable and bounded.

5. Identify the recommended planning sequence for the next turns.
   - First refine `p0-shell-and-design-token-unification`.
   - Then refine `p0-core-list-workbench-template-unification`.
   - Then refine `p0-task-detail-and-diagnostic-interaction-template`.
   - Then refine `p0-accessibility-and-responsive-regression-gate`.
   - Only after these P0 planning artifacts stabilize, refine the P1/P2 children.

6. Keep the parent task in planning.
   - Do not run `task.py start` for the parent as part of this phase.
   - Do not implement code from the parent task.
   - Use the parent only as the coordinating source for later child work.

## Suggested Validation Commands

Planning artifact sanity:

```bash
python3 - <<'PY'
import json, pathlib
for path in sorted(pathlib.Path('.trellis/tasks').glob('06-30-*/task.json')):
    with path.open() as f:
        json.load(f)
print('task json OK')
PY
```

Optional repository hygiene:

```bash
git diff --check
```

No frontend build or test command is required for this parent-task planning step because only Trellis planning artifacts are being edited.

## Risk Points

- The parent task can become overly abstract if it repeats all child details; keep it focused on shared decisions and rollout structure.
- Child tasks can drift if the parent does not clearly define invariants and sequence.
- There is a risk of premature implementation pressure if the parent task is treated as an execution target.
- `form-table` can distort planning if it is treated as a solution instead of an evaluated reference model.

## Review Gate Before Start

Before any child task is started for implementation, confirm:

- the parent PRD/design/implement artifacts are internally consistent,
- the child-task map still matches the latest product intent,
- the shell/token, core workbench, detail diagnostics, and accessibility planning artifacts are refined enough to guide implementation,
- `form-table` conclusions are still framed as evaluation rather than an unreviewed dependency decision.

The expected next action after this parent artifact work is not `task.py start` on the parent. The expected next action is to continue planning in the highest-priority P0 child task.
