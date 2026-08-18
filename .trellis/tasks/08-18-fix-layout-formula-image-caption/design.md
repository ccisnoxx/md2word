# 技术设计

## 设计结论

本任务保持单一 Trellis 任务，不拆子任务。版面、公式、图片、题注和编号联动都汇聚到正式 DocumentIR→DOCX 渲染器，并需要同一份 SC2167 输出做集成验收；拆分会增加重复上下文和交叉返工。

不改变 DocumentIR schema、公开 endpoint 或数据库。增量扩展现有 `template-config/v1` 的可选页脚字段，旧配置依靠模型默认值继续可读；其余修改保持在 MinerU 输入归一化与 DOCX 渲染内部。

## 权威边界

- `app/services/renderer/word_renderer.py` 是正式转换和线上任务的 DOCX 编排入口；`layout_plan.py` 负责正式路径的区域判定。
- `app/conversion/docx_rules/text_semantics.py` 继续负责共享 TeX 符号归一化；`app/services/renderer/text_renderer.py` 负责正式路径的 Word 专属 OMML、目录和正文引用。
- `app/services/renderer/table_renderer.py` 与 `image_renderer.py` 继续分别保持表/图位置语义，但复用同一个内部题注 field helper，避免两套 `SEQ` 规则。
- `word_renderer.py` 负责 document settings、render-local 引用目标和最终 section 编排；图片显示尺寸仍由 `image_renderer.py` 计算。
- `docx_quality.py` 只补残留检测，不新建第二套公式判断。
- `app/conversion/runtime/*` 不是正式样本的权威实现。实施前追踪其真实调用与兼容合同；只有仍受支持的调用者需要同等行为时才同步，并复用共享语义而不是反向成为主实现。

## 1. 原生分栏

### 区域判定

`layout_plan.py::_detect_stable_two_col_bands()` 的稳定区间改为左右栏共同覆盖的纵向范围，而不是所有左右块的总体包围盒。这样上方单侧标题、下方单侧说明不会因同页存在后续双栏内容而被卷入。

显式 wide 块仍由现有 `build_regions()` 切成单栏区域；不增加页码或文本特例。

### Word 结构

`DocumentIRWordRenderer._render_layout_region()` 的双栏分支改为两个小型内部操作：

1. 添加 continuous section，写入 `w:cols w:num="2"`。
2. 按源顺序渲染左栏。
3. 插入 Word column break。
4. 渲染右栏。
5. 添加 continuous section，恢复 `w:cols w:num="1"`。

栏宽继续使用现有页面可用宽度计算。新增 continuous section 只改变 `w:cols`，页面属性继续按现有配置设置，页眉页脚依靠 Word 标准分节继承，不复制 relationship。

严格成对的纯图片网格是通用例外：当区域全部为图片、左右数量相等、每对 bbox 纵向相交且每图至多一条注释时，不按每行创建双栏分节，而是在单栏正文中用 25%/75% 原生中心制表位放置两张 inline drawing，下一段用相同制表位放置两个原生 `SEQ` 题注，并以 `keepNext` 保持整个网格不拆。这样保持 4×2 阅读顺序，同时规避 WPS 对多组连续分节做栏平衡而逐行拆页。任一守卫不成立时仍回到一次 `w:cols` + column break，不猜测丢弃图片或题注。

旧的 1×2 布局表格与 cell 渲染路径删除。实际 HTML 数据表格不变。

## 2. OMML 公式

不增加数学依赖。现有依赖和标准 XML 构造足以覆盖当前真实语法。

### 支持边界

新增一个小型、确定性的结构化 TeX 读取器，支持：

- `\frac{numerator}{denominator}`
- `\times`
- `^`、`_` 的单 token 或花括号参数
- `\overline{...}`、`\mathbf{...}`、`\boxed{...}`
- 无上下限的 `\bigotimes`
- 括号、普通文本、数字和现有命令映射中的符号

解析结果直接构造 `m:oMath`、`m:f`、`m:sSup`、`m:sSub` 等 OOXML。公式 block 总是走 OMML；正文和 HTML 表格文本中检测到的 `\frac` 片段也走同一入口。`\times` 同时加入共享命令映射，保证普通内联路径也输出 `×`。

不受支持或括号不闭合的输入不猜测修复：保留可见文本，由扩充后的 `LATEX_RESIDUE_RE` 产生质量标记。

普通文本与相邻数学片段拆成 `AV $_{DD}$` 时，只在数学片段以 `_`/`^` 开始且前一普通片段以明确字母数字 token 结束时取回基底并交给同一 parser；孤立脚本不生成空基底伪语义。

