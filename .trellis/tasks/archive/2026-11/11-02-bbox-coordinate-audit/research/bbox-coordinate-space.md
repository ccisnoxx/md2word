# MinerU bbox 坐标空间核实报告

日期：2026-11-02（北京时间）；代码基线：`origin/main` `90ebb407`。

## 1. 结论

1. **content list（v1 与 v2）的 bbox 是 0–1000 归一化坐标**，x 按页宽、y 按页高分别缩放：`PDF 点 = 值 / 1000 × page_size`。`layout.json`/`middle.json` 的 `page_size` 与块 bbox 为 PDF 点。
2. 该结论覆盖 MinerU 3.1.8、3.4.0（本地）与 3.4.4（生产），后端均为 `hybrid`，OCR 开启与否不影响。
3. 当前代码没有任何位置执行这一换算。`build_pages` 用“bbox 极值 / page_size”推导出的页面尺寸既非 PDF 点也非 1000，导致：
   - 版式比例判断有约 10% 的系统偏差（栏位分类 6% 的块结果不同、图片宽度比例偏大约 11%）；
   - **表格占位裁切把归一化 bbox 当 PDF 点**：越界时被拒（失败关闭），未越界时**通过校验却裁错区域**（已实证）；
   - 复核位置投影在所有真实样本上都判为 `coordinate_space_unverified`（失败关闭，但功能实际不可用）。

## 2. 证据

### 2.1 与 layout.json 逐块对照（`tests/tmp/bbox-audit/fit.py`，未入库）

只用两侧唯一出现的 `text`/`title` 块配对（表格/图片条目的 bbox 是整个对象而非图注行，不参与）。

| 样本 | MinerU | 匹配块 | 归一化假设残差（中位/最大） | PDF 点假设残差（中位） |
|---|---|---|---|---|
| OPA228_P1 | 3.1.8 | 6/9 | 0.7 / 0.7 pt | 323 pt |
| OPA228_P2 | 3.1.8 | 7/7 | 0.7 / 0.8 pt | 351 pt |
| OPA228_P6 | 3.1.8 | 0（无正文块） | — | — |
| OPA228_P7 | 3.1.8 | 1/2 | 0.7 / 0.7 pt | 165 pt |
| RS2G04 (13 页) | 3.4.0 | 41/52 | 0.6 / 0.8 pt | 212 pt |
| 俄文二极管手册 (595×841) | 3.4.0 | 1/1 | 0.8 / 0.8 pt | 324 pt |

归一化假设下 56 个配对块的最大残差 ≤ 0.8 pt，等于整数取整误差。

### 2.2 与源 PDF 文字坐标独立对照（`pdf_text.py`，`pdftotext 26.06.0 -bbox`）

源 PDF 均为 612×792、MediaBox=CropBox、旋转 0。以换算后的框圈选词（中心点判定），统计覆盖块文本字符的比例：

| 样本 | 文本块 | 归一化假设平均覆盖 | PDF 点假设平均覆盖 |
|---|---|---|---|
| OPA228_P1 | 9 | 1.00 | 0.40 |
| OPA228_P2 | 7 | 1.00 | 0.49 |
| OPA228_P7 | 2 | 0.92 | 0.44 |

### 2.3 生产核实（经授权只读，`ssh hostdzire`，Worker 容器内标准库解析）

最近 3 个 `mineru_raw_result`（2026-10-30，为同一文档多次提交）：`_version_name=3.4.4`、`hybrid`、OCR 开启；`page_size=612×792`；content list 142 个 bbox，最大 x1/y1 = 890/972。只读取数值与元数据，未导出正文或图片。

### 2.4 裁切实证（`PopplerPdfTableCropProvider`，OPA228_P1，frame 612×792）

| 块 | 原始 bbox 直接作 PDF 点 | 换算后 bbox |
|---|---|---|
| chart `[94,463,478,661]` | **通过校验，裁错区域**：图表下半部、半截图注与相邻表格局部 | 完整图表 |
| table `[511,604,906,731]` | `table_placeholder_geometry_invalid` 拒绝 | 完整表格 |

