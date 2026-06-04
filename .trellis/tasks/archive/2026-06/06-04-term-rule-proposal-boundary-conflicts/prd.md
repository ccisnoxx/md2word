# Term Rule Proposal Boundary Conflicts

## Goal

补齐 Term Rule Proposal 审核流的结构化冲突 contract，并把 proposal 审核与 Admin 直接规则集治理的边界写清楚：operator proposal 只表达变更建议，admin approve 只在目标规则证据仍匹配时合入 draft；若 draft 已被直接治理或其他 proposal 改动，后端返回结构化 `409`，前端稳定展示冲突并保持 proposal 待审核。

本 child task 是 Phase 2 的最后收口任务。它不重做 Child 1 的 draft CRUD，不重做 Child 2 的 diff/preflight，不改变 Child 3 的治理 UI 主流程。

## Requirements

- Structured conflict contract
  - `POST /api/v1/term-rule-proposals/{proposal_id}/approve` 遇到 proposal 冲突时返回 `409`。
  - `POST /api/v1/term-rule-proposals/{proposal_id}/approve-and-publish` 遇到 approve 阶段冲突时同样返回 `409`。
  - `409 detail` 必须使用结构化 payload，至少包含 `code` 和 `conflicts[]`。
  - `conflicts[]` 需要能定位 proposal、target rule、source term、category，并包含当前 draft 规则和 proposal 创建时的目标快照。
- Conflict detection
  - `update` / `disable` proposal 审核时，当前 draft 中的 target rule 必须与 `target_rule_snapshot` 等价，否则阻止合并。
  - target rule 已不存在时必须作为冲突处理，而不是静默创建或合并到其他规则。
  - `create` proposal 与当前 draft 中已有同名 source term 但 segments 不一致时，继续作为人工冲突处理，并返回结构化 `409`。
  - 普通输入校验错误仍保持 `400`，不把所有 validation error 都包装成 conflict。
- Lifecycle boundary
  - 冲突发生时 proposal 状态保持 `pending_review`。
  - 冲突发生时不得更新 draft，不得 publish，不得记录 approved/published 状态。
  - approve 成功后仍只写入 Term Rule Set draft；发布仍走现有 publish/preflight 流程。
  - proposal 审核不实现自动 rebase，也不跳过 Admin 直接治理页面的 diff/preflight 安全门。
- Frontend display
  - `TermProposalsPage` 需要展示后端结构化 `conflicts[]`，不依赖自由文本解析。
  - 页面保留现有本地 snapshot warning，用于提前提示；以后端 `409` 为最终事实。
  - Translation Term Proposal 的现有冲突展示不应被破坏。
- Documentation and tests
  - 更新 API 文档和 OpenAPI snapshot。
  - 后端测试覆盖 structured `409`、pending 状态保持、draft 未修改、approve-and-publish 冲突路径。
  - 前端至少通过 `cd frontend && npm run build`。

## Non-goals

- 不实现 proposal 自动 rebase、自动冲突解决或 force approve。
- 不实现批量审核、批量冲突处理或 bulk publish。
- 不改变 Child 1 draft rule CRUD contract。
- 不改变 Child 2 diff/preflight publish gate。
- 不改变 Child 3 `TermRuleSetPage` 直接治理流程。
- 不给 `TermRuleWorkbenchPage` 增加新增、编辑、删除、导入、导出或发布能力。
- 不运行 pdf-mineru 解析、翻译或 Word 生成主流程。
- 不做真实文件删除。
- 不新增数据库迁移，除非实现时发现现有 proposal snapshot 无法承载冲突响应；默认不需要迁移。

## Acceptance Criteria

- [ ] stale target rule approve 返回 `409`，`detail.code == "term_rule_proposal_conflict"`。
- [ ] `detail.conflicts[]` 是结构化对象，包含冲突类型、message、proposal_id、target_rule_id、source_term、category_id、current_rule、target_rule_snapshot。
- [ ] target rule missing approve 返回结构化 `409`。
- [ ] create proposal source term segments conflict 返回结构化 `409`。
- [ ] approve-and-publish 在 approve 阶段冲突时返回同样结构化 `409`，不执行 publish。
- [ ] 冲突后 proposal 状态保持 `pending_review`。
- [ ] 冲突后 draft snapshot/hash/rules 不发生审核侧修改。
- [ ] `TermProposalsPage` 可以展示结构化 conflict item，并兼容旧字符串 detail。
- [ ] Translation Term Proposal 页面冲突展示仍可用。
- [ ] `docs/api/term-rules.md` 与 `docs/api/openapi.json` 同步更新。
- [ ] 后端 proposal 相关测试、OpenAPI 测试、前端 build 通过。

## Notes

- Parent task: `.trellis/tasks/06-04-term-rule-governance-phase2`。
- Depends on:
  - `.trellis/tasks/06-04-term-rule-draft-crud-contract`
  - `.trellis/tasks/06-04-term-rule-set-diff-preflight`
  - `.trellis/tasks/06-04-term-rule-governance-ui`
- Existing reference: Translation Term Proposal 已有 `409 detail.code/conflicts` 风格，可作为兼容响应模式参考，但本任务应为 Term Rule Proposal 提供更强的结构化对象。
