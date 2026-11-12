# TPLD2001 图表来源分类复验

本轮在 `74ab7f59` 保存的预合并合同上重放原始 MinerU v2 包。来源为 TPLD2001 SCPS286C 第 3–4 页。两次使用相同包、PDF 和版式，分别提供和省略既有表头校核。输入和历史样本的原始结构基线 0/1、意外多表 1 保留。[跨页基线](cross-page-grid-validation.md) · [上游预合并复验](upstream-table-coverage-validation.md)

| 来源 | 修复前 | 本轮复验 |
| --- | --- | --- |
| 第 3 页 `/0/0`，Figure 4-1 | 原包声明 `table`，输出 10×4 原生表。原图另存于同块的 `image_source.path`。 | 来源账保留 `table` 和 `/0/0`，有效 IR 为图片。Word 内嵌的 584×390 JPEG 与原包逐字节一致，退出表格 Grid。图题与恢复出的章节标题各出现一次。 |
| 第 3 页 `/0/1`，Figure 4-2 | 原包声明 `image`。 | 图片字节和图题保持，独立于 Figure 4-1 的重新分类。 |
| 第 3 页 `/0/2`，Table 4-1 | 明确表题，原生 22×8。 | Grid、渲染投影和实际 Word 都为 22×8。逐格文本和合并跨度与 `74ab7f59` 的复验产物一致。60/60 个标注引脚 Token 保留。使用 python-docx 修改 Word 副本的原生单元格，保存后重读取得修改值。 |

两次回放的实际原生数据表数均由 2 变为 1。独立标注的预期表数仍为 1，本轮意外多表为 0。带表头校核时，两行重复表头和主表 `[20,22)` 的次页覆盖保留，表格质量为 `warning`。省略校核时，缺片段占位和 `blocked` 保留。当前回放单独存档，历史原始 0/1 及意外多表 1 继续按原报告重算。

Figure 4-1 的 JPEG SHA-256 为 `de7cedddc54435be63805672372695c8488b18bd2699cc4df3bf2aeedfd8b161`。包 SHA-256 为 `56276ab85990b363d9a348fd5a4952c2b91b2601f56579ecff8daeb95e59bdaf`，v2 SHA-256 为 `d57460c11567265b46f846846675713020069aec165fd64d7b690399a441e8e4`。复验验证两份新 DOCX 的内容、图片及表格持久化证据，并重读五套历史 IR 和 DOCX。

LibreOffice 打开校核版并导出 PDF。第一页的顺序为章节标题、两张示意图、Table 4-1。两张图在本次 Word 回放中纵排，源 PDF 第 3 页并排，记录为页面视觉差异。[本地排版预览](../../../tests/tmp/datasheet-cross-page-grid-20261112/figure-classification-after/tpld2001-reviewed.pdf)

21 项定向回归通过，覆盖同块图表分类、来源篡改、末页图文保留、续表归组、预合并和正式渲染重读。另有两个历史 chart 夹具 `test_convert_zip_maps_nested_v2_chart_to_image_and_records_source_inventory` 和 `test_rich_chart_captions_render_without_isolated_fragments_and_keep_paired_layout` 报 `multiple_result_roots`，均在隔离的 `74ab7f59` 复现相同错误。9 个变更 Python 文件通过语法编译，`git diff --check` 通过。

[本地复算脚本](../../../tests/tmp/datasheet-cross-page-grid-20261112/figure-classification-after/replay.py) · [复算观测](../../../tests/tmp/datasheet-cross-page-grid-20261112/figure-classification-after/observations.json) · [校核版 Word](../../../tests/tmp/datasheet-cross-page-grid-20261112/figure-classification-after/tpld2001-reviewed.docx)
