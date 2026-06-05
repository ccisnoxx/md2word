# Term Rule Proposal Review Governance Linkage Design

## Current State

- `TermProposalsPage.vue`
  - 只有单条 `approve / approve-and-publish / reject`
  - 已展示结构化冲突摘要，但没有治理页跳转 CTA
- `TermRuleSetPage.vue`
  - 已有 draft CRUD、diff、preflight、publish
  - 已展示“已 approve 待核对 proposals”
  - 但当前加载逻辑使用 `scope=all,status=approved`，会混入已发布 proposal，不够精确
- Backend
  - `app/domains/term_rules/proposals_router.py`
  - `app/domains/term_rules/proposals_service.py`
  - 已有单条审核和结构化 `409`
  - 没有 bulk endpoint

## Recommended Approach

### 1. Add domain-specific bulk endpoints

推荐新增：

- `POST /api/v1/term-rule-proposals/bulk-approve`
- `POST /api/v1/term-rule-proposals/bulk-reject`

请求建议：

```json
{
  "proposal_ids": ["trp_a", "trp_b"],
  "review_comment": "shared batch note"
}
```

响应建议：

```json
{
  "action": "approve",
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "items": [
    {
      "proposal_id": "trp_a",
      "ok": true,
      "status_code": 200,
      "error_code": null,
      "detail": null,
      "proposal": {}
    }
  ]
}
```

理由：

- 比前端 fan-out 更容易保证 auth、OpenAPI、partial success 和审计语义一致。
- 可以完全复用现有单条 service 逻辑，不需要重写 approve/reject 内核。

### 2. Keep bulk logic domain-local

不做跨 domain 的 generic bulk proposal service。

Term Rule bulk 只需要：

- 小范围 router schema
- service 内部循环调用单条 `approve_proposal` / `reject_proposal`
- per-item result normalization

### 3. Add governance CTA from conflict state

Term Rule 审核页冲突信息已经足够结构化，可直接把 CTA 指向：

- route name: `settings-term-rule-sets`
- query:
  - `set_id`
  - `proposal_id`
  - `target_rule_id`
  - `source_term`
  - `return_to=term-proposals`
  - `return_tab`

治理页消费方式：

- 若 `set_id` 存在，优先选中对应规则集
- 若 `source_term` 存在，可预填 draft rule 搜索框
- 显示 context banner，说明“这是从 proposal 冲突跳转过来的治理上下文”
- 提供“返回 proposal 审核页”按钮

### 4. Tighten approved proposal card semantics

`TermRuleSetPage` 当前“已 approve 待核对 proposals”应改为真正的：

- `scope=approved_unpublished`

这样治理页展示的是“本轮仍未随版本发布的 proposal”，与页面文案一致。

行级跳转建议：

- route name: `term-proposals`
- query:
  - `tab=all`
  - `proposal_id=<id>`

理由：

- approved proposal 不在 `review` 队列
- 进入 `all` 更稳定

## Files

- `app/domains/term_rules/proposals_router.py`
- `app/domains/term_rules/proposals_service.py`
- `app/domains/term_rules/schemas.py`
- `frontend/src/api/termProposals.ts`
- `frontend/src/api/types.ts`
- `frontend/src/pages/TermProposalsPage.vue`
- `frontend/src/components/TermProposalTable.vue`
- `frontend/src/pages/TermRuleSetPage.vue`
- `docs/api/term-rules.md`
- `docs/api/openapi.json`
- `tests/test_fastapi_jobs_backend.py`

## Data Model

不新增持久化字段。

仅新增 API schema：

- bulk request / response

## Risks

- bulk reject 需要统一 `review_comment`；若未来需要逐条不同原因，再另开任务，不在本轮扩展。
- governance page 的 query 上下文只能辅助定位，不应变成隐式 draft mutation。

## Verification

- `python -m unittest tests.test_fastapi_jobs_backend -k term_rule_proposal`
- `python -m unittest tests.test_openapi_export`
- `cd frontend && npm run build`

