# 技术设计草案（C1+C2，按推荐决策；确认后细化）

## 1. 验证阶段：区分可降级错误

- `artifact_validator` 为页级 fatal issue 增加可降级判定：issue 有 `page_index`，且 code 不属于包级/路径安全/超限/JSON 结构类；与 P0-4 同样采用“推迟 + 统一结算”的模式（`resolve_page_degradation`）。
- converter 在页面几何之后计算依赖闭包（逻辑表格组跨页、同页图片组），得出降级页集合；超过阈值则把所有推迟问题恢复为中止并失败。

## 2. IR 表示

- `DocumentIRPage.metadata["degraded"] = {"reason_code": ..., "issue_pointers": [...], "page_image_asset_id": ...}`；页内块保留，块 metadata 记 `degraded_page=true`。
- 新增整页栅格化：`PopplerPdfPageRasterizer.rasterize(source, page_index)`（`pdftoppm -f N -l N -r 144 -png`，校验页尺寸与 PNG 尺寸），不经 `validate_geometry`。

## 3. 渲染

- RenderPlan：降级页生成单个 `degraded_page` 操作（提示段落 + 整页图片，宽度按当前分节可用宽等比缩放），页内其他块的决策处置为 `superseded`。
- 块证据：降级页块处置 `superseded`，覆盖校验通过；图片证据核对整页图像字节。

## 4. 质量与交付

- 新受控 flag `page_degraded_to_image`（blocker），`base_quality` 计入 blocker → `quality_status=blocked`；现有交付状态机自动保持 `internal_draft`。

## 5. 测试

- 验证器可降级分类；依赖闭包；阈值；IR 页标记与块保留；整页栅格化（真实 Poppler，本地样本）；渲染输出提示与图片；块覆盖与来源对账；质量与交付状态；端到端任务成功且批准被拒。
