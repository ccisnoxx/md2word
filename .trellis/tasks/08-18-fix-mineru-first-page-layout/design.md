# 技术设计

## 设计结论

七项缺陷位于同一条正式数据流，但由现有模块各自拥有；保持一个任务并在权威位置做最小修复：

`MinerU package → content list 选择 → DocumentIR 内容/页面归一化 → layout plan → Word 原生分页/分栏/OMML`

不修改 DocumentIR schema、公开 API、模板或数据库，不恢复完整旧 runtime 页流预测器，也不引入通用 LaTeX 依赖。

## 1. content list 选择

权威位置：`app/services/document_ir/mineru_package.py::find_content_list()`。

候选排序键增加格式优先级：v2 为 0，legacy 为 1，其后沿用路径深度与 `as_posix()`。格式优先级高于目录深度，因此任何合法 v2 候选都先于 legacy；同格式多候选仍确定性选择。

不读取 JSON 内容来猜版本，不新增环境开关或兼容 wrapper。

## 2. 页面坐标对齐

权威位置：`app/services/document_ir/layout_signals.py::build_pages()`。

当前 `raw_size` 是 PDF 物理坐标，bbox 可能是 MinerU 归一化坐标。存在两者时使用统一比例：

```text
scale = max(1, bbox_max_x / raw_width, bbox_max_y / raw_height)
page_width = raw_width × scale
page_height = raw_height × scale
```

页面尺寸既能包住全部 bbox，又严格保留物理页宽高比；orientation 继续由最终 width/height 得出。只有 `raw_size` 缺失时才直接使用 bbox extent。

## 3. 列表行归一化与 inline math 保真

权威位置：`app/conversion/docx_rules/mineru_content.py` 与 `MinerUToDocumentIRService`。

多行列表规则：

1. 从 legacy 字符串或 v2 `paragraph_content` 按原始顺序取得保留换行的文本。
2. 第一条非空行必须带现有支持的列表标记，且至少存在两条非空行，才把 paragraph/text 提升为 list。
3. 每个带标记行开始新 item；后续无标记行以 `\n` 追加到当前 item。
4. item 保留原标记，renderer 继续负责移除标记、推断层级并输出 Word 原生列表。

`join_text_fragments()` 对 `equation_inline` 不再调用普通文本降级函数，而是保留明确数学边界后拼入相邻文本。这样正文、标题和列表仍走现有 `_render_mixed_math()`；普通多行正文继续使用现有 `clean_text()`，不改变全局清理合同。

## 4. 局部双栏检测

权威位置：`app/services/renderer/layout_plan.py::_detect_two_col_bands()`。

现有逐区间 active-block 检测已经能识别 CM4112 上部文字和下部图片的真实左右重叠。过宽来自额外的 `_detect_stable_two_col_bands()` 总体包围带。

若已经得到至少一个实际重叠 `interval_band`，只合并这些实际区间；仅当实际区间为空时才调用稳定非重叠补偿。保留既有纯非重叠栏用例，不改 `DocumentIRWordRenderer` 的原生 `w:cols`、column break 与图片网格。

## 5. 语义分页

权威位置：`app/services/renderer/word_renderer.py`，表格首段落由现有 `table_renderer.py` 写入。

### 根因边界

旧实现把每个物理 PDF 页都序列化为 break-only 段落，长表自然跨页后会产生空页；今天删除该逻辑是正确的。回退来自删除后缺少内容组分页，不应恢复旧循环。

### 最小规则

对非首个 `LayoutPage`，仅在以下情况设置 `page_break_before=True`：

1. 页面第一个可见 body block 是 `heading`；
2. 页面第一个可见 body block 是带 caption/context 的独立 `table`。

分页属性附着到该 heading 段落或表格渲染出的第一个真实 caption/context 段落。CM4112 的“绝对最大额定值”和两条“默认测试条件”均已有 table caption，可直接承载，不需要样本文本判断或空锚点段落。

纯表格且没有 caption/context、纯图片页、普通段落续页继续自然流式分页。方向变化仍使用 `WD_SECTION_START.NEW_PAGE`；双栏进入/退出仍使用既有连续分节。

### 为什么不迁移旧页流估算器

旧 `page_flow_runtime` 根据字体和估算高度预测 Word 分页，且只在兼容 runtime 使用。正式 renderer 已有 Word 原生 `keep_with_next`、重复表头和 `cantSplit`，当前缺口只需明确的新内容组分页。迁移整套估算器会重新建立与 Word/WPS/LibreOffice 不一致的第二分页引擎。

