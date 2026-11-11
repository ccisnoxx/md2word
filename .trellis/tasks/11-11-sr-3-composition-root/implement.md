# 实施计划

前置条件：sr-1、sr-2 已合入当前分支。

## 检查清单

- [ ] 0. 阅读第 2 节列出的中间构造函数，确认 bootstrap 能否后移；把结论写入 `research/bootstrap-order.md`。写一个临时脚本：patch 6 个 bootstrap 方法，记录调用顺序，在基线上运行 `build_runtime(test_settings)` 并保存结果（脚本放在任务目录，不进入 `tests/`）。
- [ ] 1. 抽出 `app/api/middleware.py`。检查：`test_backend_logging`。提交。
- [ ] 2. 抽出 `platform.py`、`terminology.py`、`health.py`。检查：`PersistenceAdapterTests`。提交。
- [ ] 3. 抽出 `document_pipeline.py`（含队列选择函数）。检查：`PersistenceAdapterTests`、`test_document_worker_entrypoint`。提交。
- [ ] 4. 抽出 `startup.py`，用第 0 步的脚本对比调用顺序，必须一致。检查：`test_fastapi_jobs_backend`、`test_openapi_export`、`test_runtime_dependency_declarations`。提交。
- [ ] 5. 验证 `.venv/bin/python -c "import scripts.ops.run_file_retention_cleanup_readonly"`；更新 `directory-structure.md`；运行 `trellis-check`。

## 回滚点

每一步一次提交；第 4 步依赖第 2、3 步。

## 定向测试集合

`tests.test_database_job_repository.PersistenceAdapterTests tests.test_backend_logging tests.test_document_worker_entrypoint tests.test_runtime_dependency_declarations tests.test_openapi_export tests.test_fastapi_jobs_backend`
