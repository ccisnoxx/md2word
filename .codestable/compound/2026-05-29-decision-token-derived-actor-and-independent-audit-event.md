---
doc_type: decision
category: architecture
date: 2026-05-29
slug: token-derived-actor-and-independent-audit-event
status: active
area: backend-permission-audit
tags: [backend, audit, permissions, architecture, productization]
---

# Token-derived ActorContext and independent AuditEvent

## 背景

后端产品化路线需要给资源发布、回滚、job 运维和 artifact 下载建立最小权限与审计基线。当前系统仍以 `X-Admin-Token`、`X-Jobs-Token` 和本地配置为边界，没有 SSO、用户表或多租户模型。

## 决定

- `ActorContext` 从现有 token / open 访问模式派生，只表达 `actor_id`、`actor_role` 和 `source`。
- `X-Actor-Id` 只作为已认证 token 请求的操作者标签；匿名/open 请求不能自报 actor。
- `AuditEvent` 独立于 `JobEvent`，用于跨资源记录成功执行的高风险动作。
- audit persistence 跟随 metadata backend：file 写 `audit_events.jsonl`，sqlite / MySQL 写 `audit_events` 表。
- 本阶段不新增 SSO、用户表、细粒度 ACL、多租户字段、审计查询 HTTP API 或审计 UI。

## 理由

现有产品化阶段需要的是可追溯的最小基线，而不是完整身份系统。把 actor 绑定到已有认证边界，可以保持现有 403 / 503 行为和 API 响应兼容，同时让 service 层能记录稳定审计事件。

`JobEvent` 是单个 job 的生命周期证据；`AuditEvent` 是跨资源的操作审计。如果复用 `JobEvent`，模板、术语规则集、翻译配置这类非 job 动作会被迫塞进 job 语义，后续查询和保留策略也会混乱。

## 考虑过的替代方案

- 复用 `JobEvent`：放弃。它绑定 job 生命周期，不适合模板/资源版本动作。
- 现在引入完整用户/SSO/租户模型：放弃。会显著扩大迁移和权限设计范围，超过本 feature。
- 让各 router 直接拼 audit dict：放弃。容易产生 action、target、reason 口径分叉；统一通过 `AuditService.record()` 写入。

## 后果

- 后续接入真实身份系统时，应优先替换 actor dependency 的派生逻辑，保留 `AuditEvent` 合同。
- 重复成功动作会产生多条 audit event，审计流水不做去重。
- 旧数据没有 audit events 不影响 job / resource 读取。
- 若未来需要运营查询，需要另起 feature 增加 audit API 或导出脚本。

## 相关文档

- `.codestable/features/2026-05-29-permission-and-audit-baseline/permission-and-audit-baseline-design.md`
- `.codestable/features/2026-05-29-permission-and-audit-baseline/permission-and-audit-baseline-acceptance.md`
- `.codestable/architecture/backend-fastapi-service.md`
