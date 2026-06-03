---
doc_type: feature-acceptance
feature: 2026-06-03-document-ir-layout-risk-pass
status: accepted
accepted_at: 2026-06-03
tags: [document-ir, layout, renderer, document-jobs, acceptance]
roadmap: pdf-to-word-delivery-hardening
roadmap_item: document-ir-layout-risk-pass
requirement: fastapi-backend-productization
---

# document-ir-layout-risk-pass 验收报告

> 阶段：阶段 3（验收闭环）  
> 验收日期：2026-06-03  
> 关联方案 doc：`.codestable/features/2026-06-03-document-ir-layout-risk-pass/document-ir-layout-risk-pass-design.md`

## 1. 接口契约核对

对照方案第 2.1 节，本 feature 不扩 HTTP API，不新增前端表面，只标准化 DocumentIR v2 layout facts 和 document_jobs artifact metadata。

**接口示例逐项核对**

- [x] `DocumentIRPage.metadata.orientation`：方案示例要求 page metadata 写入 `portrait` / `landscape`。
  - 代码实际行为：`app/services/document_ir/layout_signals.py::build_pages()` 由 page size / bbox extent 推断 orientation。
  - 测试证据：`tests/test_document_ir_layout_contract.py` round-trip 覆盖 `portrait`；`tests/test_document_ir_mineru_converter_layout.py` 覆盖 `portrait` 与 `landscape`。
- [x] `DocumentIRBlockLayout.column_hint`：方案示例要求 block layout 写入 `left` / `right` / `wide`。
  - 代码实际行为：`build_block_layout()` 优先读取 raw `column_hint`，否则用 bbox + page width 推断。
  - 测试证据：converter tests 覆盖 left/right/wide；renderer tests 覆盖 plan 和 two-column cell split 优先消费 hint。
- [x] `continuation_heights`：方案示例要求 table continuation 可序列化和可追踪。
  - 代码实际行为：保留 raw continuation heights，并由 `merge_table_placeholder_continuations()` 合并 table placeholder 高度。
  - 测试证据：`test_convert_zip_merges_table_placeholder_continuation_and_landscape_orientation`。
- [x] `quality_flags` / `layout_quality_flags`：方案要求 layout 风险可检索且不含敏感正文。
  - 代码实际行为：DocumentIR artifact metadata 保存 `quality_flags`；generated Word artifact / rendering events 保存 `layout_quality_flags`。
  - 测试证据：`tests/test_fastapi_jobs_backend.py::test_document_job_worker_saves_mineru_raw_ir_and_image_assets`。

**名词层“现状 -> 变化”逐项核对**

- [x] `DocumentIRPage`：未改 Pydantic 模型字段，使用既有 `metadata` 承载 `orientation`，符合“优先用 metadata，不扩大模型”的约束。
- [x] `DocumentIRBlockLayout`：既有 `column_hint` 字段从未实际写入变为 converter 实际输出。
- [x] `DocumentIRBlock`：既有 `captions` / `footnotes` 保留，用 binding flags 增强可观察性，不改变 Word 输出顺序。
- [x] `DocumentIR.quality_flags`：新增非敏感 layout flags；未写客户全文或凭证。
- [x] `LayoutPlan`：仍是不持久化运行时对象；新增的是对 `column_hint` 的消费。

**流程图核对**

- [x] Golden Sample failure classification -> parity audit：`.codestable/features/2026-06-03-document-ir-layout-risk-pass/layout-parity-audit.md`。
- [x] MinerU raw blocks -> DocumentIR layout facts：`MinerUToDocumentIRService._convert_blocks()` 调用 `layout_signals` helpers。
- [x] DocumentIR JSON artifact + quality flags：`DocumentJobExecutionService._document_ir_layout_metadata()`。
- [x] renderer layout plan consumes facts first：`app/services/renderer/layout_plan.py::_classify_body_block()`。
- [x] document_jobs regression asserts IR/plan/OOXML evidence：`test_document_job_worker_saves_mineru_raw_ir_and_image_assets` 检查 IR payload、Word metadata 和 DOCX zip。

## 2. 行为与决策核对

**需求摘要逐项验证**

- [x] `gs-003/006/008` layout 风险已分类。
  - 证据：`layout-parity-audit.md` 对双栏、caption/table/figure、wide table、continuation 分别归入 IR fact 或后续 renderer 样式策略。
