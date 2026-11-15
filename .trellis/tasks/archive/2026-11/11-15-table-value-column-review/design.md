# Grid 层人工修正方案

## 入口

沿用 `scripts/dev/run_local_mineru_conversion.py` 和 `FormalMinerUConversionRequest`。`--table-value-column-reviews` 搭配现有 `--source-pdf` 和原 MinerU 包。首次无记录回放后，可从现有 IR 与表格报告取得源表、原格和指纹，校核人填写实际应归属的列。完整样例见 [gs-008 核定记录](../../../../../tests/fixtures/datasheet_quality/gs008_value_column_reviews.json)。

```bash
.venv/bin/python scripts/dev/run_local_mineru_conversion.py "$MINERU_PACKAGE" \
  --source-pdf "$SOURCE_PDF" --table-value-column-reviews "$REVIEW_JSON" \
  --translation-mode direct --document-language en --output "$OUTPUT_DOCX"
```

线上 Worker 目前没有校核输入，普通重试可复用已有 IR，新代会清空原 MinerU 结果指针并从上传阶段开始。首版用本地已冻结的包明确选择来源，复用正式转换、渲染和证据核心。线上接纳另需由受权操作冻结原始结果和记录并明确从 IR 前重走。[入口调研](research/source-binding-and-entry.md)

## 记录与接纳

每个表片段一条 `TableValueColumnReview`，含若干原单元格修正。复用 `TableHeaderReview` 的五个来源字段，另记原 Grid 的解析版本、片段内原格序号、原格内容指纹和原列区间。目标由零基列号与预期标题共同限定。片内行号、源单元格序号和列号均从零计，范围为左闭右开。程序从已核验来源派生稳定 `cell_id`，与执行 ID 无关。

下例使用完整 `gs-008` 缓存的真实来源指纹与原格锚点。

```json
[
  {
    "schema_version": "table-value-column-review/v1",
    "source_pdf_sha256": "24f724cf0e795f6afeb6fec5c72ff8f144085c59d57fbf0a5c9efbf1808b1eb3",
    "content_list_sha256": "fdc0ea4050914df39ce7d3e9e42798164d32d1f04b82bd9dff4d2ffc1e9e98c3",
    "page_index": 0,
    "json_pointer": "/0/2",
    "raw_html_sha256": "c5cfc86947e81ae9e8b832f36f96f08aadb37a4c4261e4c3fb5235b8677f2485",
    "normalizer_version": "table-html/v1",
    "corrections": [
      {
        "source_row_index": 2,
        "source_cell_index": 4,
        "content_sha256": "4e40b4e9dbfef4e9c36f610edab5beecec9038718e8dbe253654cf6bb4d05393",
        "original_column_range": [4, 6],
        "target_column": 5,
        "target_header": "TYP"
      },
      {
        "source_row_index": 3,
        "source_cell_index": 1,
        "content_sha256": "90342bf296626a52e53356f30d4b43074eca0dbe97c8e5ffd2716779e595548a",
        "original_column_range": [4, 7],
        "target_column": 6,
        "target_header": "MAX"
      }
    ]
  }
]
```

在逻辑表归组和既有表头校核完成后、返回 IR 前，重算实物 PDF 和实际选用的 content list 指纹。逐表比对当前 JSON Pointer、页号及原 HTML，再用当前源 Grid 比对解析版本、原格内容与跨度。首版接纳原生可见、结构有效、单片的表，以及已命中第一阶段跨列规则且 `rowspan=1` 的数据格。原跨度须完全位于并列数值列内，目标是其中一个标题一致的列。重复目标、越界、标题不符或无法定位时整批失败。合法包目录即使被重新压缩，来源判定仍依据实际内容列表和原表/原格的身份。

`table_value_column_review_invalid` 统一表示校核拒绝，按来源版本、原格、目标列及重复目标给出固定原因。拒绝发生在结果写入前。已核验记录作为 `TableFragment` 的可选字段进入本次 IR，校核记录指纹纳入对应的渲染输入身份。

## Grid、Word 和交付证据

1. `build_table_grid` 继续生成原始来源网格，`validate_document_tables` 继续认证并报告原坐标。使用原报告标识本次核定对应的确切 finding。
2. 在 `build_content_table_plan` 组装当前片段的渲染 Grid 时，用同一已核定记录定位当前视图的源行和源格序号，并核验原几何。只复制有关 `TableCell` 更新 `column` 与 `colspan=1`。原表宽、行位置、已有列位、源 cell/run 身份和文字保持。空出的列直接使用现有 Word writer 的空槽写入，避免生成带虚假源索引的单元格。
3. 复用 Word 内容完整性认证，对这一渲染计划检查实际目标列及 `w:gridSpan`，并检查释放的槽位为空。若计划无法应用、Word 位置或内容不一致，拒绝产物的修正认证。
4. 在已认证的表格交付证据附加修正记录指纹、源格和原 finding 身份、修正前后列范围、实际输出表和行。只从交付 flags 中移除证据充分且一一对应的 `table_value_column_span_ambiguous`，按其余 flags 计算状态。重读核对证据与原报告、输出行列、当前 IR 和实际 DOCX，复用既有结果凭据绑定。原报告仍可供审计。

渲染、认证及重读应使用同一计划重建边界。该变换保持原 HTML 与源 Grid，因此翻译源文本索引和续表归组仍由原逻辑拥有。无记录时省略可选字段，沿用历史序列化和身份。撤回核定通过显式省略记录重跑，既有结果保留。[Grid 和证据调研](research/grid-projections.md)
