# 完善页面格式字体配置

## Goal

页面格式配置不能只控制中文字体；标题、目录、正文、表格等会包含中文、西文和复杂文种文本，生成的 Word 文档应按配置稳定写入相应字体，避免英文或复杂文种回退到不可控的默认字体。

## Confirmed Facts

- 页面样式编辑器完全由后端 `field_schema` 驱动，当前段落样式只提供 `font_name`（显示为“字体”），页眉使用例外字段 `title_font_name`；前端没有独立字体字段或字体专用控件（`app/domains/templates/read_service.py:65-151`、`frontend/src/pages/WordPageStyleDetailPage.vue:122-184`）。
- 现有可编辑内容分组包括首页型号/品类、三级标题、目录标题与三级目录项、正文、表格正文、表注、图表题、续表标题、页眉和页脚；页脚目前没有字体配置（`frontend/src/pages/WordPageStyleDetailPage.vue:264-272`、`app/domains/templates/read_service.py:86-151`）。
- 新渲染链的 `TemplateParagraphStyleConfig` 和旧运行时的 `ParagraphStyleConfig` 都只有一个 `font_name`（`app/services/renderer/template_config.py:27-44`、`app/conversion/runtime_models.py:107-120`）。
- 两条渲染链都会把同一个 `font_name` 同时写入 `w:eastAsia`、`w:ascii` 和 `w:hAnsi`，都没有写入 `w:cs`；因此中西文字体无法分别配置，复杂文种字体完全未受控（`app/services/renderer/text_renderer.py:292-307`、`app/conversion/runtime/text_rendering.py:206-223`）。
- 配置读取、页面编辑、草稿版本保存和渲染均使用同一份 YAML；提交校验要求页面返回所有已声明分组及字段（`app/domains/templates/read_service.py:573-640`、`app/domains/templates/read_service.py:1122-1191`）。
- `language_overrides` 按整份文档语言覆盖样式，不能解决同一段落内的中西文混排字体槽位问题（`app/services/renderer/template_config.py:143-165`）。
- 旧运行时现有英文覆盖统一使用 `Arial`；内置 Word 模板主题对复杂文种按具体脚本使用不同字体，其中阿拉伯文、希伯来文等使用 `Times New Roman` 或 `Arial`，仓库没有一个已定义的统一复杂文种默认字体（`app/conversion/runtime_helpers.py:17-31`、`resources/templates/default/datasheet_template.docx` 的 `word/theme/theme1.xml`）。
- 现有测试验证了单一 `font_name` 和部分 OOXML 语义，但没有断言四个 `w:rFonts` 字体槽位，也没有覆盖复杂文种字体（`tests/test_text_render_characterization.py:167-196`、`tests/test_document_ir_word_renderer_layout.py:473-514`）。

## Requirements

- **R1 完整范围**：首页型号/品类、标题、目录、正文、表格正文、表注、图表题、续表标题、页眉和页脚等所有实际生成文字的页面样式分组，都能独立配置中文、西文和复杂文种字体。
- **R2 字段合同**：保留既有 `font_name` 并明确其语义为中文字体，新增独立的西文字体和复杂文种字体字段；配置界面、保存/加载、后端模型与文档生成使用同一组字段。
- **R3 产物合同**：中文、西文和复杂文种字体分别控制 Word 的东亚、西文和复杂文种字体槽位，不能继续用一个字体覆盖全部文种，也不能在两条渲染链形成不同规则。
- **R4 旧配置兼容**：缺少新增字段的旧配置以原 `font_name` 补齐西文与复杂文种字体，使历史字体行为保持不变；新保存版本显式持久化三种字体。该扩展不强制旧配置立即迁移或升级 schema 版本。
- **R5 内置默认值**：内置页面样式的西文字体使用 `Arial`，复杂文种字体使用 `Times New Roman`；各分组仍可单独修改。

## Acceptance Criteria

- [x] **AC1（R1、R2）**：配置中心在所有文字样式分组显示中文、西文和复杂文种字体字段，保存为草稿后重新读取值不丢失。
- [x] **AC2（R3）**：生成的 `.docx` 中，`w:eastAsia`、`w:ascii`、`w:hAnsi` 和 `w:cs` 分别与对应配置一致。
- [x] **AC3（R4）**：仅含旧 `font_name` 的配置可读取、渲染和保存；读取补齐值与旧字体一致，且不会原地改写历史 YAML。
- [x] **AC4（R5）**：内置配置的所有文字样式都显式包含 `Arial` 西文字体和 `Times New Roman` 复杂文种字体。
- [x] **AC5（R1～R4）**：可运行验证覆盖中西文与复杂文种混排、配置读写往返、页眉页脚以及正式/legacy 两条实际渲染链，不存在第二套字体槽位映射。

## Out of Scope

- 字体自动探测、操作系统字体安装和通用字体替换引擎。
- 按字符拆分 Word run，或为每一种具体语言/文字脚本维护字体映射表。
- 自动发布草稿、切换默认模板或原地改写历史配置版本。
