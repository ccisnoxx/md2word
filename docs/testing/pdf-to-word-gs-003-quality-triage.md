---
doc_type: test-report
slug: pdf-to-word-gs-003-quality-triage
component: pdf-to-word-backend
status: current
summary: gs-003 / OPA228_P1.pdf 真实链路生成 DOCX 的人工结构质量 triage。
tags: [testing, golden-sample, pdf, word, quality-triage]
last_reviewed: 2026-06-02
---

# gs-003 DOCX 质量 triage

## 1. 样本与产物

| 字段 | 值 |
|---|---|
| 样本 ID | `gs-003` |
| 源 PDF | `tests/fixtures/golden_samples/pdfs/OPA228_P1.pdf` |
| job_id | `docjob_d4c4101592ad` |
| 生成 DOCX | `tests/tmp/golden_sample_triage/20260602T071017Z/gs-003-docjob_d4c4101592ad.docx` |
| 渲染页图 | `tests/tmp/golden_sample_triage/20260602T071017Z/rendered_docx/page-1.png`、`page-2.png` |
| 源 PDF 页图 | `tests/tmp/golden_sample_triage/20260602T071017Z/source_pdf_page-1.png` |
| 检查方式 | `python-docx` 结构抽取、LibreOffice DOCX 渲染、Poppler PDF 渲染、人工对照 |

源 PDF 是 1 页 Letter datasheet 首页：主标题下方是双栏内容，左栏为 Features / Applications / 噪声曲线图，右栏为 Description / Device Information 表格。

生成 DOCX 可打开，并可渲染为 2 页 A4。结构抽取结果为 4 个顶层 paragraph、3 个 table、1 个 inline shape、2 个 media 文件。

## 2. 人工结论

结论：主链路 smoke 通过，但 `gs-003` 不能记为 P0 人工质量通过。

原因：

- 标题、正文、图表和 Device Information 表格均有内容落入 DOCX，没有空白或损坏。
- 生成结果是可编辑 Word 内容，不是整页截图；表格为 Word table，正文为 paragraph，图表为图片对象。
- 但双栏顺序、分页、标题语义、列表语义、数学符号和表格位置存在明显问题，影响 datasheet 首页的结构还原质量。

人工判定：`条件通过（主链路）/ 未通过（P0 版面与语义质量）`。

## 3. 检查项

| 检查项 | 结果 | 证据与说明 |
|---|---|---|
| 标题 | 部分通过 | 主标题 `OPAx227, OPAx228 High-Precision, Low-Noise Operational Amplifiers` 保留并可见，但 DOCX 结构中为 `Normal` 样式，不是 heading；源 PDF 顶部 TI 品牌和产品族链接未按原样保留，模板页眉替换为公司页眉。 |
| 双栏顺序 | 未通过 | 左栏 Features / Applications 和右栏 Description 大体同时出现，但实现方式是 1 行 2 列表格；部分右栏 Description 段落脱离右栏并跨整页宽度显示，破坏原 PDF 的列边界和阅读顺序。 |
| 图表 | 部分通过 | 噪声曲线图作为图片保留，坐标和曲线可辨认；图注文本保留。但图片尺寸缩小，图注和后续表格距离/分页不自然，图表没有保留为带 caption 的稳定 figure 结构。 |
| Device Information 表格 | 未通过 | 表格内容抽取为可编辑 3 列 7 行 Word table，数据行完整；但表头被压在第 1 页底部，数据行被推到第 2 页，`Device Information` 标题出现在表格下方，和源 PDF 中标题在表格上方的结构相反。 |
| 可编辑性 | 部分通过 | 正文、表格单元格和图片对象可编辑；但列表是普通字符而非真实 Word list，`$\\sqrt{Hz}$`、`$\\mu s$`、`$PACKAGE^{(1)}$`、`$-40^{\\circ}C$` 等数学/特殊符号残留为 LaTeX 文本，影响最终可编辑质量。 |

## 4. 结构抽取摘要

```text
paragraphs=4
tables=3
inline_shapes=1
media_files=2
page_size=A4
rendered_pages=2
```

主要结构：

- Paragraph 1：主标题，样式为 `Normal`。
- Table 1：1 行 2 列，左侧包含 Features / Applications，右侧包含 Description 开头。
- Table 2：1 行 2 列，左侧包含图表标题/图片区域，右侧包含 Description 后续内容。
- Table 3：7 行 3 列，包含 Device Information 数据。
- Paragraph 3：`Device Information`，但渲染位置在表格数据之后。

## 5. 后续输入

本 triage 不直接修 renderer/layout。后续若进入质量硬化，应优先拆成以下问题输入：

