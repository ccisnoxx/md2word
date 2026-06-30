# Code Reuse Thinking Guide

> **Purpose**: Stop and think before creating new code - does it already exist?

---

## The Problem

**Duplicated code is the #1 source of inconsistency bugs.**

When you copy-paste or rewrite existing logic:
- Bug fixes don't propagate
- Behavior diverges over time
- Codebase becomes harder to understand

---

## Before Writing New Code

### Step 1: Search First

```bash
# Search for similar function names
grep -r "functionName" .

# Search for similar logic
grep -r "keyword" .
```

### Step 2: Ask These Questions

| Question | If Yes... |
|----------|-----------|
| Does a similar function exist? | Use or extend it |
| Is this pattern used elsewhere? | Follow the existing pattern |
| Could this be a shared utility? | Create it in the right place |
| Am I copying code from another file? | **STOP** - extract to shared |

---

## Common Duplication Patterns

### Pattern 1: Copy-Paste Functions

**Bad**: Copying a validation function to another file

**Good**: Extract to shared utilities, import where needed

### Pattern 2: Similar Components

**Bad**: Creating a new component that's 80% similar to existing

**Good**: Extend existing component with props/variants

### Pattern 2.5: Shared Workbench Zones Before Generic Pages

**Bad**: Three list pages share the same header/summary/filter/table skeleton, but
each page redefines the structure locally until someone proposes a giant
`UniversalWorkbenchPage`.

This usually causes:

- duplicated responsive fixes,
- duplicated empty-state markup,
- page-specific divergence in table-settings placement,
- pressure toward a generic component that also owns domain logic.

**Good**: Extract the repeated *zones* first, and keep business behavior in the
pages:

```vue
<WorkbenchPageHeader ... />
<WorkbenchSummaryStrip ... />
<WorkbenchSectionHeader ... />
<WorkbenchEmptyState ... />
```

**Rule**: When multiple operator pages share the same workbench skeleton, reuse
slot-based shell components for header / summary / empty-state zones before
attempting a single all-purpose page component.

### Pattern 2.6: Shared Evidence Sections Before Rewriting Diagnostics

**Bad**: A detail page, a triage drawer, and a review drawer all show
"current state / next action / evidence / history", but each surface redefines
its own section wrappers, heading layout, and technical key-value rows.

This usually causes:

- inconsistent reading order,
- duplicated drawer header/footer fixes,
- technical IDs and traces rendered differently across surfaces,
- fragile smoke selectors tied to one-off DOM structures.

**Good**: Reuse shared evidence wrappers and keep each page's data model local:

```vue
<WorkbenchDrawerSurface ...>
  <EvidenceSurfaceSection title="下一步建议">
    ...
  </EvidenceSurfaceSection>
  <EvidenceSurfaceSection title="关键证据">
    <EvidenceKeyValueList :items="technicalItems" />
  </EvidenceSurfaceSection>
</WorkbenchDrawerSurface>
```

**Rule**: When evidence-heavy surfaces share the same reading order, first
extract section shell / drawer shell / technical key-value primitives. Do not
collapse the domain logic into one generic diagnostic component unless the data
contract is actually shared.

### Pattern 2.7: Shared Dashboard Shell Before BI Flourishes

**Bad**: Ops and admin dashboard pages all need KPI cards, blocker alerts, and
evidence panels, but each page invents its own header/grid/card shell while the
team debates charts.

This usually causes:

- first-screen hierarchy drifting between dashboard pages,
- repeated panel header markup,
- inconsistent freshness/severity placement,
- chart pressure before evidence-first layout is stable.

**Good**: Standardize the shell first, then keep page-specific modules local:

```vue
<WorkbenchPageHeader ... />
<WorkbenchMetricStrip :items=\"overviewItems\" ... />
<WorkbenchPanelCard title=\"Alert Delivery\" ...>
  ...
</WorkbenchPanelCard>
```

**Rule**: For dashboard/system pages, reuse shared header / metric-strip /
panel-card primitives before adding charts or inventing page-specific KPI
wrappers.

### Pattern 3: Repeated Constants

**Bad**: Defining the same constant in multiple files

**Good**: Single source of truth, import everywhere

### Pattern 3.5: Duplicated Global UI State Owners

**Bad**: A component redefines storage keys and DOM side effects for a
cross-page UI state that already has a shared owner:

```typescript
const THEME_STORAGE_KEY = "md2word.theme.mode";

function persistThemeMode(mode: ThemeMode): void {
  window.localStorage.setItem(THEME_STORAGE_KEY, mode);
  document.documentElement.dataset.theme = mode;
}
```

This creates a second source of truth for:

- persisted keys,
- document-root attributes,
- page-boot behavior.

**Good**: Keep one utility as the owner of storage + DOM side effects, and make
UI controls call that utility:

```typescript
import { getStoredThemeMode, persistThemeMode } from "@/utils/theme";
```

**Rule**: If a UI setting affects `localStorage`, `document.documentElement`, or
cross-page shell behavior, one shared utility owns the contract. Components may
render controls, but they must not clone the persistence/apply logic.

### Pattern 3.6: Duplicated Smoke Assertions

**Bad**: Every smoke file reimplements its own `no horizontal overflow`,
`skip-link`, or `panel fits viewport` helper with slightly different semantics.

This usually causes:

- viewport gates drifting between pages,
- false-positive layout regressions in one suite but not another,
- repeated fixes when a shared overlay contract changes.

**Good**: Put shared gate assertions in one smoke support module and reuse them:

```typescript
import {
  WORKBENCH_VIEWPORTS,
  expectNoPageHorizontalOverflow,
  expectElementContentFitsViewportWidth,
  activateSkipLink,
} from "./support/accessibility";
```

