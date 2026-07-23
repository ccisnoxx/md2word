---
doc_type: lib-api-ref
entry: translation-profiles
category: endpoint
status: current
source_files:
  - app/api/v1/router.py
  - app/domains/translation/router.py
  - app/api/dependencies.py
  - app/domains/audit/models.py
  - app/domains/audit/service.py
  - app/domains/translation/profiles_service.py
  - app/domains/resources/service.py
  - app/domains/translation/schemas.py
summary: Translation Profiles API 在 MySQL resource service 下提供翻译配置与命名 Prompt 的草稿编辑、发布、默认切换、回滚和成功动作审计。
tags: [translation, resource-versioning, api, audit]
last_reviewed: 2026-07-23
---

## 概述

`translation-profiles` 统一挂在 `/api/v1/translation-profiles` 下，用于管理翻译配置、内嵌命名 Prompt、发布版本、默认指针和回滚。

当前约束：

- 需要 `JOBS_REPOSITORY_BACKEND=mysql`，否则接口返回 `503`
- 支持 `electronics-en2zh`、`electronics-ru2zh`、`electronics-zh2en`、`electronics-zh2ru`
- profile payload 保存命名 Prompt 的 Markdown 正文，但不保存 `OPENAI_API_KEY` 或 secret header
- 每个 profile 版本可包含多个 Prompt，`prompt_version` 是唯一当前 Prompt ID 指针
- MySQL resource mode 下，翻译 job 创建时绑定默认或显式选择的 published profile，并在安全任务快照中记录 Prompt ID/hash；Prompt 正文不进入对外 job response
- file / sqlite legacy backend 下，未显式选择 profile 的翻译 job 继续使用固定 Prompt 文件和 settings / `.env`
- publish / set-default / rollback 成功后会写 audit event

## API 参考

### `GET /api/v1/translation-profiles`

- 用途：列出当前支持的 Translation Profile。
- 认证：内部用户 Bearer JWT；兼容 legacy `X-Admin-Token`。
- 响应：`items[]`，包含默认版本、版本数和当前有效配置摘要。

### `GET /api/v1/translation-profiles/{profile_id}`

- 用途：查看 profile 的默认版本和 published versions。
- 认证：内部用户 Bearer JWT；兼容 legacy `X-Admin-Token`。
- 响应只包含当前 Prompt ID 和正文 hash，不返回已发布 Prompt Markdown。

### `GET /api/v1/translation-profiles/{profile_id}/draft`

- 用途：查看当前 draft。
- 认证：内部用户 Bearer JWT；兼容 legacy `X-Admin-Token`。
- 当前行为：
  - 已有 draft 时直接返回 draft
  - 没有 draft 且已有默认 published 版本时，从默认版本派生 draft
  - 没有默认 published 版本时，从 settings 默认值派生 draft
  - `prompt_schemes[]` 返回当前草稿的 Prompt ID、名称、Markdown、hash、内置/启用/可删除状态

### `PUT /api/v1/translation-profiles/{profile_id}/draft`

- 用途：更新完整 Translation Profile draft。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `target_language`
  - `domain`
  - `model`
  - `max_pages_per_batch`
  - `max_chars_per_batch`
  - `expected_snapshot_hash`
- 关键语义：只更新基础字段并保留 Prompt 列表和当前指针；不改 jobs payload，不写 secret。

### Prompt 草稿操作

| 方法与路径 | 用途 |
|---|---|
| `POST /{profile_id}/draft/prompts` | 按 `source_prompt_id` 复制正文并创建命名 Prompt。 |
| `PUT /{profile_id}/draft/prompts/{prompt_id}` | 保存名称和 Markdown 正文。 |
| `POST /{profile_id}/draft/prompts/{prompt_id}/activate` | 将该 Prompt 设为草稿当前方案。 |
| `DELETE /{profile_id}/draft/prompts/{prompt_id}` | 物理删除符合受控删除条件的草稿 Prompt。 |

- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`。
- 所有请求必须携带当前 draft 的 `expected_snapshot_hash`；过期写入返回 `409 draft_snapshot_conflict`。
- 新建 Prompt 默认复制指定 Prompt 正文，ID 由服务端生成，名称在单个 profile 内唯一。
- 内置、当前启用或曾随任一 published/superseded/disabled profile 版本保存的 Prompt 不可删除。
- Prompt 操作只修改草稿；只有发布并设默认后才影响后续新任务，既有 published 版本和历史任务不变。
- audit 只记录 profile/Prompt ID、正文 hash 和字符数，不记录 Markdown。

### `POST /api/v1/translation-profiles/{profile_id}/publish`

- 用途：把当前 draft 发布为新的 immutable published version。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体字段：
  - `make_default`：是否发布后设为默认，默认 `true`
- 版本号格式：`YYYY.MM.DD-N`
- 审计：成功后写 `translation_profile.publish`，`target_id={profile_id}@{version}`。

### `POST /api/v1/translation-profiles/{profile_id}/versions/{version}/set-default`

- 用途：把指定 published version 设为默认版本。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：无
- 审计：成功后写 `translation_profile.set_default`，`target_id={profile_id}@{version}`。
- 关键语义：只能指向 published version，`version=draft` 会返回 `400`。

### `POST /api/v1/translation-profiles/{profile_id}/rollback`

- 用途：把默认指针切回指定 published version。
- 认证：Bearer admin JWT；兼容 legacy `X-Admin-Token`
- 请求体：
  - `version`
- 审计：成功后写 `translation_profile.rollback`，`target_id={profile_id}@{version}`。
- 关键语义：rollback 只切默认指针，不修改任何历史 published payload。

## Document Jobs 绑定边界

`POST /api/v1/document-jobs` 可在四种翻译模式下传：

- `translation_profile_id`
- `translation_profile_version`

MySQL resource mode 下，不传时按语言方向绑定当前默认 published profile；显式传版本时绑定指定 published version。`mode=direct_pdf_to_word` 不能传 Translation Profile。file / sqlite backend 下显式传 profile selection 会返回 `503`。

## 常见状态

- `400`：payload 无效、版本状态不允许，或尝试把 draft 设为默认
- `409`：Prompt 草稿写入使用了过期 `snapshot_hash`
- `403`：admin-only 写接口缺少或未通过 Bearer admin JWT / legacy `X-Admin-Token`
- `404`：profile 不存在，或目标版本不存在
- `503`：未启用 MySQL resource service

## 相关条目

- [translation-profile-and-segment-trace-guide.md](/Users/sc/PycharmProjects/md2word/docs/dev/translation-profile-and-segment-trace-guide.md)
- [jobs.md](/Users/sc/PycharmProjects/md2word/docs/api/jobs.md)
- [term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md)
