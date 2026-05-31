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
summary: Translation Profiles API 在 MySQL resource service 下提供翻译配置 draft、publish、set-default、rollback 和成功动作审计。
tags: [translation, resource-versioning, api, audit]
last_reviewed: 2026-05-31
---

## 概述

`translation-profiles` 统一挂在 `/api/v1/translation-profiles` 下，用于管理翻译配置的草稿、发布版本、默认指针和回滚。

当前约束：

- 需要 `JOBS_REPOSITORY_BACKEND=mysql`，否则接口返回 `503`
- MVP 只支持默认 profile `electronics-en2zh`
- profile payload 不保存 `OPENAI_API_KEY`、secret header 或完整 prompt 文本
- MySQL resource mode 下，`translation_mode=en2zh` job 创建时绑定默认或显式选择的 published profile 快照
- file / sqlite legacy backend 下，未显式选择 profile 的 `en2zh` job 继续使用 settings / `.env`
- publish / set-default / rollback 成功后会写 audit event

## API 参考

### `GET /api/v1/translation-profiles`

- 用途：列出当前支持的 Translation Profile。
- 响应：`items[]`，包含默认版本、版本数和当前有效配置摘要。

### `GET /api/v1/translation-profiles/{profile_id}`

- 用途：查看 profile 的默认版本和 published versions。
- 当前支持：`profile_id=electronics-en2zh`

### `GET /api/v1/translation-profiles/{profile_id}/draft`

- 用途：查看当前 draft。
- 当前行为：
  - 已有 draft 时直接返回 draft
  - 没有 draft 且已有默认 published 版本时，从默认版本派生 draft
  - 没有默认 published 版本时，从 settings 默认值派生 draft

### `PUT /api/v1/translation-profiles/{profile_id}/draft`

- 用途：更新完整 Translation Profile draft。
- 认证：`X-Admin-Token`
- 请求体字段：
  - `target_language`
  - `domain`
  - `prompt_version`
  - `model`
  - `max_pages_per_batch`
  - `max_chars_per_batch`
- 关键语义：只更新 `translation_profile` resource draft，不改 jobs payload，不写 secret。

### `POST /api/v1/translation-profiles/{profile_id}/publish`

- 用途：把当前 draft 发布为新的 immutable published version。
- 认证：`X-Admin-Token`
- 请求体字段：
  - `make_default`：是否发布后设为默认，默认 `true`
- 版本号格式：`YYYY.MM.DD-N`
- 审计：成功后写 `translation_profile.publish`，`target_id={profile_id}@{version}`。

### `POST /api/v1/translation-profiles/{profile_id}/versions/{version}/set-default`

- 用途：把指定 published version 设为默认版本。
- 认证：`X-Admin-Token`
- 请求体：无
- 审计：成功后写 `translation_profile.set_default`，`target_id={profile_id}@{version}`。
- 关键语义：只能指向 published version，`version=draft` 会返回 `400`。

### `POST /api/v1/translation-profiles/{profile_id}/rollback`

- 用途：把默认指针切回指定 published version。
- 认证：`X-Admin-Token`
- 请求体：
  - `version`
- 审计：成功后写 `translation_profile.rollback`，`target_id={profile_id}@{version}`。
- 关键语义：rollback 只切默认指针，不修改任何历史 published payload。

## Jobs 绑定边界

`POST /api/v1/jobs` 和 `POST /api/v1/jobs/pdf` 可在 `translation_mode=en2zh` 时传：

- `translation_profile_id`
- `translation_profile_version`

MySQL resource mode 下，不传时绑定当前默认 published profile；显式传版本时绑定指定 published version。`translation_mode=direct` 不能传 Translation Profile。file / sqlite backend 下显式传 profile selection 会返回 `503`。

## 常见状态

- `400`：payload 无效、版本状态不允许，或尝试把 draft 设为默认
- `403`：admin-only 写接口缺少或未通过 `X-Admin-Token`
- `404`：profile 不存在，或目标版本不存在
- `503`：未启用 MySQL resource service

## 相关条目

- [translation-profile-and-segment-trace-guide.md](/Users/sc/PycharmProjects/md2word/docs/dev/translation-profile-and-segment-trace-guide.md)
- [jobs.md](/Users/sc/PycharmProjects/md2word/docs/api/jobs.md)
- [term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md)
