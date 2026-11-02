# 技术设计（按推荐决策，确认后细化）

## 1. 共用页替换（`app/services/document_ir/page_degradation.py`，新增）

C1 的 `_degrade_pages` 里“替换块、登记合成块与资产、写记录”部分搬到共用函数，converter 与执行层各调一次，避免两份实现：

- `degradation_closure(groups, candidate_pages) -> set[int] | None`：由 converter 的 `_degradation_closure` 迭代部分抽出；converter 仍先在副本上试算挂接表格组再调用它，执行层直接用 IR 中已挂接的组。
- `replace_degraded_pages(document, rasters, reasons, *, source_pdf_sha256, dpi, trigger) -> (removed_ids, list[PageRaster])`：移除降级页全部块，插入提示段落 + 整页图像块（`metadata.synthetic="degraded_page"`），移除被删块引用的资产与质量标记，追加 `metadata.degraded_pages` 记录（新增 `trigger`），返回待登记的整页图像。
- 执行层额外调用 `drop_degraded_table_groups(document, removed_ids)`：删去全部片段都在降级页的逻辑表格组、`table-reference:*` / `table-placeholder:*` 资产、对应占位绑定，并重算 `logical_table_group_counts`。converter 路径在挂接前降级，不需要这一步。
- 结束时以 `DocumentIR.model_validate(document.model_dump())` 重新校验（含逻辑表格组与占位解码），不输出半合法 IR。

## 2. 执行层（`execution._render_and_save_word`）

在 `render_to_result` 外包一层：

1. 捕获异常 `exc`，读取 `failure_context`；不满足 PRD 范围第 1、3 条 → 原样抛出（沿用现有失败路径与诊断）。
2. 候选页 = `{source_page_index}`；闭包；阈值（含已降级页）；已降级页再失败 → 抛原异常。
3. `_load_placeholder_source(job)` + `page_rasterizer.rasterize`；任一失败 → 抛原异常。
4. 替换后登记整页图像（metadata 同 C1：`origin=pdf_page_raster`）与新 IR 文件（`object_version` 带代次，metadata 与原 IR 文件一致外加 `degraded_from_document_ir_file_id`）。
5. 条件更新：`allowed_stages={"rendering"}`、`expected_document_ir_file_id=旧 IR`、`require_no_prepared_result=True`，写入新 `document_ir_file_id` 与追加后的 `image_asset_file_ids`；失败 → `_finish_selected_or_current`。
6. 记录事件：复用 `file_registered`（`stage="rendering"`，payload 含新 IR 文件 ID、降级页码、`operation_kind`、`reason_code`；不含异常消息）。
7. 用新 IR 重建 `layout_plan` 与 image loader 后重新渲染一次；再失败直接抛出，按现有分类整体失败。
8. 后续质量检查、结果登记、`prepare_document_job_result` 全部使用新 IR 文件与新任务记录。

页栅格器注入：`DocumentJobExecutionService` 复用 `document_ir_service.page_rasterizer`，不新增装配点。

## 3. 质量信号

- `integrity.build_source_integrity` 输出新增 `render_degraded_page_count`（`trigger == "render"` 的记录数），加入 `renderer/evidence.py` 数值白名单。
- `base_quality`：`blockers += source.get("render_degraded_page_count", 0)`（需为非负整数，否则 `complete=False`）。

## 4. 测试

- 共用函数：表格组删除后 IR 重新校验通过；闭包与 C1 共享用例不回归（`tests/test_page_degradation.py` 全部保持通过）。
- 执行层（eager，patch `_render_block` 在某页抛 `ValueError`）：任务成功、新 IR 指针、提示 + 整页图像、blocked/internal_draft、批准被拒、事件不含异常消息。
- 跨页表格组失败时整组降级；含合并回执、无页码、`OSError`、超过阈值、翻译任务、重渲染仍失败 → 原失败诊断。
- 中断恢复：在切换指针后模拟中断，重投直接按新 IR 渲染成功。
