# .codestable/features/2026-06-03-document-ir-layout-risk-pass/document-ir-layout-risk-pass-implementation.md: document-ir-layout-risk-pass 实现记录。
---
doc_type: feature-evidence
feature: 2026-06-03-document-ir-layout-risk-pass
slug: document-ir-layout-risk-pass-implementation
status: completed
created_at: 2026-06-03
tags: [document-ir, layout, renderer, document-jobs, implementation]
---

# document-ir-layout-risk-pass implementation

## 实现结论

本轮只接入 DocumentIR layout facts 与 renderer layout plan consumption，不处理 heading/list/formula、caption-before-table 或表格 Word 样式质量。

已落地：

- `DocumentIRPage.metadata.orientation`：由 page size / bbox extent 推断 `portrait` 或 `landscape`。
- `DocumentIRBlockLayout.column_hint`：由 raw hint 或 bbox + page width 推断 `left` / `right` / `wide`。
- `DocumentIR.quality_flags`：记录 `layout_two_column_candidate:*`、`layout_wide_table:*`、`layout_caption_binding:*`、`layout_footnote_binding:*`、`table_continuation:*` 等非敏感诊断。
- table placeholder continuation：连续 `table_placeholder` 高度合并到前一张真实表的 `continuation_heights`，不把 placeholder 输出为 DocumentIR block。
- renderer layout plan：优先消费 `column_hint`，缺失时继续按 bbox fallback；稳定左右栏 hint 可形成 two-column band。
- document_jobs metadata：DocumentIR artifact 保存 `quality_flags`，generated Word artifact / 渲染事件保存 `layout_quality_flags`。

## 修改面

- `app/services/document_ir/layout_signals.py`
- `app/services/document_ir/mineru_converter.py`
- `app/services/renderer/layout_plan.py`
- `app/services/renderer/word_renderer.py`
- `app/domains/document_jobs/execution.py`
- `tests/test_document_ir_layout_contract.py`
- `tests/test_document_ir_mineru_converter_layout.py`
- `tests/test_document_ir_word_renderer_layout.py`
- `tests/test_fastapi_jobs_backend.py`

## 验证

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest \
  tests.test_document_ir_layout_contract \
  tests.test_document_ir_mineru_converter_layout \
  tests.test_document_ir_word_renderer_layout \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets
```

结果：`Ran 15 tests in 0.268s`，`OK`。

备注：当前 conda env 没有安装 `pytest`，`python -m pytest ...` 返回 `No module named pytest`，因此使用项目现有 unittest 路径验证。

## 保留边界

- 不改前端、不扩 HTTP API、不改 Golden Sample manifest。
- 不修 heading -> Word heading、真实 Word numbering、formula TeX 清理。
- 不修 caption-before-table、TableContent/TableNote/Caption 样式或长表分页渲染质量。
- 不写入凭证、token、客户文件全文或完整解析文本。
