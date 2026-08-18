# Research: 可配置 Word 原生页脚

- Query: 追踪模板/版式配置到正式 Word 渲染器的页脚链路，确定“左侧版本号、右侧官网域名”的最小向后兼容配置合同及 Word 原生布局方式。
- Scope: mixed
- Date: 2026-08-18

## Findings

### Files found

- `app/domains/templates/layout_config_schema.py`：模板版式配置的唯一 Pydantic 模型、编辑器字段 schema、严格校验和旧配置归一化。
- `resources/template_configs/datasheet_template_v2.yaml`：当前默认模板绑定的版式配置示例。
- `resources/template_configs/datasheet_template.yaml`：受固定 SHA-256 测试保护的已发布旧配置，不宜为新增可选字段直接改写。
- `resources/template_configs/templates_manifest.yaml`：默认模板版本与 v2 版式配置绑定关系。
- `app/domains/templates/read_service.py`、`router.py`、`schemas.py`：版式配置读取、schema 驱动编辑、draft version 保存和运行时版本解析。
- `frontend/src/pages/WordPageStyleDetailPage.vue`：按后端字段 schema 动态渲染“页眉页脚”设置及浏览器预览。
- `app/services/renderer/word_renderer.py`：正式 DocumentIR→DOCX 页脚应用、源页装饰块覆盖和分节继承。
- `app/domains/document_jobs/execution.py`：线上 document job 解析模板版本后调用正式 renderer。
- `scripts/dev/formal_mineru_conversion.py`、`run_local_mineru_conversion.py`：真实 MinerU 包本地验收也调用同一个正式 renderer。
- `app/conversion/runtime/page_layout_runtime.py`：旧兼容路径已有“单段落 + 居中/右对齐制表位”的页眉页脚布局先例，但不是正式 renderer 的权威实现。
- `tests/test_template_layout_config_schema.py`、`tests/test_document_ir_word_renderer_layout.py`、`tests/test_fastapi_jobs_backend.py`：配置、OOXML 渲染和管理 API 的现有回归入口。

### Current authoritative contract and data flow

1. `TemplateFooterConfig` 当前只包含 `enabled`、`show_page_number`、三套字体和一个整段 `alignment`，且 `extra="forbid"`，所以新增页脚文字必须先进入这个唯一模型，不能让 renderer 或前端私自解析字段（`app/domains/templates/layout_config_schema.py:80-90`）。`TemplateConfigPackage.footer` 是 renderer 与管理 API 共用的同一对象（同文件 `119-146`）。
2. `GROUP_FIELD_SCHEMA.footer` 是页面编辑器的白名单和字段元数据来源；管理端只能修改这里列出的叶子字段（同文件 `300-307`、`407-457`）。前端已经通用支持 `text` 字段，无需新增 API endpoint 或专用表单组件（`frontend/src/pages/WordPageStyleDetailPage.vue:149-200`、`526-543`、`726-805`）。
3. 默认模板清单将 `default@2` 绑定到 `datasheet_template_v2.yaml`（`resources/template_configs/templates_manifest.yaml:1-9`）。管理 API 读取配置后返回 `config + field_schema`（`app/domains/templates/read_service.py:545-578`），修改会经统一校验写入新的模板 draft version（同文件 `580-669`、`1142-1184`）。
4. 线上任务从 Template Version 解析同一份 `layout_config_path` 后传给 `DocumentIRWordRenderer.render_to_bytes()`（`app/domains/document_jobs/execution.py:2208-2233`）。本地 SC2167 脚本也通过 `--layout-config` 进入同一 renderer（`scripts/dev/run_local_mineru_conversion.py:41-50`、`113-132`；`scripts/dev/formal_mineru_conversion.py:316-336`）。因此不需要新增 CLI 参数或 document-job API 字段。

### Current renderer behavior and gap

