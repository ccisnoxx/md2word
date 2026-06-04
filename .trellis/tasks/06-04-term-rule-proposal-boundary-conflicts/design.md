# Term Rule Proposal Boundary Conflicts Design

## Scope

本任务收口 Term Rule Proposal 审核冲突。核心边界是：proposal 是 operator 提交的变更意图，Admin 直接治理是 draft 的权威编辑入口，approve 只能在 proposal 创建时保存的 target snapshot 仍匹配当前 draft 时执行。否则服务端返回结构化 conflict，让 admin 重新判断，而不是自动 rebase。

## Current State

- `TermRuleProposalService.create_proposal` 已在 `update` / `disable` 时保存 `target_rule_snapshot`。
- `TermRuleProposalService.approve_proposal` 会读取 draft、调用 `_apply_to_store`、更新 draft，再把 proposal 标记为 `approved`。
- `_apply_to_store` 已能检测 target rule missing / changed 和 create source term segment conflict，但 `TermRuleProposalConflictError` 当前只携带自由文本。
- `proposals_router.py` 当前把 conflict 转成 `HTTPException(409, detail=str(exc))`。
- `TermProposalsPage.vue` 已有本地 snapshot warning 和 `extractErrorDetailItems`，但稳定结构化展示能力不足。
- Translation Term Proposal 已使用 `409 detail={"code": "...", "conflicts": [...]}`，可作为响应风格参照。

## API Contract

`approve` 和 `approve-and-publish` conflict response:

```json
{
  "detail": {
    "code": "term_rule_proposal_conflict",
    "message": "proposal 与当前 draft 存在冲突，请重新核对后处理。",
    "conflicts": [
      {
        "type": "stale_target_rule",
        "message": "目标规则已发生变化，请重新提交 proposal。",
        "proposal_id": "trp_xxx",
        "target_rule_id": "rule_xxx",
        "source_term": "VIN",
        "category_id": "vehicle_terms",
        "current_rule": {},
        "target_rule_snapshot": {},
        "metadata": {}
      }
    ]
  }
}
```

Pydantic models in `app/domains/term_rules/schemas.py`:

- `TermRuleProposalConflictItemResponse`
  - `type`: `stale_target_rule | missing_target_rule | source_term_segments_conflict`
  - `message`
  - `proposal_id`
  - `target_rule_id`
  - `source_term`
  - `category_id`
  - `current_rule: TermRuleResponse | None`
  - `target_rule_snapshot: dict[str, Any] | None`
  - `metadata: dict[str, Any]`
- `TermRuleProposalConflictResponse`
  - `code: Literal["term_rule_proposal_conflict"]`
  - `message`
  - `conflicts: list[TermRuleProposalConflictItemResponse]`

Router behavior:

- `TermRuleProposalConflictError` maps to `HTTPException(status_code=409, detail=response.model_dump(mode="json"))`。
- Other existing errors stay unchanged:
  - `FileNotFoundError` -> `404`
  - `ValueError` -> `400`
  - service unavailable -> `503`
  - role forbidden -> existing `403`

OpenAPI:

- Document `409` response for both approve endpoints.
- Keep response model for successful approve endpoints as `TermRuleProposalResponse`。

## Service Design

Update `TermRuleProposalConflictError`:

- Store immutable `conflicts` tuple of response-ready items or internal typed payloads.
- Keep `RuntimeError` message as joined conflict messages for logging/backward compatibility.

Conflict builders:

- `_proposal_conflict(...)` or `_build_conflict_item(...)` centralizes field shape.
- `_serialize_rule_for_conflict(store, rule)` should reuse existing term rule serialization logic where practical. If router-only serialization is easier, service can return current rule snapshot dict and router maps to response schema.
- Avoid adding broad abstraction. The only repeated need is converting conflict items into response detail.

Detection points:

- `update` / `disable`
  - Missing `target_rule_id` or `target_rule_snapshot` remains `400` because proposal record is malformed.
  - Target rule missing in current draft -> `missing_target_rule` conflict.
  - Target rule snapshot differs -> `stale_target_rule` conflict.
  - Snapshot compare remains full `model_dump(mode="json")` equality to preserve current behavior.
- `create`
  - Existing same `source_term` with different segments -> `source_term_segments_conflict` conflict.
  - Same `source_term` with same segments may continue through existing uniqueness check behavior. If current code still returns `400` for duplicate same segments, do not expand scope unless tests show regression.
- Normal validation
  - Missing category, duplicate `source_term` via uniqueness rule, invalid segments, invalid intent remain `400` unless they are explicitly one of the conflict cases above.

State safety:

- Conflict detection must occur before `update_draft` and before proposal status mutation.
- `approve_and_publish_proposal` should not publish if `approve_proposal` raises conflict.
- Audit events should not record approve/publish success on conflict.

## Frontend Design

Files:

- `frontend/src/api/types.ts`
  - Add `TermRuleProposalConflictType`。
  - Add `TermRuleProposalConflictItemResponse`。
  - Add `TermRuleProposalConflictResponse`。
- `frontend/src/pages/TermProposalsPage.vue`
  - Extend `extractErrorDetailItems` or add `extractProposalConflictItems` to parse structured object conflicts.
  - Display conflict type/message and rule identifiers in the existing top conflict alert or selected proposal review panel.
  - Continue supporting string conflicts for Translation Term Proposal and older backend responses.
  - Keep existing local `snapshotConflict` warning as pre-check; do not treat it as authoritative.

UI copy:

- Use conflict message from backend first.
- Add concise context labels: proposal、target rule、source term、category。
- Do not add an approve override button.

## Documentation

Update `docs/api/term-rules.md`:

- Explain proposal vs direct governance boundary.
- Document structured `409` response for approve and approve-and-publish.
- State conflict leaves proposal `pending_review` and does not mutate draft.
- State no auto rebase / no bulk approve.

Update `docs/api/openapi.json` via existing OpenAPI export test flow.

## Tests

Backend tests in `tests/test_fastapi_jobs_backend.py`:

- Stale update approve returns structured `409` and leaves proposal `pending_review`。
- Missing target rule approve returns structured `409`。
- Create proposal same source term different segments returns structured `409`。
- approve-and-publish conflict returns structured `409` and does not publish.
- Draft snapshot/rule set is unchanged after conflict.
- Existing approve success, approve-and-publish success, reject path continue passing.

Frontend validation:

- `cd frontend && npm run build`
- Manual smoke optional if implementation touches review panel layout.

OpenAPI:

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`

## Rollback

Backend rollback:

- Revert `TermRuleProposalConflictError` payload change, router `409` detail mapping, and conflict schemas.
- Existing free-text `409` behavior can remain as compatibility fallback if needed.

Frontend rollback:

- Remove structured conflict rendering and types while retaining existing string detail display.

This rollback does not affect Child 1 draft CRUD, Child 2 diff/preflight, Child 3 governance UI, or `TermRuleWorkbenchPage` read-only behavior.
