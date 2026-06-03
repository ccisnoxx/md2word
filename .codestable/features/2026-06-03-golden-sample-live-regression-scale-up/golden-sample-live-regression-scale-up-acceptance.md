---
doc_type: feature-acceptance
feature: 2026-06-03-golden-sample-live-regression-scale-up
status: completed
accepted_at: 2026-06-03
tags: [golden-sample, acceptance, roadmap, pipeline-parity-gap]
roadmap: pdf-to-word-delivery-hardening
roadmap_item: golden-sample-live-regression-scale-up
---

# golden-sample-live-regression-scale-up 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-03
> 关联方案 doc：`.codestable/features/2026-06-03-golden-sample-live-regression-scale-up/golden-sample-live-regression-scale-up-design.md`

## 1. 接口契约核对

对照方案第 2.1 节，本 feature 只新增文档层“分类表”概念，不新增代码类型或 API 合同。

**接口示例逐项核对**

- [x] `gs-006 / OPA228_P6.pdf` 示例：`chain_result=succeeded`、`docx_openable=true`、`failure_bucket=manual_quality`、证据路径齐全。
  - 实际证据：`live-regression-run.md` 记录 `gs-006` job `docjob_8f76657979b4` succeeded 且 DOCX openable；`manual-quality-records` 记录 P0 质量未通过；`failure-classification.md` 路由到 `pipeline-parity-gap` + `document-ir-layout-risk` + `word-renderer-editable-output`。

**名词层“现状 -> 变化”逐项核对**

- [x] `RegressionConfig` / `SampleResult` / `SampleInventory`：未改代码；真实运行报告沿用脚本已有字段。
- [x] “分类表”：已落在 `.codestable/features/2026-06-03-golden-sample-live-regression-scale-up/failure-classification.md`，逐样本包含质量问题、failure bucket 和 next feature。
- [x] “人工质量记录”：已落在 `docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md`，覆盖 4 个成功样本。

**流程图核对**

- [x] gate 复核 -> 真实回归 -> 读取报告 -> 人工记录 -> 失败分类 -> 文档/roadmap 回填均有对应 evidence 文件。

## 2. 行为与决策核对

**需求摘要逐项验证**

- [x] 当前 4 个正式 PDF 均被真实回归尝试执行。
  - 证据：`gs-003/004/006/008` 在 hostdzire 批次 `20260603T070724Z` 中 4/4 succeeded，DOCX 4/4 openable。
- [x] 回归报告已回填 Golden Sample 验收报告。
  - 证据：`docs/testing/pdf-to-word-golden-sample-acceptance-report.md` 已从 1/1 smoke 更新为 4/4 live regression，并保留 blocked 判定。
- [x] 每个成功样本都有人工质量记录。
  - 证据：`docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md` 覆盖 Word 可打开、可编辑性、标题/列表、表格、图片/figure、双栏/宽表和公式/符号。
- [x] 已形成下一步分类表。
  - 证据：`failure-classification.md` 明确 `pipeline-parity-gap`，并路由到 `document-ir-layout-risk-pass` 和 `word-renderer-editable-output-pass`。

**明确不做逐项核对**

- [x] 未修改 `scripts/ops/run_golden_sample_regression.py`。
- [x] 未修 DocumentIR layout、renderer、数学符号、表格 caption、双栏或列表语义。
- [x] 未扩前端工作台、未改 API、未改部署配置。
- [x] 未把 4 个样本成功声明为 P0 正式达标。
- [x] 未把凭证、token、客户文件正文或完整解析文本写入仓库。

**关键决策落地**

- [x] 主链路成功和 P0 人工质量分开表达：4/4 succeeded，但 0/4 P0 pass。
- [x] 后续 feature 选择以分类表为准，不凭单个 gs-003 泛化。
- [x] `pipeline-parity-gap` 已成为后续两个 feature 的共同前置判断。

**挂载点反向核对**

- [x] `.codestable/features/2026-06-03-golden-sample-live-regression-scale-up/`：design、checklist、environment、live run、manual/failure/backfill/acceptance 证据齐全。
- [x] `docs/testing/pdf-to-word-golden-sample-acceptance-report.md`：已包含本轮 4 样本回归和分类结论。
- [x] `docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md`：已包含 4 样本人工质量记录。
- [x] `.codestable/roadmap/pdf-to-word-delivery-hardening/`：items.yaml 和 roadmap 主文档已同步。

拔除沙盘推演：若移除上述挂载点，本 feature 的回归证据、分类表、报告口径和 roadmap done 状态均会消失或回退；未发现方案外业务代码残留。

## 3. 验收场景核对

- [x] 读取 `tests/fixtures/golden_samples/manifest.yaml`
  - 结果：`tests.test_golden_sample_manifest` 6 条通过；当前 runnable 样本仍为 `gs-003/004/006/008`，8 个 manifest 样本仍 `missing_pdf`。
