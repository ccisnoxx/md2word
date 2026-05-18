---
doc_type: issue-fix
issue: 2026-05-17-docx-bottom-whitespace
path: fast-track
fix_date: 2026-05-17
tags: [docx, pagination, toc, table]
---

# DOCX 页底留白修复记录

## 1. 问题描述

`out_file/CWQ2P690T-visual-check.docx` 中，目录页第 2 页和附录超长表格页存在大块页底留白。

## 2. 根因

- 目录页中 `附录 A.x` 目录条目被当作正文附录标题处理，触发新 section，导致目录内部强制换页。
- 附录超长表格按 MinerU 源 PDF 页占位拆块，并在每个块前写入硬分页，Word 无法自然利用页底剩余空间。

## 3. 修复方案

- TOC 分节判断增加目录续页状态，只有非 TOC 内容中的附录标题才触发附录新 section。
- 长表改为输出单个连续 Word 表格，使用重复表头，让 Word 自然分页；保留拆分估算函数但移除源页数 guardrail。

## 4. 改动文件清单

- `page_layout_runtime.py`
- `table_long_renderer.py`
- `tests/test_page_layout_characterization.py`
- `tests/test_render_table_from_html_characterization.py`

## 5. 验证结果

- `PYTHONPATH=tests /Users/sc/miniconda3/envs/md2word/bin/python -m unittest discover -s tests` 通过，60 tests。
- 重新生成 `out_file/CWQ2P690T-fixed-check.docx` 成功。
- 结构检查结果：`page_break_paragraphs=0`，目录内部不再在 `4.4.2` 与 `4.4.3` 之间出现 `sectPr`，三个附录长表均为单个连续表格，并写入 3 个 `w:tblHeader` 重复表头标记。

## 6. 遗留事项

本机缺少 `soffice`，未执行 LibreOffice PNG 渲染检查；已用 OOXML 结构检查验证本次根因对应的硬分页和误分节已消除。
