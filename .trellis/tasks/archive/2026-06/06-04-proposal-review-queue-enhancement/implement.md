# Proposal Review Queue Enhancement Integration Review

## Status

本 parent task 仍保持 `planning`，因为它负责总设计和跨 child 集成验收，不作为直接实现目标。

当前已完成 3 个 child 的实现、最小验证和 `task.py finish` 收尾：

- `06-04-proposal-review-queue-shared-shell`
- `06-04-term-rule-proposal-review-governance-linkage`
- `06-04-translation-term-proposal-review-governance-linkage`

Trellis 列表仍显示 parent `[0/3 done]`，原因是当前项目的 `task.py finish` 只清空 active task，不会把 child `task.json.status` 改为 `completed`。归档前 child 目录仍保留在 active tasks 下，状态也仍是 `in_progress`。

## Child Integration Matrix

| Child | Scope | Result | Verification |
|---|---|---|---|
| `proposal-review-queue-shared-shell` | `TermProposalsPage` deep-link、selection id、queue focus/fallback、source task form context 回归 | done | `cd frontend && npm run build`; real browser smoke with frontend API mock |
| `term-rule-proposal-review-governance-linkage` | Term Rule bulk approve/reject、partial success、conflict 保留、Term Rule Set governance CTA/return、`approved_unpublished` scope | done | backend targeted tests; OpenAPI tests; frontend build; real browser smoke |
| `translation-term-proposal-review-governance-linkage` | Translation bulk approve/reject、structured conflict、Translation review tab toolbar/summary、Translation Term Set compatibility CTA/return | done | backend targeted tests; OpenAPI tests; frontend build; real browser smoke |

## Parent Acceptance Review

- `design.md` 的 parent/child 拆分已落地；3 个 child 都具备独立 PRD/design/implement 记录。
- bulk review 范围已收敛为 bulk `approve` / bulk `reject`；bulk `approve-and-publish` 明确不做。
- Term Rule bulk contract 和 Translation bulk contract 均为 domain-specific endpoints，但共享 per-item result envelope。
- Term Rule Proposal 与 Translation Term Proposal 的边界保持独立：没有新增统一 proposal service、统一 repository 或统一持久化模型。
- `TermProposalsPage` 作为共享审核工作台壳层被复用；业务合并和冲突判断仍在各自 domain service 内。
- 来源任务回链保持通过 `source_job_id -> job-detail`，任务上下文新建入口 `tab=new` / `tab=translation-new` 在 shared-shell smoke 中回归。
- 审核页到治理页的 query/deep-link contract 已分别落地：
  - Term Rule: `set_id`、`proposal_id`、`target_rule_id`、`source_term`、`return_to`、`return_tab`
  - Translation: `set_id`、`proposal_id`、`observed_version`、`return_to`、`return_tab`
- 治理页到审核页回跳已分别落地：
  - Term Rule: `term-proposals?tab=review&proposal_id=...`
  - Translation: `term-proposals?tab=translation-review&proposal_id=...`
- 冲突解决策略已落地为“审核页显示摘要和失败原因，治理页负责 draft/preflight/publish 处理，不自动 rebase、不 force approve”。

## Verification Summary

已观察通过的最小验证集合：

- `cd frontend && npm run build`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k term_rule_proposal`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k translation_term_proposal`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff`
- `python3 ./.trellis/scripts/task.py validate 06-04-proposal-review-queue-shared-shell`
- `python3 ./.trellis/scripts/task.py validate 06-04-term-rule-proposal-review-governance-linkage`
- `python3 ./.trellis/scripts/task.py validate 06-04-translation-term-proposal-review-governance-linkage`

已观察通过的真实页面 smoke：

- Shared shell:
  - `tab=review` / `tab=translation-review` deep-link 自动定位
  - review fallback 到 all 队列
  - queue 手动点选后刷新保持选中
  - `tab=new` / `tab=translation-new` 来源任务上下文回归
- Term Rule:
  - bulk approve partial success
  - bulk reject partial success
  - conflict item 保持可见
  - governance CTA 到 `TermRuleSetPage`
  - `TermRuleSetPage` 上下文 banner + `approved_unpublished`
  - 返回 proposal 审核页
- Translation:
  - bulk approve partial success
  - bulk reject partial success
  - structured conflict / compatibility 摘要展示
  - governance CTA 到 `TranslationTermSetPage`
  - `TranslationTermSetPage` 上下文 banner + compatibility focus
  - 返回 proposal 审核页

## Explicit Non-goals Preserved

- 未重跑 pdf-mineru 解析、翻译或生成 Word 主流程。
- 未做真实文件删除。
- 未新增 bulk `approve-and-publish`。
- 未把 proposal 审核页扩成完整 Term Rule CRUD 或 Translation Term CRUD 页面。
- 未改变 Term Rule Set draft CRUD / publish / rollback 的权威治理入口。
- 未改变 Translation Term Set CSV import/export/publish/rollback 语义。
- 未新增统一 proposal service / repository / persistence model。
- 未做自动 rebase、force approve 或自动 conflict resolution。

## Residual Risks

- 真实浏览器 smoke 使用本地 mock API server；真实 MySQL-backed API 与浏览器的完整端到端验证仍依赖可用 MySQL 服务、`PyMySQL` 依赖和真实 seed 数据。
- 两个 domain 的 bulk UI 当前复用交互模式，但仍是页面内局部实现；如果后续继续扩展第三类 proposal，才需要重新评估抽象。
- Trellis task 状态尚未 archive，父任务 progress 仍显示 `[0/3 done]`。这是流程状态，不代表实现未完成。
- Translation smoke 截图未生成；Browser CDP `Page.captureScreenshot` 两次超时，但交互断言已通过。

## Recommended Next Steps

1. 运行 parent 和 3 个 child 的 Trellis validate。
2. 若不需要继续改代码，按顺序 archive 3 个 child，再做 parent archive。
3. archive 前如需更强信心，可在真实 MySQL 环境补一次端到端浏览器 smoke。
4. commit 前按实际 staged 范围确认未混入无关改动。
