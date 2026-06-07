# Phase 5 production ops integration automation gap audit implementation

## Classification

- Type: planning-only roadmap/gap audit.
- Behavior change: none.
- Production code change: none in this task.
- External side effects: none.

## Checklist

1. Planning task
   - [x] Create Trellis task.
   - [x] Read required roadmap, closeout, Phase 4 archive, code, API, config, and tests.
   - [x] Fill `prd.md`, `design.md`, and `implement.md`.

2. Gap audit
   - [x] Inventory Phase 4 future candidates.
   - [x] Decide Phase 5 include vs defer.
   - [x] Record current backend/frontend/API/model/config/test gaps.
   - [x] Record safety plan.

3. Slicing
   - [x] Split by risk and dependency.
   - [x] Recommend first-batch order.
   - [x] Identify first low-risk implementation slice.

4. Verification
   - [x] Run Trellis validate for this task.
   - [x] Run `git diff --check`.
   - [ ] Archive this planning task after validation.

## First Implementation Slice

Recommended first slice:

```text
phase5-alert-delivery-frontend-controls
```

Reason:

- Backend API already exists and is targeted-tested.
- It is fake local outbox only and sends no external notification.
- It improves Ops usability without introducing provider calls, deletion, scheduling, S3, parsing, translation, or Word generation.

Planned boundary for that separate implementation task:

- Add frontend TS contracts and API wrapper for:
  - `POST /api/v1/ops/alert-deliveries/preview`
  - `POST /api/v1/ops/alert-deliveries/fake-send`
- Add an Admin-only action panel on `OpsDashboardPage.vue` using currently active backend alert codes from `healthApi.getOpsAlerts()`.
- Require reason and exact confirmation phrase before fake-send.
- Display response safety metadata and per-alert outcomes.
- Do not call Slack/email/webhook.
- Do not add backend behavior.

Expected verification for the first slice:

```bash
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate <slice-task>
git diff --check
```

Backend tests and OpenAPI export are not required for the first slice unless backend files change.

## Planning Verification Commands

```bash
python3 ./.trellis/scripts/task.py validate 06-07-phase5-production-ops-integration-automation-gap-audit
git diff --check
```

## Verification Results

- `python3 ./.trellis/scripts/task.py validate 06-07-phase5-production-ops-integration-automation-gap-audit` passed.
- `git diff --check` passed.
- Backend tests, OpenAPI export, frontend build, browser smoke, pdf-mineru parsing, translation provider calls, Word generation, real alert delivery, real provider cancellation, cleanup scheduler, and real S3 deletion were not run because this task changed only Trellis planning documents.

## Non-execution Reminder

Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, or autonomous destructive cleanup.
