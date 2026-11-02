# 技术设计

## 1. 验证器（`artifact_validator`）

- `complete_validation`：无法解析表格 HTML 的问题若有 `page_index`，保持非中止并在块上标记 `_mineru_degradable`；无页码者照旧中止。图片沿用 P0-4 的 `_mineru_image_fallback` 推迟。
- 已有其他中止错误时，所有推迟问题（图片与表格）恢复为中止后抛出。
- 统一结算：`resolve_deferred(pointer, codes, recovered)` 复用 P0-4 计数逻辑；`resolve_image_fallback` 委托给它。降级成功时问题保持非中止 blocker（不改动）。

## 2. 转换器（`mineru_converter._convert_blocks`）

1. P0-4 回退改为返回 `(crops, failed_pointers)`，不再在内部抛出。
2. 构建块时，回退失败或表格 HTML 不可解析的块照常生成 IR 块（失败图片 `asset_ref=None`）。
3. `DocumentIR` 构建后、挂接表格组前执行 `_degrade_pages(...)`：
   - 候选页 = 可降级块的页；任一可降级块无页码 → 放弃降级。
   - 试算：深拷贝文档挂接表格组；跨越降级页的组并入其全部页，迭代到稳定；组内有 `block_id is None` 的片段（合并回执）→ 放弃降级。
   - 阈值：降级页数 × 2 > 页面总数 → 放弃降级。
   - 栅格化每个降级页；任一失败 → 放弃降级。
   - 放弃降级：所有推迟问题恢复中止，抛出 `MinerUArtifactValidationError`。
   - 成功：移除降级页的块、图片资产与引用这些块的质量标记；在首个被移除块的位置插入提示段落与整页图像块（`metadata.synthetic="degraded_page"`）；写 `metadata.degraded_pages`；过滤表格来源账本中降级页的表与正文位置。
4. 之后照常挂接表格组、表格引用、占位与完整性对账。

## 3. 栅格器（`infrastructure/pdf_crop.py`）

`PopplerPdfPageRasterizer.rasterize(source, page_index) -> bytes`：校验 PDF 字节与 checksum，`pdftoppm -f N -l N -singlefile -r 144 -png`，校验 PNG 与像素上限；失败抛 `TablePlaceholderError("table_placeholder_crop_failed")`。`MinerUToDocumentIRService(page_rasterizer=...)` 注入，`main.py` 装配。

## 4. 来源对账（`integrity.build_source_integrity`）

- 主块排除 `metadata.synthetic` 的块；降级源块数量与类型计数加回实际计数后再与期望比较；输出新增 `degraded_source_block_count`（加入数值白名单）。

## 5. 资产登记

`MinerUImageAsset.page_raster`（页码、源 PDF sha256、DPI）；`execution` 登记 metadata `origin="pdf_page_raster"`。

## 6. 测试

- 转换器（fake 栅格器与源 PDF）：单页降级成功、跨页组闭包、合并回执放弃、阈值、无栅格器、栅格失败、无页码、其他中止错误。
- 对账：降级 IR 通过；篡改降级计数失败。
- 端到端：eager Worker 任务成功、质量 blocked、交付 internal_draft、批准被拒、DOCX 含整页图像与提示。
- 真实 Poppler：OPA228_P1 人为破坏表格 HTML 后本地转换并目视。
