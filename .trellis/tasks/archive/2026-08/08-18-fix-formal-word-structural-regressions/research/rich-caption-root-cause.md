# Research: v2 富文本图注孤立行与极稀疏页根因

- Query: 追踪正式 MinerU v2 `text/equation_inline/text` 图注从 raw → DocumentIR → DOCX 的数据形态，解释图 33 为何拆成独立 Word 段落，并确定唯一 owner、最小根修复和回归边界。
- Scope: internal / external sample evidence
- Date: 2026-08-19

## Findings

### 1. 文件与证据

- `/Users/sc/Downloads/mineru_raw_result 2/ddd54804-71d7-4ca5-91a1-b99ab35cab75_content_list_v2.json`：CM4112/CM4114 的权威 v2 输入；JSON Pointer `$[11][2].content.chart_caption` 是图 33 的单条富文本题注。
- `/tmp/md2word-cm4112-structural-fix/cm4112-fixed.document-ir.json`：当前正式候选的 IR；`block_0097` 把图 33 保存为三个 `captions` 元素。
- `/tmp/md2word-cm4112-structural-fix/document-formatted.xml`：当前 DOCX 的格式化 `word/document.xml`；第 10322～10354 行可见图 33 主题注、`±`、`18V)` 分属三个 `w:p`。
- `app/conversion/docx_rules/mineru_content.py`：通用 MinerU 文本拍平、富文本节点拼接和脚注片段合并 helper。
- `app/services/document_ir/mineru_converter.py`：正式 MinerU→DocumentIR 的图注语义 owner。
- `app/services/document_ir/models.py`：`DocumentIRBlock.captions`/`footnotes` 的持久化合同；当前类型都是 `list[str]`。
- `app/services/renderer/image_renderer.py`：图片题注输出；把每个 annotation 字符串当作独立 Word 段落。
- `app/services/renderer/table_renderer.py`：表题/表注输出；同样把每个 caption 字符串当作独立段落。
- `app/services/renderer/word_renderer.py`：题注书签收集与严格图片对判定；多 annotation 会退出 COL-003 成对图片路径。
- `tests/test_document_ir_mineru_converter_layout.py`：现有真实 v2 chart 测试反而锁定了错误的碎片化 IR 结果。
- `.trellis/tasks/08-18-fix-formal-word-structural-regressions/research/cm4112-validation.md`：WPS GUI/CLI 和 LibreOffice 的当前真实样本观察边界。

### 2. 原始 v2 合同：一条题注由多个行内节点组成

图 33 的原始结构是：

```json
"chart_caption": [
  {"type": "text", "content": "图 33 通道隔离度 (  "},
  {"type": "equation_inline", "content": "\\pm"},
  {"type": "text", "content": " 18V)"}
]
```

这里 `chart_caption` 的整个数组是一条逻辑题注，三个对象只是该题注的行内富文本节点，并非三条 caption。对 CM4112 v2 输入做形状统计得到：38 个 `chart_caption` 中 34 个都是这种 3 节点富文本数组；其余 4 个是单节点数组。当前 IR 中也恰有 34 个 chart image 的 `captions` 长度大于 1，说明错误是一对一发生在转换边界，不是 WPS 自行拆段。

样本内 `image_caption` 和 `table_caption` 也使用“数组内放富文本节点”的同一 v2 形状，只是本样本没有多节点公式图注。既有合成测试还覆盖了 `table_caption: [[{...}]]` 的嵌套包装，说明实现必须允许“逻辑项外再包一层列表”，不能只针对 chart 写特例。

### 3. 根因：通用文本收集器丢失了逻辑分组

`coerce_text_list()` 遇到 list 时递归展开每个元素，并把 `text` 和 `equation_inline` 节点分别转换成独立字符串（`app/conversion/docx_rules/mineru_content.py:98-133`）。`collect_text_from_fields()` 随后逐字符串去重并追加，没有保留原始数组代表的逻辑题注边界（`app/conversion/docx_rules/mineru_content.py:136-145`）。

