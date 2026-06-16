---
doc_type: test-report
slug: pdf-to-word-golden-sample-manual-quality-records-20260603
component: pdf-to-word-backend
status: current
summary: 2026-06-03 hostdzire 真实回归 4 个 Golden Sample DOCX 的人工质量记录。
tags: [testing, golden-sample, pdf, word, quality-triage]
last_reviewed: 2026-06-03
---

# Golden Sample 人工质量记录（2026-06-03）

## 1. 批次与检查方式

| 字段 | 值 |
|---|---|
| 回归批次 | `20260603T070724Z` |
| 执行环境 | hostdzire 真实 API / Worker / MinerU |
| 本地 run_dir | `tests/tmp/golden_sample_runs/20260603T070724Z` |
| 质量证据目录 | `tests/tmp/golden_sample_quality/20260603T070724Z` |
| runnable 样本 | `gs-003`、`gs-004`、`gs-006`、`gs-008` |
| 主链路结果 | 4 succeeded / 0 failed |
| DOCX 包可打开 | 4 true / 0 false |
| 检查方式 | LibreOffice DOCX 渲染、Poppler PDF 渲染、side-by-side 人工对照、`python-docx` 结构抽取、OOXML 媒体/numbering 检查 |

本记录只做人工质量 triage。它不能替代正式 P0 通过声明：当前仍只有 4 个 runnable 样本，且本轮发现标题语义、列表语义、双栏/宽表版面、表格 caption 和数学/特殊符号存在质量缺口。

## 2. 批次级结构摘要

| sample_id | DOCX 页数 | 源 PDF 页数 | paragraphs | tables | media | Word numbering | LaTeX 残留 | 人工结论 |
|---|---:|---:|---:|---|---:|---:|---:|---|
| `gs-003` | 2 | 1 | 49 | `1x2`, `1x2`, `7x3` | 2 | 0 | 6 | 条件通过（主链路）/ 未通过（P0 版面与语义质量） |
| `gs-004` | 2 | 1 | 54 | `1x2` | 1 | 0 | 0 | 条件通过（内容可追溯）/ 未通过（P0 目录与列表语义质量） |
| `gs-006` | 2 | 1 | 141 | `9x5`, `9x5`, `9x5` | 1 | 0 | 6 | 条件通过（表格可编辑）/ 未通过（P0 表格 caption、分页与符号质量） |
| `gs-008` | 2 | 1 | 237 | `32x8` | 1 | 0 | 19 | 条件通过（宽表可编辑）/ 未通过（P0 宽表版面与符号质量） |

说明：

- `paragraphs` 包括正文段落和表格单元格段落；本轮所有抽取文本样式均为 `Normal`，没有 heading 样式。
- `Word numbering=0` 表示未发现真实 Word numbering 段落；目录和 revision 项主要是普通字符项目符号或文本。
- `media` 中至少包含模板页眉 logo；只有 `gs-003` 有源 PDF 里的关键图表图片。

## 3. gs-003 / OPA228_P1.pdf

| 字段 | 值 |
|---|---|
| job_id | `docjob_cd6c254c5e4d` |
| DOCX | `tests/tmp/golden_sample_runs/20260603T070724Z/gs-003-docjob_cd6c254c5e4d.docx` |
| 对照图 | `tests/tmp/golden_sample_quality/20260603T070724Z/gs-003/gs-003-comparison.png` |
| 源 PDF | `tests/fixtures/golden_samples/pdfs/OPA228_P1.pdf` |

