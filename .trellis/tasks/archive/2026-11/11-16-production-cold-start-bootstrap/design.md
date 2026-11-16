# 生产冷启动单一初始化设计

## 启动职责

在 `app/main.py` 的 `build_runtime` 用一个内部关键字 `bootstrap` 控制启动写入，默认开启。将现有仅针对模板的内部选项替换为整体开关。API 和现有默认调用方继续使用默认模式。三个 Celery 入口都使用 `bootstrap=False`，其中包括在 Worker 主进程里的 `worker_ready` 恢复，以及在任务执行进程里的普通任务和翻译批次。

| 阶段 | API 默认装配 | Worker 装配 |
| --- | --- | --- |
| 持久化适配器 | SQLite、MySQL 执行现有 schema 初始化和维护 | 传递到现有后端 `initialize=False`，仅装配仓储 |
| 平台服务 | `AuthService` 沿用空库导入配置用户的规则 | 构造服务时跳过账号导入及其空库探测 |
| 启动 seed | 执行 `run_startup_bootstrap` 的全部步骤 | 跳过整个启动 seed 调用 |
| 正常执行 | 保有 API 异步任务恢复及业务访问 | 保有 MinerU 轮询恢复、队列执行及业务写入 |

复用 SQLite、MySQL 后端已有的 `initialize` 参数，由持久化工厂透传。`AuthService` 的内部构造开关默认仍导入，通过 `build_platform_services` 接收同一装配决策，保留直接构造和 API 认证行为。文件后端已有的幂等目录创建继续作为存储装配的一部分。启动期初始化与任务恢复的业务写入分别沿用各自现有入口。

API 维持 schema、平台装配及账号初次导入、业务服务装配、启动 seed 的原有顺序。`run_startup_bootstrap` 只需保留一条完整流程。`create_app(runtime=...)` 保留显式注入 Runtime 时的既有模板登记语义。启动错误按现有规则暴露，Worker 路径没有自动初始化兜底。

## Compose 和手动启动

生产和开发 Compose 的 Worker 对 API 都使用 `condition: service_healthy`。沿用 API 的 `/api/v1/health/live` 探针。标准 API 必须先完成同步 Runtime 初始化才能响应该探针。`/health/ready` 的业务依赖结果通过响应体提供，保留原有运维用途。已有 MySQL 和 Redis 健康依赖继续适用。Compose 依赖约束 `up` 的启动顺序，独立重启和 Docker 自身的重启策略沿用现有行为。[Docker Compose 启动顺序](https://docs.docker.com/compose/how-tos/startup-order/)

本地命令行按启动 API、等待 `/health/live` 成功、启动 Worker 的顺序操作。hostdzire 部署记录使用冻结基础 Compose、多层 override 和 `up --no-deps`，仓库标准 Compose 的依赖声明无法约束该路径。部署说明应写清这类入口在首次接管或 schema 变更时，由实际编排等待新 API 初始化后再放行 Worker。线上生效需以真实配置和单独授权的上线验收为准。[线上编排记录](../../../../../docs/deploy/hostdzire-dmit-md2word.md#分层-override-上线当前生产方式) · [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)

## 兼容与回滚

本方案面向标准编排中的单 API 服务初始化路径。若今后并行启动多个 API 进程或同时运行手动初始化工具，需要另外协调初始化所有权。已有 MySQL/SQLite 数据由 API 沿用原 schema 维护和 seed 检查，默认值及已发布资源继续按原规则读取。Worker 单独重启只要求其依赖的 schema 和数据已经初始化。

回滚以同一版本成对回退 API/Worker 镜像和 Compose 为单位，保留数据库与共享卷。此任务没有新增 schema SQL、数据迁移或持久化格式。回退到旧版本的全新环境可沿用已有验收采用的先 API 后 Worker 启动顺序。
