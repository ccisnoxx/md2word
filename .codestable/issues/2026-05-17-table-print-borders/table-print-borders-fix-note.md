---
doc_type: issue-fix
issue: 2026-05-17-table-print-borders
path: fast-track
fix_date: 2026-05-17
tags: [table, pdf, docx, border, render]
---

# 表格打印边框修复记录

## 1. 问题描述

生成的 Word 文档在编辑器里还能看到表格内容，但导出 PDF 后表格视觉上“消失”，看起来像普通多列文本。

## 2. 根因

表格渲染阶段统一调用 `remove_table_borders()`，把 `top/left/bottom/right/insideH/insideV` 全部写成 `w:val="nil"`。Word 编辑器可显示非打印 gridlines，但 PDF 导出只认可打印边框，因此 PDF 中表格线全部丢失。

## 3. 修复方案

- 把表格边框策略从“全部去边框”改成“可打印浅灰网格”，外框略粗、内部网格略细。
- 对表头单元格追加浅底纹，保证 PDF 中即使线条较淡也有明确表头锚点。

## 4. 改动文件清单

- `mineru_to_docx.py`
- `tests/test_render_table_from_html_characterization.py`

## 5. 验证结果

- `PYTHONPATH=tests /Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover -s tests` 通过，76 tests。
- 重新导出 `out_file/OPA228_test1-table-fix.docx` 成功。
- 用 LibreOffice 渲染链在沙箱外生成 `/private/tmp/docx_render_table_fix/page-5.png`，表格网格和表头底纹已可见，PDF 中不再表现为纯文本列。

## 6. 遗留事项

当前策略对全部表格统一生效。如果后续需要区分“轻表格 / 技术参数表 / 长表”的不同视觉密度，可以再拆更细的表格样式策略。
