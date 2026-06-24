---
doc_type: dev-guide
slug: translation-profile-and-segment-trace-guide
component: translation-profile-and-segment-trace
status: current
summary: 面向集成方说明如何通过 Translation Profile API 管理翻译配置，并在翻译 job 中读取 segment trace。
tags: [backend, translation, resource-versioning, jobs, audit]
last_reviewed: 2026-05-29
---

# Translation Profile 与 Segment Trace 指南

## 概述

Translation Profile 把翻译配置从 settings-only 升级为“先改 draft，再发布 immutable version，最后通过默认指针影响后续翻译任务”。MySQL resource mode 下，job 创建会按 `language_pair` 绑定不可变 Translation Profile 版本快照；Segment Trace 是翻译 job 的 JSON 产物，用来追踪每个 segment 的原文、模型输入、AI 初译和最终渲染文本。

适用场景：

- 后台管理脚本维护默认翻译模型、prompt 版本和分批阈值
- 前端管理页接入翻译配置发布流程
- 集成方排查某个 job 的翻译输入、AI 输出和最终渲染文本

## 前置依赖

- 后端需要启用 `JOBS_REPOSITORY_BACKEND=mysql`
- 写接口需要 `X-Admin-Token`
- 写接口可选 `X-Actor-Id`，只作为已通过 admin token 请求的审计操作者标签
- 当前默认 profile ID 按语言对区分：`electronics-en2zh`、`electronics-ru2zh`
- 翻译任务仍需要翻译运行时配置可用：`OPENAI_API_KEY`、OpenAI SDK，以及对应 prompt：`resources/prompts/translation_en2zh.md` 或 `resources/prompts/translation_ru2zh.md`
- 测试和本地验证使用 `.venv/bin/python`

file / sqlite backend 下，`/api/v1/translation-profiles` 返回 `503`；未显式选择 profile 的翻译 job 继续使用 settings / `.env` 兼容路径。MySQL resource mode 下，每个翻译 `language_pair` 都需要默认 published profile，或显式传入同语言对的 published profile 版本。

## 快速上手

1. 查看当前 Translation Profile：

```bash
curl -sS http://127.0.0.1:8000/api/v1/translation-profiles
```

2. 更新 draft：

```bash
curl -sS -X PUT \
  http://127.0.0.1:8000/api/v1/translation-profiles/electronics-en2zh/draft \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Token: <admin-token>' \
  -d '{
    "language_pair": "en2zh",
    "target_language": "zh-CN",
    "domain": "electronics engineering technical document",
    "prompt_version": "translation-minimal-v1",
    "model": "deepseek-v4-flash",
    "max_pages_per_batch": 20,
    "max_chars_per_batch": 60000
  }'
```

3. 发布并设为默认：

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/translation-profiles/electronics-en2zh/publish \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Token: <admin-token>' \
  -d '{"make_default":true}'
```

4. 提交 `en2zh` document job：

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/document-jobs \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{
    "source_file_id": "file_uploaded_pdf",
    "mode": "en2zh_pdf_to_word",
    "document_language": "en",
    "translation_profile_id": "electronics-en2zh",
    "translation_profile_version": "2026.05.29-1"
  }'
```

不传 `translation_profile_id` / `translation_profile_version` 时，MySQL resource mode 会绑定当前默认 published profile。

提交 `ru2zh` job 时使用 `translation_mode=ru2zh` 或 `mode=ru2zh_pdf_to_word`，并绑定 `electronics-ru2zh`：

```json
{
  "source_file_id": "file_uploaded_pdf",
  "translation_mode": "ru2zh",
  "document_language": "auto",
  "translation_profile_id": "electronics-ru2zh",
  "translation_profile_version": "seed"
}
```

5. 查看翻译 QA 证据：

```bash
curl -sS \
  http://127.0.0.1:8000/api/v1/document-jobs/<job-id>/translation-qa \
  -H "Authorization: Bearer ${TOKEN}"
```

## 核心概念

| 概念 | 说明 |
|---|---|
| Translation Profile | 一组可发布的翻译配置资源，当前按 `language_pair` 支持 `electronics-en2zh` 和 `electronics-ru2zh` |
| draft | 可变草稿，更新后不影响已发布版本 |
| published version | 不可变发布版本，写入 `resource_type=translation_profile` |
| default version | 当前默认 published version，翻译 job 创建时会按 `language_pair` 绑定它 |
| Segment Trace | `translation_trace` job artifact，记录 segment 级翻译证据 |

Translation Profile payload 只保存模型、目标语言、领域、prompt 版本和分批阈值，不保存 `OPENAI_API_KEY`、secret header 或完整 prompt 文本。

## 接口参考

完整端点参考见 [translation-profiles.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-profiles.md)。