## 3. 图片

`image_renderer.py::_available_width()` 使用 bbox 宽度与 `page_width` 的真实比例，范围只限制在 `0..1`，最终宽度只上限到当前栏可用宽度。删除 45% 和 4.5 cm 两个最小放大约束。

图片仍由 `python-docx` 直接嵌入原字节，不读写像素。文档初始化时在 settings 中写入标准 `w:doNotAutoCompressPictures`；不做插值、超分或格式转换。

## 4. 原生题注

### MinerU 图注关联修复

在 `MinerUToDocumentIRConverter` 的原始 block 归一化阶段处理同页连续 image/chart 组。只有图数等于编号题注数、标签一致、编号唯一连续且存在零/多题注错配时，才按既有图片阅读顺序与题注编号顺序重配；否则保持输入。renderer 不承担重新猜测图注归属。

在 `text_renderer.py` 提供一个图、表共用的内部 caption paragraph helper，解析：

`<label><source number><title tail>`

其中 label 仅为 `图`、`表`、`Figure`、`Table`，source number 为阿拉伯数字。输出保留 label 和 title tail，把 source number 替换成复合 Word 域：

`SEQ <label> \* ARABIC`

域结果先写入源编号，保证未更新字段时也可读；Word 更新后按文档顺序重排。图和表因 field instruction 的 label 不同而独立计数。

非编号 captions 保持现有普通段落。表题位置、图注位置、样式和 keep-with-next 不变。长表首题注复用共享入口；续表标题只显示续表语义，不创建新的主序列域。

文档 settings 写入 `updateFields=true`，使 Word 打开文档时更新域。

## 5. 原生目录与交叉引用

### 目录

正式渲染器检测到目录标题/条目区域时只保留目录标题段落，并插入复合 Word `TOC` 域。该域使用 1–3 级大纲、超链接、隐藏 Web 版页码和 outline-level switches。

现有 outline level 标题样式成为目录来源，源 PDF 的静态目录页码不再写入结果；字段结果保留可见占位，并由 `updateFields=true` 在 Word 打开时生成。

### 图表引用

渲染前只扫描本次 `DocumentIR` 的编号题注，建立“标签 + 源编号 → 唯一书签名”的局部映射；重复或缺失目标不进入映射。这个映射只存在于一次 `render_to_bytes()` 调用，不放入 renderer 实例，避免并发任务共享可变状态。

题注的 `SEQ` 域外围写入 bookmark。正文和真实表格单元格共用文本渲染入口，只把能在局部映射中唯一命中的图表引用编号替换为带超链接 switch 的 `REF` 域。

字段结果先写源编号；未唯一命中的引用保持普通文字。题注自身、`TOC` field instruction 和已经存在的字段不参与替换。

## 6. 流式分页与空续表

把兼容路径已有的空 table placeholder 判定收口为共享纯函数，正式 `merge_table_placeholder_continuations()` 同时识别显式 `table_placeholder` 和真实 MinerU 的空 table 形状，累计 `continuation_heights` 后不输出占位块。

删除同方向 `LayoutPage` 之间的无条件 `PAGE` break。Word 正文依靠表格、段落、图片和 section 自然分页；只有横竖方向变化才新增 `NEW_PAGE` section。连续双栏前后仍用 `CONTINUOUS` section，不尝试预测某段在 Word/WPS/LibreOffice 中是否已经溢出。

## 7. 可配置原生页脚

`TemplateFooterConfig` 是唯一合同 owner，增加 `left_text: str = ""`、`right_text: str = ""`，并在既有字段 schema 中暴露通用 text 控件。`datasheet_template_v2.yaml` 增加空值示例；受固定哈希保护的已发布 v1 YAML 不改动。

显式自定义模式清空首节页脚并生成一个段落：左文字、相对 margin 的居中 `w:ptab`、可选原生 `PAGE` complex field、相对 margin 的右对齐 `w:ptab`、右文字。后续 section 标准继承，不创建表格或重复 relationship。左右文字为空时保持现有 enabled/alignment 行为；`enabled=false` 保持模板页脚。

模板管理 API 已由字段 schema 驱动，不新增 endpoint。前端设置页沿用通用 text 字段，只调整页脚预览显示左/中/右。显式自定义页脚优先于源页 footer/page-number decorations。

## 8. 最后一页推广封底过滤

在 `app/conversion/docx_rules/mineru_content.py` 放置一个共享纯判定函数，复用现有递归文本与资产路径抽取能力；不增加分类器、二维码解码依赖、配置开关或产品/页码特例。正式 `MinerUToDocumentIRService._convert_blocks()` 在题注重配、空续表合并、`build_pages()`、翻译和图片资产登记之前调用它；仍受支持的兼容输入适配路径复用同一判定，不维护第二份关键词。

