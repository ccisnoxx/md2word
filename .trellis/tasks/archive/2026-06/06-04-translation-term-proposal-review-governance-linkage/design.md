# Translation Term Proposal Review Governance Linkage Design

## Current State

- `TranslationTermSetPage.vue`
  - 已有 `proposal compatibility` 表和 summary
  - 已带 `proposal_id` deep-link 回 `term-proposals`
  - 但审核页当前不会消费 `proposal_id`
- `TermProposalsPage.vue`
  - Translation 审核仍是单条动作
  - conflict 展示走通用 detail 提取，对 translation 主要还是字符串列表
- Backend
  - `app/domains/translation/proposals_router.py`
  - `app/domains/translation/proposals_service.py`
  - 已有单条 approve/reject/approve-and-publish
  - 409 `translation_term_proposal_conflict` 仍主要返回字符串数组

## Recommended Approach

### 1. Add translation-specific bulk endpoints

推荐新增：

- `POST /api/v1/translation-term-proposals/bulk-approve`
- `POST /api/v1/translation-term-proposals/bulk-reject`

响应 envelope 与 Term Rule child 保持同类结构，但仍由 translation domain 自己维护。

### 2. Align approve conflict shape with compatibility findings

推荐把单条 approve / approve-and-publish 的 `409` 结构，从字符串列表提升为对象列表。

优先复用现有治理页 compatibility finding 的核心字段：

- `code`
- `message`
- `normalized_source_term`
- `action`
- `current_entry`
- `observed_entry`

可新增顶层：

- `message`
- `proposal_id`（可选）

这样前端可以：

- 在治理页 compatibility 表和审核页 conflict 区复用同一套渲染逻辑
- 避免继续依赖自由文本解析

### 3. Reuse governance page as the conflict-resolution destination

审核页跳治理页：

- route name: `settings-translation-term-sets`
- query:
  - `set_id`
  - `proposal_id`
  - `observed_version`
  - `return_to=term-proposals`
  - `return_tab`

治理页消费方式：

- 若 `proposal_id` 存在，优先高亮 compatibility 表中的对应行
- 若对应 proposal 已不在当前 pending compatibility 列表中：
  - 给出提示，不报错中断页面
- 页面提供“返回 proposal 审核页”按钮

### 4. Keep publish semantics separate

即使 translation domain 已有 compatibility preview，也不把治理页变成审核动作页：

- 审核动作仍在 `TermProposalsPage`
- import / publish / rollback 仍在 `TranslationTermSetPage`
- 单条 `approve-and-publish` 仍在审核页 detail panel，不进 bulk

## Files

- `app/domains/translation/proposals_router.py`
- `app/domains/translation/proposals_service.py`
- `app/domains/translation/schemas.py` 或相关 schema file
- `frontend/src/api/termProposals.ts`
- `frontend/src/api/types.ts`
- `frontend/src/pages/TermProposalsPage.vue`
- `frontend/src/components/TranslationTermProposalTable.vue`
- `frontend/src/pages/TranslationTermSetPage.vue`
- `docs/api/translation-term-proposals.md`
- `docs/api/openapi.json`
- `tests/test_fastapi_jobs_backend.py`

## Data Model

不新增持久化字段。

允许的 contract 增量：

- bulk request / response schema
- translation conflict response schema objects

## Risks

- compatibility finding 是 read-only preview 语义，approve `409` 是 mutation 阻断语义；字段可复用，但不能误导为“preview 等于 approve 结果”。
- multi-change proposal 在 bulk approve 中如果某一 change 冲突，整条 proposal 仍应视为失败；不要做 proposal 内部 partial merge。

## Verification

- `python -m unittest tests.test_fastapi_jobs_backend -k translation_term_proposal`
- `python -m unittest tests.test_openapi_export`
- `cd frontend && npm run build`

