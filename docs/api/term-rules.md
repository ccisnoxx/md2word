---
doc_type: lib-api-ref
entry: term-rules
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/api/v1/routers/term_rules.py
  - app/services/term_rules/service.py
  - app/services/term_rules/import_validation.py
  - app/services/term_rules/sync_files.py
  - app/services/term_rules/yaml_codec.py
  - app/repositories/file_term_rule_repository.py
  - app/schemas/api_v1.py
summary: Term-rules API 以 v2 manifest 为版本化 seed，以 live runtime store 为可变真源，并向 conversion 导出兼容 runtime YAML。
tags: [term-rules, api, runtime-store]
last_reviewed: 2026-05-18
---

## 概述

当前 `term-rules` 统一挂在 `/api/v1/term-rules` 下，职责分三层：

- 版本化 seed：`template_configs/term_rules.v2.yaml`
- live runtime store：`data/config/term_rules_store.json`
- conversion 兼容 runtime YAML：`data/config/runtime_subscripts_dictionary.yaml`

运行约定：

- `import` 会整体替换 live runtime store
- `sync-files` 会把当前 live truth 回写到 seed 与 runtime YAML
- conversion 仍然只消费 runtime YAML，不直接读取 seed

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

## 当前限制

- 暂不提供 rule CRUD。
- 暂不提供 category 写接口。
- 当前 import 面向 v2 manifest，不再把 legacy `subscript_rules` YAML 当作者真源。
