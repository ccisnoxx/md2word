# Ops recovery action governance gap audit

## Goal

对 Phase 4 剩余运维闭环能力做 planning-only gap audit，专门审计恢复动作、provider cancellation、告警投递和自动化清理的安全边界，并给出下一刀可实现的最小安全切片。

本任务只做规划和审计材料，不实现新功能，不执行 `task.py start`。

## Requirements

- 对照 Phase 4 Operations and Retention 路线图，审计以下能力：
  - 任务恢复动作。
  - Provider cancellation。
  - 告警投递。
  - 自动化清理执行。
- 读取并归纳当前实现证据：
  - `ops-alerting-and-recovery-readiness`：当前只读告警 readiness。
  - `file-retention-scheduled-cleanup-readonly-plan`：当前只读 cleanup runner。
  - `file-retention-physical-delete-safety-contract`：当前手动物理删除安全合同。
  - `audit-log-export-governance`：当前审计导出治理。
  - `document_jobs` retry/cancel/archive/bulk action 现状。
  - legacy `/api/v1/jobs` retry/cancel/recover-mineru-result/cleanup-local-files 现状。
  - `MinerUClient` 当前 provider 能力。
- 明确哪些动作已经存在、哪些只是 read-only/readiness、哪些仍缺安全合同。
- 明确所有高风险动作的最低安全边界：
  - Admin-only 或明确的授权模式。
  - dry-run/preview-first。
  - 精确目标 ID，不使用 broad selector 直接执行。
  - 必填 reason。
  - 不可逆或外部调用动作需要确认短语。
  - 审计事件。
  - 幂等和并发保护。
  - provider call 和 notification delivery 必须显式标记，不允许由只读告警隐式触发。
- 给出下一刀推荐任务和暂缓项理由。

## Acceptance Criteria

- [x] Planning task exists and remains `planning`.
- [x] `prd.md`, `design.md`, and `implement.md` describe the governance audit and next-slice recommendation.
- [x] Gap matrix covers recovery actions, provider cancellation, alert delivery, and automated cleanup execution.
- [x] Safety contract covers Admin-only, dry-run, reason, confirmation, audit, idempotency, provider-call isolation, and automation limits.
- [x] Recommendation is explicit: implement a read-only recovery action safety registry / preview contract before executing new recovery/provider/notification/cleanup actions.
- [x] Non-recommended first slices are documented with rationale.
- [x] `implement.jsonl` and `check.jsonl` contain real spec/research context, not template placeholders.
- [x] `task.py validate 06-07-ops-recovery-action-governance-gap-audit` passes.
- [x] `git diff --check` passes.
- [x] No `task.py start` is run.
- [x] No production code is changed.
- [x] No pdf-mineru parsing, real translation provider, Word generation, provider cancellation, alert delivery, scheduler loop, automated cleanup execution, or physical deletion is run.

## Notes

- Existing Ops Dashboard and `health/ops-alerts` are intentionally read-only.
- Current local `MinerUClient` has submit/query/download methods but no local cancellation method. External provider cancellation support must be verified from primary provider documentation before any provider-cancel implementation task.
- Existing legacy `/api/v1/jobs/{job_id}/recover-mineru-result` actively queries MinerU and enqueues processing; it is a high-priority governance hardening candidate after a safety registry exists.
