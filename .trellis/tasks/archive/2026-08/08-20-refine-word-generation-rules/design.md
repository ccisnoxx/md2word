# Word 生成规则改造技术设计

## 1. 设计目标

在不恢复 PDF 绝对定位、不新增第二套 Word writer 的前提下，使正式
`MinerU → DocumentIR → Word` 链路满足以下共享不变量：

1. 每个归一化源块都有且只有一个可审计去向，确定性内容缺失在发布前失败关闭。
2. 语义归一化先于布局，布局容器先于具体 block renderer；renderer 不得用块类型重新猜页面拓扑。
3. 模板决定 Word 的绝对样式，PDF/MinerU 只提供阅读顺序、相对布局、方向和内容组证据。
4. Word 原生 section、columns、table、heading、caption、field、OMML 和分页属性优先。
5. 版式证据不足时保留全部内容并安全降级，不能以猜测或静默删除换取“成功”。

有问题的 DOCX 与原 PDF/MinerU 产物只用于建立失败证据和回归基线。任何修复必须落在正式链路的通用 owner，并由最小失败测试证明；不得通过二次编辑 DOCX、样本专用后处理或固定文案规则获得一份看似正确的样本文件。

不引入新的第三方依赖，不建立品牌/型号白名单，不实现通用 PDF 版面引擎或完整 TeX 引擎。

## 2. 目标数据流

```text
MinerU v2 blocks
  │
  ├─ 输入归一化：尾页过滤、续表、题注重关联
  │
  ├─ 文档级语义裁决：源类型 + 文本 + bbox + 邻接 + 跨页重复
  │      └─ block type / layout role / annotation role / decision reason
  │
  └─ DocumentIR v2
         │
         ├─ 可选翻译：正文 + 列表 + 表格 + captions + footnotes
         │
         ├─ Word 布局计划：软页面组 + 单双栏拓扑 + 表格适配
         │
         └─ Word 原生渲染
                └─ source→IR→layout→DOCX evidence + 发布门禁
```

正式本地和线上入口必须构造并传递同一份最终 `LayoutPlan` 给 renderer 和 evidence，避免线上先构造一份源布局、renderer 内部又构造另一份 Word 布局。

## 3. DocumentIR 语义归一化

### 3.1 唯一 owner

新增内部纯规则模块 `app/services/document_ir/semantic_normalization.py`，由
`MinerUToDocumentIRService._convert_blocks()` 在页面尺寸建立后、逐块构造 IR 前调用。模块只输出每个 source index 的裁决，不写 Word 样式、不修改 MinerU 原文件。

机械 schema 映射仍由 converter 负责；所有需要文档级上下文的覆盖裁决只在该模块维护。裁决结果至少包含：

- 最终 `DocumentIRBlock.type`；
- 最终 `DocumentIRBlockLayout.role`；
- paragraph 变体所需的 `metadata.annotation_role`；
- 稳定 `metadata.semantic_decision_reason`；
- 需要记录的阻断或非阻断质量信号。

不新增与 `block.type` 重复的持久化语义字段。三个既有轴各自只有一个含义：

- `metadata.source_type`：MinerU 原始分类；
- `block.type`：项目裁决后的主内容类型；
- `layout.role`：正文、真实页装饰或显式不逐项渲染的布局去向。

`DocumentIRBlockRole` 扩展 `toc_source` 和 `filtered`。`body` 才进入正文布局；真实 `page_header/page_footer/page_number` 由模板 decoration 合同消费或明确替代；`toc_source` 表示其内容用于生成一个 TOC 字段而不逐行重复输出；`filtered` 必须携带稳定原因。

### 3.2 decoration 与 `page_footnote`

