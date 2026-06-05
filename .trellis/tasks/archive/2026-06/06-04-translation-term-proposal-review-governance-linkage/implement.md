# Translation Term Proposal Review Governance Linkage Implementation Plan

## Gate

本 child task 已执行 `task.py start` 并完成实现、验证和 `task.py finish` 收尾。`task.json.status` 仍保留为 `in_progress`，因为当前项目的 `finish` 命令只清空 active task，不改变 task 状态。

本轮执行顺序必须后端优先：

- Translation review tab 的批量 UI 依赖稳定的 per-item bulk envelope。
- bulk approve/reject 必须逐条复用现有单条 `approve_proposal` / `reject_proposal`，不能绕过 pending-only 校验、draft conflict 或 audit 语义。
- Translation proposal 允许一条 proposal 内包含多条 `changes`；bulk 的 partial success 只能发生在 proposal 之间，不做 proposal 内部 partial merge。
- 结构化 conflict 先在后端稳定，再让审核页与 `proposal compatibility` 视角复用字段。

## Backend Contract Notes

- Endpoints:
  - `POST /api/v1/translation-term-proposals/bulk-approve`
  - `POST /api/v1/translation-term-proposals/bulk-reject`
- Request:
  - `proposal_ids: string[]`
  - `review_note?: string | null` for bulk approve
  - `review_note: string` for bulk reject
- Response envelope:
  - `action`
  - `total`
  - `succeeded`
  - `failed`
  - `items[]`
- Response item:
  - `proposal_id`
  - `ok`
  - `status_code`
  - `error_code`
  - `detail`
  - `proposal`
- Structured conflict fields:
  - keep `detail.code=translation_term_proposal_conflict`
  - add stable `detail.message`
  - return `detail.conflicts[]` as compatibility-style findings with:
    - `severity`
    - `code`
    - `message`
    - `normalized_source_term`
    - `action`
    - `current_entry`
    - `observed_entry`

## Checklist

1. Backend bulk schemas and endpoints
   - 增加 translation bulk approve / reject request and response
   - 保持 per-item result envelope
   - Status: done

2. Structured translation conflict
   - 把 approve `409` 从字符串 conflicts 提升为结构化对象
   - 尽量复用 compatibility finding 字段
   - Status: done

3. Frontend review queue
   - Translation review tab 加多选和 batch toolbar
   - 审核页复用结构化 conflict / compatibility 摘要
   - Status: done

4. Governance linkage
   - 审核页增加跳转 `settings-translation-term-sets`
   - 治理页消费 `proposal_id` 并提供回跳
   - Status: done

5. Validation
   - backend targeted tests first:
     - partial success
     - failed item keeps original status
     - conflict item does not bypass existing approve semantics
   - OpenAPI export tests after backend contract changes
   - `cd frontend && npm run build`
   - real browser smoke after frontend wiring
   - Status: done

## Review Notes

- 不做 bulk `approve-and-publish`
- 不改 CSV import/export/publish 语义
- 不做 proposal 内部 partial merge

## Execution Log

- 2026-06-05: 执行 `task.py start 06-04-translation-term-proposal-review-governance-linkage`；确认本 child 进入 `in_progress`。
- 2026-06-05: 明确后端优先顺序：先稳定 bulk contract、结构化 conflict 和最小后端测试，再接前端 Translation review tab。
- 2026-06-05: 完成后端 bulk contract：
  - `POST /api/v1/translation-term-proposals/bulk-approve`
  - `POST /api/v1/translation-term-proposals/bulk-reject`
  - bulk approve/reject 逐条复用现有单条 `approve_proposal` / `reject_proposal`，不新增 bulk `approve-and-publish`。
  - 单条失败进入 per-item result；冲突和非 pending 失败不会覆盖原 proposal 状态。
  - Translation approve `409` 升级为 compatibility-style 结构化 finding，保留 `detail.code=translation_term_proposal_conflict`。