正式 converter 的 `_captions()` 对 chart/image/figure/table 全部直接调用该通用拍平函数（`app/services/document_ir/mineru_converter.py:406-412`）。因此图 33 在 IR 中成为：

```json
"captions": ["图 33 通道隔离度 (", "±", "18V)"]
```

`DocumentIRBlock.captions` 只有 `list[str]`，每个元素在 renderer 侧已被解释为一条逻辑 annotation（`app/services/document_ir/models.py:62-78`）。边界信息一旦在 converter 丢失，renderer 没有可靠依据重新判断这三个字符串是行内片段还是三条独立题注。

现有测试 `test_convert_zip_maps_nested_v2_chart_to_image_and_records_source_inventory` 明确断言 `captions == ["图 1 输出", "V<sub>OUT</sub>"]`（`tests/test_document_ir_mineru_converter_layout.py:175-215`），把当前缺陷固化成了预期。该断言应改为单个完整题注，而不是新增 renderer 侧猜测。

### 4. 为什么会形成独立行和极稀疏页

图片 renderer 先组合 `block.captions + metadata.caption + block.footnotes`，然后保留每个字符串为独立 annotation（`app/services/renderer/image_renderer.py:194-209`）。普通图片路径对每个 annotation 调用一次 `document.add_paragraph()`（`app/services/renderer/image_renderer.py:76-94`），并给除最后一个外的段落设置 `keep_with_next`。所以三个 IR 元素必然成为三个 `w:p`，而不是同一段落内的三个 run/OMML 节点。

当前 OOXML 对图 33 的实际结果为：

