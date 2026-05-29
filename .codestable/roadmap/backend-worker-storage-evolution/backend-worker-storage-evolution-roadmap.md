---
doc_type: roadmap
slug: backend-worker-storage-evolution
status: active
created: 2026-05-28
last_reviewed: 2026-05-28
tags: [backend, worker, storage, jobs, artifacts]
related_requirements: [fastapi-backend-productization]
related_architecture: [architecture-index, backend-fastapi-service]
---

# 后端 worker / storage 演进路线图

## 1. 背景

当前后端已经形成以 `job` 为中心的异步工作流模型，并且 PDF 在线链路已经可以从 callback 自动推进到 `completed`。现在主链路的领域规则、事件意图、`source_pdf_context`、`parsed_result_package` 和 artifact 合同已经基本收口。

下一阶段最关键的问题不是继续扩主链路，而是把当前默认执行和存储实现的边界设计清楚。当前实现仍是：

- `BackgroundTasks` 触发后台执行
- file-based stage spool 记录 stage message
- file repository 同时承担 job snapshot、events、files 和 stage messages
- local file 作为唯一 artifact storage

这些选择适合当前单体单实例运行，但如果未来要支持独立 worker、对象存储、数据库或更强恢复能力，需要先把接口和责任边界固定下来。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 抽出后台 stage 调度入口，让当前 `BackgroundTasks` 成为默认 adapter
- 明确 stage message store 的协议和 replay 语义
- 进一步拆分 job repository 的语义边界
- 抽出 artifact storage adapter，保留 local file 作为默认实现
- 明确 worker / storage 相关 readiness、事件和诊断字段
- 形成从 local file 到数据库 / 对象存储的后续迁移顺序

### 明确不做

- 不在本 roadmap 第一阶段直接引入 Redis、Celery、RQ 或其他消息队列
- 不立刻把 FastAPI 主进程和 worker 进程拆开部署
- 不立刻把 file repository 替换为 SQLite、MySQL 或 PostgreSQL
- 不立刻引入 OSS / S3 作为默认 artifact backend
- 不修改现有 HTTP API 合同
- 不和权限模型收紧混做；`retry/cancel/cleanup-local-files` 权限应另起主题
- 不重构 `app/conversion/runtime/*` 的算法和渲染实现

## 3. 模块拆分（概设）

```text
backend-worker-storage-evolution
├── stage dispatcher port：后台 stage 调度入口和当前 BackgroundTasks adapter
├── stage message store：stage spool 协议、状态机和 replay 查询
├── repository boundary：job snapshot / events / files / stage messages 的语义拆分
├── artifact storage port：artifact 注册、下载解析和 local file adapter
├── recovery policy：启动 replay、running 恢复、失败重试和幂等边界
└── observability readiness：worker/storage 模式、spool 指标和诊断字段
```

### stage dispatcher port

- **职责**：提供后台执行调度入口；当前 adapter 仍调用 `JobStageService.dispatch_message()`，由 FastAPI `BackgroundTasks` 触发。
- **不承担**：不保存 message，不决定 workflow 合法性，不直接修改 job。
- **承载的子 feature**：`stage-dispatcher-port`、`worker-process-readiness-design`
- **触碰的现有代码 / 模块**：`app/api/v1/routers/jobs_ingest.py`、`app/api/v1/routers/mineru_callbacks.py`、`app/services/jobs/stage.py`、`app/main.py`

### stage message store

- **职责**：持久化 stage message，定义 pending/running/failed 的更新、查询和 replay 语义。
- **不承担**：不执行 stage，不登记 artifact，不解释领域状态。
- **承载的子 feature**：`stage-message-store-contract`、`repository-boundary-split`
- **触碰的现有代码 / 模块**：`app/repositories/protocols.py`、`app/repositories/file_job_repository.py`、`app/services/jobs/stage.py`

### repository boundary

