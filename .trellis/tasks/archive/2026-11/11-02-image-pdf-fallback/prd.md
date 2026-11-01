# P0-4：正文图片从源 PDF 回退裁切

## 目标与业务结果

正文图片在 MinerU 包中缺失、无法解码、格式不在栅格白名单内，或经 P0c 规范化后 Word 仍不接受时，不再让整个任务失败，而是按该图片块的 bbox 从源 PDF 裁切对应区域作为图片资产，任务继续生成 DOCX，并在质量报告中留下可见 warning。安全与限额类错误仍然硬失败。

## 依赖

- PR #18（P0c）：验证器图片检查与规范化的现有结构（本任务在其上修改）。
- PR #19（bbox 坐标修复）：`pdf_point_bbox` 与页面坐标空间标记（裁切坐标的唯一来源）。

## 背景（基于 P0c 与 PR #19 的代码）

- 必需图片的错误在 `artifact_validator.complete_validation` 中记为 `stops_conversion` 的 blocker，并在 IR 转换前直接抛出 `MinerUArtifactValidationError`；页面几何在其后的 `build_pages` 才建立。
- 源 PDF 加载器（`placeholder_source_loader`）与 Poppler 裁切器（`PopplerPdfTableCropProvider`）已用于表格占位，生产已具备 Poppler（P0b 核实）。裁切器要求页面 MediaBox=CropBox、无旋转、frame 等于 `pdf_page_size`。
- 图片证据只核对“DOCX 媒体 = 登记资产 = IR checksum”，与图片来源无关。

## 范围与要求

1. 可回退错误（必需图片）：`missing_image_asset`（含路径字段非法）、`invalid_image_asset` 中的 `unreadable_or_unsupported_image` 与 `not_allowed_raster_format`。
2. 不可回退：路径安全（穿越、歧义、语法）、单文件超限 `image_bytes`、ZIP/JSON 包级错误——保持现状硬失败。
3. 回退流程：验证阶段把可回退图片标记为待回退而不中止；页面几何建立后，经 `pdf_point_bbox` 换算坐标并调用现有裁切器；成功则以裁切 PNG 作为该块图片资产，失败（无源 PDF、坐标空间未知、页面几何不满足、裁切失败）则按原错误码硬失败，报告内容与现状一致。
4. 可见性：成功回退的块记 `image_asset_pdf_fallback` warning（定位到来源块），原错误改记为同码 warning；登记文件 metadata 记录来源 `pdf_region_crop`、页码、原始 bbox、换算后 PDF 点框、源 PDF sha256。
5. 每个图片块独立回退；同一任务只加载一次源 PDF。

## 决策（需用户确认）

- **D1 回退范围**：按“范围与要求”第 1、2 条（推荐）。
- **D2 裁切也失败时**：保持现状硬失败（推荐）。可见占位图 + 质量 blocked 的“部分成功”属于 P1，不在本任务。
- **D3 质量等级**：成功回退记 warning（推荐，`quality_status` 可能为 `warning`）；备选为 blocker（任务成功但质量 blocked，禁止批准发布）。
- **D4 实现基点**：推荐先合并 PR #18、#19，再从更新后的 `main` 实现；备选为在 P0c 分支上合入坐标修复分支后叠加实现（PR 会带合并提交）。

### 决策记录

2026-11-02 用户确认 D1–D4 均按推荐：可回退范围如范围第 1、2 条；裁切失败保持硬失败；回退成功记 warning；用户先合并 PR #18、#19，再从更新后的 `main` 实现。

## 非目标

- 不做嵌入图片对象提取、图片内容污染检测（P0-5）、整页降级与部分成功（P1）。
- 不改变表格占位裁切逻辑；不重命名现有裁切器类型。

## 验收条件

- AC1：缺失、不可解码、非白名单格式的正文图片，在源 PDF 与坐标空间可用时任务成功，DOCX 媒体为源 PDF 对应区域裁切图，报告含 `image_asset_pdf_fallback` warning。
- AC2：路径安全与超限错误仍硬失败，且不调用裁切器。
- AC3：源 PDF 不可用、坐标空间未知或裁切失败时，以原错误码失败，失败诊断（P0a）仍显示原页码与原因。
- AC4：Word 可识别或经 P0c 规范化成功的图片不触发回退，字节与现状一致。
- AC5：OPA228_P1 真实样本中把图表图片删除后转换，裁切区域与源图表一致（本地目视）。