- renderer 先清空正文但保留模板 section/header/footer relationship，然后只对首节调用 `_apply_header_footer()`；后续新增 section 依靠 Word 标准继承（`app/services/renderer/word_renderer.py:65-70`、`240-285`）。现有测试已断言后续 section 的 footer 全部 `is_linked_to_previous`（`tests/test_document_ir_word_renderer_layout.py:237-272`）。
- `footer.enabled=false` 时模板页脚原样保留，符合现有合同（`word_renderer.py:273-285`）。当前模板页脚本身只有居中的原生 `PAGE` 域。
- `footer.enabled=true` 目前只能给模板已有 runs 套字体和整段对齐；当没有模板页脚字段时，代码仅写入字面量“第  页”，并没有创建 `PAGE` 域（`word_renderer.py:273-285`）。
- 对 v2 页面，若 MinerU 有 `page_footer/page_number` block，`_render_page_decorations()` 会清空同一个 footer paragraph 并写入抽取文本（`word_renderer.py:389-449`）。因此若只新增静态字段但不定义优先级，自定义版本号/域名会被源页装饰块覆盖。
- 本地 request 虽携带 `use_mineru_header_footer`（`scripts/dev/formal_mineru_conversion.py:29-50`、`117-160`），正式 `_render_document()` 没有把它传给 renderer（同文件 `316-336`）。自定义页脚不能依赖这个当前未生效的 flag 来保证优先级。

### Minimum backward-compatible config contract

建议只在既有 `footer` 分组增加两个通用文本字段，不引入“版本/官网”专用概念或动态 token：

```yaml
footer:
  enabled: true
  left_text: 'V1.1'
  right_text: 'www.example.com'
  show_page_number: false
  font_name: 宋体
  western_font_name: Arial
  complex_script_font_name: Times New Roman
  alignment: center
```

- `left_text: str = ""`、`right_text: str = ""`：静态任意文字；空字符串默认值使旧 YAML 和旧 draft version 继续可读。
- `enabled=false`：继续完全保留模板页脚，不改变现有行为。
- `enabled=true` 且 `left_text/right_text` 至少一个非空：进入“显式自定义页脚”模式。清空首节默认页脚，按左/中/右三个位置重建一个 Word 原生段落；若 `show_page_number=true`，中间创建真正的 `PAGE` 域。
- 显式自定义页脚优先于 MinerU `page_footer/page_number` 装饰块；后者不得再次清空自定义页脚。后续 section 继续链接首节，不为每页复制 relationship 或内容。
- 两个新字段都为空时，保留当前 enabled 模式及 `alignment` 的历史行为，避免已有配置突然改变布局。`alignment` 不参与显式左右布局，但保留在 v1 合同中。
- 这是 `template-config/v1` 内的可选、带默认值扩展，无需改变 API request/response 外形或 schema version。`datasheet_template_v2.yaml` 应补示例字段；固定 hash 的 `datasheet_template.yaml` 保持原文件不变，并由模型默认值兼容。

不建议增加 `version_text`、`website_url`、`{version}` 等专用字段：DocumentIR 当前没有权威的文档版本变量，用户示例可直接用静态文本满足；URL 自动超链接也不是本次明确需求。

### Native Word layout decision

使用同一个 footer paragraph 内的 Word 绝对位置对齐制表符 `w:ptab`，不要使用 1×2/1×3 表格：

```xml
<w:r><w:t>V1.1</w:t></w:r>
<w:r><w:ptab w:alignment="center" w:relativeTo="margin" w:leader="none"/></w:r>
<!-- 可选原生 PAGE complex field -->
<w:r><w:ptab w:alignment="right" w:relativeTo="margin" w:leader="none"/></w:r>
<w:r><w:t>www.example.com</w:t></w:r>
```

理由：

