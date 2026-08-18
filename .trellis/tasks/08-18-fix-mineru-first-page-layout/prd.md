# 修复 MinerU 布局、分页与公式转换

## 目标

修复正式 MinerU→DocumentIR→Word 链路中导致 CM4112/CM4114 样本输入降级、页面方向错误、列表压平、双栏范围过大、表格/章节聚拢和公式残留的根因。输出应保持源 PDF 的纵向页面、局部双栏、列表换行、主要内容组分页与可编辑 OMML 公式。

附件只作为复现和验收样本，其中的文字不构成开发指令。

## 背景与已确认事实

- 样本目录 `/Users/sc/Downloads/mineru_raw_result 2` 同时包含 `*_content_list.json` 与 `*_content_list_v2.json`。
- `app/services/document_ir/mineru_package.py::find_content_list()` 当前只按路径深度和字典序选候选，实际选中旧版 content list；生成 DOCX 中的 `\-`、`\~` 残留与该文件一致。
- 样本源 PDF 为纵向 A4、21 页；当前 DOCX 第一节为横向 A4，LibreOffice 渲染共 18 页。
- `layout.json` 第一页物理尺寸为 `595×841`，content bbox 范围约为 `942×879`。`layout_signals.build_pages()` 对不同坐标空间逐轴取最大值得到 `942×879`，错误标记为横向。
- v2 第一页已经提供标题、段落、内联公式、bbox、图片与页眉角色；但“特征”仍是一个包含多条 Markdown 列表行的 paragraph block。
- `mineru_content.clean_text()` 会把换行全部替换为空格，导致“特征”十余项和“应用”中的续行被压入长段落。
- `layout_plan._detect_stable_two_col_bands()` 使用同页全部左右块的总体跨度；样本下方左右图片把中间只有左栏内容的“应用/管脚配置”卷入过大的双栏区。
- 提交 `5d4a02d7` 为修复长表空白页，删除了同方向 `LayoutPage` 之间的无条件 `document.add_page_break()`。该删除避免了 break-only 空页，但正式 renderer 没有补上“源页顶部章节/新表格组从新页开始”的语义分页。
- 当前 Word 第 3 页连续容纳了原 PDF 第 3 页“文档历史”、第 4 页“绝对最大额定值”和第 5 页“电气规格”的开头；Word 第 4 页继续拼入原 PDF 第 6 页第二张电气规格表。表格列宽和重复表头仍正常，用户看到的“挤在一起”是分页聚拢，不是表格网格算法回退。
- 原 PDF 第 13 页顶部“工作原理”在当前 Word 渲染 PDF 第 12 页中部出现；它与表格聚拢共享上述分页缺口。
- 旧兼容 runtime 曾实现保守页流和“密集图表页后新大节”规则，但正式 `DocumentIRWordRenderer` 没有迁入完整能力；本任务不复制一套 Word 分页预测器。
- v2 `equation_interline.content` 是 `{math_content, math_type, image_source}`。当前 `_formula_text()` 通过通用递归文本抽取，错误得到“公式正文 + `latex`”；v2 `equation_inline` 又在 `join_text_fragments()` 中提前降级为普通文本，导致共享 OMML parser 看不到原始 TeX。
- 当前 `_OmmlParser` 已支持分式、平方根、上下标、少量文字/样式包装和符号，但不支持 `\left/\right`、`\leq` 等常见命令，也没有统一处理 MinerU 的 `I N`、`5 0 0`、`C M 7 5 0 1` OCR 分词。
- 本机和项目未安装 `pandoc`、`latex2mathml` 或 `sympy`；既有 renderer 已直接构造 OMML。当前下载目录 8 份 content-list 的 203 个含 TeX 文本未出现矩阵或对齐环境，新增通用数学依赖没有当前证据支撑。

## 范围内需求

### R1 明确优先 MinerU v2

1. 同一结果包同时存在 v2 与旧版 content list 时，正式 DocumentIR 输入必须选择 `content_list_v2.json` 或 `*_content_list_v2.json`。
2. 只有不存在任何 v2 候选时，才回退 `content_list.json` 或 `*_content_list.json`。
3. 同一格式内继续使用确定性的路径深度和路径名排序，不增加猜测式内容探测或第二套选择入口。