## 6. 公式输入边界

权威位置：`MinerUToDocumentIRService._formula_text()` 和 `mineru_content.join_text_fragments()`。

- v2 interline：当 `content.math_content` 为字符串时只返回该值；`math_type` 仅是元数据，不参与文本拼接。
- legacy：继续按既有 `latex`、`text` 明确字段回退；不递归收集整棵 `content` 字典的任意字符串。
- v2 inline：保留 `$...$` 数学边界，使 `_render_mixed_math()` 可调用同一个 `_OmmlParser`。

这一步先保证 parser 接收到真实公式，再讨论语法；否则增加命令支持仍会被输入降级绕过。

## 7. 统一 TeX 预处理与 OMML 子集

权威位置：`app/services/renderer/text_renderer.py::_OmmlParser` 与现有共享符号表 `text_semantics.GREEK_AND_TEXT_COMMANDS`。

### 预处理

parser 构造阶段统一：

1. 收敛双反斜杠并剥离 `<eq>`、`$`、`$$`、`\(...\)` 包装；
2. 复用既有数学 token compact 规则，只在公式源字符串内合并被空格拆开的连续 ASCII 字母/数字；
3. 收紧 `_`、`^`、花括号周围空格，不改中文或普通正文空格。

### 语法覆盖

- 结构命令继续在 `_parse_command()` 处理：分式族、根式、文本/字体包装、overline/boxed；`boldsymbol` 复用现有粗体样式路径。
- `left/right` 作为尺寸修饰被消费，实际括号仍由后续 token 渲染；本阶段不为仅改变括号伸展高度新增 AST。
- `tag{...}` 解析为可见公式编号或明确忽略其布局语义，但不得导致整式失败；实现时以当前 Word 视觉验收选择最小可读形式。
- 单字符/单符号命令集中加入现有共享映射，覆盖本地语料及同类高频关系、运算、箭头、希腊字母和省略号；不另建第二 registry。
- `sqrt[n]{...}` 在现有 `m:rad` 的 `m:deg` 写入指数；`dfrac/tfrac` 复用 `m:f`。
- 上下标沿用现有递归 parser，接受 MinerU 带空格形式；不为每种变量名添加正则。

### 失败合同

未知命令、未闭合分组和非法参数继续使 parser 返回失败，renderer 保留原文，`docx_quality` 继续报告 `docx_latex_residue`。不得把未知命令删除后伪装成成功。

### 不增加依赖

项目现有 `python-docx`/`lxml` 已能构造 OMML；当前 8 份 content-list 未出现环境语法。`latex2mathml`、`sympy`、`pandoc` 均未安装，增加依赖还需要 MathML→OMML 转换与新的失败边界，当前不成立。

Microsoft 365 的完整分类仅作为范围地图：<https://learn.microsoft.com/en-us/office/math/latex>。本任务用明确支持矩阵和残留质量证据定义本项目子集，不声称实现完整 Microsoft 转换器。

## 数据与兼容性

- v2 优先是输入选择纠错；legacy-only 包继续支持。
- 页面宽高数值可能改变，但 schema 和坐标单位字段不变；所有 bbox 消费者得到同一比例空间。
- 仅有明确列表信号的 paragraph/text block 改为 list；普通段落保持原输出。
- 语义分页只作用于源页顶部 heading 或带注释的独立表格组，不恢复每页硬分页。
- inline TeX 从普通文本恢复为 OMML 是有意行为变化；畸形/未知公式仍可见。

## 风险与回滚点

- `mineru_package.py`：多候选选择行为；可独立回退排序键。
- `layout_signals.py`：页面 width/height 同时影响栏位和图片显示比例；覆盖 portrait、landscape、无 layout 三类。
- `mineru_content.py` / `mineru_converter.py`：列表提升与 inline math 保真；覆盖普通正文和明确公式邻接文本。
- `layout_plan.py`：纯非重叠栏依赖稳定补偿；保留既有 characterization test。
- `word_renderer.py` / `table_renderer.py`：分页只附着真实段落；需对 CM4112 和 SC2167 同时做空白页回归。
- `text_renderer.py`：parser 扩展共享 formula/inline/table 三条入口；用一组代表性 OOXML 测试证明，不按具体文档复制实现。

不需要迁移或发布开关；每项按权威模块独立可回退。