- `page_header/page_footer/page_number` 只是候选信号。跨页重复且位于稳定页边距，或短文本完全处于页边距的块可判为真实 decoration。
- 唯一出现、长文本、覆盖主体区域、页面没有其他 body，或超出页边距的候选默认提升为 body，并记录提升原因；证据冲突时保留正文并给非阻断风险。
- 真实源 decoration 不逐页写入 Word section。模板既有或显式配置的 header/footer 是最终 Word owner；页码只使用原生 `PAGE` field。删除当前未生效的 `use_mineru_header_footer` 假开关，不实现同一 section 内每源页不同 decoration。
- `page_footnote` 默认成为 body paragraph，`annotation_role=page_note`，使用 note 样式。只有同页 bbox 邻接能够唯一绑定到表格/图片时才共享内容组；没有可靠锚点时保持独立可见 note，不盲目创建 Word 原生脚注。

### 3.3 标题与竞争角色

采用 D5 的有序排除，不建立综合评分器：

1. 先识别明确图题/表题及其唯一邻接主体；
2. 再识别连续列表/步骤项；
3. 再识别修订范围表头、局部分组标签和重复页装饰；
4. 没有竞争角色时，MinerU `title` 保留 heading；
5. 非 `title` 块只有具备额外文档级结构证据时才可晋升 heading，单独的编号、字号或 `text_level` 不足。

竞争角色的输出：

- 图题/表题：paragraph + `annotation_role=standalone_caption`，使用原生 caption/SEQ 路径；若邻接主体已有相同题注则只保留一份可见内容并记录显式去重。
- 列表/步骤：原生 list block。
- 修订范围等局部分组：paragraph + `annotation_role=group_label`，使用普通段落的局部强调和 `keep_with_next`，不进入 TOC/导航。
- 无法裁决的源 `title`：保留 heading，并记录非阻断歧义。

### 3.4 TOC

TOC 识别限定为“目录标题 + 连续高比例目录项”的明确区域。区域内原始条目标为 `toc_source`，converter 在首个目录位置增加一个合成 body anchor（`annotation_role=toc_anchor`）。

renderer 只在 anchor 处生成一个原生 TOC complex field；字段缓存结果来自翻译后的最终 IR headings，保持层级和文字但不带源 PDF 页码。普通点线文本、修订记录和表格行不再触发 TOC 分支。Word/WPS 更新字段后由客户端生成实际 Word 页码。

## 4. 页面组与布局计划

### 4.1 软页面分组

`layout_plan.py` 负责把源页边界转换成候选页面组，而不是 renderer 的 `_semantic_page_break_block_id()` 临时判断：

- 方向变化使用 `NEW_PAGE` section；
- 相邻源页存在明确续表、同一列表/段落续接或同一图表内容组时合并，不加分页；
- 没有连续证据的新源页，在栏重排后的第一个真实内容块上设置 `pageBreakBefore`；
- 分页目标必须在最终左栏→右栏顺序确定后选择；不能先按全局 y 选中右栏目标，再在其前面写左栏内容；
- 没有可见 body 的页面必须被证明为真实空白/decoration-only/filter，否则进入内容完整性阻断。

`LayoutPlan` 保存每个页面组的 break anchor 和原因，renderer 只执行计划。

### 4.2 双栏拓扑

保留当前 bbox/column hint 基础，但移除“块中心点必须落入重叠 band”的决定权：

- 先确定左右栏边界和明确 wide barrier；
- 块只要与可信双栏 band 有实际纵向覆盖，或是同侧连续内容组的一部分，就保留其 left/right 归属；
- 高表格、表注或另一栏局部空白不会把栏内块提升为 wide；
- 只有 bbox 跨过 gutter、显式 wide 或 D6 安全降级产生的块退出双栏；
- 无法得到可靠栏归属的片段降级成单栏，并记录原因。

所有进入 `two_col` region 的块必须已有明确 left/right hint。renderer 只分组，不再用 bbox 兜底重判。

### 4.3 成对视觉行

layout plan 将严格图片对输出为独立 `paired_visual_row` region。renderer 使用无边框原生 1×2 Word table，每个单元格包含自己的图片和 captions/footnotes，不再使用同一段落制表位。

该布局表写入稳定 OOXML 描述标记，DOCX analyzer 将其计入 `layout_table_count`，并从语义 table count 中排除，避免破坏 IR table 完整性对账。

## 5. 表格适配

### 5.1 配置合同

新增继承现有段落样式字段的 `TemplateTableContentStyleConfig`，只让
`table_content` 使用该类型并增加可编辑可选字段 `min_font_size`；其他段落样式不接受该字段：

