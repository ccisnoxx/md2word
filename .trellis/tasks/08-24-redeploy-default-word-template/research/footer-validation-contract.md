# 页脚验证合同摘录

来源：`.trellis/spec/backend/word-generation-rules.md` 的 `FIELD-003`、`STYLE-002`、`STYLE-003`、`STYLE-005`。

## Owner 与输入

- 页眉页脚最终写入 owner：`app/services/renderer/word_renderer.py::_apply_header_footer`。
- 原生字段 owner：`app/services/renderer/word_renderer.py::_add_complex_field`。
- 输入来自绑定 Template Version 的 layout config；源 PDF 的 `page_header/page_footer/page_number` 不覆盖共享 Word section。

## 必须行为

- `footer.enabled=true` 且存在左右文字或页码时，配置明确接管页脚并重建 footer part。
- `show_page_number=true` 必须写原生 `PAGE` field，不得写死数字或静态占位。
- 同时存在 `left_text`、`right_text` 和页码时，使用 positional tab 布局形成左/中/右三个位置。
- 页脚字体分别写 eastAsia、ascii/hAnsi、cs；显式空值保持继承。
- 配置页脚后不得再写入源 PDF 的 footer decoration。

## 验证要求

- 自动结构检查必须同时验证可见左右文字、原生 `PAGE` 字段和 positional tab，不能只证明 DOCX 可打开。
- Word decoration 属于 section；后续 section 使用标准 relationship 继承，不逐源页复制。
- LibreOffice 对 positional tab 的展开与 Word/WPS 不同，视觉位置必须以 Word/WPS 实际打开结果验收。
- 当前发布候选需要确认左右文字可见、页码居中、正文与页脚不重叠。

## 既有自动回归

- `test_render_to_bytes_writes_native_custom_footer_and_ignores_source_footer`
- `test_render_to_bytes_writes_configured_body_header_and_footer_font_slots`
- `test_render_to_bytes_preserves_template_decorations_when_config_disabled`
- `test_enabled_config_without_content_preserves_template_decorations_and_ignores_source_decorations`
