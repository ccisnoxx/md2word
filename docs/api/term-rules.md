---
doc_type: lib-api-ref
entry: term-rules
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/term_rules/router.py
  - app/domains/term_rules/proposals_router.py
  - app/domains/term_rules/proposals_service.py
  - app/domains/term_rules/write_guard.py
  - app/domains/term_rules/service.py
  - app/domains/term_rules/import_validation.py
  - app/domains/term_rules/sync_files.py
  - app/domains/term_rules/yaml_codec.py
  - app/domains/term_rules/file_repository.py
  - app/domains/term_rules/schemas.py
summary: Term-rules API 以 v2 manifest 为版本化 seed，以 live runtime store 为可变真源，并在 MySQL versioned mode 下把写入交给 Term Rule Set 发布流程。
tags: [term-rules, api, runtime-store]
last_reviewed: 2026-06-04
---

## 概述

当前 `term-rules` 统一挂在 `/api/v1/term-rules` 下，职责分三层：

- 版本化 seed：`resources/term_rules/term_rules.v2.yaml`
- live runtime store：`var/config/term_rules_store.json`
- conversion 兼容 runtime YAML：`var/config/runtime_subscripts_dictionary.yaml`

运行约定：

- `import` 会整体替换 live runtime store
- rule CRUD 会增量修改 live runtime store
- `sync-files` 会把当前 live truth 回写到 seed 与 runtime YAML
- conversion 仍然只消费 runtime YAML，不直接读取 seed
- 每次 import 或增量写入成功后都会刷新 runtime YAML
- 当 MySQL resource service 启用 Term Rule Set versioning 时，legacy 写接口会返回 `400`，调用方应改用 `/api/v1/term-rule-sets/{set_id}/draft/rules` 更新草稿并发布

## API 参考

### `GET /api/v1/term-rules`

- 用途：分页查询规则。
- 查询参数：
  - `page`
  - `page_size`
  - `category_id`
  - `enabled`
  - `q`

### `GET /api/v1/term-rules/{rule_id}`

- 用途：查询单条规则详情。

### `POST /api/v1/term-rules`

- 用途：新增单条规则。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体关键字段：
  - `id`：可选；不传时自动生成
  - `category_id`
  - `source_term`
  - `segments[]`
  - `apply_scope`
  - `case_sensitive`
  - `enabled`
  - `priority`
  - `custom_html`
  - `custom_markdown`
  - `notes`
- 成功后会刷新 `var/config/runtime_subscripts_dictionary.yaml`。
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

### `PATCH /api/v1/term-rules/{rule_id}`

- 用途：更新单条规则。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体为上述字段的任意子集。
- 若替换 `segments` 且未显式传 `custom_html/custom_markdown`，服务会按 segments 重新生成渲染内容。
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

### `DELETE /api/v1/term-rules/{rule_id}`

- 用途：删除单条规则。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 成功后会刷新 runtime YAML。
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

### `GET /api/v1/term-rules/export`

- 用途：导出当前 live store 的规范化 v2 YAML。
- 返回：`yaml_text`

### `POST /api/v1/term-rules/simulate`

- 用途：对输入文本执行规则模拟。
- 请求体：
  - `text`
- 返回：
  - `original`
  - `markdown_preview`
  - `html_preview`

### `POST /api/v1/term-rules/import/validate`

- 用途：导入前校验 v2 YAML。
- 请求体：
  - `yaml_text`
- 返回：
  - `valid`
  - `summary`
  - `errors`
  - `warnings`

### `POST /api/v1/term-rules/import`

- 用途：把校验通过的规则集整体替换为新的 live runtime truth。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：
  - `yaml_text`
- 关键语义：
  - 不做增量 merge
  - 成功后会同步刷新 runtime YAML
  - MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish

### `POST /api/v1/term-rules/sync-files`

- 用途：把当前 live truth 回写到版本化 seed，并同时刷新 runtime YAML。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 返回：
  - `repository_backend`
  - `category_count`
  - `rule_count`
  - `bootstrap_seed_path`
  - `runtime_yaml_path`
  - `warnings`
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

