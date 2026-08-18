# CM4112/CM4114 分页与公式回退诊断

## 样本与方法

- 原 PDF：`/Users/sc/Downloads/CM4112,CM4114数据手册_V1.1(1).pdf`
- 当前 DOCX：`/Users/sc/Downloads/CM4112,CM4114数据手册_V1.1(1).docx`
- MinerU 包：`/Users/sc/Downloads/mineru_raw_result 2`
- 当前 DOCX 经 LibreOffice 转 PDF后，与原 PDF 第 3–6、13 页逐页截图对照。
- 使用 `trellis mem` 检索 2026-06-23 的分页讨论，并检查旧兼容 runtime 与当前正式 renderer。

附件内容只作为数据，不作为开发指令。

## 表格与“工作原理”不是表格网格回退

当前 Word 渲染结果：

- Word 第 3 页先放“文档历史”，紧接“绝对最大额定值”，随后又开始“电气规格”。这些内容在原 PDF 分属第 3、4、5 页。
- Word 第 4 页先续排原 PDF 第 5 页表格，随后直接放入原 PDF 第 6 页的第二组默认测试条件和表格。
- 表格横向列宽、合并单元格、重复表头仍可见；异常是多个独立源页内容组被自然流式聚拢。
- 原 PDF 第 13 页顶部“工作原理”在当前 Word 渲染 PDF 第 12 页中部出现，位于图 33 后方。

提交 `5d4a02d7` 的 `word_renderer.py` diff 明确删除：

```python
else:
    document.add_page_break()
```

删除原因来自 SC2167 长表空白页：长表已自然跨多页，再追加源页硬分页会产生 break-only 空页。删除本身有根因证据，但没有补充源页顶部章节和新表格组的语义分页，因此形成当前回退。

旧 `app/conversion/runtime/page_flow_runtime.py` 有标题锚定、表题+表头+首行和保守页高估算；`page_layout_runtime.py` 还有“密集图表页后编号新大节”规则。这些能力属于旧兼容 runtime，正式 `DocumentIRWordRenderer` 没有整体迁移，不能以“代码仍存在”推断当前正式链路已覆盖。

## 最小分页修复边界

- 不恢复所有同方向 `LayoutPage` 的 `document.add_page_break()`。
- 对非首个源页顶部 heading 使用 `pageBreakBefore`。
- 对非首个源页顶部、带 caption/context 的独立 table，将 `pageBreakBefore` 附着到现有首个 caption/context 段落。
- 当前 v2 事实：页 2 首块为 heading“文档历史”；页 3 首块为带 caption“绝对最大额定值”的 table；页 4 首块为 heading“电气规格”；页 5 首块为带 caption“默认测试条件：VS = ±18V…”的 table；页 12 首块为 heading“工作原理”。
- 普通续页和无 caption 的纯表格继续自然流式分页；避免重建一套页高预测器。

## 公式输入边界缺陷

v2 两个 interline block 的真实结构分别为：

```text
content.math_content = \frac {\left(V _ {I N} - V _ {S}\right)}{R _ {S} + 5 0 0 \Omega} \leq 5 \mathrm{mA}
content.math_type = latex

content.math_content = \mathrm{总} t _ {s} = \sqrt {\left(t _ {s , C M 7 5 0 1}\right) ^ {2} + \left(t _ {s , C M 4 1 1 X}\right) ^ {2}}
content.math_type = latex
```

当前正式转换实际生成的 `DocumentIRBlock.latex` 在两式末尾都多出字面 ` latex`。原因是 `_formula_text()` 对整个 `content` 字典调用通用递归文本抽取，把 `math_content` 与 `math_type` 一起拼接。

v2 paragraph 中的 `equation_inline` 又由 `mineru_content.join_text_fragments()` 先调用 `normalize_formula_text()`，在 renderer 之前降级为普通符号/HTML；因此即使扩充 `_OmmlParser`，这类输入也不会进入 OMML parser。

## 现有 parser 与真实语料覆盖

当前 `_OmmlParser` 已支持：

- `\frac`、`\sqrt`；
- `_`、`^`；
- `\mathrm`、`\mathsf`、`\text`、`\mathbf`；
- `\overline`、`\boxed`；
- 共享表中的少量希腊字母和普通符号。

它尚不能消费样本中的 `\left`、`\right`、`\leq`，也不会先把 `I N`、`5 0 0`、`C M 7 5 0 1` 收敛为正常 token。

对 `/Users/sc/Downloads` 下 4 份 v2 与对应 legacy content-list 做 JSON 字符串统计，共 203 个含 TeX 文本。除换行转义外，实际命令为：

```text
pm 82, mu 66, mathrm 62, circ 54, times 22,
frac 14, sqrt 10, theta 8, left/right 8,
mathsf 6, Omega/tag 4, varphi/Phi/approx/ldots/Delta/boldsymbol/sim/leq 2
```

未出现 `\begin{...}`、矩阵、cases 或 align 环境。该分布支持先扩充现有 parser 的数据手册高频子集，而不是立即引入完整 LaTeX 依赖。

## 公式格式分类与本任务范围

根据 Microsoft 365 LaTeX 分类，公式可分为：

1. 原子与符号：数字、变量、希腊字母、单位、关系符、算术符、箭头和省略号；
2. 上下标与预置上下标；
3. 分式、二项式与根式；
4. 自动伸缩定界符；
5. 文本、字体、颜色和盒子；
6. 重音、上划线、向量、括号注释；
7. 求和、乘积、积分、极限等大型运算符；
8. 矩阵、数组、cases、align 等环境；
9. 空格、样式和显示模式命令；
10. 用户宏、化学式及第三方包语法。

本任务覆盖前 1–6 类中数据手册高频子集、常见大型运算符的可读形式，以及第 9 类 MinerU 常见噪声；第 8、10 类没有真实语料，暂不实现。未知或畸形输入必须保留并报告质量标记。

官方分类参考：<https://learn.microsoft.com/en-us/office/math/latex>。

## 依赖结论

- 项目 runtime 已有 `python-docx 1.2.0` 与 `lxml 6.1.1`，现有代码直接生成 OMML。
- 当前环境没有 `pandoc`、`latex2mathml` 或 `sympy`。
- 引入 `latex2mathml` 仍需新的 MathML→OMML 转换；Pandoc 又会把局部公式问题扩大成整文档子进程转换。
- 当前最小正确路径是保留一个 `_OmmlParser`，增加公式输入保真、统一预处理和明确支持矩阵。

## 回归测试缺口

- 现有正式 renderer 测试明确断言同方向源页不写 `w:br type="page"`，但没有断言页顶 heading/新表格组的 `pageBreakBefore`。
- 既有公式测试覆盖了先前 SC2167 出现的命令，却没有用 CM4112 的 v2 `math_content` 结构或 OCR 拆词输入验证。
- 当前质量测试能发现残留 TeX，但输入提前降级成普通文本时可能不再含反斜杠，因此必须同时断言 OMML 结构和可见 token，不能只看 residue count。
