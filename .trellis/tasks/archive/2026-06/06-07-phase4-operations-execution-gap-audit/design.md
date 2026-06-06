# Phase 4 operations execution gap audit design

## Inputs Reviewed

| Area | Current state | Execution gap |
| --- | --- | --- |
| Ops alerts | `GET /api/v1/health/ops-alerts` computes Admin-only read-only alert signals and frontend renders them on `OpsDashboardPage.vue`. | No delivery record, fake/test delivery, dedupe, rate limit, or audit of delivery attempts. |
| Recovery action registry | `GET /api/v1/ops/recovery-actions` and preview endpoint catalog execution risk, including candidate `alert.delivery`, `provider.cancel`, and `file_retention.automated_cleanup_execute`. | Candidate actions are unavailable because execution contracts are missing. |
| Provider cancellation | `MinerUClient` supports upload/query/download only. `DocumentJobService.cancel_job()` only changes local metadata. | No fake/dry-run provider cancellation contract, no exact upstream target extraction, no audit/outcome semantics. |
| File retention | Manual physical delete supports selected expired local/local_object files with preview, confirmation phrase, reason, audit, idempotent missing-object handling, and S3 skip. | Read-only cleanup runner is advisory only; no automated execution run contract, run history, lock, limits, preview hash, or reuse wrapper around physical-delete primitive. |
| Audit/export/search/quota | Audit export, file library search, storage usage/quota readiness, retention policy CRUD are implemented and Admin-only. | These support closeout but do not themselves execute alert/cancel/cleanup loops. |

## Dependency Order

1. `ops-alert-delivery-outbox-safety-contract`
   - Lowest destructive risk: no external delivery, no provider calls, no storage deletion.
   - Converts alert computation into auditable local delivery-attempt records with `dry_run` / `fake` outcome only.
   - Makes `alert.delivery` available in the action registry as a fake/testable execution contract, not a real Slack/email/webhook sender.

2. `ops-provider-cancellation-safety-contract`
   - Depends on the action registry and fake execution precedent from alert delivery.
   - Must not call real MinerU or any true provider cancellation.
   - Adds fake/dry-run provider cancellation contract with exact job target, upstream batch/task IDs if present, local cancellation optionality clearly separated, audit, and provider outcome metadata.

3. `file-retention-automated-cleanup-execution-contract`
   - Highest destructive risk and therefore last among execution features.
   - Must reuse `FileUploadService.preview_retention_physical_delete()` and `execute_retention_physical_delete()`.
   - Adds bounded manual-trigger automated cleanup run, not an always-on scheduler loop.
   - Must include preview hash, exact selected IDs, reason, confirmation, dry-run first, execution limit, single-flight guard, audit, idempotency, and S3 skip inherited from physical delete.

4. `phase4-operations-retention-closeout`
   - Planning/verification closeout after all execution contracts archive and commit.
   - Updates parent roadmap `implement.md` with Phase 4 closeout if and only if verification supports it.

## Safety Baselines

All execution endpoints added by follow-up tasks must be:

- Admin-only through JWT `require_admin_user`.
- Exact-target only; no implicit “all alerts”, “all providers”, or “delete everything” operation.
- Preview/dry-run first, with response-level safety metadata.
- Mutating execution requires reason; irreversible or provider-side actions require exact confirmation phrase.
- Audited with compact metadata and trace ID; no secrets, tokens, local absolute paths, object bodies, prompt text, or provider credentials.
- Idempotent where retries can occur:
  - alert delivery dedupes by alert/window/channel.
  - provider cancellation treats already-finished/already-canceled fake outcomes as non-fatal.
  - cleanup uses existing physical-delete idempotent `already_missing` and `deleted` outcomes.
- Bounded:
  - alert batch/window cap.
  - provider cancellation one target at a time in first contract.
  - cleanup file count cap no greater than the existing 50-file physical-delete cap.

## Explicit Non-goals

- Real Slack/email/webhook delivery.
- Real provider cancellation or external API call.
- Real S3 delete.
- pdf-mineru parsing, real translation provider calls, Word rendering, MinerU recovery query/download, or legacy cleanup-local-files.
- Long-running scheduler loop or cron daemon.
- Structured audit details migration.
- Public Operator execution controls for Ops actions.

## Verification Matrix

| Task | Targeted backend tests | OpenAPI | Frontend build |
| --- | --- | --- | --- |
| Alert delivery outbox | Admin-only, dry-run/fake delivery, dedupe/rate limit, audit, no external sender | yes | yes if Ops dashboard UI changes |
| Provider cancellation | Admin-only, preview, fake execution success/already-finished/error, audit, no real provider call | yes | yes if Ops dashboard UI changes |
| Automated cleanup execution | Admin-only, dry-run run record, confirmation/reason/hash gates, bounded execution reusing physical delete, audit, idempotency, S3 skip | yes | yes if file retention UI changes |
| Closeout | Trellis/task docs and roadmap update only | no unless docs demand | no unless UI touched |
