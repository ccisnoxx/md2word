# 参数值列行取证验收

2026-11-17 在本机使用 Poppler 26.06.0，通过正式 Document Jobs Worker、IR、渲染及结果认证回放两份固定输入。MinerU 传输和预览 Provider 使用隔离测试夹具。源 PDF、入包字节、Word、报告及下载均经过正式代码。验收按 [独立 PDF 标注](../../../../../tests/fixtures/datasheet_quality/gs008_value_column_expected.json) 核对数值、词框纵坐标、源行格及 Word 的实际列。

| 输入 | 证据正确的自动修正 | 自动错修 | 保留 warning | DOCX |
| --- | --- | --- | --- | --- |
| 完整同源 gs-008 | 17/23（73.91%） | 0 | 6 | 转换成功，下载返回 200 |
| 18 项留存原包 | 12/18（66.67%） | 0 | 6 | 转换成功，下载返回 200 |

完整样本 17 项均由自动取证获得。源报告保留全部 23 个 finding。相较于 9 项旧基线，新增通过零基源行 6、7、8、9、11、12、19、20。实际 Word 中 `±5 µV` 只占 TYP，`±100 µV` 只占 MAX。两格均为 `gridSpan=1`。其余通过项逐格核对了目标列、原跨度内释放格为空及符合绑定的 PDF 词框。留存包的 `±100 µV` 原本已只占 MAX。

两份输入中的六个未决格均保留原跨度并由质量 API 投影为人工复核 warning。行 21–24 的对应单位未获可靠字形证据，报告 `unit_row_mismatch`。行 27–28 的共模抑制条件缺少可靠的跨行公式证据，报告 `rowspan_context_unresolved`。下载返回的字节与已认证的 Word 一致。

完整 DOCX SHA-256 为 `f346f139e4ae655c5ba1ef0e117fd5f37084f5f277e38d00acb020174bb294b5`，留存包 DOCX 为 `a14ceb7de147a45659cb9dc6d056ef08e3690f47f2f298a966dc384094017f35`。本机证据目录为 `tests/tmp/table-value-row-evidence-dFPFV1/`，含两份 DOCX 和逐项摘要。

## 本地验证命令

```shell
PYTHONPATH="$PWD" .venv/bin/python -B tests/tmp/table-value-row-evidence-dFPFV1/run_verified_samples.py
PYTHONPATH="$PWD" .venv/bin/python -B tests/tmp/table-value-row-evidence-dFPFV1/run_verified_samples.py \
  tests.test_table_value_pdf_binding \
  tests.test_online_table_value_pdf_binding.OnlineTableValuePdfBindingTests.test_full_gs008_certifies_row_evidence_and_word \
  tests.test_online_table_value_pdf_binding.OnlineTableValuePdfBindingTests.test_retained_p7_real_package_certifies_word_after_table_edge_recovery
.venv/bin/python -m scripts.ops.export_openapi --check
python3 .trellis/scripts/task.py validate .trellis/tasks/11-17-table-value-row-evidence
git diff --check
```

54 项定向测试通过。补上列界未决格参与同行冲突检查后，复跑直接受影响的 12 项，包括两份实物，结果通过。OpenAPI 快照、改动的 Python 语法、任务上下文和差异检查通过。Trellis 提示 TABLE-005 所在文件超过注入上限，实施和复核时直接读取了对应章节。

独立复核覆盖同一源合并格分裂、两个源合并格复用一个 PDF 合并格、已明确列的邻行和贴列界的邻行给出冲突证据等反例。另穷举比对了单调路径的评分、唯一性和回溯，以及词框索引与原坐标相交规则。600 行重复值划线夹具的 600 项均保持未决，复用词框索引后本机匹配耗时约 2.3 秒。

这次的证据范围为本地代码、固定输入和实际 DOCX 证据重读。生产部署、真实 MinerU 新提交、全仓回归及 Microsoft Word 客户端人工排版检查未执行。
