# 技术设计（按推荐决策）

## 1. 渲染器：附加操作上下文（owner：`word_renderer.render_to_result`）

- 主循环改为 `for index, operation in enumerate(plan.operations):`，循环体包在 `try/except Exception as error:` 中：
  `_attach_failure_context(error, {...})` 后 `raise`（不包装、不改变异常类型、不吞异常）。
- 上下文：`operation_index`、`operation_kind`、`section_id`、`block_ids`、`source_page_index`、`unit_id`（v2）。
- 只在首次附加（内层更具体的上下文优先），属性名 `md2word_failure_context`。
- 循环前 `prepare_table_input` 的字典推导改为显式循环，捕获 `TableRenderError`/`TableBuildError`，按 `document_ir.blocks` 的块 ID 与页索引附加上下文（`operation_kind="table_prepare"`）。

## 2. 执行层：结构化落库（owner：`execution._worker_failure_evidence`）

- 读取 `getattr(error, "md2word_failure_context", None)`；原因码按顺序取：`TableRenderError/TableBuildError.code`、`DocumentIntegrityError.evidence["blocking_quality_flags"][0]`、异常类型名。
- 写入 `evidence["failure_context"]`，交由 `build_renderer_event_summary` 白名单过滤。

## 3. 白名单（owner：`renderer/evidence.py`）

`failure_context` 逐字段：

| 字段 | 规则 |
|---|---|
| `operation_index` | 非负 int |
| `operation_kind` | {section, configure_page, decoration, block, image_pair, column_break, logical_table, table_prepare} |
| `section_id`、`unit_id` | 现有 ID 正则（`[A-Za-z0-9:_-]{1,120}`） |
| `block_ids` | ≤ 20 个，块 ID 正则 |
| `source_page_index` | 非负 int 或 null |
| `reason_code` | 表格错误码集合 ∪ 受控质量标记（`controlled_quality_flags`）∪ 异常类型名白名单 |

非法字段丢弃；整体不合法则不写 `failure_context`。

## 4. 投影（owner：`failure_diagnostic.project_failure_diagnostic`）

- 先按现状处理 MinerU 报告；否则读取当前代 `stage_failed` 的 `failure_context`（同样要求 `retry_count` 匹配，`_record_event` 对含 `failure_context` 的 payload 附 `retry_count`）。
- DTO：`source` 扩展为 `Literal["mineru_validation", "render_operation"]`；新增 `block_ids: list[str]`、`operation_kind: str | None`；`affected_page_numbers` 为该页；`fatal_count=1`。
- 前端 `failureDiagnosticLines`：渲染来源显示“首个失败位置：第 N 页（块 block_0012，操作 logical_table）”。

## 5. 兼容

- 新增字段全部可空；历史事件无 `failure_context` → 诊断为 `null`（现状）。
- OpenAPI 快照仍处于基线过期状态，不在本任务更新（与 P0a 一致）。

## 6. 测试

- 渲染器：fake 表格/图片使特定操作抛错，断言异常类型不变且带上下文；装饰操作无源页；预处理失败的块定位。
- 执行与 API：eager Worker 渲染失败任务，详情与诊断接口返回 `render_operation` 诊断；payload 仅白名单字段。
- 白名单：非法 ID、超长列表、未知类型名被丢弃。
- 前端：util 单测新增渲染来源文案。
