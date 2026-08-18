# Research: SC2167 Word 空白页根因

- Query: 调查 `/Users/sc/Downloads/SC2167_native_word_verified.docx` 在 Microsoft Word 中出现多页空白的结构原因，区分真实输入/分页缺陷与 LibreOffice、Word 的排版差异，并给出最小修复及回归测试建议。
- Scope: mixed
- Date: 2026-08-18

## Findings

### Files found

- `app/services/renderer/word_renderer.py`：正式 DocumentIR→DOCX 页面循环、同方向源页分页符、方向变化分节及原生双栏分节。
- `app/services/renderer/layout_plan.py`：把每个 DocumentIR 页无条件保留为 `LayoutPage`，即使该页没有可见正文区域。
- `app/services/document_ir/layout_signals.py`：正式 DocumentIR 路径只合并显式 `type=table_placeholder`，不识别 MinerU 用空 `type=table` 表示的续表占位页。
- `app/services/renderer/table_renderer.py`：空 HTML 表格仍会生成一个空正文段落。
- `app/conversion/runtime/input_adapter_runtime.py`：旧兼容路径已有 `is_empty_table_placeholder()`，能识别 `type=table + html="" + image path="images/"`，是可复用的已验证规则。
- `app/conversion/runtime/page_repair_runtime.py`：旧兼容路径已有续表占位页收集逻辑，但正式 DocumentIR 路径没有获得等价输入归一化。
- `tests/test_document_ir_word_renderer_layout.py`：现有测试明确要求每个同方向源页写一个 `w:br type="page"`，并要求某些分页符与连续分节结束段落共存；该测试把当前风险固化为合同。
- `/Users/sc/Downloads/mineru_raw_result.zip`：34 页 MinerU 输入；源页索引 8 含完整 48 行“表 3”HTML，源页索引 9、10 又各含一个空表续页占位块。
- `/Users/sc/Downloads/SC2167_native_word_verified.docx`：生成样本，含 32 个显式 `w:br type="page"`、9 个段落级 `sectPr` 和 1 个正文末 `sectPr`。

### Verified blank pages in the current artifact

1. LibreOffice 26.2.4.2 转出的 42 页 PDF 并非“无空白页”。逐页正文核对显示：
   - 第 17 页只有模板页眉“数据手册”和页码 `17`；
   - 第 18 页只有模板页眉、被 MinerU 错分为正文的“版本号：V1.1”和页码 `18`。
   先前检测只判断整页是否存在文本，因页眉/页脚和页码始终存在而产生了假阴性。
2. `document.xml` 的直接触发序列位于正文子元素 73–78：
   - 元素 73 是从源页索引 8 生成的完整“表 3”；该表已由 Word 自然重排到输出第 12–16 页；
   - 元素 74 是表后显式分页符；
   - 元素 75 是源页索引 9 的空表回退段落，并带下一个显式分页符，形成输出第 17 页；
   - 元素 76 是源页索引 10 的第二个空表回退段落；
   - 元素 77 是源页索引 10 底部 `bbox=[452,935,545,949]` 的“版本号：V1.1”，并带下一个分页符，形成输出第 18 页；
   - 元素 78 才开始“典型性能参数”。
3. MinerU 原数据证明这不是源 PDF 的两张空白物理页：
   - 页 8 的表块已经包含表 3 的全部 HTML；
   - 页 9 的表块为 `html=""`、`image_source.path="images/"`、无 caption/footnote；
   - 页 10 有相同空表块，并有处于页面底部的版本文字。
   因而这些页表示续表占位/页脚识别误差，不应再次生成独立 Word 正文页。

### Root cause

根因不是单一 `sectPr`，而是把 PDF 物理页边界当成可编辑 Word 正文的强制分页边界：

- 正式 renderer 对每个同方向 `LayoutPage` 无条件调用 `_append_page_break()`（`app/services/renderer/word_renderer.py:79-96`）。当长表、图片或段落已由 Word 自然跨页，后续固定分页符可能落在新页页首，产生空白或近空白页；Word 与 LibreOffice 的字体、表格行高和栏平衡不同，所以具体空白页数量不能靠 LibreOffice 页码外推。
- `_append_page_break()` 会在末元素为表格时创建空段落（`word_renderer.py:513-522`）。空续表块又会由 `_render_table()` 再创建空段落（`table_renderer.py:42-55`），于是连续的源页边界被具体序列化为连续空段落/分页符。
- 正式输入归一化只识别显式 `table_placeholder`（`layout_signals.py:114-136`），遗漏本样本真实 MinerU 合同中的“空 table + `images/`”形式。旧兼容路径已在 `input_adapter_runtime.py:477-548` 正确识别这一形式，说明不需要发明新启发式。
- 当前文档没有 `oddPage` 或 `evenPage` 分节；分节类型只有 `continuous` 和默认 `nextPage`，所以不能把空白页归因于奇偶页补齐。
- 当前 `settings.xml` 没有 `w:splitPgBreakAndParaMark`。Microsoft 的 OOXML 说明指出，默认情况下，段末分页符不会把段落标记单独推到下一页；只有启用该兼容设置才会这样做。因此“分页符追加在末段”本身不足以解释已经确认的第 17、18 页，连续的源页硬分页和空续表块才是直接证据。
- `w:updateFields=true` 会让 Word 打开时更新域并重新分页，但本样本没有 TOC 域；它不是空白页的内容来源，只会放大 Word/LibreOffice 分页差异。