- **职责**：把 job snapshot、events、files 和 stage messages 的协议分开，减少业务 service 对“大而全 repository”的依赖。
- **不承担**：不改变当前 file backend 的物理存储格式，不做数据库迁移。
- **承载的子 feature**：`repository-boundary-split`
- **触碰的现有代码 / 模块**：`app/repositories/protocols.py`、`app/repositories/file_job_repository.py`、`app/services/jobs/command.py`、`app/services/jobs/query.py`、`app/services/jobs/lifecycle.py`、`app/services/jobs/stage.py`

### artifact storage port

- **职责**：固定 artifact 存储和下载相关接口，让 `source_package`、`source_pdf`、`parsed_result_package`、`translation_request`、`result_docx` 继续通过统一合同暴露。
- **不承担**：不主动调用 MinerU，不执行 conversion，不决定 file_type / alias 的产品语义。
- **承载的子 feature**：`artifact-storage-local-adapter`、`storage-backend-migration-plan`
- **触碰的现有代码 / 模块**：`app/services/jobs/artifacts.py`、`app/core/job_paths.py`、`app/api/v1/routers/jobs_query.py`、`app/api/v1/routers/jobs_presenters.py`

### recovery policy

- **职责**：定义启动 replay、running message 处理、stage 重复执行和失败重试的最小规则。
- **不承担**：不实现跨进程锁，不解决多 worker 竞争；这些属于未来独立 worker 阶段。
- **承载的子 feature**：`stage-message-store-contract`、`worker-process-readiness-design`
- **触碰的现有代码 / 模块**：`app/services/jobs/stage.py`、`app/main.py`、`app/services/health_service.py`

### observability readiness

- **职责**：让 health、events 和日志能说明当前执行 / 存储 adapter 模式和 stage spool 状态。
- **不承担**：不实现外部监控系统，不引入 metrics server。
- **承载的子 feature**：`worker-process-readiness-design`
- **触碰的现有代码 / 模块**：`app/services/health_service.py`、`docs/dev/runtime-observability-and-health.md`、`docs/runbook.md`

## 4. 模块间接口契约 / 共享协议

### 4.1 stage dispatcher 协议

**方向**：HTTP boundary / lifecycle service -> stage dispatcher port  
**形式**：函数调用

**契约**：

```python
class StageDispatcherProtocol(Protocol):
    def dispatch(self, message_id: str) -> None: ...


class LocalBackgroundStageDispatcher:
    def dispatch(self, message_id: str) -> None:
        stage_service.dispatch_message(message_id)
```

**约束**：

- router 和 lifecycle service 只能通过 dispatcher 触发后台执行，不直接知道具体执行 adapter。
- 第一阶段 `LocalBackgroundStageDispatcher` 仍在同进程内调用 `JobStageService`。
- 该协议不保证异步完成，只表达“接受一个 stage message id 并尝试驱动执行”。
- 将来独立 worker 可以替换 dispatcher，但不能改变 stage message 和 job workflow 合同。

### 4.2 stage message store 协议

**方向**：JobStageService -> stage message store  
**形式**：repository protocol

**契约**：

```python
class StageMessageStoreProtocol(Protocol):
    def put_stage_message(self, message: JobStageMessage) -> None: ...
    def get_stage_message(self, message_id: str) -> JobStageMessage | None: ...
    def update_stage_message(self, message_id: str, **patch: Any) -> JobStageMessage: ...
    def list_replayable_stage_messages(self) -> list[JobStageMessage]: ...
    def delete_stage_message(self, message_id: str) -> None: ...
```

**约束**：

- `list_replayable_stage_messages()` 只返回 `pending` 和 `running`，不返回 `failed`。
- `failed` stage message 只能通过显式 retry / recover 动作重新创建或重新调度。
- store 不做 workflow 合法性判断，只保存执行消息。
- 第一阶段可由 `FileJobRepository` 继续实现该协议。

### 4.3 job repository 语义拆分