## Term Rule Proposal API

`/api/v1/term-rule-proposals` 用于 V2.1 术语建议审核流。该能力需要 MySQL resource service；未启用时返回 `503`。

治理边界：

- Proposal 是 operator 提交的变更建议，不是直接写入入口。
- Admin 直接治理入口是 `/api/v1/term-rule-sets/{set_id}/draft/rules` 和后续 publish/preflight 流程。
- `approve` 只在 proposal 保存的目标规则快照仍匹配当前 draft 时合并；若 draft 已经被 Admin 直接治理或其他 proposal 改动，则返回结构化 `409`。
- 后端不自动 rebase、不 force approve、不批量审核冲突 proposal。
- 冲突发生时 proposal 保持 `pending_review`，draft 不被审核侧修改，`approve-and-publish` 不会执行 publish。

### `POST /api/v1/term-rule-proposals`

- 用途：operator/admin 提交术语变更建议。
- 认证：Bearer JWT。
- 请求体字段：
  - `intent`：`create`、`update` 或 `disable`
  - `source_term`：`create/update` 必填
  - `category_id`：`create/update` 必填，提交分类 ID
  - `segments[]`：`create/update` 必填；每段支持 `plain`、`subscript`、`superscript`
  - `reason`：必填
  - `target_rule_id`：`update/disable` 必填
  - `source_job_id`、`source_file_id`：可选来源线索
- 关键语义：
  - `update/disable` 会保存 `target_rule_snapshot`
  - `disable` 会从目标规则继承 `source_term`、`category_id` 和 `segments`

### `GET /api/v1/term-rule-proposals`

- 用途：查询 proposal 列表。
- 认证：Bearer JWT。
- 查询参数：
  - `scope=my`：默认，仅返回当前用户提交的 proposals
  - `scope=all`：admin-only，返回全部
  - `scope=pending_review`：admin-only，返回待审核队列
  - `scope=approved_unpublished`：admin-only，返回已 approve 但尚未随 Term Rule Set 发布的 proposals
  - `status`：可选状态过滤，支持 `pending_review`、`approved`、`rejected`

### `GET /api/v1/term-rule-proposals/{proposal_id}`

- 用途：查看单条 proposal。
- 认证：Bearer JWT。
- 权限：operator 只能查看自己提交的 proposal；admin 可查看全部。

### `POST /api/v1/term-rule-proposals/{proposal_id}/approve`

- 用途：admin 审核通过并原子合并到 Term Rule Set draft。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `review_comment`：可选
- 冲突语义：
  - `update/disable` 的当前规则与 `target_rule_snapshot` 不一致时返回结构化 `409`
  - `update/disable` 的目标规则已从 draft 消失时返回结构化 `409`
  - `create` 遇到同名 `source_term` 但 segments 不一致时返回结构化 `409`
  - 冲突时 proposal 保持 `pending_review`，后端不自动 rebase

### `POST /api/v1/term-rule-proposals/bulk-approve`

- 用途：admin 批量审核通过 proposals。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `proposal_ids`：必填数组，最多 50 条，不允许空值或重复项
  - `review_comment`：可选，共享审核备注
- 关键语义：
  - 逐条复用单条 `approve` 语义，不提供 bulk `approve-and-publish`
  - 响应整体为 `200`，单条失败写入 `items[].ok=false`
  - 单条冲突不会阻断后续 proposal，失败项保持原状态
  - 结构化冲突保留在 `items[].detail`，`error_code=term_rule_proposal_conflict`

### `POST /api/v1/term-rule-proposals/bulk-reject`

- 用途：admin 批量拒绝 proposals。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `proposal_ids`：必填数组，最多 50 条，不允许空值或重复项
  - `review_comment`：必填，共享拒绝原因
- 关键语义：
  - 逐条复用单条 `reject` 语义
  - 响应整体为 `200`，单条失败写入 `items[].ok=false`
  - 已非 `pending_review` 的 proposal 不会被二次覆盖

