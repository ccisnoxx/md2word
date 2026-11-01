# 技术设计

## 1. 坐标空间识别（owner：`layout_signals.build_pages`）

- `_load_page_sizes` 同时返回布局文件的 `_version_name`（私有函数，唯一调用方为 `build_pages`）。
- 对每页：`raw_size` 有效、版本 ≥ (3, 1)、该页所有可解析 bbox 满足 `0 ≤ v ≤ 1000` → 归一化页：
  - `width = height = 1000.0`；
  - metadata：`pdf_page_size`、`page_size_source`（不变）、`bbox_extent`（不变）、`bbox_coordinate_space = "mineru_normalized_1000"`、`orientation` 由 `raw_size` 判定。
- 否则沿用现有放大系数推导，不写 `bbox_coordinate_space`。
- 常量：`NORMALIZED_BBOX_SPACE = "mineru_normalized_1000"`、`NORMALIZED_BBOX_EXTENT = 1000.0`。

## 2. PDF 点换算（单一函数）

`layout_signals.pdf_point_bbox(bbox, page) -> tuple[float, float, float, float] | None`：

- `page.metadata["bbox_coordinate_space"] == NORMALIZED_BBOX_SPACE` 且 `pdf_page_size` 有效 → `(x0/1000·W, y0/1000·H, x1/1000·W, y1/1000·H)`；
- 无标记、`page_size_source` 存在且 `pdf_page_size == [width, height]` → 原样（旧“已核实”语义）；
- 其他 → `None`。

## 3. 横竖版

- `LayoutPage` 增加 `landscape: bool = False`（运行时计划，不持久化）。`build_layout_plan` 由 IR 页 `metadata["orientation"]` 判定，缺失时退回 `width > height`。
- `render_plan`（325 行）与 `logical_table_plan`（146 行）改读 `page.landscape`。

## 4. 消费方

- `table_placeholder.prepare_placeholders`：`crop_box = pdf_point_bbox(span.bbox, page)`；`validate_geometry(span.page_index, crop_box, frame)`；`crop(PdfCropRequest(source, page_index, crop_box, frame))`。绑定仍记录原始 `span.bbox` 与 `frame`，解码校验不变。
- `review_content` 位置投影：`points = pdf_point_bbox(bbox, page)`；verified 时返回 PDF 点 bbox 与 `pdf_page_size`，否则保持现状（原始 bbox、无页尺寸、`coordinate_space_unverified`）。
- `logical_table_group`、栏位、图片比例：页尺寸改为 1000 后自动正确，无代码改动。

## 5. 兼容

- IR 块与来源 bbox 不变；新 IR 的页 `width/height` 与 metadata 变化，RenderPlan/证据哈希随之变化（预期）。
- 已持久化旧 IR：无标记，裁切不会重跑；复核投影沿用旧语义。
- 合成测试夹具无布局文件或无版本 → 行为不变。

## 6. 测试

- `build_pages`：归一化页尺寸/标记/方向；版本 < 3.1、无版本、bbox > 1000 的回退。
- `pdf_point_bbox`：归一化、旧点坐标、未知。
- 横版：page_size 宽>高的归一化页生成横版 section。
- 裁切：用 fake provider 断言收到换算后的 PDF 点坐标；原始 bbox 越界但换算后合法时成功。
- 复核投影：归一化页 verified 且坐标为 PDF 点。
- 真实样本回归脚本（本地，不入库）：6 份样本页尺寸、OPA228_P1 裁切目视。
