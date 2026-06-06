# Ops provider cancellation safety contract

## Goal

为 Phase 4 provider cancellation 建立 Admin-only fake/dry-run 安全合同：Ops 可以针对精确 document job 或 legacy job 预览 provider-side cancellation eligibility，并执行本地 fake-cancel 审计闭环；系统不调用真实 Provider cancellation，也不改变本地任务状态。

## Requirements

- Add Admin-only provider cancellation endpoints under Ops API.
- Support exact target types:
  - `document_job`
  - `legacy_job`
- First provider is `mineru` only.
- Preview must read metadata only and must not call MinerU, enqueue workers, cancel local jobs, or write audit.
- Fake execution must require:
  - exact target type and target ID.
  - non-empty reason.
  - exact confirmation phrase.
  - provider operation identifier present, for example MinerU batch ID.
  - idempotency/dedupe against recent audit events.
- Fake execution records compact `ops.provider_cancellation_fake` audit only for non-deduped eligible attempts.
- Response must include target summary, provider operation summary, missing gates, per-attempt outcome, and safety metadata.
- Update recovery action registry so `provider.cancel` represents this fake cancellation contract, while real provider cancellation remains a known gap.
- Add targeted tests and OpenAPI/docs updates.

## Acceptance Criteria

- [x] `POST /api/v1/ops/provider-cancellations/preview` is Admin-only, metadata-only, and returns provider operation eligibility.
- [x] `POST /api/v1/ops/provider-cancellations/fake-cancel` is Admin-only, requires reason + confirmation, writes compact audit, and does not call provider or mutate job state.
- [x] Missing target, terminal job, unsupported provider, and missing provider operation ID are rejected or reported as missing gates.
- [x] Repeated fake-cancel inside dedupe window returns `deduped` and writes no duplicate cancellation audit.
- [x] `provider.cancel` recovery action registry entry is available for fake cancellation and retains real provider cancellation as a known gap.
- [x] Targeted backend tests, OpenAPI check, Trellis validate, and `git diff --check` pass.

## Notes

- Do not call real provider cancellation.
- Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, alert delivery, cleanup execution, physical deletion, S3 deletion, or scheduler loops.