- `font_size` 是首选字号；
- `min_font_size` 缺失时按 `font_size` 处理，即不隐式缩字；
- 必须满足 `1 <= min_font_size <= font_size`；
- 字段继续使用 `template-config/v1`，旧配置由缺失字段默认值兼容。

已发布 seed 不原地修改。先新增不进入 manifest 的 bundled 候选
`datasheet_template_v3.yaml`，显式给出最小字号；只有全部真样本通过 Word/WPS
验收后，才单独登记 manifest 版本并经过 draft 验证和显式 set-default。数据库已有默认指针不自动迁移。默认最小值先采用现有 renderer 的下限 7pt，但在发布前不影响任何既有转换。

### 5.2 单一适配 owner

新增纯计算模块 `app/services/renderer/table_layout.py`。它复用现有 HTML table parser，输入最终翻译后的 table、容器宽度、模板首选/最小字号和源相对宽度，输出 `TableFitDecision`：

- 容器：column、full-width 或 landscape；
- 选中的最大可适配字号；
- 内容感知列宽；
- 降级原因和质量信号。

列宽优先使用可解析的源/HTML 宽度；没有时根据各列最长不可断词片段和文本显示宽度分配，使用标准库字符宽度近似，不引入字体测量依赖。rowspan/colspan 只参与已有 parser 的逻辑列覆盖，不复制第二套 HTML parser。

适配顺序固定为：

1. 当前栏 + 首选字号到最小字号之间的最大可适配值；
2. 完整结束当前双栏内容组后，单栏全宽并从首选字号重新计算；
3. 新页横向 section 并从首选字号重新计算；
4. 仍不能可靠适配时保持全部内容、使用最小字号和合理换行，记录 `table_fit_unresolved`，交由 Word/WPS 验收，不继续缩字或截断。

最终 `TableFitDecision` 存在同一 `LayoutPlan` 中，由 table renderer 和 evidence 共同消费。表题、表注不参与单元格缩字。

## 6. 翻译与公式

- `DocumentIRTranslationService` 增加 captions、footnotes target，应用替换时按 block id、字段和 index 精确回写。
- 共享 `text_semantics.py` 提供 mixed-math 分段；converter、translator 和 renderer 共用。翻译只发送普通文本段，`$...$`/明确公式段保持原样，避免公式被 provider 改写。
- caption/footnote 的 inline equation 在 IR 中保留明确数学边界，进入与正文相同的 OMML 入口。
- OMML parser 支持 `\,` 等已确认 TeX spacing token；无法解析时完整原文可见。
- DOCX residue 扫描覆盖反斜杠后字母和标点命令；未知 TeX 保持非阻断风险，任何静默丢失或部分吞命令属于阻断内容损坏。

### 6.1 D8 表格数学分级渲染

- 不增加第二套 TeX parser。表格单元格在进入共享 mixed-math 写入前，复用 `text_semantics.py` 已有的 mixed-math 边界、TeX 规范化与安全内联 HTML 转 Word run 能力，只对可无损转成“基底 + 简单上下标”的标识型片段启用。同一单元格内的普通文字保持 run，未命中的复杂公式保留原数学边界并继续进入 OMML。
- 简单标识允许字母、数字、已支持的希腊字母/文本命令和一层上下标；分式、根式、上划线、包围框、`tag`、嵌套结构、关系操作符或多项算术表达式均不进入富文本分支，继续由 `_OmmlParser` 处理。
- 富文本分支只在语义 table cell 调用点生效，不改变 caption、table note、正文和独立公式。普通 run 继承 `table_content` 字体/字号，上下标使用 `w:vertAlign`，段落仍由 table renderer 设置表头居中、表体左对齐及零段前后距。
- 分类失败不猜测：保持原 mixed-math/OMML 路径；OMML 也无法解析时保留整个原文与现有 residue 信号。
- `DocumentIRWordRenderer` 创建当前 DOCX 后读取模板 `m:mathFont`。已声明则原值保持并绑定到当前 document part；缺失则在该文档 settings 中补 `Cambria Math` 后绑定同一值。不增加生产 config/API/schema，不修改 bundled/published 模板。

