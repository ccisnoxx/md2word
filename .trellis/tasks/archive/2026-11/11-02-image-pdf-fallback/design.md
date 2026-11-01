# 技术设计（基于 P0c + PR #19，按推荐决策）

## 1. 验证阶段：待回退而不中止

- `_validate_asset(required=True)` 返回失败时，若错误属于可回退集合（D1），`complete_validation` 不再把它记为 `stops_conversion`，而是：
  - 以原 code/reason 记 blocker，但 `stops_conversion=False`；
  - 在块上标记 `_mineru_image_fallback = {"code": ..., "reason": ...}`，`_mineru_validated_asset` 为 None。
- 路径安全、超限（`error_code` 非空的 `unsafe` 路径）保持 `stops_conversion=True`。
- 报告 `can_convert` 仍只由 stops_conversion 决定，因此待回退不会提前中止。

## 2. 转换阶段：页面几何之后裁切（owner：`mineru_converter._convert_blocks`）

- `build_pages` 之后、生成图片资产时：对带 `_mineru_image_fallback` 的块调用私有函数 `_crop_image_fallback(block, page, source_loader, crop_provider)`：
  1. `crop_box = pdf_point_bbox(block bbox, page)`；`frame = page.metadata["pdf_page_size"]`；
  2. `validate_geometry(page_index, crop_box, frame)`；源 PDF 由同一 `source_loader` 惰性加载一次并校验 file_id 与 checksum（复用表格占位的校验写法）；
  3. `crop_provider.crop(PdfCropRequest(...))`，`validate_image(content)`。
- 任一步失败：把该块原 issue 改为 `stops_conversion=True` 并更新 `fatal_count/can_convert/first_fatal`，抛出 `MinerUArtifactValidationError(report)`——外部表现与现状一致（P0a 诊断不变）。
- 成功：原 issue 改为 `severity="warning"`（code 不变），追加 `image_asset_pdf_fallback` warning（facts.reason=原 reason）；资产 `MinerUImageAsset(content=PNG, mime="image/png", source_path=原路径或 "derived/pdf-region-crop.png", fallback=...)`。
- 报告修改通过 validator 提供的方法完成（如 `validator.resolve_image_fallback(locator, recovered: bool)`），保持计数与 `first_fatal` 由 validator 统一维护。

## 3. 资产登记与白名单

- `MinerUImageAsset` 增加 `pdf_fallback: dict | None`（页码、原始 bbox、PDF 点框、源 PDF sha256、原 code）；`execution` 登记时写入 metadata `origin="pdf_region_crop"` 及上述字段，文件名用 `stored_name`（`.png`）。
- `evidence.py`：`REPORT_CODES` 加 `image_asset_pdf_fallback`。
- 块 metadata 增加 `mineru_asset_origin="pdf_region_crop"`。

## 4. 测试

- 验证器：可回退/不可回退分类；待回退不提前中止；不可回退不调用裁切。
- 转换：fake 裁切器记录请求（PDF 点坐标、frame）；成功时资产与 warning；无源 PDF / 坐标未知 / 裁切抛错时以原码失败且 first_fatal 指向原块。
- 端到端：eager Worker 下缺失图片任务成功、DOCX 含裁切 PNG、文件 metadata 正确。
- 本地真实样本：OPA228_P1 删除图表图片后转换并目视裁切图。

## 5. 风险

- 源 PDF 区域可能包含图题或相邻文字（MinerU bbox 质量决定），以 warning 提示人工复核。
- 扫描版、旋转或 CropBox≠MediaBox 页面无法裁切，保持硬失败。
