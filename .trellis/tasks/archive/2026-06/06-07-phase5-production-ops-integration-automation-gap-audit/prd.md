# Phase 5 production ops integration automation gap audit

## Goal

对照 Phase 4 closeout 的 future candidates，进入 Phase 5 “Production Ops Integration & Automation” 的 planning/design 阶段：判断哪些候选适合本阶段承接，哪些继续延期，产出 roadmap、gap audit、安全计划、小切片任务拆分和第一批实现顺序。

本任务先规划，不直接接入真实外部服务、不执行真实删除或无人值守调度。规划完成且边界清楚后，再为第一个低风险切片创建独立 Trellis task 实现。

## Requirements

- 读取并盘点产品成熟化父路线图和 Phase 4 closeout/相关归档任务，尤其是：
  - alert delivery fake outbox safety contract。
  - provider cancellation fake safety contract。
  - manual cleanup run execution contract。
  - file retention physical delete / scheduled cleanup readonly / storage quota readiness / file library。
  - audit export governance。
  - ops dashboard / ops alerts / recovery action registry。
- 读取当前后端、前端、API、数据模型、配置和测试，确认现有合同与缺口。
- 对 Phase 4 closeout 中列出的 future candidates 逐项给出 Phase 5 纳入或延期判断。
- 输出 Phase 5 roadmap / gap audit / safety plan。
- 按风险和依赖拆成小切片任务，并给出第一批推荐实现顺序。
- 第一批切片必须保持外部副作用、删除、调度、provider cancellation 的安全合同：
  - dry-run / preview first。
  - explicit confirmation for execution。
  - exact target only。
  - audit and idempotency。
  - no real external alert delivery。
  - no real provider cancellation。
  - no real S3 deletion。
  - no autonomous destructive scheduler。
- 不运行 pdf-mineru 解析、翻译 provider 或 Word 生成主流程。
- 不直接调用真实 Slack/email/webhook 服务。
- 不直接调用真实 provider cancellation。
- 不直接做真实 S3 删除。
- 不引入无人值守 destructive scheduler。

## Acceptance Criteria

- [x] 已创建 Phase 5 roadmap/gap audit Trellis task。
- [x] 已盘点 Phase 4 future candidates 并判断纳入 / 延期。
- [x] 已输出 Phase 5 roadmap、gap audit 和 safety plan。
- [x] 已按风险和依赖拆成可单独验证的小切片任务。
- [x] 已给出第一批可实现切片的推荐顺序。
- [x] 已确认本规划任务不运行主流程、不调用真实外部服务、不执行真实 provider cancellation、不做真实 S3 删除、不引入 scheduler loop。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- Current planning source task: `.trellis/tasks/06-07-phase5-production-ops-integration-automation-gap-audit`.
