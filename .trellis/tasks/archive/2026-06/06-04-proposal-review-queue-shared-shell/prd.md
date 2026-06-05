# Proposal Review Queue Shared Shell

## Goal

把 `frontend/src/pages/TermProposalsPage.vue` 补成稳定的提案审核工作台壳层，
先解决 deep-link、聚焦、刷新后选中态、表格高亮和 shared review state，
为后续两个 domain child task 接批量审核与治理联动打基础。

本 child task 只做 shared shell，不落地 domain-specific 的 bulk approve/reject
后端 contract，也不改 proposal 审核语义。

## Requirements

- Route / deep-link
  - 支持 admin 从治理页或列表页通过 `tab` + `proposal_id` 直接打开对应审核队列并聚焦目标 proposal。
  - 目标 proposal 如果不在当前队列但 admin 仍有权限查看，应回退到对应 `all` 队列再聚焦，不直接丢失上下文。
  - 支持的 review 场景至少包括：
    - `review`
    - `all`
    - `translation-review`
    - `translation-all`
- Shared review state
  - 刷新当前 tab 后，若目标 proposal 仍在当前列表中，页面应保持选中态。
  - Term Rule 和 Translation 两类审核详情应共用一致的“当前选中 proposal”交互模型，而不是两套互不兼容的路由语义。
- Table contract
  - `TermProposalTable` 和 `TranslationTermProposalTable` 需要支持“当前选中项可视化”。
  - 后续 child task 要能在不重写表格主体的前提下继续接入多选和 batch toolbar。
- Constraints
  - 不新增 backend API。
  - 不改 create / approve / reject / approve-and-publish 语义。
  - 不实现真实批量 mutation。
  - 不把页面抽成泛化 proposal framework。

## Acceptance Criteria

- [ ] `tab + proposal_id` deep-link 能打开正确审核 tab 并聚焦 proposal。
- [ ] 当目标 proposal 不在当前 review 队列但可见时，页面会回退到对应 `all` 队列再聚焦。
- [ ] 刷新当前列表后，已选 proposal 若仍可见则保持选中。
- [ ] 两个 proposal table 都支持“当前选中行”的统一可视化 contract。
- [ ] 不影响任务上下文新建入口和来源任务回链。
- [ ] 不引入 backend contract 变更。
- [ ] 最小验证通过：
  - `cd frontend && npm run build`

## Non-goals

- 不实现 bulk approve / reject 网络调用。
- 不实现 bulk approve-and-publish。
- 不新增 proposal 查询筛选接口。
- 不改治理页的 domain-specific CTA 行为。

## Notes

- Parent task: `.trellis/tasks/06-04-proposal-review-queue-enhancement/`
- Downstream children:
  - `06-04-term-rule-proposal-review-governance-linkage`
  - `06-04-translation-term-proposal-review-governance-linkage`
