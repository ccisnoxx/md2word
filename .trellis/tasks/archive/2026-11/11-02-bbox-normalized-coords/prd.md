# MinerU 归一化 bbox 坐标空间修复

## 目标与业务结果

按调研结论（`archive/2026-11/11-02-bbox-coordinate-audit/research/bbox-coordinate-space.md`）修正坐标空间：表格占位裁切不再静默裁错，复核位置投影在真实任务上可用，版式比例判断不再有约 10% 的系统偏差。

## 背景

- MinerU content list bbox 为 0–1000 归一化坐标（3.1.8/3.4.0/3.4.4 已核实），`layout.json`/`middle.json` 的 `page_size` 为 PDF 点。
- `DocumentIRPage` 合同为“坐标单位保持 MinerU 原始空间”；`SourceSpan.bbox` 必须等于原始片段 bbox（`logical_table_group` 完整性校验）。因此 IR 中的 bbox 保持原值。
- 现状 `build_pages` 用“bbox 极值 / page_size”推导页尺寸（如 911×1179），既不是 bbox 空间也不是 PDF 点。

## 范围与要求

1. 识别坐标空间：包内有有效 `page_size`，布局文件 `_version_name` ≥ 3.1，且该页所有 content bbox 落在 [0, 1000] 时，判定为 `mineru_normalized_1000`；页面 `width/height` 取 1000×1000（bbox 空间），metadata 记 `bbox_coordinate_space`，`orientation` 改由 `page_size` 判定。其余情况保持现有推导，不加标记。
2. 横竖版判断改用页面方向事实（`LayoutPage.landscape`），不再依赖宽 > 高。
3. 单一换算函数把原始 bbox 转为 PDF 点：归一化页按 `值/1000×page_size`；旧页仅在 `pdf_page_size == [width, height]` 时原样视为 PDF 点；其余返回 `None`。
4. 表格占位裁切与复核位置投影只经该函数取得 PDF 点坐标；得不到时保持失败关闭（裁切 `table_placeholder_geometry_invalid`、复核 `coordinate_space_unverified`）。
5. 绑定、来源账本、IR 中的原始 bbox 与相关完整性校验不变。
6. 更新规格中的坐标合同说明。

## 非目标

- 不把 IR bbox 改写为 PDF 点；不改 legacy 流水线；不调整版式阈值数值；不迁移、重算已持久化的旧 IR。
- 表格参考图 API（`table-references`）继续返回原始来源 bbox，不在本任务改变。

## 验收条件

- AC1：真实样本（`mineru_result/` 6 份）的 `build_pages` 结果为 1000×1000 且带标记，`orientation` 与 PDF 一致；俄文 595×841 样本同样正确。
- AC2：OPA228_P1 的 chart、table 块经裁切函数得到与源对象一致的区域（单测以换算坐标断言；本地端到端以 PNG 目视）。
- AC3：复核位置投影对新标记页返回 `coordinate_verified=true`、PDF 点 bbox 与 PDF 页尺寸；旧页面行为不变。
- AC4：横版 PDF（宽>高 page_size）在 1000×1000 页面下仍生成横版 section。
- AC5：无布局文件、版本 < 3.1、bbox 超出 1000 的包保持现有行为；相关测试与基线一致，因页尺寸修正而变化的期望逐条说明。

## 决策记录

2026-11-02 用户要求“按照建议实现”。实现时将调研报告第 4 节“IR bbox 换算为 PDF 点”调整为“IR bbox 保持原值、修正页面几何并在需要 PDF 点处显式换算”，理由：`SourceSpan.bbox` 必须等于原始 bbox 的现有完整性合同与 `DocumentIRPage` 的坐标单位合同。
