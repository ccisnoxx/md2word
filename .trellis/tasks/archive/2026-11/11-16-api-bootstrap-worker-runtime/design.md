# 技术方案

## API 装配和初始化

`app/main.py` 保留一个装配入口。将 `build_runtime(settings, *, initialize=False)` 定为默认只装配，默认 API 工厂显式传 `initialize=True`。用同一个启动决策控制持久化初始化和 `run_startup_bootstrap`，移除只控制模板的 `bootstrap_templates`。schema 和目录准备先于服务使用仓储，后端工厂透传该决策，MySQL 和 SQLite 复用现有 `initialize` 参数。file 后端按该决策创建目录。SQLite 的初始化路径负责创建数据库父目录，术语规则 JSON 在实际 `save` 时准备父目录，读路径可以在目录缺失时保持只读。

`AuthService` 构造只绑定设置和仓储，现有的「仓储为空才导入配置用户」提取为显式调用。在 `run_startup_bootstrap` 中先执行该步骤，再保持验收记录、翻译术语、术语规则、翻译 Profile、模板登记和默认项核对的现有顺序。所有资源/后端适用条件保持现行含义，尤其是 MySQL 术语规则已存在时的 live store 同步、模板版本身份和线上默认指针。不更改 schema SQL、种子数据或资源选择算法。

默认 `create_app()` 是实际 API 初始化入口。显式传入的 `AppRuntime` 视为调用方已准备好的依赖，测试夹具显式准备 schema 和所需 seed（含目前隐式补登的模板），`create_app(runtime=...)` 接线时直接使用它。已有直接构造持久化适配器的测试与维护代码保留其默认初始化行为，依赖完整 Runtime 初始化的测试改为显式请求。OpenAPI 导出继续在临时环境调用 API 工厂。文件保留报告和术语规则修复 CLI 使用默认装配，读取 API 已准备的数据。术语规则修复中的草稿重建和提案清理由 `--apply` 控制。若草稿缺失，读取草稿的既有调用也可能创建草稿。显式迁移工具继续走原有入口。

## API 健康与编排

维护中的 Uvicorn 入口采用 `app.main:create_app --factory`（Python 入口传 `factory=True`）。工厂在 bind/serve 前同步完成装配和 bootstrap，异常使进程启动失败。现有 `app.main:app` 可供 ASGI 调用方继续使用。保留 API lifespan 的后台任务恢复，恢复扫描无需完成才开始服务。

dev/prod Compose 将 Worker 的 API 依赖改为 `service_healthy`，直接复用 `/api/v1/health/live`。该探针通过即说明本次 API 初始化已完成。`/api/v1/health/ready` 继续用于检查业务依赖，当前响应中的部分阻断条件位于 JSON 字段内，单靠 HTTP 200 不能判定业务可接单。避免把 Worker 消费或外部 Provider 状态变为 API bootstrap 的先决条件。

仓库 Compose 的依赖顺序用于 Compose 创建和启动服务。直接运行本地 Worker 入口时，首次使用的库和目录也应先由同一配置的 API 初始化。线上分层 Compose 经 `--no-deps` 更新时，以实际生效配置为准。发布步骤先暂停旧 Worker 的消费并完成正常退出，按同一份合并配置只更新 API，等待新容器的健康状态与版本可核对，再启动同镜像 Worker。`--wait` 只有在生效配置包含对应 healthcheck 时才提供健康门禁，否则须显式检查新容器的 `/api/v1/health/live`。API 初始化失败时保持 Worker 停止并检查 API 日志。已有数据的 Worker 单独重启继续由现有机制恢复，允许独立执行已排队任务。

## Celery 进程与配置时效

- 两个业务任务共用 Worker 模块内的进程级 Runtime 获取点；首次执行时构造，按 PID 判断归属，仅缓存成功创建的实例。由当前 prefork 的任务执行进程首次调用，进程替换或 fork 后不能命中其他 PID 的实例。模块 import、`document_jobs.ping` 和 Worker 的启动信号均不填充业务子进程缓存。无需把全量装配放进受启动时限约束的 `worker_process_init`。
- `worker_ready` 沿用现有恢复信号和 callback 跳过条件。轮询模式在主进程使用一次独立的只装配 Runtime，调用 `run_startup_recovery(trace_id="worker_startup", polling_only=True)`。保留原有扫描、入队、事件和日志行为。配置了 callback 的 Worker 读取 Settings 并应用现有日志配置后返回。
- Runtime 缓存的是服务实例。MinerU 与 AI 翻译 Provider 继续在发起调用时读取有效配置。MySQL 模板目录走实时仓储，任务资源快照及历史版本仍走原解析路径。file/SQLite 兼容路径使用 YAML manifest，Worker 跨任务复用时显式关闭该读取缓存，保留 API 的现有缓存和写入更新机制；覆盖同进程读取到另一进程更新后的 manifest。旧任务没有资源快照时走现行模板解析分支。

## 发布与回滚

沿用同镜像 API/Worker 和既有持久化卷。正式切换时先验证 API 初始化，后放开 Worker 消费。代码回滚时将 API 和 Worker 一并回到同一旧镜像，并采用先 API 健康、后 Worker 的顺序。本任务没有新增 schema 版本及业务数据改写步骤；现有 MySQL schema maintenance 可能部分提交，启动失败应保留原始错误，修复后按既有幂等路径重试。线上分层配置尚未核对，发布前需确认生效的启动命令和探针。当前单 API 实例部署是唯一写者约束，扩展为多 API 实例需另行设计协调。

## 依据

- [Docker Compose 启动顺序](https://docs.docker.com/compose/how-tos/startup-order/) · [Compose up 选项](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Celery 进程启动信号](https://docs.celeryq.dev/en/v5.6.3/userguide/signals.html#worker-process-init)
- 项目锁定 Uvicorn 0.47.0。已核对本地安装源码 `uvicorn/config.py::Config.load` 对工厂的调用，以及 `uvicorn/lifespan/on.py::LifespanOn` 对自动 lifespan 的异常处理。
- [现有装配顺序证据](../11-11-sr-3-composition-root/research/bootstrap-order.md) · [运行时配置合同](../../../../spec/backend/runtime-configuration.md)
