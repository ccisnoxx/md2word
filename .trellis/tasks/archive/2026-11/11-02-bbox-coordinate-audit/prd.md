# 核实 MinerU bbox 坐标空间与各使用点影响

## 目标与业务结果

用真实样本与源 PDF 确定 MinerU content list 中 bbox 的坐标空间，逐一核对代码中所有消费 bbox 的位置所做的坐标假设，量化偏差与可能的错误输出，产出一份有证据的调研报告和后续修复建议。它是“原 PDF 回退裁切（P0-4）”与“整页降级（P1）”的前提。本任务只调研，不改产品代码。

## 背景与初步证据（2026-11-02 只读探测）

- 本地样本：`mineru_result/` 下 6 份真实 MinerU 输出（git 忽略的本地数据），MinerU 3.1.8 / 3.4.0、`hybrid` 后端；其中 OPA228 P1/P2/P6/P7 有源 PDF（`tests/fixtures/golden_samples/pdfs/`），RS2G04 与俄文二极管手册无源 PDF。
- `layout.json` 的 `page_size` 为 PDF 点（612×792、595×841），其块 bbox 最大值均在页面尺寸内。
- `content_list.json` 与 `content_list_v2.json` 的 bbox 最大值为 902–973，超出页面尺寸；x 方向按“值/1000×页宽”换算与 layout 块一致（911→557 vs 555）。推测为 0–1000 归一化坐标。
- 初步推算的影响（待核实）：
  - `layout_signals.build_pages` 以“bbox 最大值 / 页面尺寸”为放大系数，得出的页宽≈最大 x（如 911）、页高≈页高×同系数（如 1179），既不是 PDF 点也不是 1000；依赖页宽/页高比值的判断存在系统偏差。
  - `logical_table_group` 跨页表格几何门槛（底部 75%、顶部 25%、左右 5% 容差）因页高被放大而失真。
  - `table_placeholder`/`pdf_crop` 把 content list bbox 当 PDF 点并以 `pdf_page_size` 为 frame：右侧对象越界被拒，左上对象可能通过校验却裁错区域。生产已具备 Poppler，此路径线上可达。

## 范围与要求

1. 坐标空间判定：对 6 份样本逐块匹配 content list 与 layout.json 的同一对象，拟合换算关系（预期 `pt = v / 1000 × page_size`），给出每份样本的残差；对 4 份有源 PDF 的样本，用 `pdftotext -bbox` 的文字坐标做独立验证。
2. 使用点清单：列出 `app/` 中所有读取 content list bbox 或其派生值（`DocumentIRPage.width/height`、`bbox_extent`、`pdf_page_size`、`page_width`）的位置，标注各自的坐标假设、是否正确、偏差大小与对输出的实际影响（正确/偏差可容忍/错误输出/失败关闭）。
3. 裁切实证：对有源 PDF 的样本中的表格/图片块，分别用“原始 bbox 直接作 PDF 点”与“换算后 bbox”经 `PopplerPdfTableCropProvider` 裁切，保存 PNG 并目视比对，确认现有占位裁切的实际行为。
4. 版本与稳定性：记录样本的 MinerU 版本、后端、是否 OCR；判断归一化是否依赖版本/后端。
5. 产出 `research/bbox-coordinate-space.md`：结论、证据表、使用点清单、风险排序和修复方案建议（单一坐标归一化 owner、迁移与兼容影响、需要的测试）。

## 决策（需用户确认）

- **D1 生产样本**：是否授权经 `ssh hostdzire` 只读抽取近期 1–3 个任务的 MinerU 原始包中的 `layout.json` 元数据（版本/后端）和 content list 的 bbox 数值，用于确认线上 MinerU 版本与本地一致。只取几何与元数据，不导出正文或图片。推荐：授权（本地样本最新为 2026-06，线上版本可能已变化）。
- **D2 本地样本使用**：调研报告只引用样本名、页数、数值统计与裁切缩略结论，不把 `mineru_result/` 原始文件或裁切图提交入库；裁切 PNG 留在 `tests/tmp/`（已忽略）供目视。推荐：照此执行。

### 决策记录

2026-11-02 用户确认 D1（授权经 `ssh hostdzire` 只读抽取 1–3 个近期任务的版本元数据与 bbox 数值，不导出正文或图片）与 D2（本地样本与裁切图不入库）。

## 非目标

- 不修改任何产品代码、测试基线或规格（修复另开任务）。
- 不评估 MinerU 识别准确度，只评估坐标空间与使用方式。

## 验收条件

- AC1：坐标空间结论有两类独立证据（layout.json 对照、PDF 文字坐标对照），并给出残差。
- AC2：使用点清单覆盖 `app/` 中全部 content list bbox 消费者，每项有“假设/实际/影响”判定。
- AC3：至少一个表格或图片块完成两种 bbox 的实际裁切比对，并记录结论。
- AC4：报告给出可执行的修复方案与测试清单，供下一个任务直接起草。