### Microsoft Word caveat

本机没有安装 Microsoft Word，无法直接读取 Word 的最终分页缓存，因此不能声称用户在 Word 中看到的每一个空白页页码都已复现。可以确认的是：当前 OOXML 已含两个跨渲染器可见的空白/近空白页，且“每个 PDF 页一个硬分页”的结构会因 Word 的表格和分栏重排产生额外候选页。最终验收应使用 Microsoft Word 打开并更新域后的 PDF，LibreOffice 只能作为第二实现的交叉检查。

### Smallest robust fix

建议按根因做两项小改动，不再为具体页码打补丁：

1. 将旧兼容路径已有的空表占位谓词收口为共享纯函数，让正式 MinerU→DocumentIR 路径也把 `type=table`、无 HTML/题注/正文且资产目录为 `images/` 的块归一化为续表占位，并并入前一真实表的 `continuation_heights`。不要在 renderer 中按 SC2167 文本或页码删除段落。
2. 同方向 PDF 页不要无条件写 `w:br type="page"`；Word 正文应由原生流式排版决定分页，只在页面方向变化时保留 `NEW_PAGE` section。若产品仍要求部分强制分页，应由明确的 IR page-break 语义驱动，而不是由每个 `DocumentIRPage` 的存在隐式驱动。该删除比“预测当前内容是否已经溢出”更小，也避免建立一套不可能与 Word 完全一致的分页引擎。

单独“跳过无 body 的 LayoutPage”只能消除页 9，占位页 10 仍有误识别的底部版本文字，而且无法解决 Word 与 LibreOffice 对其他长表产生的不同溢出位置，因此不是完整根因修复。

### Required tests

- 在 `tests/test_document_ir_mineru_converter_layout.py` 使用真实形状：首个真实表后跟两个 `type=table`、`html=""`、`image_source.path="images/"` 的续页，断言仅保留一个真实表且累计两个 `continuation_heights`，不产生空表正文块。
- 改写 `tests/test_document_ir_word_renderer_layout.py:181-235`：两个同方向 IR 页不应仅因 page index 不同就产生 `w:br type="page"`；方向变化仍必须产生一个 `NEW_PAGE` section；连续双栏恢复仍为 `CONTINUOUS`。
- 真样本 OOXML 断言不再出现“连续 break-only 段落”，并检查空表占位不生成空正文段。
- LibreOffice 和 Microsoft Word 验收都应在更新域后检查“正文空白”，检测时排除页眉、页脚和页码区域；不能继续以整页 `pdftotext` 非空作为无空白页证据。

### External references

- Microsoft Learn, `SectionType`: continuous section 从下一段开始，next/odd/even page 是不同的明确类型：<https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.sectiontype?view=openxml-3.0.1>
- Microsoft Learn, `SplitPageBreakAndParagraphMark`: 说明段末 `w:br type="page"` 的默认段落标记行为及兼容开关：<https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.splitpagebreakandparagraphmark?view=openxml-3.0.1>
- Microsoft Learn, `WdBreakType`: continuous、next page、odd page、even page 的 Word 行为：<https://learn.microsoft.com/en-us/office/vba/api/word.wdbreaktype>

## Caveats / Not Found

- 未找到该 DOCX 的 Microsoft Word `lastRenderedPageBreak` 缓存，也没有本机 Word 可执行文件；无法给出 Word 专属的稳定页码映射。
- 没有证据表明奇偶页分节、TOC 更新或页眉 relationship 制造了当前两页空白。
- 页 10 的“版本号：V1.1”由 MinerU 错标为普通 paragraph。它应随新的自定义模板页脚规则一起处理，但不建议在空白页修复中硬编码该文本；移除无条件同方向硬分页后，它至多是多余正文，不再单独制造一页。
