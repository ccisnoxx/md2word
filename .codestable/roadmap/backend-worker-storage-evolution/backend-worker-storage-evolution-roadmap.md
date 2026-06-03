---
doc_type: roadmap
slug: backend-worker-storage-evolution
status: completed
created: 2026-05-28
last_reviewed: 2026-06-02
tags: [backend, worker, storage, jobs, artifacts, restored]
related_requirements: [fastapi-backend-productization]
related_architecture: [architecture-index, backend-fastapi-service]
---

# 后端 worker / storage 演进历史路线

## 1. 背景

本 roadmap 恢复并校准历史 `backend-worker-storage-evolution`。历史目标是把后台 stage 调度、stage message store、repository ports、artifact storage 和 readiness 诊断边界拆清，为后续数据库 / 对象存储 / worker 演进留稳定接口。

当前 `.trellis/spec/backend/` 和 `.codestable/architecture/` 已记录 domain-first、persistence adapter、artifact storage、stage spool 等现状，本路线标记为 `completed`。

## 2. 范围与明确不做

覆盖：

- stage dispatcher port。
- stage message store replay 语义。
- job snapshot / event / file / stage message repository 窄协议。
- artifact storage adapter。
- worker/storage readiness 字段。
- storage backend migration plan。

明确不做：

- 不在当前 2-4 周路线引入多实例 worker、抢占锁或新队列体系。
- 不重构 `app/conversion/` 算法。
- 不扩新后台管理功能。

## 3. 模块拆分

```text
backend-worker-storage-evolution
├── stage dispatcher port
├── stage message store
├── repository boundary
├── artifact storage port
├── recovery policy
└── observability readiness
```

## 4. 接口契约

- stage dispatcher 只负责接受 message 并驱动执行，不保存 message。
- stage message store 的 `pending/running` 可 replay，`failed` 不自动 replay。
- services 依赖最小 repository protocol 组合，不依赖大而全 concrete adapter。
- artifact storage adapter 只负责存储和解析，file type / alias / media / filename 合同由 artifact service 集中定义。

## 5. 子 feature 清单

| slug | 状态 | 说明 |
|---|---|---|
| stage-dispatcher-port | done | 抽出后台 stage 调度 port |
| stage-message-store-contract | done | 固定 stage message store 和 replay 语义 |
| repository-boundary-split | done | 拆 job snapshot/events/files/stage messages 窄协议 |
| artifact-storage-local-adapter | done | 抽出 local artifact storage adapter |
| worker-process-readiness-design | done | readiness 暴露 worker/storage adapter 模式 |
| storage-backend-migration-plan | done | 明确 local file 到 database/object storage 的迁移边界 |

## 6. 排期状态

本路线已完成。未来如需独立 worker、多实例 heartbeat 或队列可见性超时，应另起新 roadmap；不混入当前 PDF -> Word 交付硬化。

## 7. 观察项

- `document_jobs` 已有 Celery task，但当前交付硬化只需要验证主链路和质量，不需要扩展 worker 架构。
- 当前 `frontend/` 已存在配置管理页面，本路线不再承载前端后台能力。

## 8. 变更日志

- 2026-06-02：恢复并校准历史 roadmap，状态收口为 completed。
