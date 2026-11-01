# P0-6：渲染失败的页与块定位

## 目标与业务结果

渲染阶段（DocumentIR→DOCX）失败时，任务详情与异常中心像 MinerU 验证失败一样显示首个失败页、块 ID、操作类型与原因代码，而不只是笼统的 `render_failed`。不改变任何失败分类、错误码或渲染行为。

## 背景（基线 `main` `7b7c089b`）

- P0a 的 `failure_diagnostic` 只投影 `stage_failed.payload.mineru_validation`；其他阶段失败时为 `null`。
- 渲染器按 RenderPlan 逐个执行操作（`word_renderer.py` 主循环），每个操作带 `kind`、`section_id`、`block_ids`、`source_page_index`，v2 另有 `unit_id`，但异常抛出时这些上下文全部丢失。
- 渲染期异常类型：`TableRenderError(code, block_index)`、`TableBuildError(code, fragment_id, …)`、`TablePlaceholderError`、`DocumentIntegrityError("DocumentIR→DOCX", blocking_quality_flags=[code])`（`content_failure`/`render_contract_failure`），以及各类 `ValueError`。
- `execution._worker_failure_evidence` 只提取 MinerU 报告、占位错误报告和完整性证据；`build_renderer_event_summary` 以白名单过滤后写入事件。表格错误的定位只存在于错误消息文本。
- 循环之前的表格预处理（`prepare_table_input`）失败时只有 IR 块索引。

## 范围与要求

1. 渲染器在执行每个操作时捕获异常，把操作上下文（操作序号、类型、分节 ID、块 ID、源页索引、逻辑表格单元 ID）附加到异常对象后**原样重新抛出**；循环前的表格预处理失败按块索引补充块 ID 与页索引。
2. 执行层把该上下文与可识别的原因码（表格错误的 `code`、完整性错误的首个阻断码、否则为异常类型名的受控值）写入 `stage_failed` 事件的 `failure_context`，经白名单逐字段过滤。
3. `failure_diagnostic` 增加来源 `render_operation`：页码（1 起始，无页时 `scope=document`）、块 ID、操作类型、原因代码；MinerU 验证来源的行为不变。
4. 前端失败文案显示块 ID 与操作类型。
5. 不改变异常类型、`error_code`、`failed_stage`、重试语义与渲染输出。

## 决策（需用户确认）

- **D1 实现方式**：复用现有异常类型，在异常对象上附加上下文后原样抛出（推荐）；备选为新建 `ConversionBoundaryError` 统一包装（改变异常类型，需同步调整分类与既有测试）。
- **D2 范围**：只覆盖渲染阶段（操作循环与表格预处理）（推荐）；IR 转换阶段的完整性计数失败属于文档级，保持 `null` 或 `scope=document`。
- **D3 原因代码**：只输出受控值——表格错误 code、完整性阻断码（已在白名单）、或异常类型名白名单（`ValueError`、`KeyError` 等），不输出异常消息原文（推荐）。

### 决策记录

2026-11-02 用户确认 D1–D3 均按推荐：复用现有异常类型附加上下文；只覆盖渲染阶段；原因码只输出受控值。

## 非目标

- 不做部分成功与整页降级（P1）；不改质量检查阶段的文档级完整性错误；不改前端以外的展示合同。

## 验收条件

- AC1：表格渲染失败（如 `table_html_unsupported_structure`）时，详情与异常中心显示页码、块 ID、操作类型 `block`/`logical_table` 与原因码。
- AC2：图片或其他块在循环内抛出的 `ValueError`/完整性错误同样带上下文；页眉页脚装饰等无源页的操作 `scope=document`。
- AC3：循环前表格预处理失败按块索引得到块 ID 与页码。
- AC4：事件 payload 只含白名单字段；异常类型、错误码、失败阶段与改动前一致；既有渲染测试结果与基线一致。
- AC5：MinerU 验证失败的诊断输出不变。
