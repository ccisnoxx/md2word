---
doc_type: roadmap
slug: pdf-to-word-delivery-hardening
status: active
created: 2026-06-02
last_reviewed: 2026-06-03
tags: [pdf, word, delivery, golden-sample, document-jobs, quality]
related_requirements: [fastapi-backend-productization]
related_architecture: [architecture-index, backend-fastapi-service, app-conversion-internal]
---

# PDF -> Word 主链路交付硬化路线

## 1. 背景

当前仓库已经具备 `document_jobs` 业务主链路、前端工作台、DocumentIR v2、Word renderer、Golden Sample 清单和批量回归脚本。但规划层被删除，部分 docs 与代码事实不同步，Golden Sample 报告仍按“真实 PDF 数 0”描述，而仓库里已经出现一个未纳入 manifest 的 PDF。

未来 2-4 周目标不是继续扩新后台功能，而是把 PDF -> Word 主链路变成可验证、可排障、可交付的稳定基线。

## 2. 范围与明确不做

本 roadmap 覆盖：

- 恢复并校准 `.codestable/roadmap/` 规划层，让后续 feature design 有入口。
- 对齐当前代码、docs、architecture、requirements、roadmap 状态。
- 建立 Golden Sample 质量基线：样本清单、真实 PDF、回归报告和人工验收口径一致。
- 基于 Golden Sample 失败分类，定向硬化 DocumentIR / renderer / worker 主链路。
- 只围绕 `direct_pdf_to_word` P0 默认路径；`en2zh_pdf_to_word` 只保留实验和回归风险说明。

明确不做：

- 不新增后台管理功能。
- 不扩模板、术语、翻译配置 UI。
- 不做完整多租户、SSO、审计查询 UI。
- 不做在线 Word 校对工作台。
- 不承诺扫描件 OCR 支持。
- 不把缺少业务真实样本伪装成 Golden Sample 通过。

## 3. 模块拆分

```text
pdf-to-word-delivery-hardening
├── roadmap-state：CodeStable roadmap / feature 规划状态对齐
├── golden-sample-baseline：样本、manifest、脚本、报告和人工验收口径
├── document-job-pipeline：上传、建任务、Worker、下载的 P0 主链路验证
├── document-ir-layout：MinerU -> DocumentIR v2 的布局事实和质量标记
├── word-renderer-quality：标题、正文、表格、图片、双栏和可编辑 DOCX 输出
└── delivery-docs：联调指南、验收报告和后续 feature 输入
```

## 4. 接口契约

### 4.1 规划层契约

- `.codestable/roadmap/{slug}/{slug}-roadmap.md` 是大需求规划主文档。
- `.codestable/roadmap/{slug}/{slug}-items.yaml` 是 roadmap 与 feature design 的唯一接口。
- 历史 completed roadmap 只用于事实追踪，不继续追加新后台功能。
- 当前 active roadmap 只维护 2-4 周 PDF -> Word 交付硬化条目。

### 4.2 Golden Sample 契约

- `tests/fixtures/golden_samples/manifest.yaml` 是样本清单真源。
- 只统计 manifest 中 enabled 且真实存在的 PDF。
- 正式 P0 目标仍是 10-20 份样本核心链路成功率 `>= 90%`，且成功样本 Word 可打开、可编辑。
- manifest 外 PDF 不计入正式通过率；要使用必须先纳入 manifest 或明确标为临时 smoke。

### 4.3 主链路契约

- P0 默认路径：`/api/v1/files/upload-url` -> `PUT /api/v1/files/{file_id}/content` -> `POST /api/v1/document-jobs` with `mode=direct_pdf_to_word` -> `GET /api/v1/document-jobs/{job_id}` -> `GET /download-url`。
- Worker 失败必须落 `failed_stage`、`error_code`、`error_message` 和事件。
- 成功结果必须是可打开 `.docx` 包；人工验收再判断结构、表格、图片和可编辑性。

## 5. 子 feature 清单

| slug | 状态 | 说明 |
|---|---|---|
| roadmap-state-reconciliation | done | 恢复/校准 roadmap，补当前 active 交付路线，写 feature design 输入 |
| golden-sample-quality-baseline | done | 对齐 manifest、真实 PDF、回归脚本和验收报告，建立第一版质量基线 |
| document-job-smoke-stability | done | 用 gs-003 / OPA228_P1.pdf 验证 hostdzire 真实 API + worker + MinerU + 下载主链路 smoke |
| golden-sample-live-regression-scale-up | done | 已完成当前 4 个 runnable 样本 live regression 与 acceptance：主链路 4/4 succeeded，DOCX 4/4 openable；人工质量 0/4 P0 pass，失败分类为 `pipeline-parity-gap` |
| document-ir-layout-risk-pass | done | 已完成 acceptance 闭环；DocumentIR v2 已接入 orientation、column_hint、wide table、caption/footnote binding 和 continuation facts，document_jobs metadata 可暴露 layout flags |
| word-renderer-editable-output-pass | done | 已接入 heading/list/formula/caption/table annotation 的可编辑 OOXML 语义，并补 document_jobs generated Word 回归 |
| delivery-acceptance-report | done | 汇总发布前验证、剩余风险、merge 建议和 deploy 前人工 gate |

最小闭环：`golden-sample-quality-baseline` 完成后，系统至少能明确报告当前可运行样本数、成功率、失败阶段和人工验收状态，不再出现 docs 与样本事实冲突。

## 6. 排期

建议 2-4 周节奏：