常用端点：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/v1/translation-profiles` | 查看 profile 摘要 |
| `GET` | `/api/v1/translation-profiles/{profile_id}` | 查看 published versions 和默认指针 |
| `GET` | `/api/v1/translation-profiles/{profile_id}/draft` | 查看或初始化 draft |
| `PUT` | `/api/v1/translation-profiles/{profile_id}/draft` | 更新 draft payload |
| `POST` | `/api/v1/translation-profiles/{profile_id}/publish` | 发布 draft |
| `POST` | `/api/v1/translation-profiles/{profile_id}/versions/{version}/set-default` | 切默认版本 |
| `POST` | `/api/v1/translation-profiles/{profile_id}/rollback` | 回滚默认版本 |

legacy `/api/v1/jobs` 曾提供 `translation_trace` 下载入口；当前新联调不要使用它。Document Jobs 工作台通过翻译 QA 证据接口读取可展示的片段、术语 trace 和 AI call 摘要：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/v1/document-jobs/{job_id}/translation-qa` | 查看 P1 beta 翻译 QA 证据摘要 |
| `PATCH` | `/api/v1/document-jobs/{job_id}/translation-qa` | 保存 QA 状态、问题类型和备注 |

## 常见场景

### 只预发布，不影响默认翻译配置

发布时传 `make_default=false`：

```json
{
  "make_default": false
}
```

此时会生成 published version，但默认指针不变。确认后再调用 `set-default`。

### 切换默认 Translation Profile 版本

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/translation-profiles/electronics-en2zh/versions/2026.05.29-2/set-default \
  -H 'X-Admin-Token: <admin-token>'
```

后续同 `language_pair` 的翻译 job 会在创建时绑定新的默认版本。已经创建或完成的 job 不会被回写 profile 快照。

### 查看 trace 里的关键字段

`translation_trace` 的顶层字段包含 job、profile 和模型信息：

```json
{
  "schema_version": 1,
  "job_id": "job_xxx",
  "translation_profile": {
    "translation_profile_id": "electronics-en2zh",
    "version": "2026.05.29-1",
    "snapshot_hash": "sha256:..."
  },
  "model": "deepseek-v4-flash",
  "prompt_version": "translation-minimal-v1",
  "segments": []
}
```

每个 segment 至少关注：

| 字段 | 含义 |
|---|---|
| `source_text` | MinerU 页面块中的原文 |
| `model_input_text` | 保护型号、单位、上下标变量后的模型输入 |
| `ai_translation_text` | 模型返回的初译文本 |
| `final_text` | 恢复占位符后最终用于渲染的文本 |

### legacy backend 下保持兼容路径

如果使用 file / sqlite backend，翻译 job 会继续使用 settings / `.env` 的 `OPENAI_MODEL`、`OPENAI_BASE_URL`、`OPENAI_API_KEY` 和翻译分批配置。MySQL resource mode 不走这个 fallback；缺少对应 `language_pair` 的默认 profile 且没有显式版本选择时，job 创建会失败。

### 审计与 actor

以下成功动作会写入 audit event：

| 动作 | audit action | target |
|---|---|---|
| 发布 draft | `translation_profile.publish` | `{profile_id}@{version}` |
| 切默认版本 | `translation_profile.set_default` | `{profile_id}@{version}` |
| 回滚默认指针 | `translation_profile.rollback` | `{profile_id}@{version}` |

审计 actor 来自 `X-Admin-Token` 通过后的 `ActorContext`，可用 `X-Actor-Id` 标记操作者。audit event 不保存 secret、完整 prompt 或 profile payload。

## 已知限制与注意事项

- MySQL resource mode 下，job 创建已接收 `translation_profile_id` / `translation_profile_version`；`direct` 任务传 profile 会返回 `400`。
- file / sqlite backend 下，显式传 `translation_profile_id` 或 `translation_profile_version` 会返回 `503`，未显式选择时继续 settings / `.env` 兼容路径。
- `JobRecord` 保存 `resource_snapshot`；trace 中记录本轮执行时物化的 profile 摘要，旧 job 不会被回填快照。
- `translation_mode=direct` 不生成 `translation_trace`，也不解析默认 Translation Profile。
- `translation_trace` 不保存完整 prompt 文本或 secret，不能单独作为完整 LLM 调用复现包。
- 当前只支持 `en2zh` / `ru2zh`，不新增 `zh2en` / `zh2ru` 真实翻译路径。

## 相关文档

- [translation-profiles.md](/Users/sc/PycharmProjects/md2word/docs/api/translation-profiles.md)
- [jobs.md](/Users/sc/PycharmProjects/md2word/docs/api/jobs.md)
- [term-rule-set-versioning-guide.md](/Users/sc/PycharmProjects/md2word/docs/dev/term-rule-set-versioning-guide.md)
- [backend-local-setup-and-architecture.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-local-setup-and-architecture.md)
