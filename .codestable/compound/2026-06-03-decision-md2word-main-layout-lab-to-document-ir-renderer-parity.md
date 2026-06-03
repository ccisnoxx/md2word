---
doc_type: decision
slug: md2word-main-layout-lab-to-document-ir-renderer-parity
category: convention
status: active
summary: Word 排版问题先在 md2word_main 作为 layout lab 调试并形成可观察策略，md2word 只把稳定且可由 DocumentIR 驱动的策略迁移到 DocumentIR renderer 生产链路。
created: "2026-06-03"
tags: [md2word-main, document-ir, renderer, docx, golden-sample, parity]
related_feature: 2026-06-03-word-renderer-editable-output-pass
related_requirement: fastapi-backend-productization
---

# md2word_main layout lab 到 DocumentIR renderer 接入规约

## 决定

以后处理 Word 排版质量问题时，`/Users/sc/PycharmProjects/PythonProject/md2word_main` 作为 layout lab 和 reference runtime；`/Users/sc/PycharmProjects/md2word` 作为后端生产链路，只迁移稳定、可由 DocumentIR 当前字段驱动的策略到 `app/services/renderer`。

生产验收必须落在 `md2word` 的 `document_jobs -> DocumentIR -> app/services/renderer -> generated Word artifact` 链路，不能只看 `md2word_main` sandbox DOCX。

## 背景

4 个 Golden Sample 的 live regression 已证明 API / Worker / MinerU / DocumentIR / DOCX 下载主链路可以跑通，但人工质量仍暴露 heading、真实 Word list、caption/table 顺序、formula cleanup、TableContent / TableNote 和宽表/长表版面等问题。

这些问题在 `md2word_main` 中更适合本地调试：它可以直接用 Golden Sample 快速生成 DOCX、渲染页面并观察 Word 排版效果。`md2word` 是后端项目，线上真实路径使用 `DocumentIRWordRenderer`，如果只把 `md2word_main` 调好但不迁移到 `app/services/renderer`，问题会继续表现为 `pipeline-parity-gap`。

## 标准工作流

1. 在 `md2word_main` 用 4 个 Golden Sample 先做本地排版调试。
2. 形成可观察策略，至少覆盖 heading style、真实 Word list、caption-before-table、formula cleanup、table note/style、wide/long table。
3. 在 `md2word` 中做 parity mapping，判断每个策略是直接迁移、局部迁移还是暂不迁移。
4. 只迁移能由 DocumentIR 当前字段稳定驱动的策略到 `app/services/renderer`。
5. 迁移后必须用 `document_jobs` 回归验证 generated Word artifact，不只测 `md2word_main`、sandbox 输出或 `app/conversion/runtime` 单元。

## 生产验收口径

接入 `md2word` 时，验收标准必须检查生产链路生成的 DOCX OOXML：

- heading：`w:pStyle` 是真实 Word heading 或配置指定 named style。
- list：段落有 `w:numPr`，不能只靠手写 `• ` 前缀。
- formula / special symbols：常见 LaTeX 残留被清理，必要时有 `w:vertAlign` 表达上下标。
- caption/table：caption 在 table XML 前，table note / footnote 在 table XML 后。
- table style：TableContent / TableNote 或等价配置实际落到 generated Word。
- artifact：证据来自 `document_jobs` generated Word artifact。

## 禁止事项

- 不把 `md2word_main` 整包复制到 `md2word`。
- 不把 `app/conversion/runtime` 挂成后端线上第二套渲染入口。
- 不把 `md2word_main` sandbox DOCX 当作 `md2word` production acceptance。
- 不在 renderer 中凭空猜 DocumentIR 没有表达的 layout facts；缺事实时先回到 DocumentIR / layout feature。

## 考虑过的替代方案

- 直接在 `md2word` 后端里盲调排版：调试反馈慢，容易把生产链路变成实验场，且不利于观察 Word 版面细节。
- 整包复制 `md2word_main` 到 `md2word`：会制造第二套 runtime 和边界混乱，后续 API / Worker / DocumentIR 回归仍可能不覆盖。
- 只维护 sandbox 质量：能提升本地输出，但无法保证线上 `document_jobs` 用户拿到同等质量。

## 后果与约束

- 后续涉及 Word 排版质量的 feature design 必须先读本决策，并在 design / checklist 中写清楚 layout lab 证据如何迁移到 DocumentIR renderer。
- implementation 阶段应优先在 `app/services/renderer` 接入稳定策略，而不是绕回 legacy runtime 入口。
- acceptance 阶段必须引用 document_jobs generated Word artifact 的 OOXML 证据。

## 相关文档

- `.codestable/features/2026-06-03-golden-sample-live-regression-scale-up/failure-classification.md`
- `.codestable/features/2026-06-03-document-ir-layout-risk-pass/document-ir-layout-risk-pass-acceptance.md`
- `.codestable/features/2026-06-03-word-renderer-editable-output-pass/word-renderer-editable-output-pass-design.md`
- `.codestable/features/2026-06-03-word-renderer-editable-output-pass/word-renderer-editable-output-pass-parity-mapping.md`
- `docs/testing/pdf-to-word-gs-003-quality-triage.md`
