---
doc_type: roadmap
slug: backend-productization-implementation
status: completed
created: 2026-05-28
last_reviewed: 2026-06-02
tags: [backend, productization, mysql, resources, audit, operations, restored]
related_requirements: [fastapi-backend-productization]
related_architecture: [architecture-index, backend-fastapi-service]
---

# 后端产品化实施历史路线

## 1. 背景

本 roadmap 恢复并校准历史 `backend-productization-implementation`。历史目标是把后端从可运行服务推进到单实例生产化基线：metadata backend、artifact 合同、资源版本、快照、审计和运维测试。

当前 `.codestable/architecture/` 已记录这些能力为现状，因此本 roadmap 标记为 `completed`，作为追踪来源保留。

## 2. 范围与明确不做

覆盖：

- MySQL / sqlite / file metadata adapter 基线。
- artifact 大小、hash、下载诊断和 retention dry-run。
- Template Profile、Term Rule Set、Translation Profile 的资源版本语义。
- Job Resource Snapshot。
- 最小 ActorContext / AuditEvent。
- readiness、metrics、release check、部署和 runbook 基线。

明确不做：

- 不继续扩展新后台管理面。
- 不引入 SSO、多租户、审计 UI 或外部监控平台。
- 不解决 Golden Sample 质量验收。

## 3. 模块拆分

```text
backend-productization-implementation
├── metadata foundation
├── artifact contract
├── resource versioning
├── template / term-rule / translation profile versioning
├── job resource snapshot
├── permission and audit
└── operations readiness and test baseline
```

## 4. 接口契约

- resource version 只允许 job 绑定 `published` 版本。
- `JobRecord.resource_snapshot` 是创建期资源版本快照，不随默认版本变化。
- audit event 记录高风险资源动作、job ops 和 artifact download 成功路径。
- readiness / metrics 报告 metadata store、artifact storage、worker mode、资源默认版本和 audit 计数。

## 5. 子 feature 清单

| slug | 状态 | 说明 |
|---|---|---|
| mysql-metadata-foundation | done | metadata backend 和 MySQL 基线 |
| local-artifact-contract-hardening | done | artifact hash、大小、下载诊断、retention dry-run |
| resource-versioning-foundation | done | 资源版本状态机和默认指针 |
| template-profile-versioning | done | Template Profile 版本管理 |
| term-rule-set-versioning | done | Term Rule Set 草稿、发布、默认和回滚 |
| translation-profile-and-segment-trace | done | Translation Profile 和 translation trace |
| job-resource-snapshot-binding | done | job 创建期资源快照 |
| permission-and-audit-baseline | done | 最小权限和审计 |
| operations-readiness-and-test-baseline | done | readiness、metrics、release check、runbook |

## 6. 排期状态

本路线已完成。当前优先级是 PDF -> Word 主链路交付硬化，不在此路线继续追加后台功能。

## 7. 观察项

- 真实外部 MySQL smoke、Alembic / SQLAlchemy 迁移体系仍不是当前能力。
- 真实 artifact 删除和删除审计仍是后续运维主题，不进入本轮 2-4 周交付硬化。
- 前端配置管理已经存在，但本轮不继续扩新后台功能。

## 8. 变更日志

- 2026-06-02：恢复并校准历史 roadmap，状态从历史 active 收口为 completed。
