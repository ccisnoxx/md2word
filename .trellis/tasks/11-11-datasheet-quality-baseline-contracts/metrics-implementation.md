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

## 常规回归出表

使用 [Golden Sample 常规回归入口](../../../scripts/ops/run_golden_sample_regression.py)。运行目录中的 `observations.json` 和 `metrics.json` 与原有 P0 验收报告一起生成。启用的 manifest 项形成固定分母，每项关联模式及 `GOLDEN_SAMPLE_METRICS_EVIDENCE_LEVEL` 指定的运行证据层级，默认值为 `golden_sample_api`。

任务终态、下载授权和实际下载分别记录。成功计时从首次创建文档任务请求前到取得对应主 DOCX 的下载授权，取得有效且可打开的文件后才计成功。失败和超时各自计时。原 P0 报告的 `elapsed_seconds` 仍包含源 PDF 上传、下载传输和检查。

设置 `GOLDEN_SAMPLE_COST_EVIDENCE` 可接入本批费用凭据。回归结束时读取 `golden-sample-cost-evidence/v1` JSON 的 `receipts` 数组，每项按 `job_id` 和 `retry_count` 归属。内层 `cost` 沿用指标 v1 的 `currency`、`basis`、`reference`、`components` 和 `complete`。完整凭据须覆盖解析、翻译和截至该代的全部尝试。凭据缺失、无效、代次错配或只取得分项时，总费用记录为缺测。普通回归中没有采集的表格标注、技术 Token、视觉及人工数据分别记录缺测原因。

本地以原 P0 清单的四份 PDF 运行正式 CLI，任务和费用响应由回环服务提供，报告证据层级为 `local_http_fixture`。四项分别模拟有效主件、坏 DOCX、任务失败和下载失败。指标成功率为 1/4，P0 目标继续为 100%。完整、部分和代次不匹配的测试凭据分别得到总额、已知分项和缺测结果。直接复算 `observations.json` 与自动生成的 `metrics.json` 逐项一致。[回环复验入口](../../../tests/tmp/datasheet-quality-regression/replay.py)

常规入口、P0 报告和指标采集的 42 项定向测试通过，另有 2 项 P1 清单兼容检查通过。无效费用凭据保留转换和时延结果，终态身份错配保留费用缺测。机器指标先于可选 P0 人工签字文件保存。3 个本轮 Python 文件通过语法编译，`git diff --check` 通过。

### 固定清单隔离实链验收

2026-11-12 使用同一 P0 固定清单运行常规 CLI。环境为隔离的本地 API、Celery、Redis、SQLite 和本地对象存储，实际调用 MinerU `vlm` 解析。证据层级为 `isolated_live_api_celery_sqlite`。运行依据为提交 `e3e4be94` 及当时工作区，代码指纹见对账记录。[实链对账记录](../../../tests/tmp/datasheet-quality-regression-live/20261112T033738667332Z/verification.json)

- 转换成功 4/4，CLI 退出码为 0。四份实际下载的主 DOCX 均可打开，任务主件 ID、登记文件字节数和 SHA-256、下载件 SHA-256 与观测相符。四项任务重试代次均为 0。
- `observations.json` 按固定清单复算，与自动生成的 `metrics.json` 逐项一致。任务提交至取得下载授权的 P50 为 22.158 秒，P95 为 22.203 秒，样本数 4。状态轮询间隔为 2 秒。
- 本批四个 MinerU 结果查询均返回 HTTP 200，批次 ID 和 `data_id` 均能对上本地任务。结果响应没有可用于本轮结算的金额字段，本批未提供费用凭据。总成本 4/4 缺测，原文转换产生的翻译批次数为 0。
- 旧 P0 报告的自动链路目标达成。P0 发布资格继续等待管理员 Word 质量签字。隔离实链证据单列，保留原有回环验收与历史基线。

[自动观测](../../../tests/tmp/datasheet-quality-regression-live/20261112T033738667332Z/runs/20261112T033741Z/observations.json) · [自动指标](../../../tests/tmp/datasheet-quality-regression-live/20261112T033738667332Z/runs/20261112T033741Z/metrics.json) · [本地验收目录](../../../tests/tmp/datasheet-quality-regression-live/20261112T033738667332Z/runs/20261112T033741Z/)

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
