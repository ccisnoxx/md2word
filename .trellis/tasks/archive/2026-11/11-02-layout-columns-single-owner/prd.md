# 双栏分流单一实现与栏距核实（修复方案 5.1 / 5.2）

## 目标与业务结果

- 5.1：双栏阅读顺序只有一个权威实现，布局对账（LayoutPlan、逻辑表格位置账）与实际输出（RenderPlan）不会因为改了其中一份而分叉。
- 5.2：基于实测结论决定栏距是否需要显式写入，避免为不存在的问题增加合同。

## 背景与证据（基线 `origin/main` `90ebb407`）

### 5.1

- `app/services/renderer/layout_plan.py:452` 与 `render_plan.py:256` 各有一份 `split_two_col_blocks`。逐行对照逻辑等价：`left`/`wide` 进左栏、`right` 进右栏、无 bbox 进左栏，否则按 bbox 中心与本组最大右边界的一半比较。
- `logical_table_plan.py` 使用 `layout_plan` 版本；`render_plan.py` 两处（354、389 行）使用自身副本。`layout_plan` 版本的 docstring 已声明自己是“布局对账与实际输出共用的 owner”。
- `render_plan.py` 已从 `layout_plan` 导入其他符号，无循环依赖；测试与其他模块均不直接引用 `render_plan.split_two_col_blocks`。
- 规格 COL-002 的 owner 写为 `word_renderer::_split_two_col_blocks`，该函数已不存在，规格过时。

### 5.2

- `_set_section_columns` 只写 `w:num`；栏距来自模板 `sectPr` 继承。内置模板 `datasheet_template.docx` 为 `<w:cols w:space="720" w:num="1"/>`，现有测试已断言输出含 `w:space="720" w:num="2"`。模板可上传，可能不含或含其他 `w:space`。
- 渲染器宽度计算（`_content_width_and_columns`）与图片证据（`image_evidence`）都读取实际 `w:space`，缺省按 720；块证据记录实际值。
- 实测（LibreOffice 26.2.4.2，2026-11-02）：双栏文档不写 `w:space`、写 `720`、写 `1440` 导出 PDF，右栏起点分别为 402.2 / 402.2 / 420.2 pt——缺省即 720，与渲染器假设一致；非默认值按实际值生效。Microsoft Word 行为本机无法验证。
- 结论：方案担心的“不同客户端对缺省栏距解释不同”在 LibreOffice 上不成立；渲染器与证据对任意模板值自洽。5.2 不是已证实的缺陷。

## 范围与要求

1. 删除 `render_plan.py` 中的 `split_two_col_blocks` 副本，改为从 `layout_plan` 导入同一函数；行为不变。
2. 新增回归测试：同一组 blocks 经 RenderPlan 输出的左右栏顺序与 `layout_plan.split_two_col_blocks` 一致（含 hint、wide、无 bbox、按中心分栏）。
3. 更新规格 COL-002 的正式 owner。
4. 5.2 按下方决策执行。

## 决策（需用户确认）

- **D1（推荐：不实施 5.2 代码改动）**：仅在规格 COL-002 记录实测结论与“栏距随模板、渲染器按实际值计算”的合同，并补一条回归测试锁定“缺省按 720 计算可用宽度”。
- 备选 A：写双栏时把模板实际栏距（缺省 720）显式写入 `w:space`，并让 RenderSection 记录 `column_space_twips`。输出 XML 更自描述，但 RenderPlan 合同与证据需要扩展，收益仅在 Word 行为与 LibreOffice 不同时体现，目前无证据。
- 备选 B：在模板配置中新增可配置栏距。属于产品功能，超出本方案范围。

### 决策记录

2026-11-02 用户确认 D1：不实施 5.2 代码改动，仅记录实测结论并补测试。

## 非目标

- 不改变双栏检测（COL-001）、阅读顺序规则或 column break 行为；不做分页策略（5.3）与宽表横向（5.4）。

## 验收条件

- AC1：仓库中只剩 `layout_plan.split_two_col_blocks` 一个实现；`render_plan` 与 `logical_table_plan` 引用它。
- AC2：既有双栏测试（COL-002 列出的三个）与渲染相关测试结果与基线一致；新增一致性测试通过。
- AC3：规格 COL-002 owner 与 5.2 结论更新。
- AC4（按 D1）：新增测试证明模板无 `w:space` 时双栏可用宽度按 720 计算。