PNG 保存在 `tests/tmp/bbox-audit/crops/`（未入库），已目视确认。

## 3. 使用点清单（正式链路）

推导页面：OPA228 911–921×1179–1192，RS2G04 903×1169，俄文 902×1275（应为 1000×1000，或换算后为 PDF 点）。宽高比与 PDF 一致。

| 使用点 | 坐标假设 | 实测/推算偏差 | 影响 |
|---|---|---|---|
| `layout_signals.build_pages` | 以 bbox 极值放大 page_size | 页尺寸 ≠ 1000 且 ≠ PDF 点 | **根因** |
| `layout_signals._classify_column_hint` / `layout_plan._classify_body_block`、双栏带检测 | 比例 vs 推导页宽 | 223 块中 13 块分类不同（约 6%） | 偏差，可能影响双栏判定与阅读顺序 |
| `layout_plan` 图片组间距、`image_evidence`/图片宽度 | 比例 vs 推导页宽 | 图片宽度比例偏大约 11%（0.367→0.331） | 偏差，图片显示偏宽 |
| `render_plan` 横竖版 | 推导宽 > 高 | 宽高比正确 | 正确 |
| `logical_table_group` 跨页表格 | 底 75%、顶 25% vs 推导页高 | 门槛 750→约 884、250→约 295；样本中唯一候选对判定未变 | 理论偏差（未见实例） |
| `table_placeholder` + `pdf_crop` | bbox 为 PDF 点、frame=page_size | 越界拒绝；未越界裁错 | **错误输出（静默）/失败关闭** |
| `review_content` 位置投影 | 要求推导页尺寸 == page_size | 所有真实样本不相等 | 失败关闭（位置不可用） |
| `caption_reconciler` | 同坐标系相对比较 | 缩放不变 | 正确 |
| `app/conversion/runtime/*`（legacy 流水线） | 未审计 | — | 不在正式链路，另行评估 |
| `app/services/preview/*` | 渲染后 PDF 自身坐标 | 与 MinerU 无关 | 不适用 |

## 4. 修复建议（供下一任务起草）

1. **单一坐标 owner**：在 converter 读取 content list 时（`layout_signals` 构建页面与块布局处），若包内存在 `layout.json`/`middle.json` 的有效 `page_size`，把块 bbox 按 `值/1000×page_size` 换算为 PDF 点；`DocumentIRPage.width/height` 直接取 `page_size`，不再用 bbox 极值推断。
2. **坐标空间显式标记**：页面 metadata 增加 `bbox_coordinate_space`（如 `pdf_points_from_mineru_normalized_1000`），原始归一化 bbox 保留在块 `mineru_source` 中以便追溯；无 page_size 时标为 `unknown`，裁切与复核位置投影对 `unknown` 失败关闭，版式启发式保持现有行为。
3. **合理性校验**：换算前检查 bbox 全部落在 [0, 1000]；超出则不换算并标 `unknown`（防未来 MinerU 改变约定）。
4. **兼容**：已有 IR 无该标记 → 视为旧坐标，裁切/复核维持失败关闭；新 IR 的 bbox 数值、RenderPlan/证据哈希会变化，属预期。合成测试夹具多数无 layout.json，行为不变；含 layout.json 的夹具（如 `zk7044-caption-pair`）需更新期望。
5. **阈值复核**：双栏、图片分组等阈值原在“推导页宽”下调参，换算后需用 6 份本地样本回归比较双栏判定与图片宽度，确认无回退。
6. **测试清单**：换算单测（含 595×841 非 Letter 页）；无 layout.json 的 `unknown` 路径；超出 1000 拒绝换算；OPA228_P1 chart/table 裁切区域端到端（以缩略特征或像素统计断言，不提交源 PDF 外的图片）；复核位置投影在新 IR 上 `coordinate_verified=true`；跨页表格门槛在换算后的单测。

## 5. 未覆盖与限制

- 生产样本为同一文档的三次提交，只证明 3.4.4 的格式，不代表文档多样性。
- Word 显示、legacy 流水线、图片宽度变化对视觉的影响未验证。
- 跨页表格偏差在样本中没有触发实例，影响程度为推算。
