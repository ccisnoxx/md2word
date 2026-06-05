# Term Rule Proposal Review Governance Linkage Implementation Plan

## Gate

本 child task 已执行 `task.py start`，当前 `task.json.status` 为 `in_progress`。

当前 child 已完成后端 bulk 契约、前端最小闭环和真实页面 smoke；已执行 `task.py finish` 清空 active task。`task.json.status` 仍保留为 `in_progress`，因为当前项目的 `finish` 命令只清空 active task，不改变 task 状态。最初后端优先的原因：

- 前端批量交互依赖稳定的 per-item partial success 响应。
- bulk 审核必须复用现有单条 `approve_proposal` / `reject_proposal` 语义，不能绕过结构化冲突或 pending-only 校验。
- 后端 contract 和最小测试通过后，再进入前端联动实现，便于拆分验收和回滚。

## Checklist

1. Backend bulk schemas and endpoints
   - 在 `schemas.py` 增加 bulk request / response model
   - 在 `proposals_router.py` 暴露 bulk approve / reject
   - Status: done

2. Service bulk orchestration
   - 复用单条 approve / reject
   - 返回 per-item result
   - 保持 conflict proposal 为 `pending_review`
   - Status: done

3. Frontend review queue
   - Term Rule review tab 加多选和 batch toolbar
   - 展示 partial success summary
   - 保留单条 `approve-and-publish`
   - Status: done

4. Governance CTA
   - 冲突/详情区增加跳转 `settings-term-rule-sets`
   - `TermRuleSetPage` 消费 query 并提供回跳
   - Status: done

5. Approved proposal semantics fix
   - `TermRuleSetPage` 改为使用 `approved_unpublished`
   - Status: done

6. Validation
   - backend targeted tests
   - OpenAPI export tests
   - `cd frontend && npm run build`
   - real browser smoke
   - Status: done

## Review Notes

- 不做 bulk `approve-and-publish`
- 不改 draft CRUD / publish 内核
- 不做自动 rebase

## Execution Log

- 2026-06-04: 修正 Gate；确认本 child 已进入 `in_progress`，本轮先实现 Term Rule Proposal `bulk-approve` / `bulk-reject` 后端契约和最小测试。
- 2026-06-04: 实现后端 bulk contract：
  - `POST /api/v1/term-rule-proposals/bulk-approve`
  - `POST /api/v1/term-rule-proposals/bulk-reject`
  - 请求级非法 `proposal_ids` 仍返回 400；单条失败进入 per-item result。
  - bulk approve/reject 逐条复用现有单条 `approve_proposal` / `reject_proposal`，不新增 bulk `approve-and-publish`。
  - 结构化 conflict 保留在 `items[].detail`，失败 proposal 不被状态覆盖。
- 2026-06-04: 同步 `docs/api/term-rules.md` 和 `docs/api/openapi.json`。
- 2026-06-04: 实现前端最小闭环：
  - `frontend/src/api/termProposals.ts` / `frontend/src/api/types.ts` 接入 `bulk-approve` / `bulk-reject` contract。
  - `TermProposalTable.vue` 增加可选 selection column，只有 `pending_review` proposal 可被选择。
  - `TermProposalsPage.vue` 的 Term Rule review tab 增加批量审核 toolbar、partial success summary 和失败项摘要；保留单条 `approve-and-publish`。
  - `TermProposalsPage.vue` 审核详情增加跳转 Term Rule Set 治理页 CTA，query 携带 `set_id`、`proposal_id`、`target_rule_id`、`source_term`、`return_to`、`return_tab`。
  - `TermRuleSetPage.vue` 消费治理 query，展示上下文 banner，支持返回 proposal 审核页。
  - `TermRuleSetPage.vue` 的已 approve 待核对 proposals 改为 `scope=approved_unpublished`。
- 2026-06-04: 完成真实页面 smoke：
  - 使用 `frontend/dist` + 临时 mock API server 跑真实浏览器页面，不触发 pdf-mineru 解析 / 翻译 / 生成 Word 主流程。
  - 验证 admin 登录后进入 `term-proposals?tab=review`。
  - 验证 Term Rule review tab 多选后 `bulk-approve` partial success：成功项离开 pending review，冲突项保留且显示失败原因。
  - 验证 `bulk-reject` partial success：成功项离开 pending review，失败项保留且显示失败原因。
  - 验证冲突详情 CTA 跳转 `settings/term-rule-sets` 并携带 `set_id`、`proposal_id`、`target_rule_id`、`source_term`、`return_to`、`return_tab`。
  - 验证 Term Rule Set 治理页显示 proposal 上下文 banner、使用 `approved_unpublished` 加载已 approve 待核对 proposals，并可回跳 proposal 审核页。
- 2026-06-04: 执行 `task.py validate 06-04-term-rule-proposal-review-governance-linkage` 通过；随后执行 `task.py finish` 清空 active task。

## Verification Result

- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_bulk_approve_partial_success_and_conflict tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_term_rule_proposal_bulk_reject_partial_success_preserves_failed_item`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k term_rule_proposal`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff`
- Passed: `cd frontend && npm run build`
- Passed: `git diff --check -- frontend/src/api/termProposals.ts frontend/src/api/types.ts frontend/src/components/TermProposalTable.vue frontend/src/pages/TermProposalsPage.vue frontend/src/pages/TermRuleSetPage.vue`
- Passed: real browser smoke at `http://127.0.0.1:4199/term-proposals?tab=review`
  - bulk approve partial success: success `tr-smoke-approve-ok`, failed conflict `tr-smoke-conflict`
  - bulk reject partial success: success `tr-smoke-reject-ok`, failed pending-only guard `tr-smoke-reject-fail`
  - governance CTA and return deep-link: `tr-smoke-conflict` → `settings/term-rule-sets` → `term-proposals?tab=review&proposal_id=tr-smoke-conflict`
  - screenshot: `output/term-rule-proposal-governance-smoke.png`
- Note: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --write` failed because this script has no `--write` option; reran the correct default export command successfully.
- Note: Real browser smoke used the in-app browser and a local mock API server instead of the production backend; backend behavior was separately covered by targeted API tests.

## Remaining Work

- 当前 child 的实现、最小验证和 active task 收尾已完成。
- 归档策略后续单独处理。