## 7. Word renderer 与字段

- `render_to_bytes()` 接受可选最终 `LayoutPlan`；正式本地/线上入口必须先以最终 DocumentIR 和解析后的 TemplateConfig 构造计划，并把同一实例传给 renderer/evidence。测试和兼容调用未传时由 renderer 使用同一公共 builder 构造。
- heading、group label、standalone caption、page note、TOC anchor 各走唯一 dispatch；不在普通 paragraph 再推断 v2 heading 或 TOC。
- 方向变化和 landscape table 使用新页 section；单双栏及 full-width 恢复使用 continuous section。所有 section 变化附着在真实内容，不新增 break-only 空段落。
- 配置 footer 的页码在有无左右文字时都写原生 `PAGE` field。
- 模板 header/footer 由模板/配置唯一拥有；源 decoration 不再逐物理页覆盖共享 section。

## 8. 完整性与质量证据

### 8.1 source→IR

`integrity.py` 不再假设所有 source `title` 都必须对应 heading，而是校验：

- 主源块数量仍一一对应；合成 table context/TOC anchor 不计主块；
- 每个主块具有受支持的最终 type、layout role 和 `semantic_decision_reason`；
- body 块具有对应可见 payload；decoration/toc_source/filtered 块具有明确 disposition reason；
- image asset、table HTML、公式 payload 继续失败关闭。

### 8.2 IR→layout→DOCX

在现有 block id 与 drawing/table/heading 对账上增加：

- 正文、列表项、table cell、captions、footnotes 的规范化可见文本覆盖；
- TOC field 数量为 1，缓存标题来自最终 heading，源 TOC 项有明确去向；
- paired visual layout table 与语义 table 分开计数；
- 图片媒体 checksum/资产身份对账，而不只比较 drawing 数量；
- group label 不计 heading，page note 计可见正文；
- 表格 fit decision、栏降级、软页面组和 section 结构证据；
- `\,` 等公式残留。

确定性缺失、重复布局 block、资产错配和不可见 payload 进入 `blocking_quality_flags`。栏置信度、表格末级降级、客户端分页、栏平衡、字体安装和图片清晰度保持非阻断质量风险，并在 Word/WPS 人工门禁判断。

## 9. 兼容、迁移与回滚

- `document-ir/v1` 继续顺序兼容；新增 v2 role 值有默认行为，旧 IR 不反推不存在的语义证据。
- `template-config/v1` 不升 schema version；旧版本缺少 `min_font_size` 时不缩字。已发布 v1/v2 seed 字节和 hash 不变。
- 正式任务继续固化 Template Version；不存在或 hash 错误时失败关闭，不回退 bundled v3。
- 布局和语义算法不设置型号开关。若真样本出现退化，回滚当前代码/新模板默认指针，不修改历史 seed，也不放松内容门禁。
- 复杂变更按“语义与完整性 → 页面/分栏 → 表格配置与适配 → renderer/evidence → 真样本”顺序落地；每个阶段完成对应最小测试后再进入下一阶段。

## 10. 主要受影响 owner

- 规范：`.trellis/spec/backend/word-generation-rules.md`、`.trellis/spec/backend/template-layout-configuration.md`。
- IR：`models.py`、`mineru_converter.py`、`layout_signals.py`、新 `semantic_normalization.py`、`integrity.py`。
- 翻译：`document_ir_translator.py`、共享 `text_semantics.py`。
- 布局/渲染：`layout_plan.py`、`word_renderer.py`、`image_renderer.py`、`table_renderer.py`、新 `table_layout.py`、`text_renderer.py`。
- 配置：`layout_config_schema.py` 和新 bundled v3 候选 YAML；真样本验收完成前不修改 template manifest、默认资源指针或 published v1/v2 文件。
- 证据：`evidence.py`、`docx_quality.py`，以及正式本地/线上调用处。
- 测试：DocumentIR contract/converter、translator、renderer layout、template schema/API、正式 adapter/worker、样本治理与真客户端验收记录。
