# 实施计划

前置条件：sr-1、sr-2 已合入当前分支。

## 检查清单

- [x] 0. 阅读第 2 节列出的中间构造函数，确认 bootstrap 能否后移；把结论写入 `research/bootstrap-order.md`。写一个临时脚本：patch 6 个 bootstrap 方法，记录调用顺序，在基线上运行 `build_runtime(test_settings)` 并保存结果（脚本放在任务目录，不进入 `tests/`）。
- [x] 1. 抽出 `app/api/middleware.py`。检查：`test_backend_logging`。提交。
- [x] 2. 抽出 `platform.py`、`terminology.py`、`health.py`。检查：`PersistenceAdapterTests`。提交。
- [x] 3. 抽出 `document_pipeline.py`（含队列选择函数）。检查：`PersistenceAdapterTests`、`test_document_worker_entrypoint`。提交。
- [x] 4. 抽出 `startup.py`，用第 0 步的脚本对比调用顺序，必须一致。检查：`test_fastapi_jobs_backend`、`test_openapi_export`、`test_runtime_dependency_declarations`。提交。
- [x] 5. 验证 `.venv/bin/python -c "import scripts.ops.run_file_retention_cleanup_readonly"`；更新 `directory-structure.md`；运行 `trellis-check`。

## 执行记录（2026-11-11）

- 第 0 步：分析见 `research/bootstrap-order.md`。录制工具 `tools/record_bootstrap_order.py` 对 file、database 两种后端分别录制了重构前后的调用顺序（`validation/bootstrap-order-{baseline,after}.json`）。两份录制的调用集合一致，显式 bootstrap 之间、构造期副作用之间各自的相对顺序也一致。唯一的变化是显式 bootstrap 整体移到了全部构造之后，research §3 已说明这一变化不影响持久化结果。
- 与设计的差异：`health.py` 对外提供 `build_observability_services`，同时返回健康检查和告警投递端口；`saved_view_service`、`resource_version_service` 归入 `platform`；`DocumentJobIncidentService` 归入 `document_pipeline`。`main.py` 为 163 行，其中约 60 行是 `AppRuntime` 的显式关键字参数，按设计 §3 保留，不用 `**asdict()` 合并。
- 回归（基线来自 `git archive HEAD` 导出的副本，HEAD 为 `26706a5d`）：定向集合（`PersistenceAdapterTests` 含 fake MySQL 分支、logging、worker 入口、依赖声明、OpenAPI、fastapi 后端、saved_views API、acceptance center API）的失败集合与基线一致，都是 35 项历史失败。
- `scripts/ops/run_file_retention_cleanup_readonly.py` 可以正常导入。
- 各步骤没有单独提交，按项目规则统一向用户提交计划后再提交。

## 回滚点

每一步一次提交；第 4 步依赖第 2、3 步。

## 定向测试集合

`tests.test_database_job_repository.PersistenceAdapterTests tests.test_backend_logging tests.test_document_worker_entrypoint tests.test_runtime_dependency_declarations tests.test_openapi_export tests.test_fastapi_jobs_backend`
