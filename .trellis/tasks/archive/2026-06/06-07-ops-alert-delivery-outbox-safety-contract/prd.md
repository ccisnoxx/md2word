# Ops alert delivery outbox safety contract

## Goal

把 Phase 4 已有只读 Ops alerts 进一步推进到可执行但无外部副作用的 delivery outbox 安全合同：Admin 可以针对当前活跃告警做 dry-run preview 或 fake outbox delivery，系统记录 compact audit，不调用真实 Slack/email/webhook。

## Requirements

- Add Admin-only alert delivery outbox endpoints under Ops API.
- Delivery targets must be exact current alert codes from `GET /api/v1/health/ops-alerts`; no implicit “all alerts”.
- Support two modes:
  - `dry_run`: only previews selected current alerts.
  - `fake`: writes a local audit-backed outbox attempt, but sends no external notification.
- Execution must require:
  - non-empty `alert_codes`.
  - non-empty `reason`.
  - exact confirmation phrase.
  - bounded batch and dedupe window.
- Response must include safety metadata proving no external notification, provider call, cleanup, delete, parsing, translation, or Word generation occurred.
- Dedupe must be implemented against recent audit events to make repeated fake deliveries idempotent.
- Rate limit/batch cap must prevent broad delivery attempts.
- Update recovery action registry so `alert.delivery` reflects the fake/outbox contract while still making real external delivery a known gap.
- Update docs/OpenAPI and targeted backend tests.

## Acceptance Criteria

- [x] `POST /api/v1/ops/alert-deliveries/preview` is Admin-only and read-only.
- [x] `POST /api/v1/ops/alert-deliveries/fake-send` is Admin-only, requires reason + confirmation, writes compact audit, and sends no external notification.
- [x] Both endpoints reject empty/duplicate/too-many alert codes and selected alert codes not active in current ops alerts.
- [x] Fake delivery dedupes repeated attempts inside the requested window without writing duplicate delivery audits.
- [x] Responses include per-alert outcomes and safety metadata.
- [x] `alert.delivery` in the recovery action registry is available for the fake/outbox contract and has `audit_action=ops.alert_delivery_fake`.
- [x] Targeted backend tests, OpenAPI check, Trellis validate, and `git diff --check` pass.

## Notes

- Do not call real external alert services.
- Do not run pdf-mineru parsing, real translation providers, Word generation, provider cancellation, cleanup execution, physical deletion, S3 deletion, or scheduler loops.
