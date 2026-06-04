---
doc_type: lib-api-ref
entry: translation-term-sets
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/translation/sets_router.py
  - app/api/dependencies.py
  - app/domains/audit/models.py
  - app/domains/audit/service.py
  - app/domains/translation/term_set_version_service.py
  - app/domains/translation/repository.py
  - app/domains/translation/schemas.py
summary: Translation Term Sets API 在 MySQL resource service 下提供翻译术语 CSV 导入、导出和版本化默认集管理。
tags: [translation, terminology, resource-versioning, api, audit]
last_reviewed: 2026-06-04
---

# Translation Term Sets API

## 概述

`translation-term-sets` 统一挂在 `/api/v1/translation-term-sets` 下，用于查看翻译术语集、把翻译术语 CSV 导入 SQL draft/seed、从默认或历史版本导出 CSV，并管理 published version 的默认指针。

当前约束：

- 需要 `JOBS_REPOSITORY_BACKEND=mysql`，否则接口返回 `503`
- 第一版每个 `language_pair` 只有一个固定派生 set，例如 `translation-terms-en2zh`
- `translation_terms.csv` 是 seed、导入、导出和备份格式，不是 MySQL mode 运行时真源
- list/detail/draft/read 接口用于管理台展示；mutation 接口保持 admin-only
- 导入默认 `dedupe=reject`，重复 `normalized_source_term` 会拒绝
- admin 可显式使用 `dedupe=keep_first`，保留第一条并返回重复项报告
- CSV 字段或发布前校验失败时不会保存无效 draft
- 导出默认当前默认版本；admin 可传 `version` 导出历史版本
- 发布 draft 后清除 draft 指针；set-default 和 rollback 只切默认指针，不生成新版本
- 默认指针变化只影响后续使用默认配置的新 job；已创建 job 的 `resource_snapshot` 不会被改写
- import/export 成功后写 audit event

## API 参考

### `GET /api/v1/translation-term-sets`

- 用途：列出当前可管理的 Translation Term Set。
- 成功响应字段：

| 字段 | 说明 |
|---|---|
| `items[].set_id` | Translation Term Set ID |
| `items[].language_pair` | 语言方向 |
| `items[].default_version` | 当前默认 published version |
| `items[].draft_version` | 当前 draft 指针 |
| `items[].version_count` | published version 数量 |
| `items[].default_term_count` | 默认版本术语数 |
| `items[].draft_term_count` | draft 术语数 |
| `items[].snapshot_hash` | 默认版本 snapshot hash |

### `GET /api/v1/translation-term-sets/{set_id}`

- 用途：查看 set 默认指针、draft 指针和 published versions。
- 成功响应字段：

| 字段 | 说明 |
|---|---|
| `set_id` | Translation Term Set ID |
| `language_pair` | 语言方向 |
| `default_version` | 当前默认 published version |
| `draft_version` | 当前 draft 指针 |
| `versions[]` | published versions，不包含 draft |

`versions[]` 包含 `version`、`status`、`term_count`、`snapshot_hash`、`is_default`、`published_by`、`published_at`、`release_note`、`created_at` 和 `updated_at`。

### `GET /api/v1/translation-term-sets/{set_id}/draft`

- 用途：查看当前 draft entries 和发布前校验结果；没有 draft 时从默认版本复制生成。
- 成功响应字段：

| 字段 | 说明 |
|---|---|
| `set_id` | Translation Term Set ID |
| `language_pair` | 语言方向 |
| `version` | 固定为 `draft` |
| `base_version` | draft 基于的默认版本 |
| `term_count` | draft 术语数 |
| `snapshot_hash` | draft snapshot hash |
| `validation` | 发布前校验结果 |
| `entries[]` | draft 术语条目，只读展示 |

### `POST /api/v1/translation-term-sets/{set_id}/import`

- 用途：导入 Translation Term Set CSV 到 draft，或在缺少默认版本时做 seed 初始化。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `csv_text` | 无 | CSV 正文 |
| `target` | `draft` | `draft` 或 `seed` |
| `dedupe` | `reject` | `reject` 或 `keep_first` |

