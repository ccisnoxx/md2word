# Frontend Operator Productivity Layer

## Goal

Add a cross-page operator productivity layer for the high-frequency operations frontend.

The seventh round should reduce repeated navigation and repeated action friction after the operations cockpit is in place. It should provide a Chinese-first command entry, consistent shortcut hints, consistent batch-result feedback, and a visible-copy cleanup for operator-facing pages.

This is the seventh frontend operations round after:

- dense Jobs workbench
- Translation QA queue and review drawer
- app shell/sidebar
- Incident triage workbench
- saved views
- personal operations cockpit

## Product Positioning

This is for Chinese-speaking operations staff. User-visible frontend text should default to Chinese unless it is a product/technical token operators already recognize.

The productivity layer should help operators move faster without adding visual noise:

- find a page or saved view quickly
- understand available shortcuts
- see batch-operation results without toast clutter
- keep the interface Chinese-first and operationally precise

It should not become an automation center or a second implementation of Jobs, QA, Incidents, or Cockpit.

## Current Context

- Sixth round created `OperationsCockpitPage.vue`, `/cockpit`, navigation entry `今日工作`, default landing behavior, and tests.
- Cockpit currently still has some visible English labels such as `Operations Cockpit`, `Saved Views`, and `Next Work`.
- `IncidentTriagePage.vue` has shortcut hints and compact batch-result strips.
- `TranslationQaReviewPanel.vue` has shortcut hints for review actions.
- `JobsPage.vue` has a bottom bulk-action bar and batch result handling.
- `TermProposalsPage.vue` also has bulk review feedback, but it is not the primary high-frequency operations target for this round.
- There is no global command palette or unified quick-command entry.
- Frontend layout spec requires compact workbench surfaces, stable grid rows, existing `--app-*` tokens, and desktop/mobile layout verification.

## Problems And Recommended Choices

| Problem | Options | Recommended Choice |
|---|---|---|
| Seventh-round direction | 1. Visual polish only; 2. Cross-page productivity layer; 3. Column/density preferences | Choose 2 |
| Global quick entry | 1. Add command palette; 2. Add more sidebar links; 3. Add cockpit-only launcher | Choose 1 |
| Command action safety | 1. Navigate/apply filters only; 2. Allow direct batch execution; 3. Allow destructive actions after confirm | Choose 1 |
| Shortcut guidance | 1. Keep page-specific hints; 2. Create shared shortcut hint pattern; 3. Hide shortcut hints | Choose 2 |
| Batch result feedback | 1. Keep page-specific styles; 2. Standardize compact result strips; 3. Toast only | Choose 2 |
| Chinese copy requirement | 1. Translate only new components; 2. Chinese-first sweep for high-frequency operator pages; 3. Full i18n framework | Choose 2 |
| Technical copy exception | 1. Translate everything; 2. Preserve IDs/status codes/file extensions with Chinese labels; 3. Leave all technical pages mixed | Choose 2 |
| Backend scope | 1. Frontend only; 2. Add preference APIs; 3. Add command history backend | Choose 1 |

## Requirements

### R1. Chinese-First Operator UI

User-visible frontend text for operator-facing pages must default to Chinese.

MVP scope:

- `OperationsCockpitPage.vue`
- `JobsPage.vue`
- `TranslationQaQueuePage.vue`
- `TranslationQaReviewPanel.vue`
- `IncidentTriagePage.vue`
- new productivity-layer components
- shared labels introduced by this task

Required cleanup:

- Replace visible English section labels such as `Operations Cockpit`, `Saved Views`, and `Next Work` with concise Chinese labels.
- New command palette labels, placeholders, empty states, loading states, shortcut hints, and result strips must be Chinese.
- Existing English action labels in high-frequency pages should be translated when they are visible to operators.

Allowed exceptions:

- product terms operators already use, such as `Word`, `QA`, `DOCX`, `PDF`, `API`
- raw IDs, enum codes, file IDs, event codes, and diagnostic values when shown in monospace or as technical evidence
- developer-only comments, test names, route names, API field names, and internal code identifiers

If an unavoidable raw technical value is displayed, nearby label/context should be Chinese.

### R2. Global Command Palette

Add a compact global command palette for keyboard-first navigation.

