---
doc_type: lib-api-ref
entry: term-rules
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/term_rules/router.py
  - app/domains/term_rules/write_guard.py
  - app/domains/term_rules/service.py
  - app/domains/term_rules/import_validation.py
  - app/domains/term_rules/sync_files.py
  - app/domains/term_rules/yaml_codec.py
  - app/domains/term_rules/file_repository.py
  - app/domains/term_rules/schemas.py
summary: Term-rules API 以 v2 manifest 为版本化 seed，以 live runtime store 为可变真源，并在 MySQL versioned mode 下把写入交给 Term Rule Set 发布流程。
tags: [term-rules, api, runtime-store]
last_reviewed: 2026-05-31
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
- 认证：`X-Admin-Token`
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
- 认证：`X-Admin-Token`
- 请求体为上述字段的任意子集。
- 若替换 `segments` 且未显式传 `custom_html/custom_markdown`，服务会按 segments 重新生成渲染内容。
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

### `DELETE /api/v1/term-rules/{rule_id}`

- 用途：删除单条规则。
- 认证：`X-Admin-Token`
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
- 认证：`X-Admin-Token`
- 请求体：
  - `yaml_text`
- 关键语义：
  - 不做增量 merge
  - 成功后会同步刷新 runtime YAML
  - MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish

### `POST /api/v1/term-rules/sync-files`

- 用途：把当前 live truth 回写到版本化 seed，并同时刷新 runtime YAML。
- 认证：`X-Admin-Token`
- 返回：
  - `repository_backend`
  - `category_count`
  - `rule_count`
  - `bootstrap_seed_path`
  - `runtime_yaml_path`
  - `warnings`
- MySQL versioned mode 下返回 `400`，避免绕过 Term Rule Set draft / publish。

## 当前限制

- 当前 import 面向 v2 manifest，不再把 legacy `subscript_rules` YAML 当作者真源。
- `source_term` 在 live store 内保持全局唯一。
- MySQL versioned mode 下，legacy 写接口只保留 file/sqlite 兼容用途；生产术语变更应走 [term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md)。
