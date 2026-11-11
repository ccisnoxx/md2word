# 去除执行协作者经 _host 调用宿主私有方法的耦合

父任务：`11-11-structure-refactor`（对应用户需求第 3 项）。

## 目标

`MinerUExecution`、`WordRenderExecution`、`TranslationBatchExecution` 不再持有 `DocumentJobExecutionService` 宿主引用，不再调用宿主的任何私有方法。共用的状态推进与事件记录由一个有明确公开接口的 owner 提供，协作者的依赖在构造函数中显式列出。

## 现状

- 三个协作者共 208 处 `self._host.*`：私有方法 91 处（`_record_event` 36、`_mark_failed` 33、`_get_uploaded_file` 6、`_fail_stage_attempt` 6、`_mark_timed_out_if_needed` 6、`_document_ir_layout_metadata` 3、`_mark_succeeded` 1），其余是读取宿主属性（`job_repository` 57、`file_service` 22、`settings` 16、`file_repository` 12 等），另有 1 处回调 `execute_job`。
- 测试直接调用宿主私有方法：`execution._mark_failed`（2 处）、`execution._fail_stage_attempt`（2 处）。

## 需求

1. 抽出任务状态推进/事件记录的 owner，提供公开方法：记录事件、标记失败、标记成功、超时检查、阶段尝试失败归类。宿主和三个协作者都通过它完成这些操作。
2. `_get_uploaded_file` 和 `_document_ir_layout_metadata` 改为无状态的公开函数。
3. 协作者构造函数显式接收所需依赖（`settings`、`job_repository`、`file_repository`、`file_service`、状态 owner 等），删除 `_host` 参数和属性。
4. 翻译协作者对 `execute_job` 的回调改为注入的 callable，并保持延迟绑定，使测试中 `patch.object(execution, "execute_job")` 继续生效。
5. 宿主自身的私有方法（`_mark_parsing_started`、`_mark_ir_converting_started` 等，测试会 patch）保持原名和原位置。
6. 测试中对宿主私有方法的调用迁移到新的公开接口，断言不变。

## 约束

- 行为完全不变：CAS 条件、事件 payload 收敛规则、日志格式、异常类型和错误码逐字保留。
- 协作者对外保持的属性不变：`execution.rendering.word_renderer`、`execution.translation_batches.document_ir_translation_service`、`.translation_audit_service`、`.translation_batch_task_queue`、`execution.mineru.config` 等（测试共计 100+ 处使用）。
- `DocumentJobExecutionService.__init__` 签名不变，`app/main.py` 不需要修改。
- `recovery.py` 中独立的 `_record_event` 不在本任务范围内，只记录观察结果。

## 验收标准

- [ ] `rg "_host" app/domains/document_jobs` 结果为 0。
- [ ] 三个协作者模块不导入 `execution.py`（`TYPE_CHECKING` 导入也去掉）。
- [ ] 定向测试通过：`test_document_job_execution_stages`、`test_document_job_result_persistence`、`test_translation_batch_failure_semantics`、`test_translation_batch_workflow`、`test_translation_integrity_execution`、`test_p1_translation_batch_diagnostics`、`test_mineru_download_boundary`、`test_mineru_result_root_uniqueness`、`test_render_failure_context`、`test_render_page_degradation`、`test_formal_mineru_render_evidence`、`test_document_worker_entrypoint`。
- [ ] `test_fastapi_jobs_backend` 通过（覆盖 eager 队列端到端执行路径）。
- [ ] `directory-structure.md` 中 document_jobs 协作者的描述已更新。
