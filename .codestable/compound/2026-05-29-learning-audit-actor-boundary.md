---
doc_type: learning
track: knowledge
date: 2026-05-29
slug: audit-actor-boundary
component: backend-permission-audit
tags: [backend, audit, actor, security, fastapi]
---

# 审计 actor 必须来自认证边界

## 背景

`permission-and-audit-baseline` 给模板版本、术语规则集、翻译配置、job 运维动作和 artifact 下载补上了 `AuditEvent`。其中 artifact download 允许 `JOBS_ACCESS_MODE=open`，这类请求没有可信调用方身份。

## 指导原则

- `actor_role` 只能由实际通过的访问模式派生：`admin_token`、`jobs_token` 或 `open`。
- `X-Actor-Id` 只能作为已认证 token 请求的操作者标签，不能让匿名/open 请求自报身份。
- `JOBS_ACCESS_MODE=open` 下的审计事件应写 `actor_role=anonymous` 且 `actor_id=None`。
- audit 的 `target_id` 应使用稳定业务标识，例如 `{job_id}:{artifact_alias}` 或 `{resource_id}@{version}`，不要写 token、secret、完整 payload 或本地绝对私密路径。

## 为什么重要

审计日志的价值在于能回答“哪个可信边界允许了这个动作”。如果匿名请求可以通过 header 自报 actor，日志会把不可信输入误写成操作者身份，后续排障、追责和风控都会被污染。

## 适用场景

- 现有 token / header 鉴权继续演进为更完整的身份系统前。
- 给 open、token、admin 混合入口补 audit 时。
- 后续新增高风险动作并需要记录 actor / reason / trace_id 时。

## 当前实现参考

- `require_admin_actor()`：admin token 通过后返回 `actor_role=admin`，无 `X-Actor-Id` 时默认 `actor_id=admin`。
- `require_jobs_actor()`：`token` 模式返回 `actor_role=jobs`，无 `X-Actor-Id` 时默认 `actor_id=jobs-client`。
- `require_jobs_actor()`：`open` 模式始终返回 `actor_role=anonymous` 和 `actor_id=None`，忽略 `X-Actor-Id`。
- `AuditService.record()`：统一生成 `audit_id`，过滤空白 reason，并写入 metadata backend 的 audit repository。
