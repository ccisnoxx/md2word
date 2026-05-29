---
doc_type: feature-ff-note
feature: worker-process-readiness-design
date: 2026-05-28
requirement:
tags: [backend, jobs, worker, storage, health]
---

## 做了什么
把当前单实例 worker/storage adapter 模式和 stage spool 状态计数暴露到 `/health/ready`，用于后续独立 worker 和存储迁移前的诊断基线。

## 改了哪些
- `app/repositories/protocols.py`、`app/repositories/file_job_repository.py` — stage message store 增加 pending/running/failed 状态计数能力。
- `app/services/health_service.py`、`app/main.py` — readiness 改由 stage message store 提供 spool 计数，并输出当前 adapter 模式。
- `docs/api/health.md`、`docs/dev/runtime-observability-and-health.md`、`docs/runbook.md` — 补齐 readiness 字段和排障口径。
- `.codestable/roadmap/backend-worker-storage-evolution/` — 更新 roadmap 和 item 状态。

## 怎么验证的
已通过编译检查、health readiness 目标测试、stage replay 语义测试，以及相关 jobs 回归测试。
