---
doc_type: feature-note
feature: 2026-05-28-storage-backend-migration-plan
roadmap: backend-worker-storage-evolution
status: decided
created: 2026-05-28
tags: [backend, worker, queue, jobs, storage]
---

# Worker / Queue 独立评估

## 结论

本轮不引入独立 worker、Redis、Celery、RQ、heartbeat、抢占锁或多实例执行模型。

当前运行形态继续保持：

- 单体、单实例
- `worker_mode=in_process`
- `stage_dispatcher=background_tasks`
- stage message store 继续作为 pending/running replay 和 failed 诊断轨迹
- metadata store 与 artifact storage 只在已抽出的 adapter 边界内切换

该结论满足 storage migration 当前最后一步的退出信号：明确决定继续单实例，而不是在 storage 主链路里顺手扩 worker/queue。

## 判断依据

- 主链路仍是单 job 聚合内的异步 workflow，当前问题已经通过 stage dispatcher port、stage message store、repository ports 和 artifact storage adapter 建立替换边界。
- metadata 已具备 file/database adapter 切换，artifact 已具备 local_file/local_object adapter 切换；继续向 worker 化推进会引入新的并发一致性问题，不应混进 storage 迁移收尾。
- 当前没有明确的多实例部署目标、吞吐 SLA、长任务抢占需求或跨进程失败恢复要求。
- stage message 现在只定义 pending/running replay，failed 只作为诊断信号；这不足以直接支撑多 worker 竞争执行。

## 未来触发条件

满足以下任一条件时，再另起 `backend-worker-queue-evolution` 或等价 roadmap：

- 需要同时运行多个 API/worker 实例处理同一批 jobs。
- 单实例 `BackgroundTasks` 无法满足任务吞吐、隔离或重启恢复要求。
- 需要明确的 worker heartbeat、lease、抢占锁、可见性超时或死信队列。
- 需要把 stage dispatch 从“进程内函数调用”替换成“外部队列投递”。
- 需要可观测地追踪 worker 节点、执行租约和队列积压。

## 后续 roadmap 边界

未来 worker/queue roadmap 应至少单独设计这些主题：

- Worker runtime：独立进程如何启动、消费、退出和上报健康。
- Queue contract：message id、stage、payload、retry、visibility timeout、dead letter 的语义。
- Lease / lock：同一 stage message 如何避免多 worker 并发执行。
- Idempotency：每个 stage 重复执行时哪些写入必须幂等。
- Recovery：running message 在 worker 失联后如何恢复，failed message 是否进入人工 retry。
- Observability：worker heartbeat、queue depth、oldest pending age、failed count。

## 本轮保持不做

- 不引入 Redis/Celery/RQ。
- 不把 FastAPI 主进程和 worker 进程拆开部署。
- 不修改现有 jobs HTTP API。
- 不改变 events 的审计轨迹定位。
- 不通过 events 重建 job snapshot。
- 不在 storage migration 里继续扩展主链路行为。
