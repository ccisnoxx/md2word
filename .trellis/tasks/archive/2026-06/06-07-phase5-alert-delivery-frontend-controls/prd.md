# Phase 5 alert delivery frontend controls

## Goal

把 Phase 4 已实现的 Admin-only fake alert delivery outbox 合同暴露到 Ops dashboard：Admin 可以选择当前活跃告警，先 preview，再 fake-send 到 local outbox audit；页面必须明确不发送 Slack/email/webhook，不触发 provider、cleanup、delete、解析、翻译或 Word 生成。

## Requirements

- Add frontend TypeScript contracts for existing backend alert delivery schemas.
- Add a dedicated API wrapper for:
  - `POST /api/v1/ops/alert-deliveries/preview`
  - `POST /api/v1/ops/alert-deliveries/fake-send`
- Add an Admin-only action panel to `frontend/src/pages/OpsDashboardPage.vue`.
- Use active alert codes from existing `healthApi.getOpsAlerts()` response; do not allow arbitrary free-form alert codes in the first UI slice.
- Support:
  - selecting active alerts.
  - previewing selected alert fake delivery.
  - entering reason and exact confirmation phrase before fake-send.
  - showing per-alert outcomes, totals, delivery id, dedupe window, and safety metadata.
- Keep execution semantics fake-only:
  - channel remains `local_outbox`.
  - no real external notification delivery.
  - no backend changes.
  - no main conversion workflow calls.
- Preserve current Ops dashboard read-only status for all other panels; only this panel calls the fake-send endpoint when Admin explicitly confirms.

## Acceptance Criteria

- [x] Planning artifacts exist and task is started before frontend edits.
- [x] Frontend has typed alert delivery request/response contracts.
- [x] Frontend API wrapper can call preview and fake-send endpoints.
- [x] Ops dashboard renders alert delivery controls only from active backend alert codes.
- [x] Fake-send requires reason and exact confirmation phrase entered by the Admin.
- [x] UI displays response safety metadata and does not describe fake delivery as real Slack/email/webhook delivery.
- [x] No backend behavior, OpenAPI, persistence, scheduler, provider, S3, parsing, translation, or Word generation changes are made.
- [x] Minimal verification passes and is recorded in `implement.md`.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
