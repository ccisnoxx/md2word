---
doc_type: dev-guide
slug: term-rule-set-versioning-guide
component: term-rule-set-versioning
status: current
summary: 面向集成方说明如何通过 Term Rule Set API 编辑草稿、发布术语规则版本、切默认版本、回滚和理解审计边界。
tags: [backend, term-rules, resource-versioning, audit]
last_reviewed: 2026-05-29
---

# Term Rule Set 版本管理指南

## 概述

Term Rule Set 版本管理把术语规则从“直接改 live runtime store”升级为“先改 draft，再发布 published version，最后通过默认指针影响 conversion runtime”。
发布、设默认和回滚成功后会写入 audit event，job 创建在 MySQL resource mode 下会绑定不可变 Term Rule Set 版本快照。

适用场景：

- 后台管理脚本维护术语规则
- 前端管理页接入术语发布流程
- 生产环境需要回滚到旧术语规则版本

## 前置依赖

- 后端需要启用 `JOBS_REPOSITORY_BACKEND=mysql`
- 写接口需要 `X-Admin-Token`
- 写接口可选 `X-Actor-Id`，只作为已通过 admin token 请求的审计操作者标签
- 当前默认规则集 ID 是 `electronics-default`
- 测试和本地验证使用 `/Users/sc/miniconda3/envs/md2word/bin/python`

file / sqlite backend 下，`/api/v1/term-rule-sets` 返回 `503`；legacy `/api/v1/term-rules` 和 `/api/v1/term-rule-categories` 写接口仍保持兼容。

## 快速上手

1. 查看当前规则集：

```bash
curl -sS http://127.0.0.1:8000/api/v1/term-rule-sets
```

2. 更新 draft：

```bash
curl -sS -X PUT \
  http://127.0.0.1:8000/api/v1/term-rule-sets/electronics-default/draft/rules \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Token: <admin-token>' \
  -d '{"yaml_text":"schema_version: 2\ncategories: {}\nrules: []\n"}'
```

3. 发布并设为默认：

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/term-rule-sets/electronics-default/publish \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Token: <admin-token>' \
  -d '{"make_default":true,"published_by":"operator","publish_reason":"update terminology"}'
```

4. 回滚到旧版本：

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/term-rule-sets/electronics-default/rollback \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Token: <admin-token>' \
  -d '{"version":"2026.05.29-1"}'
```

## 核心概念

| 概念 | 说明 |
|---|---|
| Term Rule Set | 一组可整体发布的术语规则资源，当前只支持 `electronics-default` |
| draft | 可变草稿，更新后不影响当前任务使用的 runtime YAML |
| published version | 不可变发布版本，写入 `resource_type=term_rule_set` |
| default version | 当前默认 published version，会同步到 legacy live runtime store |
| live runtime store | `data/config/term_rules_store.json` 和 `data/config/runtime_subscripts_dictionary.yaml` |

## 接口参考

完整端点参考见 [term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md)。

常用端点：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/v1/term-rule-sets` | 查看规则集摘要 |
| `GET` | `/api/v1/term-rule-sets/{set_id}` | 查看 published versions 和默认指针 |
| `GET` | `/api/v1/term-rule-sets/{set_id}/draft` | 查看或初始化 draft |
| `PUT` | `/api/v1/term-rule-sets/{set_id}/draft/rules` | 更新 draft YAML |
| `POST` | `/api/v1/term-rule-sets/{set_id}/publish` | 发布 draft |
| `POST` | `/api/v1/term-rule-sets/{set_id}/versions/{version}/set-default` | 切默认版本 |
| `POST` | `/api/v1/term-rule-sets/{set_id}/rollback` | 回滚默认版本 |

## 常见场景

### 只预发布，不影响线上 runtime

发布时传 `make_default=false`：

```json
{
  "make_default": false
}
```

此时会生成 published version，但默认指针和 runtime YAML 不变。后续确认后再调用 `set-default`。

### 切换默认版本

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/term-rule-sets/electronics-default/versions/2026.05.29-2/set-default \
  -H 'X-Admin-Token: <admin-token>'
```

成功后，后续未显式指定术语版本的 job 会绑定新的默认版本。已经创建的 job 保留创建时的资源快照，不会被回写。

### 审计与 actor

以下成功动作会写入 audit event：

| 动作 | audit action | target |
|---|---|---|
| 发布 draft | `term_rule_set.publish` | `{set_id}@{version}` |
| 切默认版本 | `term_rule_set.set_default` | `{set_id}@{version}` |
| 回滚默认指针 | `term_rule_set.rollback` | `{set_id}@{version}` |

`published_by` 和 `publish_reason` 仍是版本 payload 元数据；真正的审计 actor 来自 `X-Admin-Token` 通过后的 `ActorContext`，可用 `X-Actor-Id` 标记操作者。

### legacy 写接口在 MySQL versioned mode 下被保护

启用 Term Rule Set versioning 后，以下 legacy 写接口会返回 `400`，提示使用 draft API：

- `POST /api/v1/term-rule-categories`
- `PATCH /api/v1/term-rule-categories/{category_id}`
- `DELETE /api/v1/term-rule-categories/{category_id}`
- `POST /api/v1/term-rules`
- `PATCH /api/v1/term-rules/{rule_id}`
- `DELETE /api/v1/term-rules/{rule_id}`
- `POST /api/v1/term-rules/import`
- `POST /api/v1/term-rules/sync-files`

读接口、export 和 simulate 继续读取当前默认 published 版本同步出的 live truth。

## 已知限制与注意事项

- MySQL resource mode 下，job 创建已支持 `term_rule_set_id` / `term_rule_set_version`；不传时绑定当前默认版本。
- file / sqlite backend 下，显式传 `term_rule_set_id` 或 `term_rule_set_version` 会返回 `503`，继续走 legacy runtime YAML 兼容路径。
- audit event 只记录成功动作，不记录 token、完整规则 payload 或本地私密路径。
- 当前不提供多租户隔离；公司差异应通过不同资源 ID 表达，MVP 暂只启用 `electronics-default`。

## 相关文档

- [term-rule-sets.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rule-sets.md)
- [term-rules.md](/Users/sc/PycharmProjects/md2word/docs/api/term-rules.md)
- [backend-local-setup-and-architecture.md](/Users/sc/PycharmProjects/md2word/docs/dev/backend-local-setup-and-architecture.md)