只检查最后物理源页。最终页索引优先取 `layout/middle pdf_info` 的最大 page index；缺少页面元数据时才取 raw blocks 最大 page index。候选页必须全部满足：

1. 非页眉/页脚/页码正文含明确行动文案组合，例如“微信 + 扫码/扫描 + 进入/打开/关注”“小程序 + 进入/打开/扫码”“长按 + 识别二维码”或“扫一扫 + 进入/打开”；单独的“微信”“二维码”“官网”“联系我们”不命中。
2. 至少一个 `image/figure` block 能解析出真实资产路径；近方形 bbox 只能作为辅助证据，不能单独触发。
3. 不存在真实 HTML 表格、公式、列表、编号章节标题、编号图表题注或超过推广短文上限的正文。任一否决条件成立就保留整页，不做局部删除。

命中时返回 source page index，由调用者删除该页全部 raw blocks；正式转换同时从 `DocumentIR.pages` 排除该 index，因而二维码不会进入 `DocumentIRAsset`/`image_assets`，renderer 也不会生成空尾页。DocumentIR 增加 `final_promotional_page_filtered:<page_index>` quality flag，作为可观测证据；不记录图片内容或文案全文。

## 数据流

```text
DocumentIR blocks
  ├─ layout/bbox ─→ region detector ─→ 普通双栏 sections / 成对图片 tab-stop rows
  ├─ text/latex ──→ shared symbol normalization ─→ OMML builder
  ├─ image asset ─→ original bytes + bbox-relative display width
  ├─ headings ────→ existing outline styles ─→ TOC field
  ├─ captions ────→ guarded group reassociation ─→ SEQ + bookmark ─→ REF fields
  ├─ empty tables ─→ shared placeholder normalization ─→ prior table continuation
  ├─ final page ───→ conservative promo-page guard ─→ remove page/blocks/assets + quality flag
  └─ footer config → TemplateFooterConfig ─→ ptab + optional PAGE field
```

## 兼容性

- v1 或无 layout 的顺序渲染继续保持单栏。
- HTML 数据表格、标题、列表、页眉页脚和翻译合同不变。
- `template-config/v1` 只新增带默认值的可选页脚字段；旧配置、旧 draft 和 published v1 YAML 继续可读。
- 不保留旧布局表格开关；这是用户明确要求替换的行为。
- 复杂章节/附录题注编号、标题自动章节编号、Word footnote/endnote 和完整 LaTeX 不在本任务中。

## 风险与控制

- Word 与 LibreOffice 对 continuous section 的栏平衡可能略有差异：同时验证 OOXML 结构和 LibreOffice 标准渲染。
- WPS 会对逐行创建的多组 continuous 双栏/单栏 section 做栏平衡并把每行推到新页；严格成对的纯图片网格必须走单栏原生制表位，不得为追求视觉双栏重新引入逐行 section 或布局表格。
- 题注 field 的显示值依赖字段更新：写入初始结果并设置 `updateFields`。
- Word/LibreOffice 对首次生成 `TOC` 结果的时机不同：同时验收 field instruction、更新设置和实际更新结果，不把源静态页码作为回退保留。
- 错误标题语义会污染原生目录：目录只消费已有明确标题样式/outline level；不在本任务内猜测重建章节层级，样本中错误条目作为独立语义识别缺陷报告。
- `REF` 只转换唯一匹配目标，避免生成损坏书签；未匹配引用保持可见静态文字并在验收中列出数量。
- 有缺失 caption 的输入会导致自动序列与源编号不同：这是 Word 原生自动编号的预期语义，SC2167 通过全篇顺序验收。
- 源图片本身模糊无法恢复：本任务只消除转换器额外放大和压缩。
- 删除同方向物理页硬分页会改变输出页数和部分内容所在页，但避免跨排版引擎不可预测的空白页；验收以内容顺序、结构和正文非空为准。
- `w:ptab` 是 Word 原生结构，但 WPS/LibreOffice 互操作必须真样本检查，不能只断言 XML。
- 推广页规则的最大风险是误删合法封底；因此必须使用全量守卫和负样本回归，不能扩成模糊评分、短页删除或方形图片检测。SC2167 是正样本；TPL51200 免责声明、BL0942 版本表和 RS2G04 重要声明是负样本。

## 回滚

无数据迁移。回滚只需恢复上述渲染函数与测试；生成过的 DOCX 是独立产物，不影响存量源文件。