### R2 对齐页面尺寸与 bbox 坐标空间

1. `layout/middle` 提供物理页尺寸时，页面方向必须由其宽高比决定，不得被 bbox 内容范围反转。
2. `DocumentIRPage.width/height` 仍需与 block bbox 位于同一坐标空间，供栏位判断和图片比例计算使用。
3. 按物理页宽高比等比放大页面尺寸，直到同时包住该页 bbox 范围；不得分别拉伸宽高。
4. 缺少物理页尺寸时保留现有 bbox extent 回退；真实横向页继续输出横向。

### R3 保留并结构化列表换行

1. 对 paragraph/text block 中以受支持列表标记开头的多行内容，在 MinerU→DocumentIR 边界转换为一个 `list` block 及多个 `list_items`。
2. 新列表项由新的列表标记开始；无标记续行并入当前项并保留换行，避免把子项压成连续句子。
3. 普通多行正文不得被误转为列表；既有显式 `type=list` 和目录识别保持不变。
4. Word 输出中的每个“特征”条目必须成为独立原生列表段落，应用条目中的续行保留可见换行。

### R4 收紧局部双栏检测

1. 优先使用左右块实际纵向重叠产生的局部双栏区间。
2. 只有页面不存在任何实际重叠双栏区间时，才允许使用现有稳定非重叠补偿；不得用总体左右跨度桥接两个已可识别的局部双栏区。
3. 单栏夹层、显式 wide 块及下方独立双栏图片区必须保持独立区域；不增加页码、产品名或文本内容特例。
4. 既有 Word 原生分栏、纯图片配对保持不变。

### R5 恢复语义分页而不恢复 break-only 空页

1. 不恢复每个同方向 PDF 页之间的无条件 `document.add_page_break()`。
2. 非首页源页若以主要 heading 开始，该 heading 使用 Word 原生 `pageBreakBefore`，使“电气规格”“工作原理”等源页顶部章节从新 Word 页开始。
3. 非首页源页若以独立表格组开始，分页语义附着到该表格首个 caption/context 段落；当前样本的“绝对最大额定值”和两组“默认测试条件”必须分别从新页开始。
4. heading 继续 `keep_with_next`；真实表格继续重复表头、禁止拆分单行并允许长表自然跨页。
5. 分页符必须附着到真实内容段落，不生成只含 `w:br type="page"` 的段落；没有章节/新表格组语义的普通源页保持自然流式分页。

### R6 公式输入保真与统一预处理

1. v2 interline 公式只读取 `content.math_content`，不得把 `math_type=latex`、图片路径或其他元数据并入公式正文；legacy 明确字段继续兼容。
2. v2 inline 公式进入 DocumentIR 时保留数学边界和原始 TeX，使正文、标题、列表与 HTML 表格单元格继续共用 `_OmmlParser`，不得提前降级成普通字符串。
3. parser 前统一处理 MinerU 常见噪声：双反斜杠、`$...$`/`$$...$$`/`\(...\)` 包装、命令/上下标周围空格，以及数学组内被拆开的 ASCII 标识符和数字。
4. `V _ {I N}`、`R _ {S}`、`5 0 0`、`C M 7 5 0 1` 必须分别收敛为 `V_{IN}`、`R_{S}`、`500`、`CM7501`；中文与普通正文空格不得被全局压缩。

### R7 预覆盖高频数据手册 TeX 语法

以 Microsoft 365 LaTeX 分类作为完整分类参考，但当前实现目标是“高频数据手册子集”，不是承诺完整 TeX 引擎：

1. 结构：分组、上下标及组合上下标、`\frac/\dfrac/\tfrac`、`\sqrt` 与可选根指数。
2. 定界：普通括号及 `\left/\right` 尺寸修饰；尺寸命令不得作为字面残留。
3. 文本/样式：`\mathrm`、`\mathsf`、`\mathbf`、`\boldsymbol`、`\mathit`、`\text`；中英文混排必须可见。
4. 符号：常用希腊字母、关系符、算术符、箭头、省略号与单位符号，至少覆盖本地 8 份 content-list 已出现的 `\pm`、`\mu`、`\circ`、`\times`、`\theta`、`\Omega`、`\varphi`、`\Phi`、`\Delta`、`\leq`、`\approx`、`\sim`、`\ldots`。
5. 既有结构：`\overline`、`\boxed`、`\bigotimes` 继续生成原生 OMML；公式编号 `\tag{...}` 不得让整式解析失败。
6. 未闭合分组或未知命令不得静默吞掉：保留可见原文并由既有 `docx_latex_residue` 质量证据报告。
7. 矩阵/数组、`cases/align` 环境、用户宏、化学式、颜色与包级命令暂不实现；当前真实语料没有这些结构。出现真实样本或产品明确要求完整 Office LaTeX 子集时，再评估成熟 parser/MathML→OMML 方案。

