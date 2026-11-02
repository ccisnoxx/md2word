# 实施清单

1. `app/services/renderer/word_renderer.py`：计划阶段上下文辅助函数。
2. `app/services/renderer/evidence.py`：白名单新增三个 `operation_kind`。
3. `app/domains/document_jobs/execution.py`：有界循环、超时排除、`layout_plan` 后移。
4. `app/services/document_ir/page_degradation.py`：中文原因文案。
5. 测试：`tests/test_render_page_degradation.py`、`tests/test_render_failure_context.py`，同步 `test_page_degradation`、`test_degraded_page_display` 的文案断言。
6. Spec：`word-generation-rules.md` INPUT-002、`error-handling.md` P0-6。

验证：运行以下定向模块，不跑全仓回归。

`tests.test_render_page_degradation tests.test_render_failure_context tests.test_page_degradation tests.test_degraded_page_display tests.test_document_job_failure_diagnostic`
