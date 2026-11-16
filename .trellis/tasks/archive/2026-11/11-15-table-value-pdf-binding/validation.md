# 第三阶段验证

## 跨版式的本地正式转换

独立 LOW/HIGH 构造样本使用无色闭合划线、与标题右沿不对齐的数值和不同参数条件。以真实 Poppler 读取同源 PDF，经正式入口写出 Word，再由持久化 IR 和实际 DOCX 重建证据。三处原跨列发现均保留在源报告。

| 参数 | 原跨列数值 | 实际 Word 落位 |
| --- | --- | --- |
| Reset dwell | `7.2e-4 s` | 只在 HIGH，LOW 为空 |
| Cool-down | `43 ms` | 只在 LOW，HIGH 为空 |
| Lockout | `48 ms` | PDF 词框压列界，Word 保留原两列跨度，仍为 blocker |

测试还覆盖标题别名、疑似值重复、释放格内另有文字或字形、同行条件和单位冲突、两处源格竞争同一实物位置。若邻行已划内竖线而本行断开，即使本行边缘的横线看起来按列分段，仍保留 blocker。实际 PDF 的 `ActualText` 与可见值不同、隐字、叠印或遮挡时无法获得完整可见证据。

评审使用实际字体造出错误的 `ToUnicode` 映射，复现了两个 Poppler 文字工具均把实际画出的 `45` 读为 `75`。本轮核对依赖原件字体映射的字符语义，并证实字形确实绘制在对应位置。字体映射误标的情况仍需比对实物字形。

## 完整 gs-008 回放

完整缓存的包内源 PDF、选中 v2 内容列表均匹配 [gs-008 基线清单](../../../../../tests/fixtures/datasheet_quality/local_baseline_manifest.json)。Poppler 为 26.06.0，使用 `pdfinfo`、`pdftotext`、`pdftocairo` 和 `pdftohtml`。通过本地 CLI 入口独立运行两次，使用默认模板和版式资源，不传人工核定文件。

```bash
.venv/bin/python -B scripts/dev/run_local_mineru_conversion.py "$MINERU_PACKAGE" \
  --source-pdf "$SOURCE_PDF" --auto-table-value-columns \
  --template "$DEFAULT_TEMPLATE" --layout-config "$DEFAULT_LAYOUT" \
  --subscript-config resources/term_rules/subscripts_dictionary.yaml \
  --translation-mode direct --document-language en --output "$OUTPUT_DOCX"
```

分别从实际 DOCX 读取源片段 `/0/2` 的表头、行和格位，并用持久化 IR 重建交付证据。

| 源数据行 | MIN | TYP | MAX | UNIT |
| --- | --- | --- | --- | --- |
| 2 | 空 | ±5 | ±75 | μV |
| 3 | 空 | 空 | ±100 | μV |

两次数值格与释放格均只占一列，单位保持纵向合并。原报告保留 23 个跨列 finding。两次都认证 9 条自动 Grid 修正，修正 ID、绑定证据和剩余 finding 身份一致。14 条因为行上下文未能唯一定位仍保持 blocker，原因是 `row_ambiguous`，质量结果为 `blocked`。IR 保留片段、源行、源格和原 finding ID，供第二阶段的人工核定入口处理。

以同名、同文本但 SHA-256 不同的仓库 P7 替换源 PDF，正式转换保留全部 23 个原 blocker，未生成自动核定，原因是 `source_pair_unverified`。同源且显式提供第二阶段人工记录时，两条所请求的格位由人工记录控制，另外 7 条仍通过自动修正认证。不同版本的 PDF 加上旧人工记录则在写结果前整批拒绝，原因为 `pdf_fingerprint`。

## 定向核查

- PDF 观测、参数列绑定与独立真实 Poppler 到 Word 的三组回归共 14 项通过。
- 同源配对、人工优先与过期整批拒绝的集成回归共 4 项通过。交付、原人工修正和正式 evidence 回归共 9 项通过，覆盖实际 Word 错列、旧证据混用、删除或改写 PDF 出处以及历史无自动选项的转换。
- 第一阶段规则 8 项、人工接纳 6 项通过。审批与发布、表头核定和本地正式 CLI 的既有定向回归共 21 项通过。
