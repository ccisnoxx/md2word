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
last_reviewed: 2026-06-02
---

# Translation Term Sets API

## 概述

`translation-term-sets` 统一挂在 `/api/v1/translation-term-sets` 下，用于把翻译术语 CSV 导入 SQL draft/seed，并从默认或历史版本导出 CSV。

当前约束：

- 需要 `JOBS_REPOSITORY_BACKEND=mysql`，否则接口返回 `503`
- 第一版每个 `language_pair` 只有一个固定派生 set，例如 `translation-terms-en2zh`
- `translation_terms.csv` 是 seed、导入、导出和备份格式，不是 MySQL mode 运行时真源
- 导入默认 `dedupe=reject`，重复 `normalized_source_term` 会拒绝
- admin 可显式使用 `dedupe=keep_first`，保留第一条并返回重复项报告
- 导出默认当前默认版本；admin 可传 `version` 导出历史版本
- import/export 成功后写 audit event

## API 参考

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

## 常见状态

- `400`：CSV 字段缺失、字段值非法、重复项未显式去重、`set_id` 与 `language_pair` 不匹配，或 seed 初始化条件不满足
- `403`：admin-only 接口缺少或未通过 Bearer admin JWT / legacy `X-Admin-Token`
- `404`：Translation Term Set 或指定版本不存在
- `503`：未启用 MySQL resource service

## 相关条目

- [translation-term-proposals.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-term-proposals.md)
- [translation-profiles.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-profiles.md)
- [jobs.md](/Users/sc/PycharmProjects/md2word/docs/api/jobs.md)
