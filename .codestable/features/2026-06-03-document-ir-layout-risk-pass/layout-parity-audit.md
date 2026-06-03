---
doc_type: feature-evidence
feature: 2026-06-03-document-ir-layout-risk-pass
slug: layout-parity-audit
status: completed
created_at: 2026-06-03
tags: [document-ir, layout, parity-audit, pipeline-parity-gap]
---

# layout-parity-audit

## 结论

`document-ir-layout-risk-pass` 不从零重写 layout。当前先迁移最小 layout facts，使 API `document_jobs -> DocumentIR -> app/services/renderer` 链路能观察和消费 legacy runtime 已经存在的布局信号。

本轮进入实现的 layout facts：

- page orientation：由 page size / bbox extent 推断，写入 `DocumentIRPage.metadata.orientation`。
- block column hint：由 bbox + page width 推断 `left` / `right` / `wide`，写入 `DocumentIRBlockLayout.column_hint`。
- wide table risk：table 被判为 `wide` 时写入 `layout_wide_table:{block_id}`。
- table continuation：保留 raw `continuation_heights`，并补充 table placeholder 后续页高度的最小迁移。
- caption / footnote binding：继续保留 `captions` / `footnotes`；本 feature 只让关系可观察，不调整 Word 输出顺序。

不进入本 feature：

- heading -> Word heading、list -> Word numbering、formula TeX 清理。
- table caption-before-table、TableContent / TableNote / Caption Word 样式。
- 完整视觉版式重排或复制整套 `page_layout_runtime.py`。

## 逐样本分类

| sample | layout 风险 | 本 feature 处理 | 后续 renderer 处理 |
|---|---|---|---|
| `gs-003` | 双栏、figure/caption/table binding、Device Information 表格位置与分页风险 | `column_hint`、caption/footnote binding 可观察、wide block/table flags | heading/list/formula、caption-before-table、figure/table 输出质量 |
| `gs-006` | Thermal table caption 与 continuation 弱，表格分页风险 | table captions / footnotes / continuation facts 与 flags | caption-before-table、table style、公式清理 |
| `gs-008` | 宽表在 portrait 中压缩、末行孤立分页 | page orientation metadata、wide table `column_hint=wide` 与 flag | landscape / page fit / table style 输出策略 |

## legacy runtime 对照

| legacy 策略 | 位置 | 迁移方式 |
|---|---|---|
| 横竖版判断 | `page_layout_runtime.is_landscape_page()` / `configure_section()` | 只迁移 page orientation fact，不在本 feature 调整 Word section 输出 |
| 双栏识别 | `detect_two_col_bands()` / `detect_stable_two_col_band()` / `classify_body_block()` | `DocumentIRBlockLayout.column_hint` + layout plan 优先消费 hint，缺字段时继续 bbox fallback |
| caption/footnote binding | `input_adapter_runtime` caption fields / `backfill_middle_visual_metadata()` | 保留 DocumentIR `captions` / `footnotes`，补风险 flags；不改变 Word 输出顺序 |
| 长表 continuation | `page_repair_runtime.attach_table_continuations()` | 支持 raw continuation heights 和 table placeholder height 合并到前一张 table |
| 长表分页渲染 | `table_long_renderer.py` | 不迁移；留给后续 renderer 输出质量 |

## 退出信号

本步骤已满足 checklist `parity-audit` 退出信号：`gs-003/006/008` 的 layout 风险已分别归入可迁移 IR fact、需补 IR fact、或后续 renderer 样式策略。
