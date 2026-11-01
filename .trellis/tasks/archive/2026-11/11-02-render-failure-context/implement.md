# 实施计划

前置：D1–D3 获确认后 `task.py start`。

## 1. 有序任务

1. 基线：`test_document_ir_word_renderer_layout`、`test_image_group_rendering`、`test_document_job_failure_diagnostic`、`test_image_pdf_fallback`、`test_fastapi_jobs_backend -k render`，记录失败集合。
2. 测试先行：渲染器上下文、执行与 API 投影、白名单、前端文案。
3. 渲染器：操作循环与表格预处理附加上下文。
4. 执行层与白名单：`failure_context` 落库与过滤；`_record_event` 附 `retry_count`。
5. 投影与 DTO、前端类型与文案。
6. 规格：`error-handling.md` 失败定位投影章节补充渲染来源。

## 2. 验证

- 定向后端测试与基线对比；前端 `vitest` 相关单测与 `npm run build`（需临时链接依赖，结束后删除）。
- 不跑全仓回归与 Playwright。

## 3. 回滚点

回退提交即恢复渲染失败诊断为 `null`；无数据迁移。

## 4. 实施结果与验证（2026-11-02 北京时间）

- 渲染器：操作循环与表格预处理捕获异常后附加定位并原样抛出；块类操作无页索引时取首块渲染决策的源页（实施中发现 RenderOperation 仅分节类操作带页索引）。
- 执行层/白名单/投影/前端：按 design 实现；DTO 新增 `block_ids`、`operation_kind`，`source` 增加 `render_operation`。
- 测试：新增 `tests/test_render_failure_context.py` 4 例（操作失败保留类型并带定位、预处理按块定位、白名单、eager 端到端）；P0a 测试 3 处精确字典期望补入两个新字段默认值。对比集 118 例（基线 114 + 4），1 个既有错误与基线一致；fastapi 异常中心/渲染/完整性相关 3 例通过。前端 `failureDiagnostic.test.ts` 5 例通过，`npm run build` 通过（临时依赖软链接已删除）。
- 已知限制：普通异常的 `error_message` 仍含异常消息原文（既有行为）；OpenAPI 快照仍为基线过期状态未更新；循环外的 `build_content_table_plan` 失败无块定位，诊断为 null。