**Rule**: When a smoke assertion encodes a cross-page non-functional contract
(viewport widths, focus-return, skip-link, overlay fit), extract it before a
third spec copies it.

### Pattern 4: Repeated Payload Field Extraction

**Bad**: Multiple consumers cast the same JSON/event fields locally:

```typescript
const description = (ev as { description?: string }).description;
const context = (ev as { context?: ContextEntry[] }).context;
```

This is duplicated contract logic even when the code is only two lines. Each
consumer now has its own definition of what a valid payload means.

**Good**: Put the decoder, type guard, or projection next to the data owner:

```typescript
if (isThreadEvent(ev)) {
  renderThreadEvent(ev);
}
```

**Rule**: If the same untyped payload field is read in 2+ places, create a
shared type guard / normalizer / projection before adding a third reader.

---

## When to Abstract

**Abstract when**:
- Same code appears 3+ times
- Logic is complex enough to have bugs
- Multiple people might need this

**Don't abstract when**:
- Only used once
- Trivial one-liner
- Abstraction would be more complex than duplication

---

## After Batch Modifications

When you've made similar changes to multiple files:

1. **Review**: Did you catch all instances?
2. **Search**: Run grep to find any missed
3. **Consider**: Should this be abstracted?

### Reducers Should Use Exhaustive Structure

When state is derived from action-like values (`action`, `kind`, `status`,
`phase`), prefer a reducer with one `switch` over scattered `if/else` updates.

```typescript
// BAD - action-specific state transitions are hard to audit
if (action === "opened") { ... }
else if (action === "comment") { ... }
else if (action === "status") { ... }

// GOOD - one reducer owns the transition table
switch (event.action) {
  case "opened":
    ...
    return;
  case "comment":
    ...
    return;
}
```

This matters when the event log is the source of truth. A reducer is the
documented replay model; display code and commands should not duplicate pieces
of that replay model.

---

## Checklist Before Commit

- [ ] Searched for existing similar code
- [ ] No copy-pasted logic that should be shared
- [ ] No repeated untyped payload field extraction outside a shared decoder
- [ ] Constants defined in one place
- [ ] Similar patterns follow same structure
- [ ] Reducer/action transitions live in one reducer or command dispatcher

---

## Gotcha: Python if/elif/else Exhaustive Check

**Problem**: Python's if/elif/else chains have no compile-time exhaustive check. When you add a new value to a `Literal` type (e.g., `Platform`), existing if/elif/else chains silently fall through to `else` with wrong defaults.

**Symptom**: New platform works partially — some methods return Claude defaults instead of platform-specific values. No error is raised.

**Example** (`cli_adapter.py`):
```python
# BAD: "gemini" falls through to else, returns "claude"
@property
def cli_name(self) -> str:
    if self.platform == "opencode":
        return "opencode"
    else:
        return "claude"  # gemini silently gets "claude"!

# GOOD: explicit branch for every platform
@property
def cli_name(self) -> str:
    if self.platform == "opencode":
        return "opencode"
    elif self.platform == "gemini":
        return "gemini"
    else:
        return "claude"
```

**Prevention**: When adding a new value to a Python `Literal` type, search for ALL if/elif/else chains that switch on that type and add explicit branches. Don't rely on `else` being correct for new values.

---

## Gotcha: Asymmetric Mechanisms Producing Same Output

**Problem**: When two different mechanisms must produce the same file set (e.g., recursive directory copy for init vs. manual `files.set()` for update), structural changes (renaming, moving, adding subdirectories) only propagate through the automatic mechanism. The manual one silently drifts.

**Symptom**: Init works perfectly, but update creates files at wrong paths or misses files entirely.

**Prevention**:
- **Best**: Eliminate the asymmetry — have the manual path call the automatic one (e.g., `collectTemplateFiles()` calls `getAllScripts()` instead of maintaining its own list)
- **If asymmetry is unavoidable**: Add a regression test that compares outputs from both mechanisms
- When migrating directory structures, search for ALL code paths that reference the old structure

**Real example**: `trellis update` had a manual `files.set()` list for 11 scripts that `getAllScripts()` already tracked. Fix: replaced the manual list with a `for..of getAllScripts()` loop. See `update.ts` refactor in v0.4.0-beta.3.

---

## Template File Registration (Trellis-specific)

When adding new files to `src/templates/trellis/scripts/`:

**Single registration point**: `src/templates/trellis/index.ts`

1. Add `export const xxxScript = readTemplate("scripts/path/file.py");`
2. Add to `getAllScripts()` Map

That's it. `commands/update.ts` uses `getAllScripts()` directly — no manual sync needed.

**Why this matters**: Without registration in `getAllScripts()`, `trellis update` won't sync the file to user projects. Bug fixes and features won't propagate.

**History**: Before v0.4.0-beta.3, `update.ts` had its own hand-maintained file list that frequently fell out of sync with `getAllScripts()`. This caused 11 Python files to be silently skipped during `trellis update`. The fix was to eliminate the duplicate list and use `getAllScripts()` as the single source of truth.

### Quick Checklist for New Scripts

```bash
# After adding a new .py file, verify it's in getAllScripts():
grep -l "newFileName" src/templates/trellis/index.ts  # Should match
```

### Template Sync Convention

`.trellis/scripts/` (dogfooded) and `packages/cli/src/templates/trellis/scripts/` (template) must stay identical. After editing `.trellis/scripts/`, always sync:

```bash
rsync -av --delete --exclude='__pycache__' .trellis/scripts/ packages/cli/src/templates/trellis/scripts/
```

**Gotcha**: Running rsync with wrong source/destination paths can create nested garbage directories (e.g., `.trellis/scripts/packages/cli/...`). Always double-check paths before running.
