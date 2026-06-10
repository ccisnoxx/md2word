# Configuration Governance UX Consolidation Acceptance

## Result

Implemented for the agreed frontend-only scope. The task keeps existing backend contracts and routes, adds a shared terminology workbench navigation layer, groups `/settings` into governance areas, and aligns breadcrumb / state language around draft, live, published, default and rollback semantics.

The task does not add `/settings/terminology`, does not expand Translation Term Set summary aggregation, and does not introduce backend API changes.

## Implementation Covered

- Added `TerminologyWorkbenchNav` as a shared terminology governance subview switcher.
- Added terminology tabs to:
  - `/settings/term-rule-sets`
  - `/settings/term-rules`
- Preserved proposal governance query keys across terminology tabs and breadcrumb return:
  - `proposal_id`
  - `source_term`
  - `target_rule_id`
  - `return_tab`
  - `set_id`
- Updated breadcrumbs:
  - `配置中心 / 术语工作台 / 草稿与发布`
  - `配置中心 / 术语工作台 / 当前生效规则`
- Regrouped `/settings` into:
  - `术语工作台`
  - `模板与版式`
  - `翻译治理`
- Aligned existing configuration todo wording without adding new aggregate API calls.

## Boundary Confirmation

- No `/settings/terminology` route was added.
- No backend route, schema, service, or API wrapper contract was added for this task.
- No Translation Term Set summary aggregation was added.
- No live term-rule write action was added to `/settings/term-rules`.
- No prompt body, secret, provider, S3, worker, or deployment environment editor was added.
- Operator access to `/settings/**` remains governed by existing route meta roles.

## Verification

Passed:

```bash
cd frontend && npm run build
```

Observed existing Vite/Rollup warnings only:

- third-party `@vueuse/core` pure-annotation warning
- existing chunk-size warning over 500 kB

Passed:

```bash
git diff --check
python3 ./.trellis/scripts/task.py validate 06-10-config-governance-ux-consolidation
```

Browser smoke used Vite at:

```text
http://127.0.0.1:3000/
```

Smoke boundary:

- No backend API server was started.
- Playwright mocked only read-only frontend auth/config endpoints needed to render pages.
- No mutation endpoint was called.

Browser checks passed:

- `/settings` renders grouped sections `术语工作台`, `模板与版式`, and `翻译治理`.
- `/settings` keeps existing `配置发布待办` summary with aligned wording.
- `/settings/term-rule-sets?proposal_id=p1&source_term=VIN&target_rule_id=r1&return_tab=review&set_id=electronics-default` renders:
  - breadcrumb `配置中心 / 术语工作台 / 草稿与发布`
  - shared terminology tabs
  - proposal governance context
  - query-preserving link to `当前生效规则`
- Clicking `当前生效规则` opens `/settings/term-rules` with the governance query preserved.
- `/settings/term-rules` renders:
  - breadcrumb `配置中心 / 术语工作台 / 当前生效规则`
  - read-only live runtime copy
  - query-preserving link back to `草稿与发布`
- Mobile viewport `390x820` renders `/settings` as a single-column governance section list.

## Residual Risks

- Browser smoke used API mocks, so it validates front-end routing/layout but not real backend resource data rendering.
- Existing large bundle warning remains out of scope.
- The repository still contains unrelated dirty files from prior work; staging must remain selective.