- [x] 至少一组 P0 layout facts 已迁移或补齐。
  - 证据：orientation、column_hint、wide table flags、caption/footnote binding flags、table continuation 已接入 converter 和 document_jobs metadata。
- [x] DocumentIR v2 合同保持兼容。
  - 证据：v1 payload 默认布局字段为空的测试仍通过；v2 round-trip 覆盖新增事实。
- [x] document_jobs 回归不只测 sandbox。
  - 证据：eager worker 测试从 PDF upload -> document job -> IR artifact -> Word artifact 完成断言。

**明确不做逐项核对**

- [x] 未重写整套 layout algorithm，未复制 `page_layout_runtime.py` 为第二套大渲染器。
- [x] 未处理 heading 样式、真实 Word numbering、formula/rich text TeX 清理。
- [x] 未完成 caption-before-table、TableContent/TableNote/Caption Word 样式质量。
- [x] 未改前端、未扩 HTTP API、未新增后台管理功能。
- [x] 未改 Golden Sample manifest，未把 4 个样本声明为 P0 通过。

**关键决策落地**

- [x] 计算留在 `layout_signals.py`，converter 只编排调用。
- [x] IR facts 只表达来源布局事实，不表达最终 Word 样式决策。
- [x] renderer layout plan 优先消费 typed `column_hint`，缺失时保持 bbox fallback。
- [x] table caption/footnote 关系只保证可观察，不改变 Word 输出顺序。

**挂载点反向核对**

- [x] `.codestable/features/2026-06-03-document-ir-layout-risk-pass/`：design、checklist、parity audit、implementation、acceptance 产物齐全。
- [x] DocumentIR layout fact / metadata / quality flag 挂载点：`layout_signals.py`、`mineru_converter.py`、layout contract tests。
- [x] renderer layout plan 挂载点：`layout_plan.py`、`word_renderer.py`、renderer layout tests。
- [x] document_jobs metadata 挂载点：`execution.py`、FastAPI jobs backend 回归。
- [x] roadmap 挂载点：items.yaml 和 roadmap 主文档已由 `in-progress` 回写为 `done`。

反向核查：当前 HEAD 改动文件清单不包含 `frontend/`、API router、Golden Sample manifest 或 `app/conversion/runtime`。方案外出现的 heading/formula/list 命中均为既有代码或设计/证据中的“不做”说明。

拔除沙盘推演：按挂载点逆向移除 feature 目录、`layout_signals` 新增 helpers、converter 调用、renderer hint consumption、document_jobs `layout_quality_flags` 和相关 tests 后，本 feature 的 runtime 行为和证据会回退；未发现清单外残留。

## 3. 验收场景核对

- [x] **S1：读取 failure classification 和人工质量记录**
  - 结果：`layout-parity-audit.md` 明确 `gs-003/006/008` layout 风险；heading/list/formula 和 caption-before-table 留给后续 renderer feature。
- [x] **S2：构造 v2 DocumentIR payload round-trip**
  - 结果：orientation、column_hint、continuation、caption/footnote、quality flags 可序列化；v1 payload 默认行为不变。
  - 证据：`tests.test_document_ir_layout_contract`。
- [x] **S3：MinerU converter 处理 bbox/page_size/caption/continuation fake zip**
  - 结果：输出 page orientation、left/right/wide column_hint、caption/footnote、continuation 和非敏感 quality flags。
  - 证据：`tests.test_document_ir_mineru_converter_layout`。
- [x] **S4：renderer layout plan 处理带 column_hint 的 DocumentIR**
  - 结果：优先按 `column_hint` 形成 two-column regions；缺字段仍可 fallback 到 bbox 推断。
  - 证据：`tests.test_document_ir_word_renderer_layout`。
- [x] **S5：document_jobs eager worker 回归**
  - 结果：保存的 `document_ir_v2.json`、generated Word metadata 和 events 暴露 layout facts / flags；DOCX 包可打开。
  - 证据：`tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets`。
- [x] **反向核对**
  - 结果：未改前端、不扩 API、不改 Golden Sample manifest、不修 heading/list/formula、不把 caption-before-table Word 输出质量算进本 feature。

验证命令：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_document_ir_layout_contract \
  tests.test_document_ir_mineru_converter_layout \
  tests.test_document_ir_word_renderer_layout \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets
