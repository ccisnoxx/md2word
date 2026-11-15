# 第二阶段验证

## 完整 gs-008 本地回放

固定 [gs-008 基线清单](../../../../../tests/fixtures/datasheet_quality/local_baseline_manifest.json) 的完整 MinerU 缓存和源 PDF。实际 PDF 和选中的 v2 内容列表指纹均与清单一致。用 [两项核定记录](../../../../../tests/fixtures/datasheet_quality/gs008_value_column_reviews.json) 通过本地 CLI 主入口分别写入两个临时结果。保留真实转换的返回证据供核对，并用两个实际 Word 与持久化 IR 各自重建一次证据。

```bash
.venv/bin/python -B scripts/dev/run_local_mineru_conversion.py "$MINERU_PACKAGE" \
  --source-pdf "$SOURCE_PDF" \
  --table-value-column-reviews tests/fixtures/datasheet_quality/gs008_value_column_reviews.json \
  --template "$DEFAULT_TEMPLATE" --layout-config "$DEFAULT_LAYOUT" \
  --subscript-config resources/term_rules/subscripts_dictionary.yaml \
  --translation-mode direct --document-language en --output "$OUTPUT_DOCX"
```

完整回放使用仓库默认模板及其版式文件和符号配置。实际 Word 表头下的两行位置如下，两次独立回放一致。

| 源数据行 | MIN | TYP | MAX | UNIT |
| --- | --- | --- | --- | --- |
| 2 | 空 | ±5 | ±75 | μV |
| 3 | 空 | 空 | ±100 | μV |

数值格与释放格均占一列，单位保持纵向合并。两次包含相同的两个修正证据，原报告保留 23 个该规则的 finding，解除同样的两个 ID，其余 21 个仍为 blocker。两次本地 CLI 均输出 `blocked` 与剩余阻断项 21。

## 整批拒绝

| 变化 | 固定原因 | 产物 |
| --- | --- | --- |
| 用可读的 OPA228 P6 源 PDF 替换原 PDF | `pdf_fingerprint` | 无本次 IR 或 DOCX |
| 保留原 PDF 和 HTML，在临时包的 v2 内容列表追加换行 | `content_list_fingerprint` | 无本次 IR 或 DOCX |
| 保留原 PDF 与包，令第二格的原内容指纹失效 | `cell_binding` | 无本次 IR 或 DOCX |

## 局部回归证据

- `tests.test_table_value_column_review` 的 6 项通过，覆盖整批接纳、指纹、表、格与列约束及 IR 重读。
- `tests.test_table_value_column_review_delivery` 的 4 项通过。两行片段的原报告保留两个跨列发现，认证后的有效 blocker 为零。实物错列、旧 Word 混用、修正证明缺失或断开绑定，以及旧渲染认证路径均拒绝。
- 第一阶段的跨列检测 8 项、表头校核 6 项及交付 2 项通过。另有本地 CLI 和正式转换的受影响回归通过。
- `git diff --check`、Python 语法编译及 Trellis 任务清单校验通过。
