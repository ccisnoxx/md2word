# Translation Term Governance Diff Browser Smoke Implementation Plan

## Status

Smoke completed. No production UI fix was required.

No production code was changed.

## Proposed Steps

1. Start frontend runtime

   - Prefer the existing Vite dev server command.
   - Use a non-conflicting local port.
   - Do not start backend workers or document processing flows.

2. Build mock API payloads

   - Authenticated admin user.
   - Translation Term Set list/detail/draft.
   - default-vs-draft diff with added / removed / changed / unchanged.
   - non-blocked preflight.
   - blocked preflight variant.
   - proposal compatibility rows for compatible / warning / conflict.
   - proposal deep-link context.

3. Run browser automation

   - Intercept the Translation Term Set API endpoints.
   - Navigate to the governance page.
   - Assert visible text and table content for each smoke scenario.
   - Prefer deterministic DOM/text assertions over screenshots.

4. Record result

   - If passed, update this `implement.md` with command and observed checks.
   - If failed because of UI issue, record the issue and create a small fix task.
   - If tooling is blocked, record the exact blocker and recommended retry path.

5. Finish/archive

   - Run `task.py validate`.
   - Run `git diff --check`.
   - Finish/archive when smoke result is recorded.

## Temporary Tooling Boundary

If Playwright or another browser automation package is not available in the project, use a temporary `/private/tmp` harness rather than changing project dependencies.

Any temporary package install must remain outside the repo and be recorded in the task closeout.

## Smoke Result

Command:

```bash
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/ms-playwright node /private/tmp/md2word-qa-smoke/translation_term_governance_diff_smoke.mjs
```

Data source:

- Temporary Playwright harness under `/private/tmp/md2word-qa-smoke`.
- Browser-side mock API responses for auth and Translation Term Set governance endpoints.
- Existing Vite frontend runtime on local port `3103`.

Observed checks:

- Translation Term Set page heading rendered.
- Diff / Preflight section rendered.
- Added, Removed, Changed, and Unchanged summary labels rendered.
- Changed diff row rendered `target_term` and `after` payload evidence.
- Non-blocked preflight copy rendered.
- Blocked preflight copy and blocking reason rendered.
- Diff evidence remained visible while preflight was blocked.
- Pending proposal compatibility section rendered.
- Compatible, warning, and conflict rows rendered.
- Conflict finding code `stale_target_term` rendered.
- Proposal governance deep-link banner rendered for `ttp_conflict`.
- Return action kept `term-proposals?tab=translation-review&proposal_id=ttp_conflict`.
- Mocked unavailable service state rendered the Translation Term Set unavailable copy.

Notes:

- Initial sandboxed Chromium launch failed with macOS Mach port permission denial.
- The same local smoke command passed with elevated browser execution.
- No project dependencies were changed.
- No pdf-mineru parsing, real translation provider call, or Word generation flow was run.

## Suggested Assertions

- `翻译术语集` or equivalent page heading is visible.
- `Diff / Preflight` is visible.
- `Added`, `Removed`, `Changed`, `Unchanged` summary values are visible.
- A changed field such as `target_term` appears.
- `Preflight 未发现阻断项` appears for non-blocked response.
- `Preflight 阻断发布` and a blocking reason appear for blocked response.
- `Pending proposal compatibility` appears.
- `compatible`, `warning`, `conflict`, and `stale_target_term` appear.
- Deep-link proposal ID appears in context.
- Return link points back to proposal review with `proposal_id`.

## Explicit Non-actions

- Do not run pdf-mineru parsing.
- Do not call translation providers.
- Do not generate Word.
- Do not modify backend API or persistence.
- Do not implement row-level Translation Term CRUD.
- Do not add permanent browser test framework in this task unless review changes the scope.
