# Term Rule Governance Phase 2

## Goal

补齐 md2word 产品成熟化路线图 Phase 2 中“术语规则配置治理”的核心缺口，让 Admin 能围绕 Term Rule Set draft 完成结构化术语规则维护、版本 diff、发布前校验和冲突处理，同时保留现有任务上下文 proposal 审核流和已完成的只读检查台。

本任务是 Phase 2 术语规则治理的 parent task。它先产出可拆、可验收、可回滚的规划；具体实现应拆成 child tasks，在各 child task 审核后再进入实现。

## Requirements

- 术语规则完整 CRUD
  - Admin 可以在 Term Rule Set draft 中新增、查看、编辑、启停和移除术语规则。
  - CRUD 必须操作 draft，不直接写 live runtime store，不绕过 Term Rule Set publish/default/rollback 流程。
  - 规则字段至少覆盖 `source_term`、分类、segments、apply scope、case sensitivity、enabled、priority、custom markdown/html、notes。
  - 移除规则只影响 draft 和后续 published version，不做真实文件删除。
- Term Rule Set diff
  - Admin 可以查看 draft 与当前 default published version 的差异。
  - Diff 至少区分 added、updated、disabled、removed、unchanged count。
  - Diff 展示必须能定位到具体规则、字段变化和发布影响。
- 发布前校验
  - 发布前必须展示校验报告，区分 blocking errors 和 warnings。
  - Blocking errors 应阻止发布；warnings 可由 Admin 确认后继续。
  - 校验必须复用现有 term rules YAML / store validation 能力，并补充治理层检查。
- 冲突提示
  - 对 source term 重复、分类缺失、stale proposal snapshot、draft 被其他变更修改等冲突给出可读提示。
  - 后端冲突响应应结构化，前端不依赖自由文本解析。
  - 冲突不做自动 rebase 或 last-write-wins。
- 与现有流程边界
  - `TermRuleWorkbenchPage` 保持只读检查/模拟台，不被改造成编辑页。
  - `TermRuleSetPage` 承接规则集 draft、diff、preflight、publish/default/rollback 治理。
  - Proposal 审核流继续服务 Operator/任务上下文建议；Admin 直接 CRUD 服务配置治理。
  - 现有 approve / approve-and-publish / publish 语义保持兼容。

## Non-goals

- 不启动具体实现，不运行 `task.py start`。
- 不重跑 pdf-mineru 解析、翻译或生成 Word 主流程。
- 不做真实文件删除。
- 不破坏现有 `TermRuleWorkbenchPage` 只读检查台。
- 不改变已完成 Phase 1 任务工作台闭环。
- 不做外部客户门户、多租户规则集创建、复杂权限模型或操作审计查询页。
- 不做 proposal 批量审核、自动 rebase、自动冲突解决。
- 不做翻译术语集完整 diff / 冲突治理；本 parent task 只处理术语规则治理。

## Acceptance Criteria

- [ ] Parent task 下明确 child task 拆分、边界和依赖顺序。
- [ ] PRD 明确术语规则 CRUD、diff、preflight、冲突提示和 proposal 边界要求。
- [ ] Design 明确涉及前端页面、后端 API、数据模型、错误响应、测试和回滚策略。
- [ ] Implement 计划列出可独立验收的 child tasks、每步验证命令和 review gate。
- [ ] 规划明确不触碰 pdf-mineru / 翻译 / Word 生成主流程。
- [ ] 规划明确 `TermRuleWorkbenchPage` 保持只读。
- [ ] 规划明确生产写入路径基于 Term Rule Set draft，而不是 legacy `/api/v1/term-rules` 写接口。
- [ ] `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-governance-phase2` 通过。

## Notes

- Parent roadmap: `.trellis/tasks/06-03-product-roadmap`.
- Related archived slice: `.trellis/tasks/archive/2026-06/06-04-term-rule-workbench`.
- Existing code already has Term Rule Set draft/publish/default/rollback, import/export, proposal approve/publish and read-only rule inspection.
- Full implementation should create child tasks after this parent planning is reviewed.
