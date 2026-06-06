# Phase 4 operations execution gap audit

## Goal

对照产品成熟化路线图 Phase 4 “Operations and Retention”，确认剩余执行型 Ops 闭环的缺口、依赖顺序和安全边界，为后续三个执行切片和最终 closeout 提供唯一执行计划。

## Requirements

- 只做 gap audit、执行计划和 Trellis bookkeeping；不修改生产代码。
- 不运行 pdf-mineru 解析、真实翻译 provider、Word 生成主流程、真实外部告警服务、真实 provider cancellation、真实 S3 删除或清理 scheduler loop。
- 必须读取并归纳已完成 Phase 4 基础任务：
  - `file-retention-physical-delete-safety-contract`
  - `file-retention-policy-crud-governance`
  - `file-retention-storage-usage-quota-readiness`
  - `file-retention-scheduled-cleanup-readonly-plan`
  - `audit-log-export-governance`
  - `file-retention-file-library-search-governance`
  - `ops-alerting-and-recovery-readiness`
  - `ops-recovery-action-governance-gap-audit`
  - `ops-recovery-action-safety-registry`
- 明确剩余 Phase 4 执行项：
  - `ops-alert-delivery-outbox-safety-contract`
  - `ops-provider-cancellation-safety-contract`
  - `file-retention-automated-cleanup-execution-contract`
  - `phase4-operations-retention-closeout`
- 给出最小风险实现顺序、每项必须复用或新增的安全合同、目标测试范围和不做项。
- 明确哪些后续增强不阻塞 Phase 4 收口。

## Acceptance Criteria

- [x] 已确认当前无 active Trellis task，工作区 clean。
- [x] 已确认 Phase 1/2/3 已收口，Phase 4 已完成 read-only/readiness 和手动 physical-delete safety primitive。
- [x] 已产出剩余执行型 Ops 闭环的依赖顺序。
- [x] 已明确每个执行项的 Admin-only、dry-run/preview、exact target、reason、confirmation、audit、幂等、限流和外部副作用边界。
- [x] 已明确不得触发的真实外部流程和高风险操作。
- [x] 已给出每项 targeted verification 范围。

## Notes

- 这是 planning-only 任务，不执行 `task.py start`。
