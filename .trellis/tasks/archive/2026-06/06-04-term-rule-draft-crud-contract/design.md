# Term Rule Draft CRUD Contract Design

## Current State

`TermRuleSetVersionService` already stores draft and published versions as resource version payloads. Draft can be read through `GET /api/v1/term-rule-sets/{set_id}/draft` and replaced wholesale through `PUT /api/v1/term-rule-sets/{set_id}/draft/rules` with full v2 YAML.

The current production-safe write path is Term Rule Set draft. Legacy rule/category write endpoints under `/api/v1/term-rules` and `/api/v1/term-rule-categories` are guarded in MySQL versioned mode.

This task adds structured CRUD over the same draft store. It does not add a new persistence model.

## API Contract

### `GET /api/v1/term-rule-sets/{set_id}/draft/rules`

Purpose: list rules from the current draft.

Query params:

- `page`: default `1`, min `1`
- `page_size`: default `20`, max `200`
- `category_id`: optional
- `enabled`: optional boolean
- `q`: optional keyword matched against `source_term`

Response: reuse `TermRuleListResponse`.

### `GET /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`

Purpose: get one rule from draft.

Response: reuse `TermRuleResponse`.

### `POST /api/v1/term-rule-sets/{set_id}/draft/rules`

Purpose: create one rule inside draft.

Request: reuse or mirror `TermRuleCreateRequest`.

Response:

- Prefer `TermRuleDraftRuleMutationResponse`
  - `rule`: `TermRuleResponse`
  - `draft`: `TermRuleSetDraftResponse`

Rationale: frontend needs both the changed rule and the new `snapshot_hash`.

### `PATCH /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`

Purpose: update one rule inside draft.

Request: reuse `TermRuleUpdateRequest`.

Response: same mutation response shape.

### `DELETE /api/v1/term-rule-sets/{set_id}/draft/rules/{rule_id}`

Purpose: remove one rule from draft.

Response:

- `id`
- `removed: true`
- `draft`: `TermRuleSetDraftResponse`

## Service Design

Add methods to `TermRuleSetVersionService` rather than mutating `TermRuleService`, because draft CRUD must work on resource version draft payload:

- `list_draft_rules(set_id, category_id, enabled, q, page, page_size)`
- `get_draft_rule(set_id, rule_id)`
- `create_draft_rule(set_id, payload)`
- `update_draft_rule(set_id, rule_id, fields)`
- `delete_draft_rule(set_id, rule_id)`

Implementation pattern:

1. Load draft store via `get_draft_store(set_id)`.
2. Validate or mutate `TermRulesStore`.
3. Write updated store through `update_draft(set_id, store)`.
4. Return serialized rule and draft metadata.

The service should keep helper functions local and explicit:

- find category
- find rule
- ensure unique `source_term`
- parse segments
- normalize optional text
- render markdown/html from segments when needed
- sort/list rules consistently

Avoid using `TermRuleService.create_rule/update_rule/delete_rule`, because those methods save live store and refresh runtime YAML.

## Validation Rules

- `set_id` must still pass existing `_require_known_set_id`; only `electronics-default` is supported.
- `source_term` is required and unique inside draft.
- `category_id` must exist in draft categories.
- `segments` must be non-empty.
- Each segment requires non-empty `segment_text` and valid `render_type`.
- `apply_scope` must be one of the existing `RuleApplyScope` values.
- `enabled` defaults to `true`.
- `priority` should be parsed as int and preserve current model defaults.
- Empty `custom_html/custom_markdown` should normalize to `None` when consistent with existing code.

## Runtime Semantics

Draft CRUD must not call:

- `repository.save(store)` on the live term rule repository.
- runtime YAML write.
- `sync_live_store_then_set_default`.
- file sync.

Only publish/default/rollback may update live runtime store and runtime YAML.

## Error Semantics

Use existing `bad_request_http_exception` and `not_found_http_exception` where possible.

Recommended mapping:

- `503`: `runtime.term_rule_set_version_service is None`
- `403`: non-admin writes
- `404`: unknown set or rule not found
- `400`: invalid category, duplicate source term, invalid segment, invalid enum value

Structured conflict response is deferred, but messages should be deterministic enough for tests.

## Docs and OpenAPI

Update:

- `docs/api/term-rule-sets.md`
  - Add draft rule CRUD endpoints.
  - Add currently missing import/export endpoint docs.
- `docs/api/openapi.json`
  - Regenerate via existing OpenAPI export script.

## Compatibility

- Existing `PUT /draft/rules` remains supported.
- Existing `GET /api/v1/term-rules` remains live/default oriented and unchanged.
- Existing proposal approve still merges into draft through `TermRuleSetVersionService.update_draft`.
- Existing tests around publish/default/rollback should remain valid.

## Rollback

Rollback is endpoint-level:

- Remove new router methods and schema models.
- Remove new service methods.
- Revert docs/OpenAPI updates.
- Existing YAML draft update and publish flow continue to work.