| 检查项 | 结果 | 证据与说明 |
|---|---|---|
| Word 可打开 | 通过 | 脚本和本地二次 zip 检查均确认 `docx_openable=true`。 |
| 可编辑性 | 部分通过 | 正文为 paragraph，Device Information 为 `7x3` Word table，噪声曲线图为图片对象；不是整页截图。 |
| 标题语义 | 未通过 | 主标题可见，但结构抽取显示所有文本样式均为 `Normal`，未映射为 Word heading。 |
| 列表语义 | 未通过 | Features / Applications 项目符号为普通字符，`numbering_paragraphs=0`，不是 Word list。 |
| 双栏顺序 | 未通过 | 源 PDF 首页是左右双栏；DOCX 通过两个 `1x2` 表格近似承载，Description 后续段落跨整页宽度显示，列边界和阅读顺序不稳定。 |
| 表格 | 部分通过 | Device Information 内容为可编辑表格，但第 1 页底部只露出表头，第 2 页才显示数据；`Device Information` 标题在表格下方，和源 PDF 中标题在表格上方相反。 |
| 图片/figure | 部分通过 | 噪声曲线图保留为图片，坐标和曲线可辨认；但图表尺寸缩小，图注/图片/后续表格没有稳定 figure 绑定。 |
| 数学/特殊符号 | 未通过 | 存在 `$\\sqrt{Hz}$`、`$5 \\mu s$`、`$PACKAGE^{(1)}$`、`$-40^{\\circ}C$` 等 LaTeX 残留。 |

人工结论：`条件通过（主链路）/ 未通过（P0 版面与语义质量）`。

## 4. gs-004 / OPA228_P2.pdf

| 字段 | 值 |
|---|---|
| job_id | `docjob_ca6dbb503b55` |
| DOCX | `tests/tmp/golden_sample_runs/20260603T070724Z/gs-004-docjob_ca6dbb503b55.docx` |
| 对照图 | `tests/tmp/golden_sample_quality/20260603T070724Z/gs-004/gs-004-comparison.png` |
| 源 PDF | `tests/fixtures/golden_samples/pdfs/OPA228_P2.pdf` |

| 检查项 | 结果 | 证据与说明 |
|---|---|---|
| Word 可打开 | 通过 | 脚本和本地二次 zip 检查均确认 `docx_openable=true`。 |
| 可编辑性 | 部分通过 | Table of Contents 和 Revision History 文本均为可编辑 Word 文本；TOC 主区域是 `1x2` Word table。 |
| 标题语义 | 未通过 | `Table of Contents`、`4 Revision History` 等标题可见，但样式仍为 `Normal`。 |
| 列表语义 | 未通过 | Revision History 项以普通字符项目符号呈现，`numbering_paragraphs=0`，不是 Word list。 |
| 目录版面 | 部分通过 | 左右两栏目录和页码可追溯，但点线 leader、缩进和页码对齐明显漂移；内容从 1 页源 PDF 展开为 2 页 DOCX。 |
| 修订历史 | 部分通过 | Revision 条目顺序基本保留，但普通项目符号和手写页码文本降低可编辑语义质量。 |
| 图片/figure | 不适用 | 源样本无关键图片/figure；DOCX media 主要来自模板页眉。 |
| 页眉页脚边界 | 部分通过 | 内容未与模板页眉重叠；但源 PDF 页眉页脚、TI branding 和 Product Folder links 没有按原布局保留。 |

人工结论：`条件通过（内容可追溯）/ 未通过（P0 目录与列表语义质量）`。

## 5. gs-006 / OPA228_P6.pdf

| 字段 | 值 |
|---|---|
| job_id | `docjob_8f76657979b4` |
| DOCX | `tests/tmp/golden_sample_runs/20260603T070724Z/gs-006-docjob_8f76657979b4.docx` |
| 对照图 | `tests/tmp/golden_sample_quality/20260603T070724Z/gs-006/gs-006-comparison.png` |
| 源 PDF | `tests/fixtures/golden_samples/pdfs/OPA228_P6.pdf` |

