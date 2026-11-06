# 旧 Jobs 链路删除记录

## 修改边界

- `app/main.py` 删除旧 conversion entrypoint、artifact storage、command/query/lifecycle/stage 服务与 stage dispatcher 装配；启动生命周期仅创建正式 DocumentJob 恢复任务，退出时维持原取消语义。
- `AppRuntime` 删除旧 jobs/files/stage 仓储端口和旧服务字段，保留 `job_event_repository` 与全部正式 DocumentJob 端口。
- `app/api/errors.py` 删除仅旧链路使用的 `ConversionFailure`、`JobWorkflowViolation` 和旧 artifact 下载异常映射；正式共享快照错误、HTTP/API/校验错误、MinerU 配置错误映射保持。
- `HealthService` 调用已与仓储分工同步：移除 stage store、stage dispatcher 和旧 job repository 参数；artifact backend 沿用 Settings 的 `local_file`/`local_object`/`s3` 枚举，保留其余正式域参数。
- 删除旧服务、调度、状态机、未挂载路由、响应模型、presenter、专属 artifact 实现、StageWorker 和独立脚本入口。

## 保留的真实闭包

- `jobs/models.py`：`document_jobs/service.py` 仍使用 `ConversionOptions`、`JobRecord`、`JobResourceSnapshot` 构建和物化资源快照；execution/publication_evidence/publication_provenance 使用快照模型，因此保留共享模型合同，不迁移或猜测替代模型；后续仅删除无消费者的旧 stage message 模型，见补充。
- `jobs/resource_snapshots.py`：正式 service/execution 使用资源版本解析、物化及错误合同，保持原行为。
- `jobs/paths.py`：正式 service/publication_provenance 与 file persistence backend 使用目录和资源快照路径，保留原布局。
- `jobs/repository.py`：仅保留 `JobEventRepositoryProtocol.append_event/list_events`，支持明确要求保留的历史 `job_events` 全部读写。
- `jobs/mineru_callbacks_router.py`：仍由 API v1 router 挂载；现有请求校验、checksum、正式 execution 查找/入队、正式 worker 唤醒保持不变。此文件没有改动。
- `jobs/__init__.py`：保留共享包标识。
- 正式 DocumentJob task queue、translation batch queue、DocumentIR converter、renderer 和 recovery 装配保持。

## 文件清单

| 文件 | 动作 | 新增行 | 删除行 |
| --- | --- | ---: | ---: |
| `app/api/errors.py` | 修改 | 0 | 27 |
| `app/core/runtime.py` | 修改 | 1 | 18 |
| `app/domains/jobs/artifact_integrity.py` | 删除 | 0 | 71 |
| `app/domains/jobs/artifact_retention.py` | 删除 | 0 | 166 |
| `app/domains/jobs/artifact_storage.py` | 删除 | 0 | 80 |
| `app/domains/jobs/artifacts.py` | 删除 | 0 | 112 |
| `app/domains/jobs/command.py` | 删除 | 0 | 175 |
| `app/domains/jobs/dispatch.py` | 删除 | 0 | 49 |
| `app/domains/jobs/ingest_router.py` | 删除 | 0 | 342 |
| `app/domains/jobs/lifecycle.py` | 删除 | 0 | 295 |
| `app/domains/jobs/object_artifact_storage.py` | 删除 | 0 | 277 |
| `app/domains/jobs/ops_router.py` | 删除 | 0 | 192 |
| `app/domains/jobs/presenters.py` | 删除 | 0 | 118 |
| `app/domains/jobs/query.py` | 删除 | 0 | 91 |
| `app/domains/jobs/query_router.py` | 删除 | 0 | 198 |
| `app/domains/jobs/repository.py` | 修改 | 3 | 52 |
| `app/domains/jobs/router.py` | 删除 | 0 | 14 |
| `app/domains/jobs/schemas.py` | 删除 | 0 | 165 |
| `app/domains/jobs/stage.py` | 删除 | 0 | 897 |
| `app/domains/jobs/workflow.py` | 删除 | 0 | 525 |
| `app/domains/jobs/workflow_events.py` | 删除 | 0 | 80 |
| `app/main.py` | 修改 | 11 | 122 |
| `app/workers/stage_worker.py` | 删除 | 0 | 47 |
| `scripts/dev/run_stage_worker.py` | 删除 | 0 | 37 |

合计 24 个已有文件：新增 15 行，删除 4150 行，净减少 4135 行。该统计不含本文和其他分工修改。

## 验证与交接

- 9 个保留文件 AST 解析和内存 `compile` 通过，未写入字节码。
- 静态检查 `AppRuntime` 调用的 53 个参数与 dataclass 字段完全一致。
- 本分工路径 `git diff --check` 通过，已检查最终差异。
- 运行时导入、测试配置 `build_runtime`、Celery、定向 API/健康/回调验证由主会话在并行仓储修改完成后统一执行，本分工不重复启动验证。
- 未修改 tests；专属 artifact/workflow/stage 测试删除及混合测试裁剪由主会话处理。旧运维脚本及其测试由 persistence 分工处理。
- 未访问外部服务、未运行全仓测试、未提交或推送、未写入仓库外文件。
- 已将触及的模块说明改为中文并更新历史事件端口说明；未修改共享快照和回调模块内未触及的文档或开发者输出。

## 后续补充：模型、配置与当前文档

- 删除共享 models 文件内已经没有消费者的 `JobStageMessage`、`JobStageName`、`JobStageStatus`；其他共享模型保持原状。
- 删除 `jobs_worker_poll_interval_seconds`、`jobs_worker_id` 和 `stage_messages_dir`。保留 `jobs_worker_mode` 的健康配置回显；`stage_message_lease_seconds` 被正式 `document_jobs/execution.py` 回调消费租约实际引用，必须保留。
- `tests/test_job_workflow_policy.py` 仅删除 14 个旧 workflow 转移测试及其导入，保留 4 个直接共享模型测试：旧状态投影、嵌套与平铺字段 patch 同步、嵌套上下文读取优先级、持久化兼容字段同步。4 项定向测试全部通过。
- 同步六份 backend Spec（database 部分承接仓储分工已完成的修改）及运行手册、系统架构、开发结构、可观察性、health/ops API 当前说明。历史架构调查文档保持不变。
- 文档明确旧三表 `jobs`、`job_files`、`stage_messages` 留待 B08 治理，本次不 DROP；`job_events` 仍由正式事件仓储使用。
- metrics 的旧 `jobs`、`stage_messages` 保留空对象兼容，不再读取旧仓储；stage spool 观察与告警已移除。
- 真实 Slack pilot 固定许可仍是 `stage_spool_failed_messages_present`，健康不再产生该码，active-alert 门禁因此无法满足。当前不扩大真实外发许可；后续迁移另行授权，合成安全测试不是正式发送可用证据。fake outbox/destination dry-run 文档示例使用正式 callback 告警。
- 新改模块说明和任务文档使用中文；未改动正式回调和共享快照行为。

补充验证：模型/配置/共享模型测试 3 个 Python 文件 AST 与内存编译通过；health/ops 文档全部 JSON 示例可解析；共享模型 4 项测试在删除 stage 模型后再次通过；新增删除符号在 app/scripts/tests 零引用，最终 diff whitespace 检查通过。