- 2026-06-05: 后端最小验证通过：
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_proposal_bulk_approve_partial_success_and_conflict tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_proposal_bulk_reject_partial_success_preserves_failed_item tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_proposal_approve_and_publish_sets_default_and_conflict_blocks_merge`
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k translation_term_proposal`
  - `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
  - `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff`
- 2026-06-05: 完成前端 Translation review tab 最小闭环：
  - `frontend/src/api/termProposals.ts` / `frontend/src/api/types.ts` 接入 `bulk-approve` / `bulk-reject` contract。
  - `TranslationTermProposalTable.vue` 增加可选 selection column，只有 `pending` proposal 可被选择。
  - `TermProposalsPage.vue` 的 Translation review tab 增加批量审核 toolbar、partial success summary 和失败项摘要；保留单条 `approve-and-publish`。
  - `TermProposalsPage.vue` 审核详情增加跳转 Translation Term Set 治理页 CTA，query 携带 `set_id`、`proposal_id`、`observed_version`、`return_to`、`return_tab`。
  - `TranslationTermSetPage.vue` 消费治理 query，展示上下文 banner，高亮 compatibility 行，支持返回 proposal 审核页。
- 2026-06-05: 完成真实页面 smoke：
  - 使用 `frontend/dist` + 临时 mock API server 跑真实浏览器页面，不触发 pdf-mineru 解析 / 翻译 / 生成 Word 主流程。
  - 验证 admin 进入 `term-proposals?tab=translation-review` 后显示 Translation 批量审核 toolbar。
  - 验证 `bulk-approve` partial success：成功项离开 pending review，冲突项保留且显示 `stale_target_term` 和当前/证据译文摘要。
  - 验证 `bulk-reject` partial success：成功项离开 pending review，失败项保留且显示失败原因。
  - 验证审核详情 CTA 跳转 `settings/translation-term-sets` 并携带 `set_id`、`proposal_id`、`observed_version`、`return_to`、`return_tab`。
  - 验证 Translation Term Set 治理页显示 proposal 上下文 banner、compatibility conflict、返回 proposal 审核页按钮，并可回跳 `term-proposals?tab=translation-review&proposal_id=...`。
  - Note: Browser screenshot 两次调用均因 CDP `Page.captureScreenshot` 超时失败；本轮只记录交互断言结果。
- 2026-06-05: 执行 `task.py validate 06-04-translation-term-proposal-review-governance-linkage` 通过；随后执行 `task.py finish` 清空 active task。

## Verification Result

- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_proposal_bulk_approve_partial_success_and_conflict tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_proposal_bulk_reject_partial_success_preserves_failed_item tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_term_proposal_approve_and_publish_sets_default_and_conflict_blocks_merge`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k translation_term_proposal`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- Passed: `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py --check --no-diff`
- Passed: `cd frontend && npm run build`
- Passed: `git diff --check -- app/domains/translation/proposals_router.py app/domains/translation/proposals_service.py app/domains/translation/schemas.py tests/test_fastapi_jobs_backend.py docs/api/translation-term-proposals.md docs/api/openapi.json frontend/src/api/termProposals.ts frontend/src/api/types.ts frontend/src/components/TranslationTermProposalTable.vue frontend/src/pages/TermProposalsPage.vue frontend/src/pages/TranslationTermSetPage.vue .trellis/tasks/06-04-translation-term-proposal-review-governance-linkage/implement.md`
- Passed: real browser smoke at `http://127.0.0.1:4198/term-proposals?tab=translation-review`
  - bulk approve partial success: success `tt-smoke-approve-ok`, failed conflict `tt-smoke-conflict`
  - bulk reject partial success: success `tt-smoke-reject-ok`, failed item `tt-smoke-conflict`
  - governance CTA and return deep-link: `tt-smoke-conflict` → `settings/translation-term-sets` → `term-proposals?tab=translation-review&proposal_id=tt-smoke-conflict`
- Not generated: smoke screenshot; Browser CDP `Page.captureScreenshot` timed out twice.

## Remaining Work

- 当前 child 的实现、最小验证和 active task 收尾已完成。
- 归档策略后续与 parent integration review 一起处理。
