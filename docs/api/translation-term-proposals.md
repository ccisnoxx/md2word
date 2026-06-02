---
doc_type: lib-api-ref
entry: translation-term-proposals
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/translation/proposals_router.py
  - app/api/dependencies.py
  - app/domains/audit/models.py
  - app/domains/audit/service.py
  - app/domains/translation/proposals_service.py
  - app/domains/translation/term_set_version_service.py
  - app/domains/translation/repository.py
  - app/domains/translation/schemas.py
summary: Translation Term Proposals API 提供 operator 翻译术语建议提交、admin 审核、拒绝和一键审核发布。
tags: [translation, terminology, proposal, api, audit]
last_reviewed: 2026-06-02
---

# Translation Term Proposals API

## 概述

`translation-term-proposals` 统一挂在 `/api/v1/translation-term-proposals` 下，用于从 job 结果提交翻译术语建议，并由 admin 审核合入 Translation Term Set draft 或一键发布为默认版本。

当前约束：

- 需要 `JOBS_REPOSITORY_BACKEND=mysql`，否则接口返回 `503`
- operator 只能创建 proposal 和查看自己提交的 proposal
- admin 可查看全部、审核、拒绝和 approve-and-publish
- proposal 支持批量 `add`、`update`、`delete` changes
- proposal 记录来源 `source_job_id/source_file_id` 和 observed Translation Term Set version
- approve 时合入当前 draft；approve-and-publish 合入后发布并设为默认版本
- 与当前 draft 冲突时返回 `409`，不做 last-write-wins
- 成功 create/approve/reject/approve-and-publish 会写 audit event

## API 参考

### `POST /api/v1/translation-term-proposals`

- 用途：创建 pending 翻译术语 proposal。
- 认证：Bearer JWT；operator 和 admin 都可提交。
- 请求体字段：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `language_pair` | `en2zh` | 语言方向 |
| `source_job_id` | `null` | 来源 job ID |
| `source_file_id` | `null` | 来源 file ID |
| `observed_translation_term_set_id` | 当前语言方向默认 set | job 当时绑定的 set |
| `observed_translation_term_version` | 当前默认版本 | job 当时绑定的 version |
| `changes` | 无 | 一条或多条术语变更 |

`changes[]` 字段：

| 字段 | 说明 |
|---|---|
| `action` | `add`、`update` 或 `delete` |
| `source_term` | 原文术语 |
| `target_term` | 目标译文；`add/update` 需要 |
| `case_sensitive` | 是否大小写敏感 |
| `status` | `active` 或 `disabled` |
| `priority` | 同长度命中时的优先级 |
| `domain` / `category` | 元数据 |
| `note` | 审核说明或维护备注 |

### `GET /api/v1/translation-term-proposals`

- 用途：查询 proposal 列表。
- 认证：Bearer JWT。
- 查询参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `scope` | `my` | `my`、`pending` 或 `all`；非 admin 只能用 `my` |
| `status` | 无 | `pending`、`approved`、`rejected`、`published` |

### `GET /api/v1/translation-term-proposals/{proposal_id}`

- 用途：查看单条 proposal。
- 权限：operator 只能查看自己提交的 proposal；admin 可查看全部。

### `POST /api/v1/translation-term-proposals/{proposal_id}/approve`

- 用途：admin 审核通过 proposal，并把 changes 合入当前 draft。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `review_note`：可选审核备注
- 冲突：返回 `409`，`detail.code=translation_term_proposal_conflict`，`detail.conflicts[]` 描述冲突原因。

### `POST /api/v1/translation-term-proposals/{proposal_id}/approve-and-publish`

- 用途：admin 审核通过 proposal，发布当前 draft，并把新版本设为默认版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `review_note`：可选审核备注
  - `release_note`：可选发布说明
- 成功后 proposal 状态为 `published`，并回填 `published_translation_term_set_id/version` 和 `published_at`。

### `POST /api/v1/translation-term-proposals/{proposal_id}/reject`

- 用途：admin 拒绝 proposal。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `review_note`：必填拒绝原因

## 响应模型

`TranslationTermProposalResponse` 核心字段：

| 字段 | 说明 |
|---|---|
| `id` | proposal ID |
| `status` | `pending`、`approved`、`rejected` 或 `published` |
| `submitted_by` | 提交人 |
| `source_job_id/source_file_id` | 来源证据 |
| `observed_translation_term_set_id/version` | 来源 job 绑定版本 |
| `reviewed_by/reviewed_at/review_note` | 审核信息 |
| `published_translation_term_set_id/version` | 发布结果 |
| `changes[]` | 本次 proposal 的变更项 |

## 常见状态

- `400`：payload 无效、action 不支持、proposal 状态不可审核、缺少拒绝原因，或发布校验失败
- `403`：当前角色无权限查看、审核或发布
- `404`：proposal 或 Translation Term Set 不存在
- `409`：proposal 与当前 draft 冲突
- `503`：未启用 MySQL resource service

## 相关条目

- [translation-term-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-term-sets.md)
- [jobs.md](/Users/sc/PycharmProjects/md2word/docs/api/jobs.md)
- [term-rules.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rules.md)
