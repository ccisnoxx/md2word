# TPLD2001 跨页续表结构对照

2026-11-12，使用 TI TPLD2001 SCPS286C 的第 3–4 页。源 PDF 的 Table 4-1 Pin Functions 跨这两页，后一页的标题明确标为 continued。独立核对 PDF 页面的行、列和合并。两段各有 8 列、2 行表头，分别有 18 和 2 行引脚数据。合成同一原生 Word 逻辑表时，预期是 22 行，保留首部两行并去掉续段重复的表头。两段有同样的两个表头横合并，每段另有一个描述字段横合并。核对用的 60 个技术 Token 包括 20 个引脚名和两列各 20 个引脚号。[TI 原始 PDF](https://www.ti.com/lit/ds/symlink/tpld2001.pdf) · [结构标注和观测](cross-page-grid-observations.json)

## 同一次解析的两个输入

- **原始 v2。** 两页切片的版面文本与原第 3–4 页逐字节一致。用 MinerU `vlm` 解析一次，归档原始 ZIP。content list v2 的 `/0/2` 已经合并两页，包含 22 行，`/1/0` 的 HTML 为空。
- **完整片段对照。** 同一个包的 `_model.json` 中，`/0/8/content` 和 `/1/4/content` 仍分别保存 20 行、4 行的 HTML，两段均与对应页 `layout.json` 的 `preproc_blocks` 表体 HTML 逐字一致。在单独的派生包中，将这两段原样放回 v2 的 `/0/2`、`/1/0`，按同一版面节点恢复每页的表题与表注。其余包内文件及 v2 块保持原值。原始和派生包分别保留指纹。[原始 DOCX](../../../tests/tmp/datasheet-cross-page-grid-20261112/original.docx) · [完整片段对照 DOCX](../../../tests/tmp/datasheet-cross-page-grid-20261112/premerge.docx)

## 从 Grid 到实际 Word

| 核对项 | 原始 v2 | 完整片段对照 |
| --- | --- | --- |
| 源逻辑表及 Grid | 一个逻辑表，已合并 HTML 产生 22×8 网格，后续片段为空 | 两个独立逻辑表，各有 20×8、4×8 网格，续表诊断为 `insufficient_evidence` |
| 渲染计划与 Word 实物 | 一张 22×8 原生引脚表，次页另有源 PDF 裁图占位 | 两张原生引脚表，分别为 20×8 和 4×8，续段两行标题仍作为普通行保留 |
| 表头和合并 | `w:tblHeader` 行为空。首部两个横合并和两条数据行的横合并与独立标注吻合 | 两段各无 `w:tblHeader`。两段内部的合并坐标均与独立标注吻合 |
| 技术内容和额外表 | 60/60 个标注技术 Token 保留。Figure 4-1 另被渲染为一张 10×4 表 | 同左 |
| 表格质量与结构准确率 | `blocked`，`table_noneditable_placeholder`，完整匹配 0/1 | `warning`，完整匹配 0/1 |

两份 Word 均可打开，均通过持久化渲染证据重读。以渲染计划中的逻辑表 ID 和实际输出索引定位 OOXML，再独立核对 `w:tblGrid`、`w:gridSpan`、`w:vMerge`、`w:tblHeader`，并按片段顺序逐项核对 20 条引脚数据的前三列。原始 v2 和完整片段 HTML 均无可信 `<th>`。对完整片段，两个表题进入分组器时都因复合表号 `4-1` 被判为歧义，续表判定在列宽和表头签名检查之前返回。问题已按最早出现差异的环节登记。[问题清单](issues.md)

这是完整源片段的真实跨页结构对照。原始 MinerU v2 和由同次模型 HTML 恢复的派生输入分别计量。指标可复算，正式链路时延、成本、人工和页面视觉偏差不纳入本次结构对照。

```bash
.venv/bin/python scripts/ops/datasheet_quality_metrics.py \
  .trellis/tasks/11-11-datasheet-quality-baseline-contracts/cross-page-grid-observations.json
```
