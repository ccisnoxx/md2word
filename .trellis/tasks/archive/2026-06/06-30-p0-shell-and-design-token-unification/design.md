# P0 Shell And Design Token Unification Design

## Architecture

This task owns the shared shell and token source of truth for the redesign.

It should define:

1. token categories,
2. shell surface hierarchy,
3. typography roles,
4. interaction/layer rules,
5. the migration boundary between current styles and future page-template work.

Later child tasks should consume these decisions instead of redefining them locally.

## Scope Boundary

This task should coordinate three layers:

- global token layer,
- shell component layer,
- entry/protected-shell alignment layer.

It should not own page-family internals such as queue filters or diagnostic evidence blocks.

## Current Source Of Truth

The initial style source of truth already lives in:

- `frontend/src/styles/main.scss`
- `frontend/src/layouts/AppLayout.vue`
- `frontend/src/components/AppSidebar.vue`
- `frontend/src/pages/LoginPage.vue`

The redesign should evolve these surfaces into a governed design system rather than create a parallel token file with unclear ownership.

Ownership should remain:

- `main.scss`
  - global token values and responsive shell primitives;
- `AppLayout.vue`
  - protected shell composition, sticky header, drawer/dialog shell behavior;
- `AppSidebar.vue`
  - navigation identity, collapse/mobile variants, active-state patterns;
- `AppThemeToggle.vue`
  - theme switching entry and theme-mode affordance;
- `LoginPage.vue`
  - public-entry shell expression aligned with the protected workbench tone.

## Token Model

The planned token model should cover:

- color roles:
  - background,
  - surface,
  - elevated surface,
  - border,
  - text primary/muted/faint,
  - action primary,
  - success/warning/danger/info,
  - technical/evidence accents when needed;
- typography roles:
  - heading,
  - body,
  - caption,
  - mono/technical;
- spatial roles:
  - spacing scale,
  - shell paddings,
  - panel paddings,
  - dense/compact list spacing;
- depth roles:
  - border strength,
  - shadow strength,
  - glass/overlay use;
- motion/layer roles:
  - transition durations,
  - easing,
  - z-index scale.

The implementation should preserve the existing token namespace and shift semantics/value mapping instead of renaming everything at once.

## Recommended Token Direction

### Typography

- `--app-font-sans`
  - target stack: `"Source Sans 3", "PingFang SC", "Noto Sans SC", system-ui, sans-serif`
- new heading utility or documented heading stack
  - target stack: `Lexend, "PingFang SC", "Noto Sans SC", sans-serif`
- `--app-font-mono`
  - target stack: `"IBM Plex Mono", "SFMono-Regular", Consolas, monospace`

Rationale:

- `Lexend` fits the enterprise/accessibility requirement better than the current generic system heading treatment.
- `Source Sans 3` is more neutral and readable for dense operator UI than the current default stack.
- `IBM Plex Mono` is more intentional for IDs/logs/evidence than leaving shell mono entirely to system defaults.

### Light Theme Color Roles

Recommended shell direction:

- background: `#F8FAFC`
- surface: `#FFFFFF`
- muted surface: `#F1F5F9`
- primary text: `#1E293B`
- muted text: `#475569`
- faint text: `#64748B`
- primary action: `#2563EB`
- primary hover: `#1D4ED8`
- primary soft: `#DBEAFE`
- primary border: `#93C5FD`
- cyan accent: `#0EA5E9`
- success: `#059669`
- warning: `#D97706`
- danger: `#BE123C`

Rationale:

- This keeps trust-blue enterprise semantics.
- It removes purple from the primary shell path.
- It preserves strong severity colors for operations risk states.

### Dark Theme Direction

Keep dark mode, but align it to the same blue/slate system:

- background should remain deep navy/slate, not purple-black.
- primary accent should shift to blue/cyan, not lavender.
- text contrast should remain high enough for evidence-heavy work.

Dark mode does not need a separate visual language. It should be a faithful inversion of the same shell system.

## Visual Direction

The shell should shift from the current indigo-heavy SaaS tone toward a calmer enterprise operations tone:

- slate/navy-neutral foundation,
- restrained blue/cyan action accents,
- amber/red reserved for risk/severity,
- less decorative gradient dominance outside the login and selective shell accents,
- stronger text contrast on primary work surfaces.

This does not require a flat monochrome redesign. It requires better semantic discipline.

## Typography Strategy

Typography should explicitly separate:

- readable body copy for dense operations work,
- stronger but calm headings,
- technical mono treatment for IDs, logs, paths, and evidence fields.

The typography plan should also ensure the login page and protected shell feel related, not like two different products.

Implementation guidance:

- headings should use the heading stack only where hierarchy matters: page titles, major section titles, shell brand emphasis;
- dense body copy, descriptions, labels, and table-adjacent text should stay on the body stack;
- monospace should be reserved for identifiers and evidence, not general UI chrome.

## Shell Interaction Rules

The shell design contract should capture:

- sticky header behavior,
- sidebar collapse vs mobile drawer behavior,
- command palette entry affordance,
- breadcrumb visibility rules,
- focus-return and modal/drawer interaction expectations,
- skip-link expectation for keyboard users.

Recommended interaction decisions:

- keep the sidebar sticky on desktop and hidden behind drawer interaction on mobile/tablet;
- keep the topbar sticky with module/page context and command-palette access always reachable;
- add a shell-level skip link before the main navigation/header stack;
- preserve `Esc`-driven close behavior for drawer/dialog/palette surfaces;
- keep visible keyboard focus rings as a mandatory shell rule, not a page-level optional style.

## Layer Scale

The task should freeze a shell-level z-index ladder:

- base content: `1`
- sticky topbar: `20`
- sidebar rail: `30`
- mobile drawer / overlay shell: `40`
- popover / dropdown / tooltip plane: `50`
- modal dialog plane: `60`
- command palette plane: `70`
- toast / global transient feedback: `80`

The exact implementation may use variables later, but these relative layers should not be renegotiated by child tasks.

## Migration Strategy

This shell/token task should favor incremental migration:

1. keep token names,
2. adjust values and semantic use,
3. align login and shell surfaces,
4. let downstream child tasks consume the stabilized values.

Avoid:

- mass token renames before downstream adoption,
- new theme systems parallel to the current one,
- shell-specific overrides that bypass the token layer entirely.

## Dependency Notes

- Core workbench and diagnostics tasks depend on this task's token and shell rules.
- Accessibility/regression planning depends on this task to define the shell-level focus and layer model.
- Dashboard/governance and long-tail tasks should inherit this visual baseline.

## Rollback

Rollback is planning-only:

- revert the task artifacts,
- keep the parent/child decomposition,
- or revise the design direction if user review rejects the token strategy.

No runtime or dependency rollback exists at this planning stage.
