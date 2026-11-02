# 实施计划

1. 基线：`test_page_degradation`、`test_render_failure_context`、`test_document_job_failure_diagnostic`、`test_image_pdf_fallback`、`test_document_job_delivery_state_api`、`test_fastapi_jobs_backend` 中渲染/恢复相关用例、`test_document_ir_word_renderer_layout`。
2. 抽出 `page_degradation.py`，converter 改为调用它；先跑 `test_page_degradation` 确认 C1 行为不变。
3. 新增 `drop_degraded_table_groups` 与重新校验。
4. 执行层：失败捕获、前提判断、栅格、登记新 IR、条件切换指针、事件、重渲染一次。
5. 质量信号：来源对账字段、证据白名单、`base_quality` blocker。
6. 测试：新增 `tests/test_render_page_degradation.py`（design 第 4 节）。
7. 规格：INPUT-002 / IR-004 降级合同补充渲染阶段触发；如有质量条目同步。
8. 回归对比基线失败集合；真实样本可选（需要可复现的渲染失败输入，若无则只做 eager 端到端）。

## 实施结果与验证（2026-11-02）

- 代码：新增 `app/services/document_ir/page_degradation.py`（`degradation_closure`、`replace_degraded_pages`、`drop_degraded_table_groups`），converter 的 C1 路径改为调用它；`execution._degrade_render_failure_page` 与 `_render_and_save_word` 中的一次重渲染；`integrity` 输出 `render_degraded_page_count`（证据数值白名单同步）；`base_quality` 计入 blocker。
- 设计偏差：降级事件复用 `file_registered`（`stage=rendering`，payload 含新/旧 IR 文件、降级页、白名单后的 `failure_context`）；替换后 IR 若不再自洽（如保留组的续表诊断指向被删片段）由 `DocumentIR.model_validate` 拒绝并放弃降级，不另写专门判断。
- 测试：新增 `tests/test_render_page_degradation.py` 3 项通过（成功降级与指针/结果绑定/质量/批准被拒/DOCX 含整页图；无栅格器、基础设施错误、超阈值、重渲染仍失败；表格组移除后 IR 重新校验通过）；`tests/test_page_degradation` 与 `test_image_pdf_fallback` 13 项保持通过。
- 回归：12 个相关模块 207 项与基线（同一 HEAD 的临时 worktree）失败集合完全一致；`tests.test_fastapi_jobs_backend` 217 项失败集合与基线一致，均为既有失败。
- 未验证：Worker 在指针切换后、重渲染前中断的重投路径未单独构造用例（重投读取的就是任务当前 `document_ir_file_id`，与正常渲染同一路径）；跨页表格组在渲染阶段的闭包由 C2 的共用闭包单测覆盖，未构造真实跨页续表的端到端用例；无真实渲染失败样本。
