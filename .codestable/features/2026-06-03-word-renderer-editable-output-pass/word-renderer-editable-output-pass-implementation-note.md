---
doc_type: feature-implementation-note
feature: 2026-06-03-word-renderer-editable-output-pass
status: current
summary: renderer editable output pass 的实现边界和 acceptance 回写输入。
---

# word-renderer-editable-output-pass implementation note

## 已接入范围

- Heading：DocumentIR heading block 会写入真实 Word paragraph style。默认映射为 `Heading 1/2/3`；模板配置可通过 `word_style_name` 覆盖。
- List：DocumentIR list block 会生成真实 Word bullet numbering，OOXML 中有 `w:numPr`，可见文本不再依赖手写 `• ` 前缀。
- Formula / rich text：formula block、table cell 和 table note 会清理常见 TeX 残留，并通过 `<sub>/<sup>` 路径输出 `w:vertAlign`。
- Table annotation：table caption 在 editable table 前渲染并设置 `keep_with_next`；table footnote / note 在 table 后渲染并走 `table_note` 配置。
- Regression：renderer focused test 覆盖 heading/list/formula/table OOXML；document_jobs eager worker test 覆盖生成的 Word artifact OOXML。

## 未接入范围

- 未改前端、HTTP API、Golden Sample manifest 或真实部署配置。
- 未把 `app/conversion/runtime` 作为线上第二渲染入口。
- 未实现完整 LaTeX parser、OMML 公式对象、TOC leader、完整 landscape section、长表分页视觉还原或 10-20 样本扩容。
- 未在 implementation 阶段更新 architecture / requirement / roadmap done 状态；这些留给 `cs-feat-accept` 对照实际验收结果回写。

## acceptance 回写输入

- `.codestable/architecture/ARCHITECTURE.md`：可把 renderer editable output 从“未接入”更新为“已覆盖 heading/list/formula/table annotation 的 OOXML 语义”，同时保留视觉版面与样本规模阻塞。
- `.codestable/architecture/backend-fastapi-service.md`：可补充 document_jobs 生成 Word artifact 已具备 renderer semantic pass。
- `.codestable/requirements/fastapi-backend-productization.md`：可更新 Golden Sample blocked 边界，说明主链路仍需正式样本规模和人工质量验收。
- `.codestable/roadmap/pdf-to-word-delivery-hardening/`：只有 acceptance 通过后再把 `word-renderer-editable-output-pass` 从 `in-progress` 改为 `done`。
