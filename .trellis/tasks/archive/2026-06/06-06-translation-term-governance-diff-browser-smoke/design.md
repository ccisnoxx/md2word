# Translation Term Governance Diff Browser Smoke Design

## Scope

This smoke task validates the existing Translation Term Set governance UI in a real frontend runtime. It should not add product features or execute document processing flows.

## Data Source Strategy

Use browser-side mock API responses as the primary source.

Rationale:

- It avoids coupling the smoke to MySQL setup, seeded resource state, or CSV import side effects.
- It deterministically covers states that are hard to produce in one real backend session.
- It keeps the task focused on frontend rendering and navigation acceptance.

Mock endpoints should cover:

- `GET /api/v1/auth/me`
- `GET /api/v1/translation-term-sets`
- `GET /api/v1/translation-term-sets/{set_id}`
- `GET /api/v1/translation-term-sets/{set_id}/draft`
- `GET /api/v1/translation-term-sets/{set_id}/diff`
- `GET /api/v1/translation-term-sets/{set_id}/preflight`
- `GET /api/v1/translation-term-sets/{set_id}/proposal-compatibility`

If local test fixtures already expose equivalent payloads, reuse them. Otherwise create temporary smoke-only mock payloads under `/private/tmp` and do not add project dependencies unless review explicitly asks for permanent test infrastructure.

## Smoke Scenarios

### Scenario 1: Governance page happy path

Route:

- `/settings/translation-term-sets`

Expected visible evidence:

- Page title for Translation Term Set management.
- Diff / Preflight section.
- Summary values for Added, Removed, Changed, Unchanged.
- A changed row showing `target_term` or `note` in changed fields.
- `before` and `after` payloads are visible.
- Preflight non-blocked copy is visible.
- Pending proposal compatibility section renders compatible, warning, and conflict counts.
- Compatibility table includes at least one conflict finding code such as `stale_target_term`.

### Scenario 2: Preflight blocked

Use the same route with a mock preflight response that sets `publish_blocked=true`.

Expected visible evidence:

- Blocking alert.
- At least one blocking reason, for example empty target term.
- Diff area still renders; blocked state does not hide diff evidence.

### Scenario 3: Proposal deep-link context

Route:

- `/settings/translation-term-sets?set_id=translation-terms-en2zh&proposal_id=ttp_conflict&observed_version=v1&return_to=term-proposals&return_tab=translation-review`

Expected visible evidence:

- Proposal context banner.
- Compatibility row for `ttp_conflict` is visible or highlighted.
- Return link targets `term-proposals?tab=translation-review&proposal_id=ttp_conflict`.

### Scenario 4: Unsupported/unavailable service copy

Optional if time allows. Mock `503` for Translation Term Set APIs.

Expected visible evidence:

- Page explains Translation Term Set service is unavailable.
- No misleading diff/preflight values are shown.

## Constraints

- Do not run pdf-mineru parsing.
- Do not call translation providers.
- Do not generate Word.
- Do not add row-level Translation Term CRUD.
- Do not add automatic conflict resolution or rebase.
- Do not mutate proposal statuses or draft entries.
- Do not add permanent browser test framework unless review explicitly changes scope.

## Handling Findings

- If smoke passes: record the command, mock data source, observed checks, and finish/archive the smoke task.
- If a small UI bug appears: stop after recording the finding and create a separate fix task.
- If the issue is larger than a small UI fix: do not broaden this task; propose a new planning task.
