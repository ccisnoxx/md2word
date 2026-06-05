# Term Rule Proposal Review Governance Linkage

## Goal

补齐 Term Rule Proposal 的审核队列增强闭环：

- admin 批量 `approve / reject`
- 审核冲突时跳转到 `TermRuleSetPage` 处理
- 从 `TermRuleSetPage` 回到 proposal 审核页继续复核

同时保持既有 proposal 边界：proposal 只是变更建议，真正的 draft 编辑和发布仍在
`TermRuleSetPage`。

## Requirements

- Review queue
  - admin 在 Term Rule `review` 队列中可对 `pending_review` proposal 做批量 `approve / reject`
  - bulk 操作必须返回逐条结果，允许 partial success
  - 单条 `approve-and-publish` 仍保留，但不进入 bulk 范围
- Conflict resolution
  - 当单条或批量 `approve` 遇到结构化 `term_rule_proposal_conflict` 时：
    - proposal 保持 `pending_review`
    - 审核页能明确提示去 `TermRuleSetPage` 处理
  - 跳转治理页时应带上足够上下文：
    - `set_id`
    - `proposal_id`
    - `target_rule_id`
    - `source_term`
- Governance linkage
  - `TermRuleSetPage` 应能消费 proposal 上下文，并提供回到审核页的入口
  - “已 approve 待核对 proposals”列表必须使用真正的 `approved_unpublished` 语义，而不是泛 `approved`
- Constraints
  - 不绕过现有 single approve service 语义
  - 不做 bulk `approve-and-publish`
  - 不做自动 rebase / force approve
  - 不把审核页扩成 Term Rule CRUD 页

## Acceptance Criteria

- [ ] Term Rule 审核页支持批量 `approve`
- [ ] Term Rule 审核页支持批量 `reject`
- [ ] bulk 响应按 proposal 返回逐条成功/失败结果
- [ ] 冲突 proposal 在 bulk / single approve 后都保持 `pending_review`
- [ ] 审核页冲突 CTA 能跳到 `settings-term-rule-sets`
- [ ] `TermRuleSetPage` 能带着 proposal 上下文回跳审核页
- [ ] `TermRuleSetPage` 的“已 approve 待核对 proposals”使用 `approved_unpublished` 语义
- [ ] 不引入 bulk `approve-and-publish`
- [ ] 最小验证通过：
  - backend targeted tests
  - `cd frontend && npm run build`
  - `python -m unittest tests.test_openapi_export`

## Non-goals

- 不做 Term Rule Proposal 自动 rebase。
- 不做 Term Rule governance 新 CRUD。
- 不做 publish 策略扩展或多版本发布编排。
- 不改任务上下文提案入口。

## Notes

- Parent: `.trellis/tasks/06-04-proposal-review-queue-enhancement/`
- Depends on shared shell:
  - `.trellis/tasks/06-04-proposal-review-queue-shared-shell/`
