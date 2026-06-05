# Proposal Review Queue Enhancement

## Goal

在不改变现有 `approve / reject / approve-and-publish / publish` 语义的前提下，
补强现有提案审核队列，使 Admin 能更高效地处理 Term Rule Proposal 与
Translation Term Proposal，并把审核流和既有治理页面、任务上下文来源串成
可追溯的闭环。

本任务属于产品成熟化路线图 Phase 2，当前只进入 Trellis planning/design，
不直接开始大范围实现。

## Requirements

- 审核队列增强目标
  - 支持批量审核，优先覆盖批量 `approve` / `reject`。
  - 保持单条 `approve-and-publish` 语义，不把它升级为隐式 bulk publish。
  - 当 proposal 与当前 draft 存在冲突时，审核页必须给出明确的“下一步去哪里解决”。
  - 从 proposal 审核页可回到来源任务详情，且不能破坏已完成的任务上下文提案入口和来源任务回链。
  - 从 proposal 审核页可跳转到：
    - `TermRuleSetPage`
    - `TranslationTermSetPage`
  - 需要明确 Term Rule Proposal 与 Translation Term Proposal 的边界、职责和复用层次。
- 复用约束
  - 优先复用 `frontend/src/pages/TermProposalsPage.vue` 作为统一审核工作台壳层。
  - 优先复用现有 proposal API/service，而不是新建泛化 proposal 领域模型。
  - 优先复用已有 `TermRuleSetPage` 的 draft diff/preflight/发布能力。
  - 优先复用已有 `TranslationTermSetPage` 的 diff/preflight/proposal compatibility 能力。
- 一致性与安全约束
  - 不绕过现有 `approve / reject / publish` 语义。
  - 不把提案审核页扩成完整术语规则 CRUD 页面。
  - 不重跑 pdf-mineru 解析、翻译或 Word 生成主流程。
  - 不做真实文件删除。
  - 改动必须可拆、可验收、可回滚。

## Acceptance Criteria

- [ ] 产出经 review 的 `design.md`，明确推荐 task 拆分、边界、复用策略和最小实现顺序。
- [ ] 明确批量审核范围：
  - 至少回答是否包含 bulk `approve`、bulk `reject`、bulk `approve-and-publish`
  - 并给出不包含项的原因
- [ ] 明确冲突解决策略：
  - 审核页展示哪些冲突信息
  - 何时停留在审核页
  - 何时跳转到 `TermRuleSetPage` / `TranslationTermSetPage`
- [ ] 明确来源任务回链与治理页联动的 query / deep-link contract。
- [ ] 明确 Term Rule Proposal 与 Translation Term Proposal 的边界：
  - 哪些交互共享
  - 哪些后端 contract 只按领域分别维护
  - 为什么不做统一泛化 proposal service / table / mutation flow
- [ ] 明确前端页面、后端 API、数据模型、测试范围以及本轮明确不做项。

## Non-goals

- 不在本 task 中直接实现完整术语规则 CRUD 或翻译术语逐条 CRUD。
- 不新增外部客户门户能力。
- 不在本 task 中承诺自动 rebase、force approve、自动冲突修复。
- 不做真实文件删除、文件保留策略扩展或任务主流程重跑。
- 不把 Translation Term Set CSV 治理页改造成 proposal 直接编辑页。
- 不在未完成 planning review 前启动 `task.py start`。

## Notes

- 推荐用 parent task 承接本轮总设计；child tasks 在 design review 后再创建。
- 已有相关归档任务可直接复用为设计输入：
  - `.trellis/tasks/archive/2026-06/06-04-job-context-proposals/`
  - `.trellis/tasks/archive/2026-06/06-04-term-rule-proposal-boundary-conflicts/`
  - `.trellis/tasks/archive/2026-06/06-04-translation-term-governance-diff/`
  - `.trellis/tasks/archive/2026-06/06-04-term-rule-governance-phase2/`