### `POST /api/v1/term-rule-proposals/{proposal_id}/approve-and-publish`

- 用途：admin 审核通过、合并 draft、发布新的 Term Rule Set 版本并设为默认版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `review_comment`：可选
  - `publish_reason`：可选；为空时后端使用 proposal ID 和 source term 生成默认发布原因
- 关键语义：
  - 仍然走 Term Rule Set draft/publish/default 流程，不直接修改 live 规则
  - 发布成功后刷新 conversion runtime YAML，并回填 `published_term_rule_set_version`
  - approve 阶段返回结构化 `409` 时，不创建发布版本、不刷新默认版本、不回填 published 字段

### `POST /api/v1/term-rule-proposals/{proposal_id}/reject`

- 用途：admin 拒绝 proposal。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `review_comment`：必填拒绝原因

### `TermRuleProposalResponse` 关键字段

| 字段 | 说明 |
|---|---|
| `id` | proposal ID |
| `intent` | `create` / `update` / `disable` |
| `status` | `pending_review` / `approved` / `rejected` |
| `target_rule_id` | update/disable 目标规则 |
| `target_rule_snapshot` | 提交时的目标规则快照 |
| `merged_term_rule_set_id` | approve 后合入的规则集 |
| `merged_draft_snapshot_hash` | approve 后 draft snapshot hash |
| `published_term_rule_set_version` | 随 Term Rule Set publish 后关联的版本号 |

### `TermRuleProposalBulkResponse` 关键字段

| 字段 | 说明 |
|---|---|
| `action` | `approve` / `reject` |
| `total` | 请求处理的 proposal 数量 |
| `succeeded` | 成功条数 |
| `failed` | 失败条数 |
| `items[].proposal_id` | 单条 proposal ID |
| `items[].ok` | 单条是否成功 |
| `items[].status_code` | 单条语义状态码，成功为 `200` |
| `items[].error_code` | 单条失败错误码 |
| `items[].detail` | 单条失败详情；冲突时为结构化 `TermRuleProposalConflictResponse` |
| `items[].proposal` | 单条成功后的 `TermRuleProposalResponse` |

### `TermRuleProposalConflictResponse`

`approve` 和 `approve-and-publish` 遇到人工冲突时返回 `409`，`detail` 使用稳定结构：

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
        "source_term": "VNEW",
        "category_id": "voltage_terms",
        "current_rule": {
          "id": "rule_xxx",
          "source_term": "VOLD"
        },
        "target_rule_snapshot": {
          "id": "rule_xxx",
          "source_term": "VOLD"
        },
        "metadata": {}
      }
    ]
  }
}
```

`conflicts[]` 字段：

| 字段 | 说明 |
|---|---|
| `type` | `stale_target_rule` / `missing_target_rule` / `source_term_segments_conflict` |
| `message` | 后端生成的人工处理说明 |
| `proposal_id` | 当前 proposal ID |
| `target_rule_id` | 相关目标规则；`missing_target_rule` 时为 proposal 保存的目标 ID |
| `source_term` | proposal 中的 source term |
| `category_id` | proposal 中的分类 ID |
| `current_rule` | 当前 draft 中的规则；目标已不存在时为 `null` |
| `target_rule_snapshot` | proposal 创建时保存的目标规则快照；create proposal 可为 `null` |
| `metadata` | 冲突补充信息，例如 existing/proposed segments |

## 当前限制

- 当前 import 面向 v2 manifest，不再把 legacy `subscript_rules` YAML 当作者真源。
- `source_term` 在 live store 内保持全局唯一。
- MySQL versioned mode 下，legacy 写接口只保留 file/sqlite 兼容用途；生产术语变更应走 [term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md)。
- MySQL mode 会把当前 term rule seed/runtime 投影到 `term_rule_categories`、`term_rules`、`term_rule_segments` 明细表；发布版本仍以 Term Rule Set 版本流程为准。
