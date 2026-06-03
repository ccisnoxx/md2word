---
doc_type: test-report
slug: pdf-to-word-golden-sample-acceptance-report
component: pdf-to-word-backend
status: blocked
summary: P0 Golden Sample 验收报告；当前正式匹配 PDF 为 4，其中 1 个已跑过真实主链路 smoke，尚未达到 10-20 份正式样本目标。
tags: [testing, golden-sample, pdf, word, p0]
last_reviewed: 2026-06-03
---

# P0 Golden Sample 验收报告

## 当前结论

截至 2026-06-03，`tests/fixtures/golden_samples/pdfs/OPA228_P1.pdf`、`OPA228_P2.pdf`、`OPA228_P6.pdf` 和 `OPA228_P7.pdf` 已映射到 `manifest.yaml`，作为 4 个正式可运行样本。当前正式样本数量仍低于 10-20 份目标，且只有 `gs-003 / OPA228_P1.pdf` 已跑过真实主链路 smoke，不能声称完成 “10-20 份样本核心链路成功率 >= 90%” 的正式验收。

## 已完成

- 样本目录：`tests/fixtures/golden_samples/pdfs/`
- 样本清单：`tests/fixtures/golden_samples/manifest.yaml`
- 人工验收模板：`tests/fixtures/golden_samples/acceptance-record-template.md`
- 批量回归脚本：`scripts/ops/run_golden_sample_regression.py`
- 回归输出目录：`tests/tmp/golden_sample_runs/`
- 样本映射：`OPA228_P1.pdf`、`OPA228_P2.pdf`、`OPA228_P6.pdf` 和 `OPA228_P7.pdf` 已分别作为 `gs-003`、`gs-004`、`gs-006` 和 `gs-008` 纳入正式 manifest。

## 当前执行状态

| 项目 | 当前值 |
|---|---|
| 清单样本数 | 12 |
| 正式匹配 PDF 数 | 4 |
| Manifest 外 PDF 数 | 0 |
| Manifest 外 PDF | none |
| 可运行正式样本数 | 4 |
| 主链路已执行正式样本数 | 1 |
| 主链路成功数 | 1 |
| 主链路失败数 | 0 |
| 主链路成功率 | 100.00%（1/1，仅代表已执行的 `gs-003` 真实 smoke；新映射的 `gs-004`、`gs-006`、`gs-008` 尚未执行） |
| P0 目标 | 10-20 份样本核心链路成功率 >= 90%，成功样本 Word 可打开可编辑 |
| 当前状态 | blocked: 真实链路 smoke 已通过 1 个正式样本，但仍需执行新映射样本、补齐 10-20 份样本并完成人工质量验收 |

## 最近脚本验证

2026-06-02 已运行一次 Golden Sample 脚本做 inventory smoke。该次运行使用 dummy bearer token，未启动真实后端/Worker/MinerU，因此只用于验证样本清单和报告字段，不计入正式 P0 回归。

| 项目 | 结果 |
|---|---|
| Manifest 样本数 | 12 |
| 正式匹配 PDF 数 | 1 |
| 实际执行 | 1 |
| 缺少 PDF | 11 |
| Manifest 外 PDF 数 | 0（该次运行发生在 P2/P6/P7 进入当前工作区之前） |
| 成功 | 0 |
| 失败 | 1 |
| 失败原因 | `ConnectionError`，预期原因是本次未启动真实后端服务 |
| 是否达标 | false |

## 真实链路 smoke

2026-06-02 在 hostdzire 真实部署环境中运行 `gs-003 / OPA228_P1.pdf`。本次使用真实 API、worker、MySQL、Redis 和 MinerU 配置，目标是确认上传、建任务、Worker、MinerU、DocumentIR、Word 渲染和下载是否存在卡点。

| 项目 | 结果 |
|---|---|
| 执行环境 | hostdzire API 容器内临时放入 Golden Sample 脚本、manifest 和 PDF |
| 回归结果目录 | `/app/tests/tmp/golden_sample_runs/20260602T071017Z` |
| Manifest 样本数 | 12 |
| 正式匹配 PDF 数 | 1 |
| 实际执行 | 1 |
| 缺少 PDF | 11 |
| Manifest 外 PDF 数 | 0（本次远端容器 smoke 只临时放入 `OPA228_P1.pdf`） |
| 成功 | 1 |
| 失败 | 0 |
| job_id | `docjob_d4c4101592ad` |
| Word 可打开 | true |
| result_file_id | `file_35a5e9c43885` |
| 主链路结论 | 未卡在上传、建任务、Worker、MinerU、DocumentIR、Word 渲染或下载任一 stage |
| P0 判定 | 仍 blocked：本次远端 smoke 只执行 1 个正式样本；当前 manifest 已扩展到 4 个正式匹配 PDF，但仍不满足 10-20 份样本规模目标 |

## gs-003 人工质量 triage

2026-06-02 已对 `gs-003 / OPA228_P1.pdf` 真实链路生成的 DOCX 做人工结构质量 triage，记录见 `docs/testing/pdf-to-word-gs-003-quality-triage.md`。

| 项目 | 结论 |
|---|---|
| Word 可打开 | true |
| 可编辑性 | 部分通过：正文、表格和图片对象可编辑；列表语义和数学符号质量不足 |
| 标题 | 部分通过：主标题可见，但未映射为 Word heading |
| 双栏顺序 | 未通过：列边界和阅读顺序存在破坏 |
| 图表 | 部分通过：曲线图保留且可辨认，但 figure/caption 结构不稳定 |
| Device Information 表格 | 未通过：表格内容完整可编辑，但标题位置和分页明显错误 |
| 人工结论 | 条件通过（主链路）/ 未通过（P0 版面与语义质量） |

## 正式验收命令

```bash
GOLDEN_SAMPLE_USERNAME=operator \
GOLDEN_SAMPLE_PASSWORD='<password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

正式执行后，把 `tests/tmp/golden_sample_runs/{timestamp}/report.md` 的汇总结果回填到本报告，人工打开每个成功样本 Word 后按 `tests/fixtures/golden_samples/acceptance-record-template.md` 记录结论。

当前 4 个 OPA228 PDF 已进入正式 manifest，但只有 `gs-003 / OPA228_P1.pdf` 完成真实链路 smoke；正式 P0 通过仍需要更多样本、完整回归和人工质量验收结果。
