# 实施与验收计划

2026-11-17 用户批准实施。固定输入和旧实现的 IR/Poppler 观察见样本记录，实施后的实际 DOCX 验收另记入 `validation.md`。

## 执行顺序

1. 按 [样本记录](research/gs008-baseline.md) 固定输入。在查看新增匹配结果前独立标注 23 项的源行/格、数值、单位、PDF 实际列；关联原 finding。已有人工记录只在同源并通过实际 Word 认证后计入；与自动证据去重。
2. 在 `pdf_value_column_binding.py` 结构化行匹配与原因，保留现有成功路径。增量实现唯一值反查、组合及跨行物理映射。上下文表示扩展以已观察到的样本或定向反例为限。
3. 增加表片段的单调对齐，验证无解、多解、倒序及计数不符都能保守退出；保留现有列侧校验和提议去重。
4. 增补 `app/domains/document_jobs/views/quality_review.py` 的原因枚举，导出 `docs/api/openapi.json`，更新 TABLE-005 合同。按项目约定检查所改 Python 的注释、文档字符串和开发者可见文字。
5. 完成定向检查和两个实物回放。达到 14/23 前不得降低证据要求；若未达标，按原因和独立标注记录缺口。保存命令、结果、跳过项及未验证范围到本任务 `validation.md`。

## 定向验证

| 验收 | 入口 | 验证点 |
| --- | --- | --- |
| AC1、AC2 | `tests.test_table_value_pdf_binding` | 每项细分原因；同名唯一值、空条件、参数和单位 rowspan、同值不同条件；全局唯一或多解、计数不合、候选竞争。负例翻转值、条件、单位、字形或顺序。 |
| AC3 | `tests.test_pdf_value_column_table_edge`、`tests.test_table_value_pdf_binding_integration`、`tests.test_table_value_pdf_binding_poppler`、`tests.test_table_value_pdf_binding_delivery` | 同源和小幅横向截断门禁；实际 Poppler 和 Word 单列、跨列警告、拒绝错列及证据篡改。 |
| AC1、AC3 | `tests.test_online_table_value_pdf_binding.OnlineTableValuePdfBindingTests` 的警告下载、源不匹配、历史 v3、人工同包和截断场景 | 从本地正式 Worker 到 API 检查原因、原 finding、可下载 Word。若既有多行夹具已被严格取证，用真正未决的负例继续覆盖警告和人工路径。 |
| AC4 | 本地正式 Worker 的完整缓存回放和现有留存包回放 | 对照输入指纹及独立列标注，核对全部原 finding、认证与未决集合、Word `gridSpan` 及释放格。分别统计 23 与 18 项。 |

```shell
.venv/bin/python -m unittest tests.test_table_value_pdf_binding tests.test_pdf_value_column_table_edge tests.test_table_value_pdf_binding_integration tests.test_table_value_pdf_binding_poppler tests.test_table_value_pdf_binding_delivery
.venv/bin/python -m scripts.ops.export_openapi
.venv/bin/python -m scripts.ops.export_openapi --check
git diff --check
```

计划为 `OnlineTableValuePdfBindingTests` 增加 `test_full_gs008_certifies_row_evidence_and_word`，由 `MD2WORD_TABLE_VALUE_GS008_DIR` 指向完整本地缓存，以临时打包调用现有 `worker_case`。留存原包继续用 `test_retained_p7_real_package_certifies_word_after_table_edge_recovery` 和已有的 `MD2WORD_TABLE_VALUE_P7_PDF`、`MD2WORD_TABLE_VALUE_P7_ZIP`。记录精确命令及 Poppler 版本。无外部 MinerU 调用、全仓回归或发布门禁。

## 审查与回退

激活前检查三份计划和 JSONL。`word-generation-rules.md` 超过 Trellis 单文件注入上限，实现及复核代理需直接读取其中 TABLE-005 全节。实现后安排独立复核实际 diff，核对错修反例、顺序唯一性、原因兼容和实物认证边界。回退时保留兼容读者；不改写历史证据，不将原始样本包提交进仓库。