- 第 1 批：`roadmap-state-reconciliation`。
- 第 2 批：`golden-sample-quality-baseline`。
- 第 3 批：`document-job-smoke-stability`。
- 第 4 批：`golden-sample-live-regression-scale-up`，先复跑当前正式样本并形成失败分类。
- 第 5 批：`document-ir-layout-risk-pass`，按真实失败分类收敛 DocumentIR v2 layout 风险。
- 第 6 批：`word-renderer-editable-output-pass`，在 IR 输入稳定后修 renderer 可编辑输出质量。
- 收尾：`delivery-acceptance-report`。

## 7. 观察项

- `frontend/` 已存在工作台和配置管理页面；本路线不继续扩后台 UI。
- `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` 当前 blocked 判断仍成立，但 PDF 数量描述需要跟 manifest 事实重新对齐。
- `tests/fixtures/golden_samples/pdfs/OPA228_P1.pdf`、`OPA228_P2.pdf`、`OPA228_P6.pdf` 和 `OPA228_P7.pdf` 已映射到 `manifest.yaml`，当前正式 runnable sample 为 4。
- hostdzire 真实部署链路已在 `gs-003/004/006/008` 跑通；上传、建任务、Worker、MinerU、DocumentIR、Word 渲染和下载均未发现卡点。
- 当前 4 个 runnable 样本均可生成可打开 DOCX，但人工质量 0/4 P0 pass；`document-ir-layout-risk-pass` 已把 orientation、column_hint、wide table、caption/footnote binding 和 continuation facts 接入 API DocumentIR renderer 链路，`word-renderer-editable-output-pass` 已把 heading/list/formula、caption-before-table 和表格 annotation 的可编辑 OOXML 语义接入 generated Word。正式 P0 仍缺 10-20 份 manifest-matched PDF、真实复跑、人工质量验收和后续视觉版面修复。
- 本轮失败分类为 `pipeline-parity-gap`：`md2word_main` / `app/conversion/runtime` 已有部分修复，但 `document_jobs -> DocumentIR -> app/services/renderer` 线上链路未接入。
- 正式 P0 通过还需要补齐 10-20 份 manifest-matched PDF，并让成功样本通过人工质量验收。
- `.codestable/features/` 已开始承载本路线的 design / checklist / acceptance 产物，后续 feature 继续从 roadmap item 起头。
- 第二轮 feature design 启动前 gate：architecture / requirements 必须同步 `document_jobs` 主链路现状；API 参考需补 `/files` 与 `/document-jobs`；`delivery-acceptance-report` 需修正工作区状态；attention.md 需记录线上 Golden Sample 复跑和部署入口核对注意事项。

## 8. 变更日志

- 2026-06-03：`word-renderer-editable-output-pass` 完成 acceptance 闭环并回写为 done；renderer generated Word 已覆盖 heading named style、真实 list numbering、formula/table note rich text normalization、caption-before-table 和 TableNote 顺序语义，剩余 P0 风险回到样本规模、真实复跑、人工质量和视觉版面。
- 2026-06-03：`document-ir-layout-risk-pass` 完成 acceptance 闭环并回写为 done；DocumentIR v2 layout facts、renderer layout plan consumption 和 document_jobs metadata 回归已落地，后续进入 `word-renderer-editable-output-pass`。
- 2026-06-03：`golden-sample-live-regression-scale-up` 完成 acceptance 闭环并回写为 done：hostdzire 真实回归 `gs-003/004/006/008` 主链路 4/4 succeeded、DOCX 4/4 openable，但人工质量 0/4 P0 pass；核心分类为 `pipeline-parity-gap`，后续 `document-ir-layout-risk-pass` 和 `word-renderer-editable-output-pass` 需优先做 legacy runtime 到 DocumentIR renderer 的 parity 判断与迁移。
- 2026-06-03：完成 `delivery-acceptance-report` 发布验收；后端 release check、前端 build、direct/en2zh smoke、失败分类和 DocumentIR v2 metadata 验证通过，建议进入 merge；deploy 前保留真实环境人工 gate。
- 2026-06-03：确认第二轮只推进 `golden-sample-live-regression-scale-up`、`document-ir-layout-risk-pass`、`word-renderer-editable-output-pass`；进入 feature design 前先完成现状文档与 API 参考 gate。
- 2026-06-03：merge 前范围确认，`resources/term_rules/term_rules.v2.yaml` 纳入发布，`OPA228_P2/P6/P7.pdf` 映射为 `gs-004/006/008`，manifest 外 PDF 清零。
- 2026-06-02：`document-job-smoke-stability` 完成 acceptance；hostdzire 真实链路执行 `gs-003 / OPA228_P1.pdf` 成功，`job_id=docjob_d4c4101592ad`，Word 可打开。
- 2026-06-02：`roadmap-state-reconciliation` 完成 acceptance 收尾，历史 roadmap 断链修复，当前 active 交付硬化路线进入 Golden Sample 基线阶段。
- 2026-06-02：`golden-sample-quality-baseline` 完成 acceptance，回归报告可区分 manifest-matched、missing 和 orphan PDF；baseline 验收时正式 runnable sample 为 0。
- 2026-06-02：将 `OPA228_P1.pdf` 映射到 `gs-003`，当前正式 runnable sample 从 0 增加到 1。
- 2026-06-02：启动 `golden-sample-quality-baseline` design，当前重点是 manifest-matched / missing / orphan PDF 事实对账。
- 2026-06-02：创建当前 active 交付硬化 roadmap，并将 `roadmap-state-reconciliation` 设为第一条 in-progress feature。
