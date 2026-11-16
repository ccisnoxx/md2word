# 定向验证记录

## 验收证据

| 验收 | 本地证据 |
| --- | --- |
| AC1 | Uvicorn 工厂完成 SQLite 初始化后才可请求健康端点，注入模板 seed 失败时工厂加载失败。覆盖已有资源与模板默认、内部用户导入、验收初始化及 fake MySQL 的 schema 和种子。OpenAPI 导出继续在临时目录通过。 |
| AC2 | file/SQLite 使用临时目录，MySQL 使用 fake connection。空存储下 Worker 装配不创建目录也不发 SQL。已有存储装配前后比较目录结构和文件字节，并记录 fake MySQL SQL 调用。 |
| AC3 | 用占位环境对仓库 dev/prod Compose 运行 `config --quiet`，读取合并配置核对 `--factory`、`/api/v1/health/live`、`service_healthy` 和 API/Worker 镜像一致。 |
| AC4 | 两类任务调用覆盖按 PID 复用、失败后再构造。另用真实 `os.fork()` 和替身 Runtime 调用两类任务，验证父子进程分别装配一次。复用测试覆盖 MinerU/AI Provider 读取轮换配置及 legacy manifest 更新，旧任务的模板与快照路径通过既有回归用例。 |
| AC5 | 验证 callback 模式应用 `LOG_FORMAT=json`，跳过 Worker Runtime 装配及轮询恢复。轮询模式按 `polling_only=True` 调用现有服务，恢复使用独立装配。API 的 lifespan 恢复调用也通过定向测试。 |

## 测试结果

使用项目 `.venv/bin/python -m unittest`，以下 63 项通过。

- 53 项。涵盖 `tests.test_worker_template_bootstrap`、`tests.test_document_worker_entrypoint`、`tests.test_template_seed_history`、`tests.test_mineru_config`，以及计划中的三个验收、术语和认证初始化用例。
- 9 项。涵盖 file/SQLite/MySQL 运行时切换与 readiness、MySQL 资源版本服务、认证生命周期、绑定模板和历史任务渲染，以及模板 CRUD 和资源默认切换。
- 1 项。`tests.test_openapi_export.OpenAPIExportTests.test_export_openapi_writes_snapshot_and_check_passes`。

复核修正 callback 日志配置后，单独重跑对应的恢复测试并通过。另有真实 fork 验证、两份 Compose 配置解析、改动 Python 文件的 AST 解析、Trellis 上下文校验与 `git diff --check`。

## 验证边界

本轮的数据库证据来自临时 SQLite、文件后端和 fake MySQL，Compose 证据来自配置解析。真实 MySQL、Redis/Celery 的端到端编排及 hostdzire 生效配置需在相应环境中验证。保持任务处于 `in_progress`，本轮交付工作区实现和定向证据。