**方向**：jobs application services -> repository ports  
**形式**：repository protocol

**契约**：

```python
class JobSnapshotRepositoryProtocol(Protocol):
    def create_job(self, job: JobRecord) -> None: ...
    def get_job(self, job_id: str) -> JobRecord | None: ...
    def list_jobs(self) -> list[JobRecord]: ...
    def update_job(self, job_id: str, **patch: Any) -> JobRecord: ...


class JobEventRepositoryProtocol(Protocol):
    def append_event(self, job_id: str, event: JobEvent) -> None: ...
    def list_events(self, job_id: str) -> list[JobEvent]: ...


class JobFileRepositoryProtocol(Protocol):
    def upsert_file(self, job_id: str, file: JobFile) -> None: ...
    def list_files(self, job_id: str) -> list[JobFile]: ...
```

**约束**：

- `FileJobRepository` 可以继续同时实现这些协议。
- service 构造函数应逐步依赖最小协议组合，而不是依赖单个大 repository。
- `source_pdf_context -> mineru_*` 兼容投影同步继续留在持久化边界。
- 不在该阶段改变 `job.json/files.json/events.jsonl/stage_messages/*.json` 的物理格式。

### 4.4 artifact storage 协议

**方向**：JobCommandService / JobStageService / lifecycle service / query router -> artifact storage port
**形式**：函数调用 + file contract

**契约**：

```python
class ArtifactStorageProtocol(Protocol):
    def build_registered_file(self, file_type: ArtifactFileType, paths: JobPaths) -> JobFile: ...
    def resolve_download(self, paths: JobPaths, file: JobFile) -> DownloadArtifact: ...
```

**约束**：

- 默认实现为 local file adapter，切换实现为 local object adapter，继续使用 `JobPaths` 推导本地 fallback。
- `JobFile.path` 仍是 job 内逻辑路径，不是本地绝对路径。
- `JobFile.storage_backend=object` 时，`object_key` 只作为服务端内部对象定位字段，不替代 `download_url`。
- `parsed_result_package` 是受支持的中间 artifact，但 `result_docx` 仍是默认交付物。
- adapter 只负责 artifact 注册、shadow upload 和下载结果解析，不负责 file_type / alias / media type / 下载文件名等产品语义。
- file_type / alias / media type / 下载 URL / 下载文件名仍由 `JobArtifactService` 作为 artifact 合同服务集中定义。
- adapter 不负责远端 MinerU 下载；远端下载仍属于 `MinerUClient`。

### 4.5 worker / storage readiness 协议

**方向**：health service -> 调用方 / 运维  
**形式**：HTTP readiness 字段

**契约**：

```json
{
  "worker_mode": "in_process",
  "stage_dispatcher": "background_tasks",
  "stage_message_store": "file",
  "artifact_storage": "local_file",
  "stage_spool_pending_messages": 0,
  "stage_spool_running_messages": 0,
  "stage_spool_failed_messages": 0
}
```

**约束**：

- 第一阶段只报告当前 adapter 模式，不承诺多实例健康。
- `artifact_storage` 默认是 `local_file`，切换到本地对象 adapter 时为 `local_object`。
- readiness 不自动修复 failed message。
- 若未来独立 worker 落地，应新增 worker heartbeat 或 last-seen 字段，但不应改变已有字段含义。

## 5. 子 feature 清单

1. **stage-dispatcher-port** — 抽出后台 stage 调度 port，让 router / lifecycle 通过 dispatcher 触发执行，当前实现仍使用 `BackgroundTasks + JobStageService.dispatch_message()`。
   - 所属模块：stage dispatcher port
   - 依赖：无
   - 状态：done
   - 对应 feature：2026-05-28-stage-dispatcher-port
   - 备注：已抽出 `StageDispatcherProtocol`；当前 `InProcessStageDispatcher` 仍委托 `JobStageService.dispatch_message / replay_pending`

