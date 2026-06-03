---
doc_type: feature-evidence
feature: 2026-06-03-golden-sample-live-regression-scale-up
slug: docs-and-roadmap-backfill
status: completed
created_at: 2026-06-03
tags: [golden-sample, roadmap, acceptance-input, pipeline-parity-gap]
---

# docs-and-roadmap-backfill

## 结论

`docs-and-roadmap-backfill` 已完成。本步骤只回写报告、roadmap notes 和后续 feature design 输入，没有修改 DocumentIR、renderer、前端、后端 API 或部署配置。

回写后的事实口径：

- 2026-06-03 hostdzire 真实回归批次 `20260603T070724Z` 中，`gs-003/004/006/008` 主链路 4/4 succeeded，DOCX 4/4 openable。
- 当前仍不能声明 P0 Golden Sample 通过：runnable 样本只有 4 个，低于 10-20 份目标；人工质量 0/4 P0 pass。
- 主要质量分类为 `pipeline-parity-gap`：`md2word_main` / `app/conversion/runtime` 已有部分 heading、list、formula、caption、table 和 layout 策略，但当前 API `document_jobs -> DocumentIR -> app/services/renderer` 链路没有接入。

## 已回写文件

| 文件 | 回写内容 |
|---|---|
| `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` | 从旧的 1/1 smoke 状态更新为 4/4 live regression；补入人工质量 0/4 P0 pass、`pipeline-parity-gap` 分类和后续 feature 输入。 |
| `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-roadmap.md` | 更新 feature 清单、观察项和变更日志；本 implementation 步骤当时保留 `golden-sample-live-regression-scale-up` 为 `in-progress`，等待后续 acceptance 闭环再置为 done。 |
| `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-items.yaml` | 更新当前 item notes；把 `document-ir-layout-risk-pass` 和 `word-renderer-editable-output-pass` 的 planned notes 改为 legacy runtime parity/migration 优先。 |

## 后续 feature design 输入

### document-ir-layout-risk-pass

不要从零修 layout。进入 design 前应先做 parity 判断：

1. 对比 live job 保存的 DocumentIR 与 `md2word_main` / `app/conversion/runtime` legacy pages/blocks。
2. 判断 page orientation、two-column grouping、caption/figure binding、wide/long table continuation 等策略哪些可直接迁移到 DocumentIR 链路。
3. 只有当现有 IR 缺少必要 layout fact 时，才设计 DocumentIR 字段或转换链路变更。

### word-renderer-editable-output-pass

第一目标是同步 legacy renderer 策略到 API renderer：

1. 把 `app/conversion/runtime` 的 heading、list、formula、caption、table 策略迁移到 `app/services/renderer`。
2. 为 API `document_jobs` 链路新增或更新回归用例。
3. 验收必须检查 OOXML 语义，包括 paragraph style、`w:numPr`、LaTeX 残留、caption/table 顺序，不能只测 `md2word_main` sandbox 输出。

## 验收输入

后续 `cs-feat-accept` 应读取：

- `.codestable/features/2026-06-03-golden-sample-live-regression-scale-up/live-regression-run.md`
- `docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md`
- `.codestable/features/2026-06-03-golden-sample-live-regression-scale-up/failure-classification.md`
- `docs/testing/pdf-to-word-golden-sample-acceptance-report.md`
- `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-items.yaml`

## 边界

- 未更新 architecture / requirements：本 feature 没有改变系统结构或能力承诺，只同步回归事实和后续 feature 输入。
- 本 implementation 步骤未把 roadmap item 标为 done；后续 acceptance 闭环负责最终 done 回写。
- 未写入凭证、token、客户文件正文或完整解析文本。