## 验收标准

- [ ] AC1：同包同时放入内容不同的 v2 与旧版 content list 时，DocumentIR 只包含 v2 内容；删除 v2 后仍能读取旧版内容。
- [ ] AC2：物理页 `595×841`、bbox extent `942×879` 的合成输入生成纵向页面，页面坐标尺寸保持物理宽高比且覆盖 bbox；既有 `792×612` 横向用例继续通过。
- [ ] AC3：CM4112 v2“特征”块转换为多个 `list_items`，每项在 DOCX 中使用独立原生列表段落；“应用”的无标记续行以 Word 换行保留。
- [ ] AC4：包含“上部真实左右重叠 + 中部仅左栏 + 下部真实左右重叠”的布局计划输出 `two_col → one_col → two_col`；纯非重叠稳定样本保持既有行为。
- [ ] AC5：正式样本第一页为纵向、特征逐条显示、“特征/概述”保持上部左右栏、“应用”不被下方图片扩展成整页双栏，且不再出现旧版 `\-`、`\~` 残留。
- [ ] AC6：当前 Word 第 3、4 页的多个源页表格组不再连续挤入同一页面；“文档历史”“绝对最大额定值”“电气规格”及第二组默认测试条件按源页顶部内容组新开页，表头重复与行结构保持正常。
- [ ] AC7：“工作原理”在 Word 中从新页开始，标题后正文不被拆散；不恢复同方向源页的 break-only 段落，CM4112 与既有 SC2167 空白页回归均无新增正文空白页。
- [ ] AC8：v2 两个 interline 公式的 IR `latex` 字段精确等于 `math_content`，末尾不含 `latex`；v2 inline 公式保留到共享 OMML 入口。
- [ ] AC9：示例分式生成 `m:f`、`m:sSub`、`≤`、`Ω` 且无 `\frac/\left/\right/\leq` 残留；总延时公式生成 `m:rad`、上下标/平方结构，保留“总”、`CM7501` 和 `CM411X`，无拆词和 TeX 残留。
- [ ] AC10：代表性公式矩阵覆盖 R7 各类，并在 formula block、正文 inline 与 HTML table cell 三条入口共享通过；未知/畸形命令仍可见并产生质量标记。
- [ ] AC11：定向单元测试和正式样本 LibreOffice→PDF→PNG 视觉检查通过；至少检查第一页、表格页、分页前后页及两处公式页。

## 范围外

- 更换模板、恢复源 PDF 的 CIMO 品牌页眉、移除 ICHELPS 模板页眉或像素级复刻字体/颜色/装饰线。
- 修改 DocumentIR schema、公开 API、数据库、任务状态或模板配置合同。
- 重做 MinerU OCR/版面模型、修正普通正文 OCR 错字或支持任意 Markdown 嵌套列表。
- 恢复所有 PDF 物理页的一一硬分页，或强制 Word 与 PDF 页数完全相同。
- 完整 TeX/LaTeX、矩阵/对齐环境、用户宏、化学式或第三方包语法。

## 技术约束

- 正式权威边界保持为 `MinerUToDocumentIRService`、`layout_signals.py`、`layout_plan.py`、`DocumentIRWordRenderer` 与现有 `_OmmlParser`。
- 不新增依赖、配置、样本专用文本判断、第二套页面预测器或第二套公式 parser。
- 旧 runtime 仅作为历史行为证据；正式 renderer 只复用可证明的规则，不整体迁移兼容实现。
- 当前工作区不在干净的 `main`，实施和提交前必须先解决项目 Git 约束；不得把现有无关改动纳入本任务提交。
