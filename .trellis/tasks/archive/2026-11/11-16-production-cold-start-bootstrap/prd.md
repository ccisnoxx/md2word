# 生产冷启动单一初始化

## 目标

使用一条标准生产 Compose `up` 命令启动空 MySQL 环境。API 完成初始化后，Worker 首次启动即能执行恢复和消费任务，无需操作人员手动分批启动。

## 已确认的现状

- Worker 就绪恢复、普通任务和翻译批次都构建 Runtime。当前选项仅跳过模板 seed，其余 seed、内部账号导入和 MySQL schema 维护仍可从 Worker 触发。证据见 `app/workers/document_tasks.py:19`、`app/composition/startup.py:16`、`app/services/auth/service.py:83`、`app/infrastructure/persistence/mysql/backend.py:38`。
- Translation Profile 首次登记跨多次数据库操作，重叠执行可触发资源版本主键冲突。生产 Compose 的 Worker 对 API 使用 `service_started`。已有模板目录验收按 API、Worker 分两次启动，避开了这条路径。证据见 `app/domains/translation/profiles_service.py:676`、`app/infrastructure/persistence/mysql/resources.py:100`、`docker/prod/docker-compose.yml:54`、`tests/integration/template_catalog_compose.py:429`。

## 需求

- **R1** 在正常服务启动路径中，API 负责 SQL schema 创建和维护、内部账号初次导入，以及 Acceptance、Translation Term、Term Rule、Translation Profile 和模板 seed。Worker 的三个入口共用同一装配模式，跳过这些初始化。正常恢复、任务状态写入和业务产物生成沿用原有合同。
- **R2** 生产 Compose 在 API 初始化完成后启动 Worker。若 API 初始化失败，Worker 不进入消费。开发 Compose 和本地手动启动沿用相同的先后顺序。
- **R3** 初始化保持既有数据兼容性。现有默认资源、已登记版本、账号和任务可以继续使用，API 重启的初始化沿用现有幂等规则，已初始化环境可单独重启 Worker。

## 验收标准

- **AC1（R1）** 定向验证覆盖 Worker 启动恢复、普通任务和翻译批次，证明各入口装配 Runtime 时均无 schema、seed 或账号初始化。验证默认 API 启动仍完成账号和资源登记。
- **AC2（R2）** 使用隔离的空 MySQL、Redis 和共享卷，从仓库生产 Compose 通过一次 `up` 成功拉起全栈。记录 API 首次健康检查和 Worker 首次启动顺序，校验资源与账号可用、Worker 可消费真实 Celery 队列任务并生成 DOCX。使用可控的 API 初始化失败场景，验证 Worker 未启动消费。
- **AC3（R3）** 使用已有账号、已发布默认资源和任务产物的数据集。分别重启 API 和 Worker 后，比较既有记录、默认指针和产物校验值，并验证后续任务可完成。

## 范围边界及后续议题

交付范围为仓库内的启动实现、标准编排、文档和隔离验收。进程级 Runtime 缓存、独立 migration job、多 API 实例并发初始化与 hostdzire 实机部署分别作为后续议题。现有 schema SQL、seed 内容、API 合同和 Celery 业务行为继续沿用。
