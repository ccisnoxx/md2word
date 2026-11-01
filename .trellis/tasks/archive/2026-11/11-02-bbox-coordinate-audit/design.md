# 调研设计

## 1. 证据来源

| 来源 | 内容 | 用途 |
|---|---|---|
| `mineru_result/*/layout.json` | `pdf_info[].page_size`（PDF 点）、`para_blocks`/`preproc_blocks` 的 bbox | 坐标基准 |
| `mineru_result/*/*_content_list.json`、`*_content_list_v2.json` | 系统实际消费的 bbox | 待判定对象 |
| `tests/fixtures/golden_samples/pdfs/OPA228_P{1,2,6,7}.pdf` | 源 PDF | `pdftotext -bbox` 文字坐标、Poppler 裁切 |
| （D1 授权后）hostdzire 近期任务原始包 | 版本/后端元数据与 bbox 数值 | 确认线上一致 |

## 2. 方法

1. **块匹配与拟合**：content list 与 layout.json 按页、类型与文本（规范化后前缀）匹配；对匹配对拟合 `pt_x = a·v_x`、`pt_y = b·v_y`（无截距），期望 `a = W/1000`、`b = H/1000`；报告 a、b、R²、最大残差（pt）。匹配率与未匹配原因一并记录。
2. **PDF 文字独立验证**：`pdftotext -bbox-layout` 得到词级坐标；把 content list 文本块按候选换算映射到点坐标，计算其覆盖的词中属于该块文本的比例；分别对“归一化假设”和“PDF 点假设”计算。
3. **使用点审计**：以 `grep` 定位 `bbox`、`width`/`height`（页）、`bbox_extent`、`pdf_page_size`、`page_size_source`、`page_width` 的读取，按调用链归类到：页面构建、版式信号/双栏、图片计划与证据、caption 关联、逻辑表格分组、表格占位裁切、渲染证据。每项用一份样本实际运行（不改代码，在临时脚本中调用模块函数）给出数值偏差。
4. **裁切实证**：从 OPA228 选表格块与图片块各一，构造 `PdfCropRequest`：A 用原始 bbox，B 用换算 bbox；记录 A 是否被 `validate_geometry` 拒绝、两者输出 PNG，目视确认 B 与源对象吻合。
5. **报告**：`research/bbox-coordinate-space.md`，含结论、证据表、使用点清单（文件:行、假设、实测偏差、影响等级）、修复方案建议。

## 3. 修复方案的预期方向（供报告验证或推翻）

- 在 `artifact_validator` 或 `layout_signals` 设一个坐标归一化 owner：读取 content list bbox 时依据 layout.json 的 `page_size` 换算到 PDF 点（或统一到 0–1 相对坐标），IR 中只存一种坐标空间并记录来源与换算参数。
- `build_pages` 直接使用 `page_size`，不再用 bbox 极值推断；无 layout.json 时明确标记“坐标空间未知”，下游（裁切、跨页表格）失败关闭而非猜测。
- 需要评估：IR schema/哈希与已有任务兼容性、版式阈值是否按旧坐标调过参、测试夹具中合成 bbox 的坐标空间。

## 4. 产物与边界

- 临时脚本放 `tests/tmp/bbox-audit/`（已忽略），不提交；报告引用其结果。
- 不修改 `app/`、`tests/` 下受版本控制的文件。
