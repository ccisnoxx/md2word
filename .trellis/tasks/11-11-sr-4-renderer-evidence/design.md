# 设计

## 1. Evidence 拆分

| 新模块 | 内容（来自 `evidence.py`） |
|---|---|
| `render_evidence.py` | `build_renderer_metadata`、`build_renderer_aggregate_evidence`、`_binding_key`、`formula_source_inventory`、`build_renderer_evidence` |
| `render_evidence_validation.py` | `ensure_renderer_integrity`、`render_contract_failure`、`validate_render_result`、`_validate_persisted_image_targets`、`validate_persisted_render_evidence`、`_validate_render_evidence`、`validate_persisted_renderer_content`、`_restore_legacy_docx_quality` |
| `render_event_summary.py` | `controlled_quality_flags`、`_safe_counts`、`_type_counts`、`_safe_failure_context`、`build_renderer_event_summary`、`_safe_validation_input`、`_report_*`、`_safe_mineru_report`、`is_valid_table_rendering_evidence` |

依赖方向：`render_evidence_validation` → `render_evidence`（如果校验时需要重新构建证据）；`render_event_summary` 不依赖另外两个。实施时以函数实际的相互调用为准；如果某个私有 helper 被两个模块使用，就放到被依赖的那一方。

若 `_validate_render_evidence`（约 220 行）拆完后 `render_evidence_validation.py` 仍超过上限，再按"plan/块证据校验"和"图片/公式/锚点校验"拆成两个私有函数，但仍放在同一模块内，不再新增模块。

## 2. `render_to_result` 拆分

```text
render_to_result()
  prepared = prepare_render(document_ir, template_config, resources, ...)   # render_preparation.py
      -> PreparedRender(layout_plan, table_plan, tables, plan, collector)    # frozen dataclass
  document, render_context = self._open_document(...)                       # 模板加载、清空正文、页面设置、页眉页脚、文档设置、上下文初始化
  for index, operation in enumerate(plan.operations):
      self._dispatch_operation(document, operation, prepared, render_context, ...)  # 保留原 try/except 与 attach_failure_context
  return self._freeze_result(document, prepared, render_context, reserved_bookmarks)  # 锚点实体化、保存、collector.freeze、公式覆盖
```

- `_attach_plan_failure_context` 的调用位置和参数保持不变，保证失败上下文的字段与基线一致。
- `document.part._md2word_formula_context = render_context` 这类对象属性赋值，保持原来的赋值顺序。

## 3. Mixin 拆分

| 新模块 | 迁出内容 |
|---|---|
| `page_layout_renderer.py`（`WordPageLayoutMixin`） | `_apply_page_setup*`、`_configure_layout_page_section`、`_portrait_page_dimensions`、`_apply_header_footer`、`_add_positional_tab`、`_set_section_columns`、`_render_page_decoration`、`_resolve_decoration_font` |
| `formula_renderer.py`（`WordFormulaRendererMixin`） | `_fill_formula_paragraph`、`_append_formula`、`_set_formula_source`、`_render_mixed_math`、`_add_complex_field` |
| `list_numbering.py`（`WordListNumberingMixin`） | `_apply_bullet_numbering`、`_ensure_bullet_numbering`、`_next_numbering_id`、`_set_numbering_child_value` |
| `native_table_renderer.py`（`WordNativeTableRendererMixin`） | `NativeCellPart`、`_append_grid_cell`、`_fill_native_grid_runs`、`_append_native_rows`、`_render_native_unit` 及其专用 helper |

`DocumentIRWordRenderer` 的基类列表增加新的 Mixin。Python 的 MRO 只影响同名方法的解析，实施前用 `rg "    def (_\w+)"` 确认所有 Mixin 之间没有同名方法，因此方法解析结果不变。

## 4. 不改为组合对象的原因

Mixin 之间通过 `self._xxx` 互相调用的点很多（table 调用 text 的 `_fill_paragraph`、`_apply_run_style` 等），改为组合对象需要显式传递 3–4 个协作者，并改动测试中直接调用的私有方法。在"输出零变化"的约束下，这种改动的风险明显高于收益。本任务只解决"单个模块/方法过大"的问题。

## 5. 渲染等价性基线

第 0 步新增 `.trellis/tasks/11-11-sr-4-renderer-evidence/verify_render_equivalence.py`（任务目录内的验证工具，不进入 `tests/`）：

- 输入：`tests/fixtures` 中的 MinerU fixture，以及 `test_component_pdf_sample_governance` 使用的组件样本，通过 `scripts.dev.formal_mineru_conversion.run_conversion` 跑正式路径；如果有翻译模式样本，只使用离线 response。
- 输出：每个样本生成的 DOCX 解压后各 part 的 sha256 清单（JSON）。
- 用法：在基线上运行一次保存清单，每次提交后重新运行并对比，要求完全一致。
- 前置检查：在基线上连续运行两次，确认清单稳定；如果 python-docx 写入了时间戳等不稳定 part（例如 `docProps/core.xml`），就从对比中排除这些 part，并在报告中列出排除项。
