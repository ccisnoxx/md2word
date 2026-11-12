# 表头来源与本地校核

目录公式修复及其验证记录已保存于本地提交 `d88ddb1`。本轮按 [质量任务计划](implement.md) 继续表头来源，原始 [0/3 基线](validation.md) 仍以未补充表头的 MinerU 输入为准。

## 来源合同

先使用 MinerU HTML 中可确认的 `<th>`。上游完整且连续的表头优先进入 Grid 和 Word。HTML 的 `<thead>` 可包含普通单元格，本轮按单元格和可信校核确定列标题语义。[HTML 表格标准](https://html.spec.whatwg.org/multipage/tables.html#the-thead-element)

当上游缺少可确认的表头前缀时，调用方可提交本地 JSON 校核记录。每条记录声明从第 0 行起的连续表头数量，并绑定 PDF 内容 SHA-256、MinerU content list SHA-256、零基页号、源 JSON Pointer 和原始表格 HTML SHA-256。转换端核对实际 PDF 字节和来源账本，复用已有的 Grid 行列及合并检查。校核覆盖范围须有现存原生 HTML，且不能截断跨表头边界的合并单元格。校核记录与有效源表格一起保留，源 HTML 继续作为原始证据。

校核通过后，源 Grid 和 Word 渲染读取同一行范围，Word 使用现有重复表头写入规则。仅在存在校核时写入附加来源字段，历史普通输入和结果仍使用原记录及身份。缺少新证据的普通输入继续按上游语义输出。

## 复跑

将校核 JSON 显式传给 [本地正式转换入口](../../../scripts/dev/run_local_mineru_conversion.py)。校核格式参见[三张表的锁定记录](../../../tests/fixtures/datasheet_quality/table_header_reviews.json)。

```bash
.venv/bin/python scripts/dev/run_local_mineru_conversion.py "$MINERU_PACKAGE" \
  --source-pdf "$SOURCE_PDF" --table-header-reviews "$REVIEW_JSON" \
  --document-language en --output "$OUTPUT_DOCX"
```

单次转换只提供绑定该 PDF 的记录。样本回放入口可使用完整三表记录，按 PDF 和解析结果指纹匹配提供的结果包。校核回放使用 `local_replay_with_header_review`，方便与原始回放对照。

```bash
.venv/bin/python scripts/dev/run_datasheet_quality_baseline.py \
  --table-header-reviews tests/fixtures/datasheet_quality/table_header_reviews.json \
  --package "gs-003=$OPA228_PACKAGE" \
  --package "gsx-rs2g04=$RS2G04_PACKAGE" \
  --package "gsx-sn74ac244-specs=$SN74AC244_SPECS_PACKAGE" \
  --output tests/tmp/datasheet-header-review-replay
```

## 三张表的同源对照

每个用例使用相同的 PDF、MinerU 结果和模板。校核版仅额外提供来源绑定记录。先从正式转换输出的 DocumentIR 重建 Grid，再通过渲染计划表锚定位实际 DOCX，读取对应行的 `w:tblHeader`。同源对照确认原始 HTML 指纹一致，行列和合并区域匹配，8/8 个已标注技术 Token 保留。

| 样本 | Grid 行 × 列 | 原始表头行（Grid / Word） | 校核后表头行（Grid / Word） |
| --- | --- | --- | --- |
| OPA228 Device Information | 7 × 3 | 无 / 无 | 0 / 0 |
| RS2G04 ESD Ratings | 4 × 4 | 无 / 无 | 0 / 0 |
| SN74AC244 规格页 Operating Conditions | 19 × 8 | 无 / 无 | 0、1 / 0、1 |

原始 0/3 在相同输入上复现，[历史观察](observations.json)与样本清单未改写。[独立的校核观测](table-header-reviewed-observations.json)可用既有指标工具复算。校核后的 3/3 衡量已确认行范围的传递与写入。

24 项定向回归通过，涵盖来源绑定失败、上游 `<th>` 优先、合并边界、正文 `<th>` 及跨页续表行保留。另外对照历史版本重算三份无校核 IR，序列化、源 Grid、质量报告和渲染输入指纹一致。既有原生 `<th>` 完全跨盖下一行且下一行没有独立单元格时，旧 Grid 只统计有单元格锚点的行，Word 会同时标记被覆盖的行。本轮三张实表不触发该边界，旧路径口径保留。
