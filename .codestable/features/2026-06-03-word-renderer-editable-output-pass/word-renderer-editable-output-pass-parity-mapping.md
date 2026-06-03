---
doc_type: feature-evidence
feature: 2026-06-03-word-renderer-editable-output-pass
status: current
summary: renderer editable output pass 的 legacy runtime 策略映射证据。
---

# word-renderer-editable-output-pass parity mapping

## 输入来源

- live regression 分类：当前 4 个 runnable Golden Sample 主链路成功但人工质量 0/4 P0 pass，核心缺口是 `pipeline-parity-gap`。
- design 约束：只迁移 DocumentIR 当前字段可驱动的 heading/list/formula/caption/table 可编辑语义；不把 `app/conversion/runtime` 变成线上第二渲染入口。
- legacy strategy 来源：
  - `app/conversion/runtime/text_rendering.py`
  - `app/conversion/runtime/table_render_runtime.py`
  - `app/conversion/runtime/table_long_renderer.py`
- 当前目标 renderer：
  - `app/services/renderer/word_renderer.py`
  - `app/services/renderer/text_renderer.py`
  - `app/services/renderer/table_renderer.py`
  - `app/services/renderer/template_config.py`

## 策略映射

| 类别 | 结论 | legacy 证据 | DocumentIR renderer 迁移方式 | 暂不迁移内容 |
|---|---|---|---|---|
| heading | 局部迁移 | `fill_title_paragraph()` 会写 `Heading {level}` named style，并用 rich text 写标题正文 | `DocumentIRBlock.level` 已有 1-3 级信息；renderer 写入 `Heading 1/2/3` 或配置指定 named style，再保留直接样式覆盖 | cover title / PartNumber 推断依赖 legacy page bbox 语义，不在本轮处理 |
| list | 直接迁移 | `fill_list_paragraph()` 清理 marker 后调用 `apply_bullet_numbering()` 写真实 `w:numPr` | `DocumentIRBlock.list_items` 已有列表项；renderer 去除 `•/-/–` marker，写共享 bullet numbering definition | 嵌套层级只能从 marker 粗略推断；复杂多级编号不在本轮处理 |
| formula | 局部迁移 | `normalize_formula_text()`、`convert_inline_tex_to_html()` 能清理 `\sqrt`、`\mu`、`^{\circ}` 和上下标 | renderer 复用等价 normalization 思路，把 `latex/text` 转成安全 inline markup，再交给现有 rich text run 输出 | 完整 LaTeX parser、公式对象和 OMML 转换不在本轮处理 |
| caption/table note | 直接迁移 | `render_block_captions_impl(... keep_with_next=True)` 会在表格前写 caption；footnote 使用 `TableNote` | table renderer 先写 dedup caption with `keep_with_next`，再写 editable table，最后写 dedup `table_note` / footnote | 长表分页、续表拆分、图片 fallback table rendering 不在本轮处理 |
| table content | 局部迁移 | `fill_table_cell_impl()` 对表头加粗，正文走 `TableContent` | 当前 renderer 已走 `table_content`；本轮补 formula/rich text normalization 与 header/cell 可编辑样式取证 | 5 列权重、长表分页、视觉行高估算不在本轮处理 |

## 退出信号核对

- heading：局部迁移，理由是 DocumentIR 当前有 `level`，但没有 legacy cover title 所需页面语义。
- list：直接迁移，理由是 `list_items` 足够驱动 marker 清理和 Word bullet numbering。
- formula：局部迁移，理由是 normalization 可由文本字段驱动，但完整公式对象超出本轮。
- caption：直接迁移，理由是 `captions` / `footnotes` 已在 DocumentIR 合同中稳定存在。
- table：局部迁移，理由是 `html` 已足够驱动可编辑表格和单元格 rich text，但不覆盖长表视觉分页。