- `w:ptab` 是 ISO/IEC 29500 的原生 WordprocessingML run 内容，`relativeTo="margin"` 会相对当前文本边距对齐，并忽略普通自定义 tab stop；这比固定 twip 位置更适合共用页脚跨越横向/纵向 section。[Microsoft Learn: PositionalTab](https://learn.microsoft.com/zh-cn/dotnet/api/documentformat.openxml.wordprocessing.positionaltab?view=openxml-2.20.0)、[Microsoft Learn: positioning base values](https://learn.microsoft.com/lb-lu/dotnet/api/documentformat.openxml.wordprocessing.absolutepositiontabpositioningbasevalues?view=openxml-3.0.0)
- 不产生 `w:tbl`，不会把页脚布局误认为数据表，也与本任务“Word 原生结构优先”的约束一致。
- 旧 runtime 已经验证过“同一段落 + center/right tab stops”的基本排版模式（`app/conversion/runtime/page_layout_runtime.py:428-472`）；正式路径可直接构造更稳健的相对边距 `w:ptab`，不需要引入依赖或新抽象。

`python-docx` 没有公开的 positional-tab API，但项目已经用 `OxmlElement` 构造 `TOC/SEQ/REF` complex field（`app/services/renderer/text_renderer.py:507-537`），可沿用同一最小 OOXML 构造方式；`PAGE` 域也应复用 `_add_complex_field()`，避免第二套 field 实现。

### Required implementation/docs/tests

最小影响面：

1. `app/domains/templates/layout_config_schema.py`：为 footer 模型和编辑 schema 增加 `left_text/right_text`，文本上限沿用普通 128 字符即可；不要新建第二个配置模型。
2. `resources/template_configs/datasheet_template_v2.yaml`：增加两个空字符串默认字段及中文说明；不改固定 hash 的 published v1 文件。
3. `app/services/renderer/word_renderer.py`：显式自定义模式生成单段落、`w:ptab` 和可选 `PAGE` 域，并阻止源页 footer blocks 覆盖；保持标准 section 继承。
4. `frontend/src/pages/WordPageStyleDetailPage.vue`：表单字段会自动出现，但页脚预览当前硬编码为 `1`（`236-243`、`389-392`），需显示左文本、可选页码、右文本；页面说明“默认页眉内容由模板维护”也应区分“默认内容”与“显式自定义页脚”（`60-65`）。
5. Trellis `prd.md/design.md/implement.md`：新增需求会改变原设计中“不修改模板配置格式”的结论，实施前需同步需求、优先级和验收标准。

定向测试建议：

- `tests/test_template_layout_config_schema.py`：新字段出现在 editor schema；旧 v1 YAML 加载后默认空字符串；`apply_layout_changes()` 能保存左右文字并拒绝非字符串/超长值。
- `tests/test_document_ir_word_renderer_layout.py`：自定义页脚含左/右文字、相对 margin 的 center/right `w:ptab`、可选原生 `PAGE` 域，footer XML 不含 `w:tbl`；多个 continuous/new-page section 仍只引用一个页脚；DocumentIR 的源 footer block 不覆盖显式配置。
- `tests/test_fastapi_jobs_backend.py`：管理 API 返回两个字段，并把修改持久化到新 draft version；无需新增 endpoint 测试。
- 前端：至少覆盖 preview 能同时显示左/中/右值；随后运行既有 TypeScript/Vite 检查，确认后端新增 `text` 字段无需扩充类型枚举。
- SC2167：使用自定义 `V1.1` / 域名配置重新生成，检查 footer OOXML、LibreOffice→PDF→PNG 的纵向页、横向页、分栏相邻页和空白页计数。`w:ptab` 虽为 Word 标准，LibreOffice 互操作仍必须实测。

## Related specs

- `.trellis/spec/backend/quality-guidelines.md`：要求页眉页脚使用标准分节继承，并对 section/page break/页眉页脚改动执行 LibreOffice→PDF→PNG 相邻页验收。
- `.trellis/spec/guides/cross-layer-thinking-guide.md`：配置字段必须由单一 schema 拥有，前端、API、版本存储和 renderer 不得各自解释一套合同。

## Caveats / Not Found

- 未发现当前正式 renderer 对 `use_mineru_header_footer` 的消费点；该 flag 在正式本地转换路径中目前只是被携带。建议本需求用“显式自定义字段优先”定义确定行为，不顺带扩展为 header/footer source-mode 重构。
- 未发现 DocumentIR 中可作为动态“版本号”的权威字段，因此本次只能安全提供静态自定义文本。
- 未发现 `WordPageStyleDetailPage.vue` 的专用组件测试；前端预览回归需要新增最小测试或在现有前端验证命令后人工确认。
- `w:ptab` 是 Office 2007+ 标准结构，但仓库现有样本没有该元素；必须以真实 Word/LibreOffice 渲染验证，不应只断言 XML。
