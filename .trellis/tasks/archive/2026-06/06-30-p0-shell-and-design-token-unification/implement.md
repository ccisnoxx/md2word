# P0 Shell And Design Token Unification Implementation Plan

## Scope

Finish the planning artifacts for shell/token unification so later implementation can be scoped cleanly. Do not implement style changes in this task yet.

## Checklist

1. Finalize the PRD.
   - Capture shell scope, token categories, current source of truth, and out-of-scope page work.
   - Freeze resolved decisions on token namespace, theme-mode preservation, and shell ownership files.

2. Produce the token inventory.
   - Identify the current token families in `frontend/src/styles/main.scss`.
   - Decide which token names remain, which should be renamed, and which should become semantic-only aliases.
   - Preferred implementation path: keep names, change values/semantics, minimize rename churn.

3. Define the shell contract.
   - Record the target behavior for login, sidebar, topbar, breadcrumb, main content shell, command palette entry, and mobile drawer.
   - Include `AppThemeToggle` and password dialog/drawer layering behavior in the shell contract.

4. Define typography and color direction.
   - Record the target palette shift and heading/body/mono roles.
   - Keep the plan constrained to enterprise operations needs, not visual novelty.
   - Freeze the recommended MVP stacks and hex-direction so implementation does not reopen font/palette debates.

5. Define shell-level accessibility rules.
   - Include skip-link expectation, focus-return behavior, visible focus rules, and layer ordering requirements.
   - Convert the current smoke-test behavior into explicit acceptance inputs.

6. Record downstream dependencies.
   - Note which later child tasks depend on shell/token decisions before they can become implementation-ready.

7. Prepare later implementation touchpoints.
   - Expected implementation files:
     - `frontend/src/styles/main.scss`
     - `frontend/src/layouts/AppLayout.vue`
     - `frontend/src/components/AppSidebar.vue`
     - `frontend/src/components/AppThemeToggle.vue`
     - `frontend/src/pages/LoginPage.vue`
   - Expected validation focus:
     - shell overflow and responsive screenshots,
     - mobile drawer behavior,
     - collapsed sidebar persistence,
     - focus/keyboard behavior for shell overlays.

## Suggested Validation Commands

Planning-only sanity:

```bash
python3 - <<'PY'
from pathlib import Path
for name in ['prd.md', 'design.md', 'implement.md']:
    assert Path('.trellis/tasks/06-30-p0-shell-and-design-token-unification', name).exists()
print('planning files OK')
PY
```

When this task later enters implementation, the minimum expected validation set should start with:

```bash
cd frontend && npm run build
cd frontend && npm run test:smoke -- --grep "operations redesign renders verified desktop, tablet, and mobile screenshots"
```

If shell interaction changes touch theme toggling or overlay focus behavior, add targeted smoke coverage rather than broad full-suite expansion first.

## Risk Points

- Token planning can drift into abstract theme work unless tied back to existing shell surfaces.
- Over-renaming tokens can create migration churn later without improving semantics.
- The login page can diverge from the protected shell if it is treated as a standalone brand surface.
- Dark-mode support can regress if light-theme decisions are specified without an explicit dark-theme parity rule.
- Child tasks can bypass shell decisions if ownership files and z-index expectations are not fixed here.

## Review Gate Before Start

Before later implementation:

- token categories must be explicit,
- shell interaction rules must be testable,
- palette and typography direction must be approved,
- theme-mode preservation must be explicit,
- implementation touchpoints and minimum validation commands must be recorded,
- dependent child tasks must be able to reference this artifact instead of re-deciding shell basics.
