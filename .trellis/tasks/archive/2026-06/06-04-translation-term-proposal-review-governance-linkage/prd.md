# Translation Term Proposal Review Governance Linkage

## Goal

补齐 Translation Term Proposal 的审核队列增强闭环：

- admin 批量 `approve / reject`
- 审核页复用当前 `proposal compatibility` 视角
- proposal 审核页和 `TranslationTermSetPage` 之间可双向定位和回跳

同时保持既有边界：proposal 审核只决定是否合入，Translation Term Set 的治理、
发布、默认指针切换仍在治理页完成。

## Requirements

- Review queue
  - admin 在 Translation `pending` 队列中可批量 `approve / reject`
  - bulk 操作必须返回逐条结果，允许 partial success
  - 单条 `approve-and-publish` 保留，但不进入 bulk 范围
- Conflict / compatibility
  - 审核页应展示与治理页 `proposal compatibility` 一致的核心冲突语义
  - 从治理页跳回审核页时，`proposal_id` deep-link 必须真正生效
  - 从审核页跳治理页时，应带上：
    - `set_id`
    - `proposal_id`
    - `observed_version`
- Governance linkage
  - `TranslationTermSetPage` 应能根据 `proposal_id` 聚焦 compatibility 行或给出清晰提示
  - 治理页需要提供回到审核页的入口
- Constraints
  - 不改变 Translation Term Set import/export/publish/rollback 语义
  - 不做 bulk `approve-and-publish`
  - 不做逐条 Translation Term CRUD

## Acceptance Criteria

- [ ] Translation 审核页支持批量 `approve`
- [ ] Translation 审核页支持批量 `reject`
- [ ] bulk 响应按 proposal 返回逐条成功/失败结果
- [ ] 审核页可展示结构化 translation conflict，而不只依赖字符串列表
- [ ] 从 `TranslationTermSetPage` 跳回 `term-proposals?tab=translation-review&proposal_id=...` 时会自动聚焦目标 proposal
- [ ] 从审核页可跳到 `settings-translation-term-sets` 并聚焦 compatibility 上下文
- [ ] 不引入 bulk `approve-and-publish`
- [ ] 最小验证通过：
  - backend targeted tests
  - `cd frontend && npm run build`
  - `python -m unittest tests.test_openapi_export`

## Non-goals

- 不做 Translation Term Set 逐条编辑。
- 不做 CSV import/export 语义改造。
- 不做 automatic conflict resolution。
- 不改任务上下文提案创建入口。

## Notes

- Parent: `.trellis/tasks/06-04-proposal-review-queue-enhancement/`
- Depends on shared shell:
  - `.trellis/tasks/06-04-proposal-review-queue-shared-shell/`
