# Research: SC2167 扩展 TeX 到原生 OMML

- Query: 检查真实 MinerU 包中 `\overline`、`\mathbf`、`\bigotimes`、`\boxed`、`_{DD}`、`_{TRACK}` 的输入形态、当前残留原因，以及正文、标题、表格和公式块共用的最小正确 OMML 扩展。
- Scope: mixed
- Date: 2026-08-18

## Findings

### 真实包与现有产物

- 输入包为 `/Users/sc/Downloads/mineru_raw_result.zip`。当前 `find_content_list()` 对同层候选按路径字符串排序（`app/services/document_ir/mineru_package.py:22-34`），本包实际选中无 `_v2` 后缀的 `37548120-74b7-4402-be65-6761475b5494_content_list.json`；以下计数以正式转换实际消费的该文件为准。
- 真实输入共有：`\overline` 126 次、`\mathbf` 3 次、`\bigotimes` 2 次、`\boxed` 1 次、`_{DD}` 13 次、`_{TRACK}` 2 次。
- 典型来源：
  - 表格：block 51 的 `EXC` 互补信号、block 68 的时序引脚、block 90 的管脚定义都包含 `\overline`；block 90 还包含 `AV $_{DD}$` 及同一句中的 `AV $_{DD}$` / `DV $_{DD}$`。
  - 正文/标题：block 229、231 为 `$\overline{\mathbf{SOE}}$`、`$\overline{\mathbf{SAMPLE}}$`；block 280、288 为 `$\bigotimes$`；block 326 为 `$\boxed{\mathrm{X}}$`；block 352 包含 `$\mathbf{t}_{\text{TRACK}}$` 和多个普通 `t_{\text{TRACK}}`。
- 现有 `/Users/sc/Downloads/SC2167_native_word_verified.docx` 的质量证据恰有 6 类唯一残留：`_{DD}`、`\overline`、`\mathbf`、`\bigotimes`、`\boxed`、`_{TRACK}`。其 `document.xml` 中 `m:bar`、`m:borderBox`、粗体 `m:sty` 和 U+2A02 均为 0；反而有 398 个组合上划线 U+0305。这说明当前简单 `\overline` 虽未都被残留检测捕获，但也没有生成可编辑的原生上划线结构。

### 当前代码路径与根因

- 正式公式块从 `word_renderer.py:344-347` 进入 `text_renderer.py:387-399` 的 `_fill_formula_paragraph()`，直接调用 `_OmmlParser`。
- 正文和标题最终进入 `_fill_paragraph()`（`text_renderer.py:235-259`）；其中 `_render_mixed_math()` 在 `text_renderer.py:450-486` 识别 `$...$` / `\(...\)` 并复用 `_OmmlParser`。真实 HTML 表格单元格也调用同一个 `_fill_paragraph()`（`table_renderer.py:200-218`），因此不应另建表格公式实现。
- `_OmmlParser._parse_command()` 目前只专门处理 `frac`、`mathrm/mathsf/text`、`sqrt`，其余仅查共享字符映射（`text_renderer.py:121-166`）；新四个命令均未被完整支持。
- `GREEK_AND_TEXT_COMMANDS` 已是共享单符号命令的权威映射（`text_semantics.py:71-97`），适合只新增 `bigotimes: "⨂"`；结构命令仍应留在正式 OMML parser。
- 标题入口 `_fill_heading_paragraph()` 在调用 `_fill_paragraph()` 前先执行了一次 `normalize_formula_text()`（`text_renderer.py:261-275`）。这会让本来可由 OMML parser 消费的简单公式先退化成组合字符或普通 HTML；应把原始文本直接交给已有共享入口，避免双重归一化。
- 真实的三个 `_{DD}` 残留都来自 `AV $_{DD}$` / `DV $_{DD}$`。其余 10 个带明确基底的 `AV_{DD}`、`DV_{DD}` 已能生成 `m:sSub`。因此问题不是通用下标语法，而是 MinerU 把基底与下标拆到相邻的普通文本和数学片段。
- `LATEX_RESIDUE_RE` 已覆盖控制词和 `_{...}`（`docx_quality.py:22-24`），并按唯一字符串归并（`docx_quality.py:327-335`）。成功 OMML 解析后原文命令自然消失；无需为这些已受支持命令另建质量判断或白名单。畸形输入继续保留并由现有证据报告。