2. **stage-message-store-contract** — 将 stage message 能力从大 repository 依赖里进一步拆出，固定 replayable message 语义和失败消息处理规则。
   - 所属模块：stage message store / recovery policy
   - 依赖：stage-dispatcher-port
   - 状态：done
   - 对应 feature：2026-05-28-stage-message-store-contract
   - 备注：已定义 `StageMessageStoreProtocol`；`pending/running` 可 replay，`failed` 不自动 replay

3. **repository-boundary-split** — 把 job snapshot、events、files、stage messages 的协议拆成更窄的 application 依赖，`FileJobRepository` 继续作为组合实现。
   - 所属模块：repository boundary
   - 依赖：stage-message-store-contract
   - 状态：done
   - 对应 feature：2026-05-28-repository-boundary-split
   - 备注：已拆出 job snapshot、events、files 和 stage messages 的窄协议；不改当前 JSON 物理存储格式

4. **artifact-storage-local-adapter** — 在现有 `JobArtifactService` 合同上抽出 local artifact storage adapter，保留当前 file_type / alias / download 行为。
   - 所属模块：artifact storage port
   - 依赖：repository-boundary-split
   - 状态：done
   - 对应 feature：2026-05-28-artifact-storage-local-adapter
   - 备注：已新增 `LocalArtifactStorageAdapter`，业务写侧和下载路径解析改走 `artifact_storage`；`JobArtifactService` 继续承担 artifact 合同语义

5. **worker-process-readiness-design** — 补充 worker / storage adapter 模式的 readiness 字段、runbook 和诊断口径，为未来独立 worker 做前置说明。
   - 所属模块：observability readiness / recovery policy
   - 依赖：stage-message-store-contract
   - 状态：done
   - 对应 feature：2026-05-28-worker-process-readiness-design
   - 备注：已在 readiness 暴露 worker/storage adapter 模式和 pending/running/failed spool 计数；failed 只诊断，不自动 replay

6. **storage-backend-migration-plan** — 设计从 local file 到数据库 / 对象存储的迁移顺序、兼容字段和回滚策略。
   - 所属模块：artifact storage port / repository boundary
   - 依赖：artifact-storage-local-adapter, worker-process-readiness-design
   - 状态：done
   - 对应 feature：2026-05-28-storage-backend-migration-plan
   - 备注：已完成 metadata 与 artifact 的最小迁移边界；worker/queue 独立评估结论为继续单体单实例，未来多实例需求另起 roadmap

**最小闭环**：第 1 条 `stage-dispatcher-port` 做完后，现有 `POST /jobs`、`POST /jobs/pdf`、callback 自动后处理和 retry 路径仍保持通过，同时后台执行触发点已有可替换入口。

## 6. 排期思路

这组演进应从执行入口开始，而不是先换存储。`stage-dispatcher-port` 能以最小行为变更建立替换点；随后拆清 stage message store，避免未来 worker 化时把“执行消息”和“job 快照”继续揉在一起。

repository 协议拆分排在第三，是因为它依赖 stage message 语义先稳定。artifact storage adapter 排在第四，是因为当前 artifact 合同已经清晰，但 storage backend 仍是 local file 细节。readiness 设计可在 stage store 稳定后并行推进。最后再做 storage backend migration plan，避免在边界未稳定时提前讨论数据库或对象存储选型。

## 7. 观察项

- `.codestable/architecture/` 和 `.codestable/roadmap/mineru-online-ingestion/` 中仍有部分 PDF 在线链路旧表述，后续应单独做 architecture / roadmap update，不混进本 roadmap。
- 权限模型收紧应另起 `backend-permission-hardening` 主题，重点处理 `retry/cancel/cleanup-local-files`、jobs access mode、admin token 和 callback public mode。
- 如果未来真正引入独立 worker，需要另起 roadmap，单独设计 worker heartbeat、任务抢占锁、并发幂等、队列可见性超时和多实例部署拓扑。