Recommended trigger:

- `Cmd/Ctrl + K`

Required behavior:

- Opens from protected app pages.
- Uses a Chinese placeholder, recommended: `搜索页面、视图或操作`.
- Supports keyboard navigation with visible focus.
- Closes on `Esc`.
- Does not trap focus after close.
- Shows only entries the current user can access.
- Routes to existing pages or existing saved-view query states.
- Does not execute destructive or write operations directly.

Recommended command groups:

- 页面入口
- 保存视图
- 当前页面操作

Initial commands:

- 今日工作
- 任务工作台
- 异常处理
- 翻译 QA
- 创建任务, when permitted
- 运维看板, when permitted
- personal default saved views and useful system presets for Jobs, QA, and Incidents

Out of scope for v1:

- command history
- fuzzy ranking backed by analytics
- remote command registry
- direct bulk retry/cancel/archive execution

### R3. Shared Shortcut Hint Pattern

Create a reusable shortcut hint pattern or helper where it reduces duplication.

Expected behavior:

- Operators can see available shortcuts without reading documentation.
- Hints are concise, Chinese, and placed near the relevant command surface.
- Hints do not consume excessive vertical space.
- Existing QA drawer and Incident detail hints remain visible.
- New command palette trigger is discoverable from the app shell or cockpit command header.

Recommended shortcuts:

- `Cmd/Ctrl + K`: 打开命令面板
- `Esc`: 关闭面板或抽屉
- Existing QA review shortcut remains scoped to the review drawer.
- Existing Incident safe-action shortcut remains scoped to the incident drawer.

Do not introduce many new shortcuts in this round. The goal is discoverability and consistency, not a full hotkey system.

### R4. Unified Batch Result Feedback

Standardize batch-operation feedback for high-frequency operation pages.

Target pages:

- Jobs workbench
- Incident triage
- Translation QA only if a batch result surface exists or is introduced by existing behavior

Expected result-strip behavior:

- compact single-row summary
- success, failed, skipped, and total counts where applicable
- expandable failed/skipped details
- close/dismiss action
- retry/navigation affordance only when already supported by the page
- Chinese labels and messages
- no excessive toast stacking for batch results

Do not change backend batch semantics. Reuse existing response shapes.

### R5. Command Palette Saved View Integration

The command palette should reuse the saved views work from round five.

Behavior:

- Load saved views for accessible pages only.
- Prefer personal default views near the top.
- Include relevant system presets as fallback.
- Selecting a saved-view command navigates to the target page with the existing query helper semantics.
- Do not create, update, delete, reorder, or set default views from the command palette.

### R6. Permission And Route Safety

All productivity commands must respect current route access rules.

Rules:

- Use existing app navigation access helpers where possible.
- Do not show commands for inaccessible routes.
- Do not fetch saved views for inaccessible page keys.
- If no commands are available beyond the current page, show a Chinese empty state.
- Never expose admin/system operations commands to users without the required permissions.

### R7. Accessibility And Keyboard Behavior

Keyboard behavior is part of the product requirement.

Requirements:

- All command palette items are reachable by keyboard.
- Visual focus state is clear.
- Tab order follows visual order.
- `Esc` closes overlay surfaces predictably.
- Screen-reader labels are Chinese and meaningful.
- No keyboard trap after opening and closing the command palette.
- Color is not the only indicator for selected or dangerous states.

### R8. Low-Noise Visual Design

Use existing project styling.

Requirements:

- Use existing `--app-*` tokens.
- Prefer flat or lightly elevated panels.
- Keep command palette compact and scannable.
- Do not add decorative gradients, hero sections, or large educational copy.
- Do not put cards inside cards.
- Keep mobile layout usable at 375px.
- Do not create uncontrolled horizontal overflow.

## Acceptance Criteria