### 最小正确语法与 OOXML 映射

1. `\overline{expr}`：递归解析必需参数组，生成：

   ```xml
   <m:bar>
     <m:barPr><m:pos m:val="top"/></m:barPr>
     <m:e>...</m:e>
   </m:bar>
   ```

   Microsoft 的 OMML 说明明确把 `\overline` 映射为 `m:bar` top，而不是 `m:acc` 或逐字符 U+0305。

2. `\mathbf{expr}`：递归解析参数组，并给其中每个 `m:r` 在 `m:t` 前写入 `<m:rPr><m:sty m:val="b"/></m:rPr>`。真实样本的参数均为简单 `SOE`、`SAMPLE`、`t`；为了不限制同一已解析组，多个节点可沿用现有 `m:box/m:e` 组合包装，不增加新 AST。
3. `\boxed{expr}`：递归解析参数组，生成 `<m:borderBox><m:e>...</m:e></m:borderBox>`；不需要属性节点即可表达普通四边框。
4. `\bigotimes`：加入共享命令映射，值必须是 U+2A02 `⨂`，不是 U+2297 `⊗`。当前真实用法没有上下限，只需 `m:r/m:t`，无需引入 `m:nary`。
5. `base_{sub}` / `base^{sup}`：继续使用现有 `m:sSub` / `m:sSup`。`\mathbf{t}_{\text{TRACK}}` 在 `mathbf` 返回单一可作为基底的 OMML 节点后，会自然走现有 `_script()`（`text_renderer.py:212-220`）。
6. 对 `AV $_{DD}$` 这种拆分输入，不应把 `_` 放宽成任意空基底或错误的 `m:sPre`。在 `_render_mixed_math()` 处理某个数学片段前，仅当表达式以 `_`/`^` 开头且前一普通片段以明确的字母数字 token 结束时，把该 token 从普通片段取出并与表达式组合为 `AV_{DD}`，再交给同一 parser。没有可证明基底的孤立 `_{...}` 仍保持原文并报告质量残留。
7. 新命令应加入 `DOUBLE_ESCAPED_TEX_COMMAND_RE` 的已支持命令列表，保证 MinerU 偶发双反斜杠输入先收敛到同一 grammar；不应在共享普通文本归一化中把 `mathbf` / `boxed` 静默剥掉，否则解析失败会被伪装成成功。

### 目标文件与测试

- 产品代码：
  - `app/services/renderer/text_renderer.py`：扩充 `_OmmlParser._parse_command()`、数学 run 样式、拆分下标基底合并；移除标题入口的提前公式归一化。
  - `app/conversion/docx_rules/text_semantics.py`：增加 `bigotimes` 字符映射，并把 `mathbf`、`bigotimes`、`boxed` 加入双反斜杠收敛列表。
  - `app/services/renderer/docx_quality.py`：现有规则已够用，预计无需修改。
- 回归测试：
  - 在 `tests/test_document_ir_word_renderer_layout.py` 靠近现有公式测试（`466-537`）增加一个样本，至少同时覆盖 formula block、普通/heading inline math 和 HTML table cell。
  - 合成内容应包含 `\overline{\mathbf{SOE}}`、`\boxed{\mathrm{X}}`、`\bigotimes`、`\mathbf{t}_{\text{TRACK}}`、`AV $_{DD}$`、表格中的 `DV $_{DD}$`。
  - 断言 `m:bar + m:pos top`、`m:rPr/m:sty b`、`m:borderBox`、U+2A02、`m:sSub` 的 `(AV,DD)` / `(DV,DD)` / `(t,TRACK)`；断言 XML 无六类字面残留，`analyze_docx_quality_bytes()` 的 `latex_residue_count == 0`。
  - 保留现有畸形分式测试；可用孤立或未闭合 `\overline{...` 补一个失败断言，证明没有把错误 TeX 静默吞掉。
  - `tests/test_text_render_characterization.py:138-140` 目前只验证共享普通文本把简单 overline 降级为组合字符。该兼容行为可保留，但应另加 `\bigotimes -> ⨂` 的共享语义断言；正式 Word 原生路径的主要结构断言必须放在 renderer 测试中。