```

结果：`Ran 15 tests in 0.267s`，`OK`。

## 4. 术语一致性

- `DocumentIR layout facts`：代码中落为 `DocumentIRPage.metadata.orientation`、`DocumentIRBlockLayout.column_hint`、`captions`、`footnotes`、`quality_flags`。
- `renderer layout plan`：仍由 `build_layout_plan()` 生成，不持久化；只消费 facts。
- `legacy layout runtime`：只作为 parity audit 参考，没有复制到 `app/services/renderer`。
- `pipeline-parity-gap`：Golden Sample 报告、roadmap、architecture、requirement 中均保留为当前 blocked 根因之一。
- 禁用范围术语：heading/list/formula、caption-before-table、TableContent/TableNote/Caption 只出现在“不做 / 后续 feature”语境中，未作为本 feature 实现目标。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`
  - 已补入 DocumentIR v2 layout facts：orientation、column_hint、continuation、caption / footnote binding、quality flags。
  - 已补入 document_jobs generated Word metadata 的 `layout_quality_flags`。
- [x] `.codestable/architecture/backend-fastapi-service.md`
  - acceptance 阶段补写 artifact metadata 诊断摘要：`document_ir` artifact 的 `quality_flags`，generated Word artifact / rendering events 的 `layout_quality_flags`。
- [x] `.codestable/architecture/app-conversion-internal.md`
  - 不需要更新。本 feature 未改 `app/conversion/runtime`，只迁移最小事实到 DocumentIR 链路；legacy runtime 仍作为后续 renderer 输出质量输入。

## 6. requirement 回写

- [x] `.codestable/requirements/fastapi-backend-productization.md`
  - 已补入 document_jobs 主链路 metadata 可追踪 DocumentIR layout facts 和 renderer layout flags。
  - 已更新 Golden Sample blocked 边界：layout facts 已接入，但 renderer 可编辑输出质量仍 blocked。

Requirement 已是 `current`，本次是边界刷新，不改变 pitch 或新增独立 requirement。

## 7. roadmap 回写

- [x] `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-items.yaml`
  - `document-ir-layout-risk-pass` 已由 `in-progress` 回写为 `done`。
  - notes 已记录本 feature 完成 acceptance，heading/list/formula、caption-before-table 和表格 Word 样式留给下一项。
- [x] `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-roadmap.md`
  - 子 feature 清单已同步为 `done`。
  - 变更日志已记录进入 `word-renderer-editable-output-pass`。

YAML 解析通过。

## 8. attention.md 候选盘点

- [x] 无新增候选。

本 feature 继续使用 `/Users/sc/miniconda3/envs/md2word/bin/python` 跑测试，该注意事项已在 `.codestable/attention.md` 中存在。`pytest` 在当前 env 不可用这一点已记录在 implementation evidence，但不是每个 feature 必然会踩的长期约束，暂不追加 attention。

## 9. 遗留

后续 feature 输入：

- `word-renderer-editable-output-pass`：把 `app/conversion/runtime` 的 heading/list/formula/caption/table 策略同步到 `app/services/renderer`。
- 回归必须覆盖 document_jobs 链路，检查 OOXML heading style、`w:numPr`、LaTeX 残留、caption/table 顺序，不能只测 md2word_main sandbox 输出。

已知限制：

- 本 feature 没有修 Word section landscape / page fit，只把 orientation 和 wide table 风险变成可观察 facts。
- caption / footnote binding 已在 IR 中可观察，但 caption-before-table 的 Word 输出仍未修。
- 长表 continuation fact 已接入，长表分页渲染质量仍留给后续 renderer feature。
- Golden Sample P0 仍 blocked：4 个 runnable 样本人工质量 0/4 pass，且样本规模仍低于 10-20 份目标。

## 验证记录

- `git status --short`：验收开始时工作区干净；当前仅 acceptance / roadmap / backend architecture 收尾文件有未提交改动。
- `git log --oneline -8`：HEAD 为 `591f71b`，用户已单独 push 实现代码。
- 目标 unittest：15 tests OK。
- YAML 解析：checklist 和 roadmap items 均通过。
- 敏感信息检查：实现 evidence 和 docs 未写入凭证、token、客户文件正文或完整解析文本。