- `/tmp/md2word-cm4112-structural-fix/document-formatted.xml:10322-10342`：含 `SEQ 图`、编号 33 和“通道隔离度 (”的主题注段落；
- `...:10343-10350`：只含 `±` 的第二段，带 `keepNext`；
- `...:10351-10354`：只含 `18V)` 的第三段；
- `...:10356` 起紧接 `Heading1`“工作原理”。

WPS 12.1.26055 GUI 对同一 DOCX 实际排版为 27 页，第 17 页只剩图 33 拆出的 `±18V)` 片段，“工作原理”从第 18 页开始；这已记录在 `research/cm4112-validation.md:41-54`。因此所谓“标题前空白页”实为题注碎片被分页后形成的极稀疏页，并无证据支持修改 continuous section 或标题强制分页规则。

这个错误还有一个放大效应：严格成对图片只在每张 image 的 annotation 数不大于 1 时成立（`app/services/renderer/word_renderer.py:621-632`）。富文本题注被拍成 3 条后，34 张 chart 都会被视作“多 annotation”，退出 COL-003 制表位图片对路径，改走原生双栏流；因此修复逻辑分组也会恢复这些图的正确配对资格，无需新增布局规则。

### 5. 唯一 owner 与最小根修复

唯一权威 owner 应是 `MinerUToDocumentIRService._captions()`（`app/services/document_ir/mineru_converter.py:406-412`）：这里首次同时知道“当前字段是 caption”以及原始值的数组层级，并负责把 MinerU 语义转换成 `DocumentIRBlock.captions`。renderer 的既有合同“一个 `captions` 元素 = 一条 Word 题注/annotation”是正确的，不应在那里根据标点、公式或文本长度重新合并。

最小根修复应只收紧 caption 的 value-level 归一化，并复用已有文本清理/公式归一化能力：

1. 一个 list 若全部元素都是富文本 inline node dict（`text`、`equation_inline`、`inline_formula` 等既有可读取节点），则该 list 是一条逻辑 caption；先用现有 `coerce_text_list()` 得到可渲染片段，再按已有 `append_footnote_fragment()` 的标点/CJK 拼接规则合成一个字符串。
2. 外层 list 若包含 string 或子 list，则每个 string/子 list 是独立逻辑 caption；对子 list 递归执行上一步。这样 `[[rich nodes 1], [rich nodes 2]]` 保持两条，legacy `['图 3', '图 5']` 也保持两条。
3. 单个 string 保持一条；空项仍过滤；最终继续使用 `_unique_texts()` 去重。
4. 不全局改变 `collect_text_from_fields()`：它还被末页实质内容判断、table placeholder 判断和 footnote 等路径使用（`app/conversion/docx_rules/mineru_content.py:190-215`，`app/services/document_ir/layout_signals.py:308-310`）。全局改变会扩大无关语义回归面。

现有 `append_footnote_fragment()` 会在左侧以 `(` 结束时直接拼接，在右侧为 `)`/标点时直接拼接，在 CJK 边界直接拼接，其余情况补一个空格（`app/conversion/docx_rules/mineru_content.py:309-322`）；它足以把图 33 组成单个可见字符串“图 33 通道隔离度 (± 18V)”，也能保留 `V<sub>OUT</sub>` 这类现有 inline HTML 结果，避免用 `join_text_fragments()` 生成 renderer 当前题注专用路径未必消费的 `$...$` 字面量。

不应修改：

- `image_renderer.py` / `table_renderer.py`：它们无法可靠区分“多条真实 annotation”和“已丢失边界的片段”；在这里合并会破坏真正的多题注/脚注。
- `DocumentIRBlock.captions` 类型：本问题不需要引入新的 rich-node IR schema；当前 renderer 已能把合并后的 sub/sup HTML 留在同一题注段落。
- continuous section / `pageBreakBefore`：稀疏页是内容分组错误的下游结果，不是这些规则的根因。
- legacy runtime：当前任务只约束正式链路；历史 runtime 的相同行为仅是差异证据，不迁移、不双修。

### 6. 多逻辑题注与脚注的区分边界

- caption：v2 的“flat list of inline node dicts”按一条逻辑题注处理；string 列表或“list of rich-node lists”按多个逻辑题注处理。这个判定只使用结构，不根据是否以“图/表”开头、页码、型号或 bbox 猜测。
- footnote：继续走现有 `_footnotes() → merge_footnote_fragments()`（`app/services/document_ir/mineru_converter.py:414-420`）。该函数用 `(5)`、`[1]`、`Note:`/`注:` 等新注释起始标记分割，使用标点/语法连续性合并同一脚注片段（`app/conversion/docx_rules/mineru_content.py:234-322`）；不要把所有 footnote 无条件并成一条。
- 无可靠结构时保持原状：如果未来 MinerU 在同一个 flat rich-node list 中无分组地编码两条题注，当前输入合同无法无损区分；本任务不应增加基于文本内容的启发式猜测，应先用真实 schema/样本明确边界。

### 7. 受影响调用者

- chart/image/figure：全部经 `_captions()`，并在普通图片路径按 annotation 输出；修复后同一富文本题注成为一个 Word 段落。
- 严格图片对：`_split_two_column_image_rows()` 的 `len(annotation) > 1` 防线会重新把一条富文本题注视为一个 annotation，从而恢复 COL-003 资格；`_render_two_column_image_row()` 继续每侧只消费第一条题注是安全的（`app/services/renderer/image_renderer.py:132-166`）。
- table：同样经 `_captions()`；`_render_table_captions()` 当前为每个逻辑 caption 新建段落（`app/services/renderer/table_renderer.py:278-308`），修复后多片段表题也会自然保持为一个段落。`split_table_annotation_texts()` 应继续在合并后的完整字符串上判断 caption/context。
- bookmark/SEQ：`_build_render_context()` 当前逐 annotation 解析题注编号（`app/services/renderer/word_renderer.py:133-160`）。合并后仍由完整题注首部生成相同编号/bookmark，孤立公式片段不再作为无意义 annotation 被扫描。
- image fallback：`_text_for_block()` 和 `_image_fallback_text()` 都取第一条 caption（`app/services/document_ir/mineru_converter.py:337-348`；`app/services/renderer/image_renderer.py:190-192`）；合并后 fallback 也会从“只有题注首片段”修正为完整题注。

### 8. 最小回归与视觉检查

1. Converter 定向测试：把现有 nested v2 chart 断言改为单条完整 caption，并至少覆盖 `text/equation_inline/text`，例如 `['图 1 输出 V<sub>OUT</sub>']`；同时断言 source inventory、asset 和 chart→image 合同不变。
2. 分组负例：一个 legacy string list 或两个嵌套 rich-node groups 必须仍产生两条 caption，保护 `_reassociate_image_group()` 的真实多题注语义。
3. Renderer 定向测试：含 `图 33 ... ( / ± / 18V)` 的单条 caption 最终只有一个 caption `w:p`，同一段内保留 `SEQ` 33 和完整可见文本；DOCX 中不得出现文本恰为 `±` 或 `18V)` 的独立段落。
4. COL-003 冲突回归：两张各含单条富文本 caption 的 chart 仍走严格图片对路径，题注顺序正确且不新增 continuous section；真正两条 captions/footnote 的 image 仍退出配对路径。
5. 表题共享回归：多片段 table caption 合并为一段，但两个真实 table captions 仍是两段；table context 判定和表体/表注顺序不变。
6. CM4112 正式样本：重新生成后确认 `block_0097.captions` 长度为 1 且文本完整；drawing/table/heading 对账仍为 53/8/18，`blocking_quality_flags=[]`；OOXML 不再有图 33 后的独立 `±`、`18V)` 段。
7. WPS 12.1.26055 GUI：重新打开新 hash 的 DOCX，确认原第 17 页不再只含题注碎片，“工作原理”前无由该碎片形成的极稀疏页；记录新页数和客户端分页差异。LibreOffice/WPS CLI 只作辅助，不能替代 GUI 结论。

### 9. External references / versions

- 未使用网络资料；本问题由本地 MinerU v2 payload、DocumentIR 和 OOXML 直接证明。
- WPS Office 12.1.26055（build 26055）GUI：同一候选为 27 页，观察到第 17 页题注碎片极稀疏页。
- 同一 WPS 安装包的 `wpscli 1.1.0`：候选转 PDF 为 21 页，仍可见富文本图注拆行。
- LibreOffice 26.2.4.2：候选转 PDF 为 23 页；不同客户端页数不构成固定页数合同。

### 10. Related specs

- `INPUT-004`：v2 rich text 与 inline equation 边界；当前规则尚未明确“caption 节点数组是一条逻辑 annotation”。
- `IR-001`：DocumentIR 是内容/版式事实边界；caption 的逻辑分组必须在进入 IR 前确定。
- `COL-003`：多 annotation 禁止强行图片配对；本修复必须区分“单条富文本题注”与“多条真实 annotation”。
- `TEXT-003`：富文本保真与共享文本归一化；不得丢失 inline node 或在 renderer 分叉清理。
- `TABLE-002`、`IMAGE-001`、`FIELD-002`：分别约束表题顺序、图片题注可见性和题注 SEQ/bookmark。
- `QUALITY-003`：实际分页/极稀疏页必须用当前代码生成物在 WPS 验证，不能只靠 OOXML。

## Caveats / Not Found

- CM4112 v2 样本没有“两个独立 caption 各自为 rich-node list”的真实项；该形状来自既有嵌套测试和保守结构合同，需要用合成回归保护，但不能声称已由真样本证明。
- 当前 `DocumentIRBlock` 不保存原始 rich node；本任务的最小修复只能合并为已有 renderer 可消费的字符串/inline HTML。若未来要求题注中的任意复杂 TeX 都生成 OMML，需要单独扩展 IR/renderer 数学合同，不能夹带进本次分页修复。
- WPS GUI 仅已确认问题页和部分关键页，尚未完成全部 27 页复核；修复后必须重新执行完整或至少受影响页段的 GUI 验收。
- `/tmp` 产物属于当前未提交工作区的 external evidence，不是 committed Golden fixture。