- 双栏 block 分组和列内阅读顺序：避免右栏段落脱离列容器、跨页宽显示。
- heading/list 语义：标题映射为 Word heading，bullet/sub-bullet 映射为真实 Word list。
- 数学/特殊符号渲染：把 MinerU/IR 中的 LaTeX 表达转换成 Word 可读符号或公式。
- 表格 caption 与分页控制：Device Information 标题应在表格上方，表头和首批数据行应尽量同页。
- figure 结构：图表、图注和周围内容需要更稳定地绑定。

## 6. md2word_main 本地基线

> 2026-06-23 更新：本节保留 2026-06-02 的历史基线证据。当前长期维护策略已调整为
> `/Users/sc/PycharmProjects/md2word/app/conversion` 是唯一转换代码源，
> `md2word_main` 只保留薄调试壳、样例输入输出和运行配置。新的本地调试流程见
> [local-conversion-sandbox.md](/Users/sc/PycharmProjects/md2word/docs/dev/local-conversion-sandbox.md)。

2026-06-02 使用 `md2word_main/mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4` 跑本地转换基线。

运行方式：

```bash
PYTHONPATH=/Users/sc/PycharmProjects/md2word:/Users/sc/PycharmProjects/md2word/tests/tmp/md2word_main_baseline/shim \
/Users/sc/miniconda3/envs/md2word/bin/python mineru_to_docx.py \
  /Users/sc/PycharmProjects/PythonProject/md2word_main/mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4 \
  --output /Users/sc/PycharmProjects/md2word/tests/tmp/md2word_main_baseline/OPA228_P1/md2word_main_direct.docx \
  --document-language en \
  --translation-mode direct
```

本地入口事实：

- `md2word_main/mineru_to_docx.py` 直接运行会失败：`ModuleNotFoundError: No module named 'app'`。
- `md2word_main/.idea` 未配置额外 source root；`md2word_main` 目录内也没有 `app/conversion/`。
- 本地基线实际通过 `PYTHONPATH=/Users/sc/PycharmProjects/md2word` 加载当前仓库的 `app.conversion.runtime_runner` 和 `app/conversion/runtime/*`。
- 临时 `config.py` shim 只用于导入 `app.conversion.runtime_config.APP_CONFIG`，不属于业务代码。
- 之后已将当前可运行的 `app/conversion/`、`resources/`、根级 `config.py`、`README.md` 和 `requirements.txt` 复制到 `md2word_main`，使其恢复为可独立运行的本地转换项目。

本地基线结果：

| 项目 | 结果 |
|---|---|
| 输出 DOCX | `tests/tmp/md2word_main_baseline/OPA228_P1/md2word_main_direct.docx` |
| 渲染页图 | `tests/tmp/md2word_main_baseline/OPA228_P1/rendered_docx/page-1.png` |
| 渲染页数 | 1 |
| DOCX 页尺寸 | A4 |
| 段落 / 表格 / 图片 | 5 paragraphs / 3 tables / 1 inline shape |
| 标题 | 比线上 smoke 更好，分成 `PartNumber` 与 `Category` 样式 |
| 数学/特殊符号 | 比线上 smoke 更好，`√Hz`、`μs`、`µV`、`PACKAGE(1)`、`–40°C` 可读 |
| 双栏 | 仍用 1 行 2 列表格承载，列边界显式可见，不是自然双栏版式 |
| 列内阅读顺序 | 仍有右栏后续段落脱离第一双栏区域、跨整页宽度显示的问题 |
| Device Information 表格 | 数据留在同一页，但 `Device Information` 标题渲染在表格下方，和源 PDF 相反 |
| list 语义 | 视觉上是项目符号字符，仍未确认是真实 Word numbering/list |
| figure/caption | 图表和图注可见，但结构仍依赖双列表格容器，不是稳定 figure/caption 绑定 |

独立项目验证：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python mineru_to_docx.py \
  mineru_result/OPA228_P1.pdf-d1491424-9662-411d-8e39-fa6bcbd785a4 \
  --output out/OPA228_P1_standalone.docx \
  --document-language en \
  --translation-mode direct
```

验证结果：

- 输出：`/Users/sc/PycharmProjects/PythonProject/md2word_main/out/OPA228_P1_standalone.docx`
- 渲染：`/Users/sc/PycharmProjects/PythonProject/md2word_main/out/OPA228_P1_standalone_rendered/page-1.png`
- 渲染页数：1
- 模板来源：`/Users/sc/PycharmProjects/PythonProject/md2word_main/resources/templates/default/datasheet_template.docx`（历史路径；当前模板由官方 `md2word/resources/` 提供）

当前结论：`md2word_main` 不再作为独立转换代码源。后续质量修复必须先落在正式项目
`md2word/app/conversion/runtime/*`，再用 `md2word_main` 的薄壳和样例资产做本地 render 验证。