CSV 支持基础 seed 四列：

```csv
language_pair,source_term,target_term,version
en2zh,ADC,模数转换器,v1
```

也支持扩展列：

```csv
language_pair,source_term,target_term,version,case_sensitive,status,priority,domain,category,note
en2zh,FPGA,现场可编程门阵列,draft,false,active,5,electronics,chip,first
```

成功响应字段：

| 字段 | 说明 |
|---|---|
| `target` | 导入目标 |
| `set_id` | Translation Term Set ID |
| `language_pair` | 语言方向 |
| `version` | `draft` 或 seed 发布版本 |
| `term_count` | 导入后的术语数 |
| `snapshot_hash` | draft/seed 快照 hash |
| `validation` | 发布前校验结果 |
| `import_report` | 去重报告 |

`import_report.duplicates[]` 会列出被 `keep_first` 丢弃的重复行，包含 `row_number`、`kept_row_number`、`source_term` 和 `normalized_source_term`。

失败语义：

- `dedupe=reject` 发现重复 `normalized_source_term` 时返回 `400`，不会保存 draft。
- CSV 缺少必填列、字段为空、布尔/整数/status 字段非法，或 `language_pair` 与目标 set 不匹配时返回 `400`，不会保存 draft。
- `dedupe=keep_first` 成功时只导入第一条重复项，并通过 `import_report.duplicates[]` 告知被丢弃行，供前端展示和人工复核。

### `GET /api/v1/translation-term-sets/{set_id}/export`

- 用途：导出当前默认或指定历史版本为 CSV。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `version` | 当前默认版本 | 指定要导出的 published version |

成功响应：

```json
{
  "manifest": {
    "set_id": "translation-terms-en2zh",
    "language_pair": "en2zh",
    "version": "v1",
    "format": "csv",
    "exported_at": "2026-06-02T00:00:00Z",
    "exported_by": "admin"
  },
  "csv_text": "language_pair,source_term,target_term,version,..."
}
```

manifest 作为旁路元信息返回，不写入 CSV 正文，避免破坏现有 CSV 读取器。

### `POST /api/v1/translation-term-sets/{set_id}/publish`

- 用途：发布当前 draft。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `make_default` | `true` | 发布后是否设为默认版本 |
| `release_note` | `null` | 发布说明 |

成功响应为单个 `TranslationTermSetVersionResponse`。

### `POST /api/v1/translation-term-sets/{set_id}/versions/{version}/set-default`

- 用途：把指定 published version 设为默认版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 成功响应为单个 `TranslationTermSetVersionResponse`。
- 语义边界：只更新 Translation Term Set 默认指针；不修改、删除或重写任何 published version，也不改变已创建 job 的 `resource_snapshot.translation_term_set`。

### `POST /api/v1/translation-term-sets/{set_id}/rollback`

- 用途：rollback 默认指针到指定 published version；不生成新版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：

| 字段 | 说明 |
|---|---|
| `version` | 要回滚到的 published version |

成功响应为单个 `TranslationTermSetVersionResponse`。

rollback 是运维语义更强的 set-default：它只把默认指针切回指定 published version，不生成补丁版本，不归档历史版本，不删除 CSV 或条目，也不改变已创建 job 的 `resource_snapshot.translation_term_set`。

## 常见状态

- `400`：CSV 字段缺失、字段值非法、重复项未显式去重、`set_id` 与 `language_pair` 不匹配、seed 初始化条件不满足，或 set-default/rollback 指向非 published 版本
- `403`：admin-only 接口缺少或未通过 Bearer admin JWT / legacy `X-Admin-Token`
- `404`：Translation Term Set 或指定版本不存在
- `503`：未启用 MySQL resource service

## 相关条目

- [translation-term-proposals.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-term-proposals.md)
- [translation-profiles.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-profiles.md)
- [jobs.md](/Users/sc/PycharmProjects/md2word/docs/api/jobs.md)
