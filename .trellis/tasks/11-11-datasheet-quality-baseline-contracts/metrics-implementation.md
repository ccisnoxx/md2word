# Datasheet 七组量化指标

七组指标的定义、失败规则和缺测规则见[指标合同](design.md#2-指标合同)。同一运行按固定的样本与转换模式计算，重试归入原计划项。正常计划项与预期阻断用例分别汇总。历史观测、校核后回放和完整链路各自有运行 ID。

## 统一复算

```bash
task_dir=.trellis/tasks/11-11-datasheet-quality-baseline-contracts
mkdir -p tests/tmp/datasheet-quality-metrics
.venv/bin/python scripts/ops/datasheet_quality_metrics.py \
  "$task_dir/metrics-baseline.json" \
  --output tests/tmp/datasheet-quality-metrics/baseline-report.json
```

[基线清单](metrics-baseline.json)固定六份已保存的观测。统一报告为 `datasheet-quality-baseline-report/v1`，每次运行保留原观测 SHA-256 和一份原格式 `datasheet-quality-metrics/v1`。直接传入一份历史 `datasheet-quality-observations/v1` 仍可复算原报告。清单路径相对清单所在目录，输出路径与输入分开。

| 指标 | 报告字段和读法 |
| --- | --- |
| 转换成功率 | `conversion_success` 记录正常计划项分子、分母、已评估数及失败原因。完整链路要求主 DOCX 可下载且可打开。本地回放单列。 |
| 原生表格结构准确率 | `table_structure` 按 Word 实物的一对一结构匹配计分。源 Grid 差异留在采集观测中供定位。原始基线照原口径复算。历史 v1 中缺少 `table.unexpected` 时汇总默认显示 0，只有明确采集该字段的观测可用于判断意外多表。 |
| 技术 Token 保留率 | `technical_tokens` 汇总标注位置的一对一匹配，按类别保留分母及已评估数。 |
| 页面视觉偏差 | `page_visual` 汇总匹配页和区域覆盖、归一化边界差异均值与 P95。现有英译中观测因缺同模式批准基准而缺测。 |
| 人工修改次数 | `manual_edits` 按实际已修正的缺陷 ID 去重。空数组表示已采集且为零，省略表示缺测。 |
| 人工验收耗时 | `manual_review_minutes` 只汇总完整审核轮次内不重叠的有效区间。 |
| 单文档成本和延迟 | `cost` 按币种、账单或估算依据分组，完整成本含解析和翻译。 `latency_seconds` 分开汇总完整链路、回放和失败。当前已保存的实链估算为 USD 0.001626756，任务提交至取得下载授权 32.234 秒，含 PDF 提交 32.245 秒。 |

## 人工数据回填

清单每个运行可加 `manual_reviews`，指向独立的 `datasheet-quality-manual-reviews/v1` JSON。其 `reviews` 数组每条记录使用 `sample_id`、`mode` 和 `initial_docx_sha256` 绑定该运行的首次可打开 DOCX。可选 `revisions` 记录修订产物 SHA-256。可选 `edits` 中每项给出缺陷 `id`、`disposition`，处置为 `fixed` 时计入。可选 `rounds` 中每轮给出 `id`、`reviewer`、`docx_sha256` 和 `intervals`，有效区间用 `start_seconds`、`end_seconds`。每轮指纹须对应首次稿或本记录内的修订稿。只有实际审核后才写入相应字段。报告保留回填文件 SHA-256，首次观测保留原文件。

人工修改次数与验收耗时当前均待采集。沿用既有 P0 成功率和受保护技术 Token 完整率要求，其余门槛等待实测覆盖。

16 项定向测试通过，覆盖单次复算兼容、多次运行隔离、人工回填及指纹错配、报告覆盖保护、Word 实物与源 Grid 差异，以及单一实物表的重复认领。六次基线运行按清单生成并与逐份单独复算核对。