| 检查项 | 结果 | 证据与说明 |
|---|---|---|
| Word 可打开 | 通过 | 脚本和本地二次 zip 检查均确认 `docx_openable=true`。 |
| 可编辑性 | 部分通过 | 3 张 Thermal Information 均为可编辑 Word table，表格尺寸均为 `9x5`。 |
| 标题语义 | 未通过 | `6.4/6.5/6.6 Thermal Information` 可见，但均为 `Normal` 样式，不是 heading。 |
| 表格行列 | 部分通过 | 3 张热阻表均被识别为表格，主要数值可追溯；但表头重复/合并关系被扁平化，列宽较窄，阅读压力高。 |
| caption 与分页 | 未通过 | 表格标题渲染在表格下方，不符合源 PDF 标题在表格上方的结构；第三张表在第 1 页只露出表头，主体在第 2 页，continuation 语义不足。 |
| 符号与单位 | 未通过 | 存在 `$R_{\\theta JA}$`、`$R_{\\theta JC(top)}$`、`$\\psi_{JT}$` 等 LaTeX 残留；`°C/W` 单位可见但符号语义不达标。 |
| 图片/figure | 不适用 | 源样本无关键图片/figure；DOCX media 主要来自模板页眉。 |

人工结论：`条件通过（表格可编辑）/ 未通过（P0 表格 caption、分页与符号质量）`。

## 6. gs-008 / OPA228_P7.pdf

| 字段 | 值 |
|---|---|
| job_id | `docjob_d86b732f2103` |
| DOCX | `tests/tmp/golden_sample_runs/20260603T070724Z/gs-008-docjob_d86b732f2103.docx` |
| 对照图 | `tests/tmp/golden_sample_quality/20260603T070724Z/gs-008/gs-008-comparison.png` |
| 源 PDF | `tests/fixtures/golden_samples/pdfs/OPA228_P7.pdf` |

| 检查项 | 结果 | 证据与说明 |
|---|---|---|
| Word 可打开 | 通过 | 脚本和本地二次 zip 检查均确认 `docx_openable=true`。 |
| 可编辑性 | 部分通过 | Electrical Characteristics 为 `32x8` Word table，可编辑且不是整页截图。 |
| 标题语义 | 未通过 | 标题和条件说明可见，但均为 `Normal` 样式；公式化条件文本包含 LaTeX 残留。 |
| 宽表版面 | 未通过 | 源 PDF 宽表在单页内可读；DOCX 使用 A4 portrait，宽表列被压缩，部分单元格换行密集。最后一行被单独推到第 2 页顶部，产生大量空白。 |
| 表格结构 | 部分通过 | 行列内容大体可追溯，但分组表头和重复字段被扁平化；`PARAMETER`、`TEST CONDITIONS` 重复列反映出合并单元格语义丢失。 |
| 符号与单位 | 未通过 | 存在 `$T_A = +25^\\circ C$`、`$V_S = \\pm 5$`、`$V_{CM}$`、`$I_B$`、`$R_L=5 kΩ$` 等 LaTeX 残留；`nV/\\sqrt{Hz}` 相关符号没有转成自然 Word 表达。 |
| 图片/figure | 不适用 | 源样本无关键图片/figure；DOCX media 主要来自模板页眉。 |

人工结论：`条件通过（宽表可编辑）/ 未通过（P0 宽表版面与符号质量）`。

## 7. 人工质量结论

本轮 4 个 runnable 样本主链路全部通过，且均生成可打开、可编辑的 Word 对象；但没有任何一个样本可以声明为 P0 人工质量通过。

主要缺口：

- 标题语义：所有样本文本仍为 `Normal`，没有稳定 heading。
- 列表语义：`gs-003`、`gs-004` 的项目符号/目录条目不是 Word numbering。
- 双栏与宽表版面：`gs-003` 双栏退化为表格近似；`gs-008` 宽表没有 landscape 或更合理分页策略。
- 表格 caption：`gs-003`、`gs-006` 的标题/说明和表格相对顺序不稳定。
- 数学/特殊符号：`gs-003`、`gs-006`、`gs-008` 都有 LaTeX 残留。

这些问题应在后续 `failure-classification` 中继续路由到 `document-ir-layout-risk-pass` 和 `word-renderer-editable-output-pass`；本记录不直接做修复。

