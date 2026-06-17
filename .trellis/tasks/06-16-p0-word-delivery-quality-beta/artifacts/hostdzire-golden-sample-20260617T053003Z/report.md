# Golden Sample 回归报告

- 执行时间: `2026-06-17T05:30:53.855921+00:00`
- 结果目录: `/work/tests/tmp/golden_sample_runs/20260617T053003Z`
- Manifest 样本数: `4`
- 正式匹配 PDF 数: `4`
- 实际执行: `4`
- 缺少 PDF: `0`
- Manifest 外 PDF 数: `0`
- Manifest 外 PDF: `none`
- 成功: `4`
- 失败: `0`
- 成功率: `100.00%`
- 目标: `100%`
- 自动链路是否达标: `True`
- P0 是否可发布: `True`
- P0 发布阻断: `none`
- Admin 人工签字有效: `True`
- Admin reviewer: `admin`
- Admin signed_at: `2026-06-17T05:38:55Z`
- Admin 签字 blockers: `none`
- DOCX 质量证据可用: `True`
- DOCX 质量标记样本数: `1`
- DOCX 质量标记: `docx_unstyled_heading_candidates:3`
- 可编辑内容证据样本数: `4`
- 疑似整页截图样本数: `0`
- Heading 段落总数: `9`
- 疑似标题未样式化段落总数: `3`
- Word numbering 段落总数: `30`
- 手写列表符号段落总数: `0`
- TOC 点线制表位段落总数: `34`
- 纯文本目录项段落总数: `0`
- 宽表总数: `1`
- 表头重复行总数: `5`
- 表格防跨页断行总数: `66`
- 表格零段前后距段落总数: `320`
- 表头底纹单元格总数: `24`
- Landscape section 总数: `2`
- LaTeX 残留总数: `0`

| 样本 ID | 文件名 | 状态 | job_id | 失败阶段 | 错误码 | Word 可打开 | DOCX flags | 可编辑证据 | 疑似截图 | Heading | 疑似标题 | Numbering | 手写列表 | TOC Tabs | 纯文本 TOC | 宽表 | Landscape | TblHeader | NoSplit | CellSpacing0 | LaTeX 残留 | 表格 | 耗时秒 |
|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| gs-003 | OPA228_P1.pdf | succeeded | docjob_b13468b519c3 |  |  | True |  | True | False | 4 | 0 | 16 | 0 | 0 | 0 | 0 | 0 | 1 | 7 | 51 | 0 | 1x2, 7x3 | 16.214 |
| gs-004 | OPA228_P2.pdf | succeeded | docjob_3e7ba8b8960e |  |  | True |  | True | False | 4 | 0 | 14 | 0 | 34 | 0 | 0 | 0 | 0 | 0 | 34 | 0 | 1x2 | 11.215 |
| gs-006 | OPA228_P6.pdf | succeeded | docjob_cc4e04338e30 |  |  | True | docx_unstyled_heading_candidates:3 | True | False | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 27 | 114 | 0 | 9x5, 9x5, 9x5 | 11.295 |
| gs-008 | OPA228_P7.pdf | succeeded | docjob_e3c2f334f9a5 |  |  | True |  | True | False | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 32 | 121 | 0 | 32x7 | 11.199 |

## Admin 人工验收关注点

### gs-003 / OPA228_P1.pdf
- 双栏阅读顺序正确，Features/Applications/Description 不左右栏交错
- 标题层级和项目符号列表基本保留
- 噪声曲线图和 Device Information 表格相对位置可追溯

### gs-004 / OPA228_P2.pdf
- 双栏目录条目和页码顺序可追溯
- Revision History 项目符号列表顺序保留
- 页眉、页脚和正文边界不互相覆盖

### gs-006 / OPA228_P6.pdf
- 多张 Thermal Information 表行列稳定
- θ/ψ、°C/W、封装和 pin 数等符号可读
- 表格脚注靠近对应表格且正文顺序正确

### gs-008 / OPA228_P7.pdf
- Electrical Characteristics 宽表列名、单位和分组保留
- VOS、PSRR、CMRR、nV/√Hz、µV/°C 等上下标和特殊符号可读
- 表格内容可编辑且不大面积挤压或错列