- Sixth-round cockpit visible English labels are replaced with Chinese equivalents.
- New productivity-layer components use Chinese visible copy by default.
- Existing high-frequency operator pages no longer show avoidable English section labels, button text, placeholders, loading text, or empty-state text.
- Technical tokens such as `QA`, `DOCX`, `PDF`, `API`, IDs, and raw codes are either intentionally preserved or shown with Chinese surrounding context.
- A global command palette opens with `Cmd/Ctrl + K` on protected pages.
- Command palette placeholder, groups, empty states, and item labels are Chinese.
- Command palette entries are permission-filtered.
- Command palette can navigate to key pages and saved-view query states.
- Command palette does not execute destructive or write operations.
- Shortcut hints follow a shared pattern on the relevant high-frequency surfaces.
- Batch result feedback for Jobs and Incidents follows a consistent compact strip pattern.
- Batch result feedback shows success, failure, skipped, and total counts where the API response supports them.
- Keyboard navigation and focus states are verified for the command palette.
- Existing Jobs, QA, Incident, Saved Views, Cockpit, and App Shell behavior remains functional.

## Definition Of Done

- Trellis frontend specs are read before implementation.
- Chinese-copy sweep covers the MVP operator-facing pages listed in R1.
- New shared helpers/components have targeted tests where practical.
- Command palette routing/filtering behavior has targeted tests.
- Saved-view command routing reuses existing saved-view query helpers.
- Batch result formatting has targeted tests if extracted to a helper.
- `npm run build` passes in `frontend/`.
- Browser smoke check covers command palette and affected pages at desktop width around `1440px`.
- Browser smoke check covers command palette and affected pages at mobile width around `375px`.
- Verification checks for no uncontrolled horizontal overflow.

## Technical Approach

Recommended frontend-only approach:

1. Audit visible operator-facing English copy in the MVP pages.
2. Replace avoidable English UI labels with Chinese labels.
3. Add a shared command palette component mounted in `AppLayout.vue` or another protected-shell layer.
4. Build command entries from existing navigation definitions and saved-view helpers.
5. Add a small command-palette utility for filtering, grouping, permission gating, and route creation.
6. Add a shared shortcut hint component or utility only where it removes real duplication.
7. Extract or standardize batch result strip formatting for Jobs and Incidents.
8. Add focused tests and run build/browser smoke checks.

Avoid:

- adding a new backend resource
- adding persistent command history
- adding global state for all page filters
- changing backend batch operation behavior
- introducing a full i18n framework in this round

## Out Of Scope

- Full multilingual i18n infrastructure.
- Locale switching.
- Translating developer comments, route names, test names, API fields, or internal enum constants.
- Direct command execution for retry, cancel, archive, delete, approve, or reject.
- Team assignment, workload balancing, or operator ownership queues.
- Command analytics or ranking telemetry.
- Customizable keyboard shortcut editor.
- Replacing cockpit, Jobs, QA, or Incident page workflows.
- Backend command registry or command history storage.

## Technical Notes

- Frontend layout spec: `.trellis/spec/frontend/layout-guidelines.md`.
- Route and navigation files:
  - `frontend/src/router/index.ts`
  - `frontend/src/navigation/appShell.ts`
- Current cockpit page:
  - `frontend/src/pages/OperationsCockpitPage.vue`
  - `frontend/src/utils/operationsCockpit.ts`
- Existing saved-view helpers:
  - `frontend/src/api/savedViews.ts`
  - `frontend/src/utils/savedViews.ts`
  - `frontend/src/components/SavedViewStrip.vue`
- Existing shortcut and batch surfaces:
  - `frontend/src/components/TranslationQaReviewPanel.vue`
  - `frontend/src/pages/IncidentTriagePage.vue`
  - `frontend/src/pages/JobsPage.vue`
- UI/UX research notes:
  - Use Chinese-readable typography and copy.
  - Keep keyboard navigation, focus states, loading feedback, and empty states explicit.
  - Ignore marketing-oriented design-system suggestions such as hero sections, large decorative blocks, and high-saturation consumer styling because this project is a dense operations workbench.

## ADR-lite

**Context**: The sixth round created a personal operations cockpit, but operators still need faster cross-page navigation, clearer shortcut discovery, consistent batch feedback, and Chinese-first visible UI text.

**Decision**: Build a frontend-only operator productivity layer: command palette, shortcut hint consistency, batch result feedback standardization, and Chinese copy cleanup for high-frequency operator pages.

**Consequences**: This improves daily operator speed without expanding backend scope or duplicating page workflows. It also creates a stronger UI language baseline for future frontend rounds.
