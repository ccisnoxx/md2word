# 实施计划

每一步完成后执行对应验证；每步一个提交（提交需用户另行授权）。

## 0. 基线

- [ ] 记录 `app.openapi()` 输出到 `/tmp/md2word-refactor/openapi.before.json`。
- [ ] 记录受影响测试基线（`.venv/bin/python -m unittest ...`，见下方列表）。

## 1. translation_execution 包化

1. 建立 `translation_execution/` 包与七个组件模块，按 design.md §2.1 逐字迁移方法体。
2. 门面 `TranslationBatchExecution` 组装组件，提供 §2.3 公开方法。
3. `execution.py` 改用 `start_generation / finalize_generation`。
4. 测试改用 `translation_batches.runner.claim`、`translation_batches.planner.build_expected_plans`、`translation_batches.finalize_generation` 等公开入口。
5. 验证：`test_translation_batch_failure_semantics`、`test_translation_integrity_execution`、`test_document_job_execution_stages`、`test_translation_batch_workflow`、`test_translation_batch_repository`、`test_p1_translation_batch_diagnostics`、`test_translation_table_context`。

## 2. router 与应用层接口

1. `queries.get_translation_batch_snapshot` 返回 `TranslationBatchListView`；composition 注入 summarizer。
2. 下载/发布物下载令牌与 TTL 迁入用例（§3.2）。
3. router 拆为 `router.py` + 三个子路由 + `http_responses.py`（§3.3）。
4. 验证：OpenAPI 逐字节相同；`test_fastapi_jobs_backend`、`test_document_job_download_availability_api`、`test_document_job_delivery_state_api`、`test_document_job_modes`。

## 3. schemas 包化

1. 逐字迁移模型到六个子模块，更新全部导入方。
2. 验证：OpenAPI 逐字节相同；`python -c "import app.main"`；第 2 步测试集。

## 4. 预览与渲染

1. 抽出 `preview_evidence.py`、`render_placeholders.py`、`render_result.py`；`MinerUExecution` 私有入口改公开名。
2. 验证：`test_word_preview_historical_replay`、`test_document_job_result_persistence`、`test_render_page_degradation`、`test_render_failure_context`、`test_rnd503_dependency_integration`、`test_mineru_download_boundary`、`test_document_job_execution_stages`。

## 5. 收尾

- [ ] `rg` 跨对象私有访问检查；router 不引用 `document_job_execution_service`。
- [ ] 更新 `directory-structure.md`、`translation-batch-lifecycle.md`。
- [ ] 检查 diff：无无关格式化、无死代码、无遗留转发层。