- [x] 运行真实 Golden Sample 回归
  - 结果：hostdzire 批次 `20260603T070724Z`，4/4 succeeded，0 failed，DOCX 4/4 openable；报告脱敏扫描 clean。
- [x] 打开每个成功样本 DOCX
  - 结果：4 个样本均有人工质量记录；均条件通过主链路，但 0/4 通过 P0 版面与语义质量。
- [x] 生成分类表
  - 结果：链路失败为 0；质量缺口归入 `pipeline-parity-gap`、`document-ir-layout-risk`、`word-renderer-editable-output` 和样本扩容缺口。
- [x] 打开 Golden Sample 验收报告
  - 结果：报告已反映 4 个正式样本最新执行和人工质量状态，不再停留在 1/1 smoke。
- [x] 反向核对
  - 结果：未修改 DocumentIR、renderer、前端、后端 API 或部署配置。

## 4. 术语一致性

- `真实回归`：evidence 与报告统一使用 hostdzire 真实 API / Worker / MinerU，不再混同 dummy inventory smoke。
- `失败分类`：统一落为 `pipeline-parity-gap` + 后续 `document-ir-layout-risk-pass` / `word-renderer-editable-output-pass` 路由。
- `人工质量记录`：统一表达为主链路条件通过但 P0 质量未通过。
- `样本扩容缺口`：统一表达为 12 个 manifest 样本中 8 个 `missing_pdf`，不计入本轮 4 runnable 样本链路失败。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`
  - 已更新 Golden Sample 当前状态：`gs-003/004/006/008` 主链路 4/4 succeeded，DOCX 4/4 openable；P0 仍 blocked，因为样本规模不足且人工质量 0/4 P0 pass。
  - 已补入 `pipeline-parity-gap`：legacy runtime 策略未接入 API DocumentIR renderer。
- [x] `.codestable/architecture/backend-fastapi-service.md`
  - 不需要更新。该文档描述 API/Worker/DocumentIR 主链路结构，本 feature 未改变结构。
- [x] `.codestable/architecture/conversion-flow.md` / `.codestable/architecture/app-conversion-internal.md`
  - 不需要更新。本 feature 未改变 conversion runtime；只把 legacy runtime 作为后续 feature 的迁移输入。

## 6. requirement 回写

- [x] `.codestable/requirements/fastapi-backend-productization.md`
  - 已更新 Golden Sample blocked 边界：4 个正式匹配 PDF 已真实链路跑通且 DOCX 可打开，但样本规模和人工质量仍阻塞 P0。
  - 已补入 `pipeline-parity-gap`，避免 requirement 继续保留“只有 1 个跑过真实链路”的旧口径。

## 7. roadmap 回写

- [x] `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-items.yaml`
  - `golden-sample-live-regression-scale-up` 已从 `in-progress` 改为 `done`。
  - 后续 `document-ir-layout-risk-pass` notes 保持 legacy layout parity 判断优先。
  - 后续 `word-renderer-editable-output-pass` notes 保持 renderer 策略同步 + document_jobs 回归优先。
- [x] `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-roadmap.md`
  - 子 feature 清单已同步为 `done`。
  - 变更日志已记录 acceptance 闭环完成。

## 8. attention.md 候选盘点

- [x] 无新增候选。

本 feature 再次验证了“线上 Golden Sample 复跑不能假设部署容器内已有 `tests/fixtures/golden_samples/`”，但该注意事项已存在于 `.codestable/attention.md`，无需重复追加。

## 9. 遗留

后续 feature 输入：

- `document-ir-layout-risk-pass`：先判断 `app/conversion/runtime` / `md2word_main` 的 page orientation、two-column grouping、caption/figure binding、wide/long table continuation 等策略哪些可迁移到 DocumentIR 链路，哪些必须补 IR layout facts。
- `word-renderer-editable-output-pass`：优先同步 `app/conversion/runtime` 的 heading/list/formula/caption/table 策略到 `app/services/renderer`，并新增或更新 `document_jobs` 回归用例。

已知限制：

- 当前 runnable 样本只有 4 个，仍低于 10-20 份 P0 目标。
- 4 个样本均未通过 P0 人工版面与语义质量。
- `md2word_main/out` 当前未找到 `OPA228_P1_standalone.docx`，不能声称 P1 legacy baseline 已完全修复。

## 验证记录

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_golden_sample_manifest`：通过，6 tests OK。
- YAML / frontmatter 解析：通过。
- 敏感信息扫描：通过，无 OpenSSH 私钥、JWT、Authorization bearer、明文 password/token 命中。
- git diff 范围：仅 `.codestable/` 与 `docs/testing/` 文档；未改业务代码。
