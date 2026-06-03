---
doc_type: feature-acceptance
feature: 2026-06-02-golden-sample-quality-baseline
status: accepted
summary: 验收 Golden Sample inventory/report 基线，确认 orphan PDF 不计入正式通过率。
tags: [golden-sample, pdf-to-word, testing, quality-baseline]
accepted_at: 2026-06-02
roadmap: pdf-to-word-delivery-hardening
roadmap_item: golden-sample-quality-baseline
requirement: fastapi-backend-productization
---

# golden-sample-quality-baseline 验收报告

> 阶段：阶段 3（验收闭环）  
> 验收日期：2026-06-02  
> 关联方案 doc：`.codestable/features/2026-06-02-golden-sample-quality-baseline/golden-sample-quality-baseline-design.md`

## 1. 接口契约核对

本 feature 不修改 document job API、后端路由或前端入口，只扩展 Golden Sample 回归脚本的报告层合同。

- [x] `SampleInventory` 表达 manifest-matched、missing、orphan PDF inventory。
- [x] `build_report()` summary 保留既有 `configured_samples` / `runnable_samples` / `missing_pdf_samples`，并新增 `manifest_samples`、`manifest_matched_pdfs`、`orphan_pdf_count`、`orphan_pdf_files`。
- [x] `format_console_report()` 和 `format_markdown_report()` 均输出 orphan PDF 信息。
- [x] orphan PDF 只报告，不参与 runnable sample、pass rate 或 P0 met_target 判定。

## 2. 行为与决策核对

- [x] 保留 manifest 作为正式样本真源：baseline 阶段 `OPA228_P1.pdf` 未自动写入 manifest，后续按用户确认映射到 `gs-003`。
- [x] baseline 阶段目录事实可见：`OPA228_P1.pdf` 被报告为 orphan PDF。
- [x] baseline 阶段正式 runnable sample 为 0：当时 12 个 manifest sample 仍缺少匹配 PDF。
- [x] 文档不再使用旧的“真实 PDF 数 0”单一口径，而是区分正式匹配 PDF 和 manifest 外 PDF。
- [x] 不修改 backend/frontend 业务代码，不新增 API 或后台功能。

## 3. 验收场景核对

- [x] 扫描 `tests/fixtures/golden_samples/pdfs/`：测试确认 baseline 阶段 `OPA228_P1.pdf` 是 orphan PDF。
- [x] 读取 `manifest.yaml`：测试确认 12 个样本仍为正式清单，baseline 阶段缺失匹配 PDF。
- [x] 构造回归报告 summary：测试确认 manifest、missing、orphan 和 runnable 字段存在且值正确。
- [x] 打开 Golden Sample 验收报告：文档当前事实已更新为“正式匹配 PDF 数 0 / Manifest 外 PDF 数 1”。
- [x] targeted tests 通过：`/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_golden_sample_manifest`，6 tests OK。

## 4. 术语一致性

- `orphan PDF`：design、脚本、README、验收报告和测试含义一致，均指 sample_root 下未被 manifest 引用的 PDF。
- `manifest-matched PDF`：只表示 enabled manifest sample 中 filename 匹配真实文件。
- `runnable sample`：只来自 manifest-matched PDF，不包含 orphan PDF。

## 5. 架构归并

本 feature 不改变 FastAPI 后端架构、document job 主链路、DocumentIR 或 renderer。无需更新 `.codestable/architecture/`。

长期事实更新落在测试和验收文档：

- `docs/testing/pdf-to-word-golden-sample-acceptance-report.md`
- `tests/fixtures/golden_samples/README.md`
- `scripts/ops/run_golden_sample_regression.py`

## 6. requirement 回写

关联 requirement 为 `fastapi-backend-productization`，当前状态已是 `current`。本 feature 只补 Golden Sample 质量基线可观测性，不改变用户故事或后端产品化能力边界，因此无需更新 requirement。

## 7. roadmap 回写

- [x] `pdf-to-word-delivery-hardening-items.yaml` 中 `golden-sample-quality-baseline` 从 `in-progress` 回写为 `done`。
- [x] `pdf-to-word-delivery-hardening-roadmap.md` 子 feature 清单同步为 `done`。
- [x] roadmap notes 明确当前 baseline 结论：正式 runnable sample 仍为 0，后续需要先确认样本映射或补齐正式 PDF。

## 8. attention.md 候选盘点

无新增候选。已有 `.codestable/attention.md` 已说明测试默认使用 `/Users/sc/miniconda3/envs/md2word/bin/python`。

## 9. 遗留

- 当前正式 runnable sample 仍为 0，不能进入正式 P0 通过率验收。
- 后续已确认 `OPA228_P1.pdf` 映射到 `gs-003`，下一步阻塞转为补齐 10-20 个 manifest-matched PDF 和真实链路/人工质量验收。
- 在 runnable sample 变为 1+ 之前，不建议开始 `document-ir-layout-risk-pass` 或 `word-renderer-editable-output-pass`。
