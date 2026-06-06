# File retention operations Phase 4 gap audit

## Goal

对照产品成熟化路线图 Phase 4 “Operations and Retention”，完成文件生命周期和运维能力的 gap audit，判断 Phase 4 第一刀应该落在哪个能力，并在进入任何实现前明确安全边界。

本任务只做规划、审计和 review 材料，不实现新功能，不执行 `task.py start`，不运行 pdf-mineru 解析、真实翻译 provider 或 Word 生成主流程。

## Requirements

- 读取并对照以下输入：
  - `AGENTS.md`
  - `.trellis/workflow.md`
  - `.trellis/tasks/archive/2026-06/06-03-product-roadmap/{prd.md,design.md,implement.md,acceptance.md}`
  - Phase 1/2/3 closeout 记录
  - `file-retention-management` 相关归档任务
  - 当前 files / retention / storage / audit / system-status 相关前后端代码和测试
- 对照 Phase 4 范围做 gap audit：
  - 文件管理和保留策略
  - 物理删除
  - 清理计划
  - 存储空间统计
  - 操作审计查询和导出
  - Worker/队列监控和告警
- 在以下候选中判断 Phase 4 第一刀：
  - 物理删除
  - 保留策略 CRUD
  - 定时清理
  - 存储配额
  - 文件搜索
  - 审计导出
- 优先明确危险操作安全边界：
  - Admin-only
  - dry-run-first
  - 不可逆操作显式确认
  - 必填 reason
  - 审计事件
  - 不删除任务记录、事件记录或 metadata 记录
  - 不扩大到 legacy `/api/v1/jobs` cleanup / recovery 运维动作
- 产出后续最小实现任务建议，但不在本任务中实现。

## Acceptance Criteria

- [x] 已创建 planning task，且任务状态保持 `planning`。
- [x] 已完成 Phase 4 候选能力 gap matrix。
- [x] 已给出 Phase 4 第一刀推荐和非推荐项理由。
- [x] 已明确物理删除相关 dry-run、审计、确认、权限和不可逆边界。
- [x] 已写出 `prd.md`、`design.md`、`implement.md` 供 review。
- [x] 未执行 `task.py start`。
- [x] 未修改生产代码。
- [x] 未运行 pdf-mineru 解析、真实翻译 provider 或 Word 生成主流程。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- First-slice recommendation: start Phase 4 with a constrained physical-delete safety contract, not broad policy CRUD, scheduler, quota enforcement, full file library/search, or audit export.
- Closeout: user approved moving to `file-retention-physical-delete-safety-contract` implementation on 2026-06-06.
