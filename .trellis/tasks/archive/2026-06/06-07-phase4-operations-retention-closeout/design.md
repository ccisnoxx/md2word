# Phase 4 operations retention closeout design

## Scope

This is a closeout audit and documentation task. It does not change backend code, frontend code, API contracts, persistence schemas, runtime settings, dependencies, scheduler behavior, provider integrations, notification integrations, or deletion primitives.

The only planned repository change outside this task directory is the parent roadmap closeout section in:

- `.trellis/tasks/archive/2026-06/06-03-product-roadmap/implement.md`

## Acceptance Matrix

| Phase 4 area | Verdict | Evidence |
| --- | --- | --- |
| 文件管理和保留策略 | Complete for internal Ops maturity | File library Admin search, retention metadata plan/mark-expired, policy CRUD/governance, storage usage/quota readiness, and docs/OpenAPI are implemented and archived. |
| 物理删除、清理计划、存储空间统计 | Complete with guarded local execution | Selected-file physical delete has preview/reason/confirmation/audit/path containment/S3 skip; scheduled cleanup readonly report exists; cleanup run execution reuses physical-delete with preview hash, exact IDs, reason, confirmation, idempotent outcomes, and cap. |
| 操作审计查询和导出 | Complete for current compliance slice | Audit event query already existed; export governance added Admin-only CSV export and audit recording without server-side delivery files. |
| Worker/队列监控和告警 | Complete with fake delivery boundary | Ops dashboard/health readiness exposes queue/worker alert conditions; alert delivery supports Admin-only active-alert preview and fake local outbox audit/dedupe, explicitly no Slack/email/webhook delivery. |
| 任务恢复与外部服务取消 | Complete with honest cancellation boundary | Recovery action registry and exact-target preview expose gates/risk flags; provider cancellation supports metadata-only preview and audit-backed fake-cancel/dedupe, explicitly no real provider cancellation or local job mutation. |

## Execution Contracts Now Present

- `alert.delivery`
  - Admin-only preview and fake-send.
  - Exact active alert codes.
  - Reason and confirmation for fake-send.
  - Dedupe through recent audit events.
  - Compact `ops.alert_delivery_fake` audit.
  - Safety metadata reports no external delivery.

- `provider.cancel`
  - Admin-only preview and fake-cancel.
  - Exact `document_job` or `legacy_job` target.
  - Requires stored MinerU operation ID for eligible fake-cancel.
  - Reason and confirmation for fake-cancel.
  - Dedupe through recent audit events.
  - Compact `ops.provider_cancellation_fake` audit.
  - Safety metadata reports no provider call and no local job mutation.

- `file_retention.automated_cleanup_execute`
  - Admin-only cleanup preview and execute.
  - Exact `file_ids` and `max_files` cap.
  - Preview hash gate before execution.
  - Reason and confirmation.
  - Reuses `FileUploadService.execute_retention_physical_delete()`.
  - Compact `file.retention_automated_cleanup_execute` audit.
  - Safety metadata reports no scheduler loop, no provider call, and no S3 deletion.

## Non-blocking Follow-ups

- Real external alert delivery to Slack/email/webhook remains future work.
- Real provider cancellation remains future work pending provider API semantics and fake-client test coverage.
- Scheduler loop, autonomous policy executor, run history, distributed lock, and signed cleanup plans remain future work.
- Real S3 deletion remains future work and requires a provider-specific safety contract.
- Structured audit details and per-file durable audit evidence remain future compliance hardening.
- Quota enforcement/upload blocking remains future product policy work; current quota readiness is advisory.
- Frontend buttons for the new fake/execution contracts can be added later; current Phase 4 backend contracts and documentation are sufficient to close the internal Ops maturity slice.

## Closeout Decision

Phase 4 can be closed for the roadmap's current Operations and Retention maturity target. The remaining items are real external integrations or deeper automation layers that were explicitly excluded by the Phase 4 execution safety plan and should become future roadmap candidates.
