# 集中 API 启动初始化并复用 Celery Worker Runtime

## 目标

API 独占服务启动时的 schema 和种子初始化。开发与生产 Compose 中，Worker 在 API 完成初始化并通过健康探针后开始消费。每个 Celery 任务执行子进程首次需要时构造 Runtime，在后续文档任务和翻译批次中复用。保留 Worker 单独重启时唤醒已知 MinerU 轮询任务的能力。

## 已确认的现状

- `app/workers/document_tasks.py:19–58` 的文档任务、翻译批次任务和 `worker_ready` 都调用 `build_runtime(bootstrap_templates=False)`。`app/composition/startup.py:16–40` 仍会初始化验收记录、翻译术语、术语规则和翻译 Profile。MySQL 已有默认规则时仍同步 live store、YAML 和 SQL 明细（`app/domains/term_rules/versioning_service.py:720–725,935–940`）。
- `app/infrastructure/persistence/factory.py:211–237` 构造持久化适配器时准备目录，MySQL 和 SQLite 后端还会执行 schema 初始化。`app/services/auth/service.py:83–86,182–191` 在构造认证服务时可能导入内部用户。
- dev/prod Compose 当前用 `service_started`，已有的 API 健康探针请求 `/api/v1/health/live`。线上部署记录另有使用 `--no-deps` 的分层 Compose 路径（`docs/deploy/hostdzire-dmit-md2word.md:59–100`），依赖等待需要由发布步骤显式兑现。

## 需求与验收

| 编号 | 需求 | 验收结果 |
| --- | --- | --- |
| AC1 | API 独占启动初始化 | 从空存储启动 API，现有 schema 和当前后端支持的 seed 均就绪后健康探针才成功。范围包括配置内部用户、验收记录、翻译术语、术语规则、翻译 Profile、模板目录/版本和默认项。用已有存储再次启动，保留现有用户、已登记版本和运营设置的默认项，继续遵守既有规则同步及 schema maintenance。初始化失败时探针无法成功。 |
| AC2 | Worker 装配只读 | 文档、翻译批次及启动恢复入口使用的 Runtime 装配均跳过目录初始化、数据库 schema、所有 seed、账号导入和模板默认项解析。Worker 任务执行以及既有启动恢复仍可按业务合同写入。 |
| AC3 | 启动顺序由正常入口保证 | dev/prod Compose 等待 API 健康后才在首次编排启动 Worker。分层部署文档给出 `--no-deps` 下先验收新 API、再启动同一镜像 Worker 的顺序，以及健康失败的处理。 |
| AC4 | 子进程复用且保持配置时效 | 同一执行进程的文档任务和翻译批次共用首次成功创建的 Runtime，进程变化后重新装配。复用时，任务仍按现有约定读取新的 MinerU/AI Provider 配置、模板版本和历史任务资源。 |
| AC5 | 保留 MinerU 启动恢复 | callback 配置存在时跳过 Worker 轮询恢复。轮询模式仍在 `worker_ready` 通过现有服务以 `polling_only=True` 唤醒已知任务。API 的现有启动恢复继续运行。 |

## 范围边界

本轮规划覆盖应用装配、Celery 入口、仓库 Compose 与受影响的部署说明。schema SQL、seed 内容、用户认证语义、业务重试协议及健康响应合同沿用现行定义。数据库权限拆分、多 API 实例间的初始化协调、独立 migration job 和生产部署另行处理。
