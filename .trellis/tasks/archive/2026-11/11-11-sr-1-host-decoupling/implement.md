# 实施计划

Python：`.venv/bin/python`（在 worktree 中使用主仓库的 venv）。测试命令形如 `.venv/bin/python -m unittest tests.<module>`。

## 检查清单

- [x] 0. 记录基线：运行第 4 节中的定向测试，记录通过/失败情况（已有的失败单独列出，不在本任务修复）。
- [x] 1. 新增 `execution_support.py`，搬入 `DocumentJobLifecycle`、`require_uploaded_file`、`document_ir_layout_metadata`；宿主删除对应私有方法，改为使用 `self.lifecycle`；协作者暂时使用 `self._host.lifecycle.*`；修改测试调用点。
      - 检查：`test_document_job_execution_stages`、`test_document_job_result_persistence`。
      - 提交 1。
- [x] 2. `MinerUExecution` 改为显式依赖。检查：`test_mineru_download_boundary`、`test_mineru_result_root_uniqueness`、`test_document_job_execution_stages`。提交 2。
- [x] 3. `WordRenderExecution` 改为显式依赖。检查：`test_render_failure_context`、`test_render_page_degradation`、`test_formal_mineru_render_evidence`、`test_document_job_result_persistence`。提交 3。
- [x] 4. `TranslationBatchExecution` 改为显式依赖并注入 `resume_job`。检查：`test_translation_batch_failure_semantics`、`test_translation_batch_workflow`、`test_translation_integrity_execution`、`test_p1_translation_batch_diagnostics`。提交 4。
- [x] 5. 收尾：`rg "_host" app/domains/document_jobs` 结果为 0；`rg "from app.domains.document_jobs.execution import" app/domains/document_jobs/*_execution.py` 结果为 0；更新 `directory-structure.md`；运行 `test_fastapi_jobs_backend`、`test_document_worker_entrypoint`。提交 5。

## 审查关口

- 每一步都检查 `git diff`：被搬移的方法体除改名外不得有任何改动（可用 `git diff --color-moved` 辅助核对）。
- 第 5 步完成后运行 `trellis-check` 审查。

## 回滚点

每个提交都可以单独 revert；第 2–4 步互相独立，都只依赖第 1 步。

## 执行记录（2026-11-11）

- 基线（HEAD `0c9a7923`）上已有历史失败：12 个定向模块中 82 项（主要是测试仍按旧签名调用 `_build_image_loader()`），`test_fastapi_jobs_backend` 中 35 项。这些属于历史测试维护，不在本任务修复范围内。
- 判定方式：`validation/failset.sh` 提取失败用例标识（包括子测试参数），`validation/check.sh` 与基线对比。每一步完成后，失败集合都与基线完全一致，没有新增也没有消失。
- publication fixture 的 4 个使用方（`test_document_job_list_publish_light_check`、`test_document_job_list_query_v2_service`、`test_document_job_list_query_v2_writers`、`test_document_job_incident_publish_light_check`）在 `git archive HEAD` 导出的副本上和当前分支上都全部通过。
- 方法搬移的逐字一致性：从 HEAD 取出 6 个原方法，套用相同的改名规则后，都能在 `execution_support.py` 中原样找到。
- 设计偏差：`DocumentTranslationBatchTaskQueueProtocol` 从 `execution.py` 移到唯一的消费方 `translation_execution.py`，这样协作者连类型导入也不再依赖宿主模块。publication fixture 在构造后替换 `job_resource_snapshot_service`，现在同时把新值同步到渲染和翻译协作者（design §4 预先标出的情况）。
- 各步骤没有单独提交：按项目规则，提交前需要用户先确认提交计划，因此全部完成后统一提交。

## 定向测试集合

`tests.test_document_job_execution_stages tests.test_document_job_result_persistence tests.test_translation_batch_failure_semantics tests.test_translation_batch_workflow tests.test_translation_integrity_execution tests.test_p1_translation_batch_diagnostics tests.test_mineru_download_boundary tests.test_mineru_result_root_uniqueness tests.test_render_failure_context tests.test_render_page_degradation tests.test_formal_mineru_render_evidence tests.test_document_worker_entrypoint`，收尾时加上 `tests.test_fastapi_jobs_backend`。
