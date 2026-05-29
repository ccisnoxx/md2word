---
doc_type: test-report
slug: pdf-to-word-golden-sample-acceptance-report
component: pdf-to-word-backend
status: blocked
summary: P0 Golden Sample 验收报告；当前缺少真实 PDF 样本，尚未执行正式回归。
tags: [testing, golden-sample, pdf, word, p0]
last_reviewed: 2026-05-29
---

# P0 Golden Sample 验收报告

## 当前结论

截至 2026-05-29，仓库内未提供真实 Golden Sample PDF；只建立了样本清单、人工验收模板和可执行回归脚本。因此本轮不能声称完成 “10-20 份样本核心链路成功率 >= 90%” 的正式验收。

## 已完成

- 样本目录：`tests/golden_samples/pdfs/`
- 样本清单：`tests/golden_samples/manifest.yaml`
- 人工验收模板：`tests/golden_samples/acceptance-record-template.md`
- 批量回归脚本：`scripts/ops/run_golden_sample_regression.py`
- 回归输出目录：`tests/golden_samples/runs/`

## 待执行

| 项目 | 当前值 |
|---|---|
| 清单样本数 | 12 |
| 实际 PDF 数 | 0 |
| 已执行样本数 | 0 |
| 成功数 | 0 |
| 失败数 | 0 |
| 成功率 | 未执行 |
| P0 目标 | 10-20 份样本核心链路成功率 >= 90%，成功样本 Word 可打开可编辑 |
| 当前状态 | blocked: 等待业务确认并放入真实 PDF 样本 |

## 正式验收命令

```bash
GOLDEN_SAMPLE_USERNAME=operator \
GOLDEN_SAMPLE_PASSWORD='<password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

正式执行后，把 `tests/golden_samples/runs/{timestamp}/report.md` 的汇总结果回填到本报告，人工打开每个成功样本 Word 后按 `tests/golden_samples/acceptance-record-template.md` 记录结论。