- SC2167 真样本验收建议：转换后 `document.xml` 至少应有 `m:bar=126`、粗体 `m:sty b=3`、`m:borderBox=1`、U+2A02 `⨂=2`，并且六类质量残留全部消失；同时用 LibreOffice 检查上划线覆盖整个标识符、粗体位于上划线内、方框和大运算符可见、AV/DV 与 DD 下标没有断开。

## Files Found

- `app/services/renderer/text_renderer.py` — 正式 Word 文本、标题、公式和 OMML 的唯一共享入口。
- `app/services/renderer/table_renderer.py` — HTML 单元格复用 `_fill_paragraph()`，无需第二套公式 parser。
- `app/services/renderer/word_renderer.py` — heading、paragraph、formula、table 的正式调度入口。
- `app/conversion/docx_rules/text_semantics.py` — 共享字符命令与双反斜杠归一化规则。
- `app/services/renderer/docx_quality.py` — DOCX TeX 残留统计与质量 flag。
- `app/services/document_ir/mineru_package.py` — 决定真实包实际消费哪个 content-list。
- `tests/test_document_ir_word_renderer_layout.py` — 现有 OMML 和 DOCX 质量回归测试。
- `tests/test_text_render_characterization.py` — 共享/兼容文本语义 characterization tests。
- `/Users/sc/Downloads/mineru_raw_result.zip` — 真实公式输入样本。
- `/Users/sc/Downloads/SC2167_native_word_verified.docx` — 当前六类残留和非原生上划线的复现产物。

## External References

- Microsoft 365 LaTeX 支持表：`\overline` ↔ `m:bar`、`\boxed` ↔ `m:borderBox`、`\bigotimes` ↔ U+2A02、上下标 ↔ `m:sSub/m:sSup`：https://learn.microsoft.com/en-us/office/math/latex
- Microsoft Open XML `m:bar` 示例及 `m:pos m:val="top"`：https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.math.bar?view=openxml-3.0.1
- Microsoft Open XML `m:sty`，`b` 表示 bold，且节点位于 `m:rPr`：https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.math.style?view=openxml-3.0.1
- Microsoft Open XML `m:borderBox` 的子节点为 `borderBoxPr`、`e`：https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.linq.m.borderbox?view=openxml-3.0.1
- 本地依赖版本：`python-docx 1.2.0`、`lxml 6.1.1`、`beautifulsoup4 4.15.0`；现有代码已用 `OxmlElement` 直接构造 OMML，不需要新依赖。

## Related Specs

- `.trellis/spec/backend/quality-guidelines.md`：DocumentIR 语义明确时使用 OMML；公式、section 等需同时检查 OOXML 与 LibreOffice 可见结果；畸形输入不得伪装成功。
- `.trellis/tasks/08-18-fix-layout-formula-image-caption/prd.md`：R0 原生优先、R2 OMML 与残留证据合同。
- `.trellis/tasks/08-18-fix-layout-formula-image-caption/design.md`：正式 `DocumentIRWordRenderer` 是权威路径，表格与正文共享文本入口，不引入数学依赖。

## Caveats / Not Found

- 本研究没有修改产品代码，也没有生成新 DOCX。
- 当前需求不等于支持完整 LaTeX；仅扩充真实样本出现的四个命令和两类现有上下标组合。矩阵、积分、可带上下限的通用 n-ary operator 仍不应顺带实现。
- `\overline` 的普通文本兼容归一化仍可保留 U+0305 行为，但正式 Word 数学片段必须优先进入 OMML；质量扫描只看残留字面文本，不能替代 `m:bar` 结构断言。
- `m:bar=126` 是以当前正式消费的 flat content-list 计得的真样本目标；若后续修改 content-list 选择规则，需按新的权威输入重新核算，不能把该计数硬编码进通用单元测试。
