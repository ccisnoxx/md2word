# 完善页面格式字体配置：技术设计

## 1. 问题与边界

现有页面样式只有一个 `font_name`，两条渲染链都把它写入 `w:eastAsia`、`w:ascii` 和 `w:hAnsi`，且不写 `w:cs`。本次只扩展现有页面样式契约和字体槽位写入，不引入字体安装检测、字体目录、按字符拆分 run 或按具体语言维护字体映射表。

该任务保持为单任务：字段定义、旧配置兼容、配置中心读写和 DOCX 输出构成一个不可分割的往返合同，拆分会产生前端能编辑但渲染无效、或渲染支持但配置无法保存的中间状态。

## 2. 配置合同

### 2.1 段落类样式

`TemplateParagraphStyleConfig` 和 legacy `ParagraphStyleConfig` 增加两个可选字段：

- `font_name`：保留现有字段名，语义明确为中文/东亚字体。
- `western_font_name`：西文字体。
- `complex_script_font_name`：复杂文种字体。

覆盖 `part_number`、`category`、`heading1`～`heading3`、`toc_title`、`toc_level1`～`toc_level3`、`normal`、`table_content`、`table_note`、`caption`、`long_table_caption`。

### 2.2 页眉与页脚

为避免重构既有扁平 YAML：

- 页眉保留 `title_font_name`，新增 `title_western_font_name`、`title_complex_script_font_name`。
- 页脚新增 `font_name`、`western_font_name`、`complex_script_font_name`，用于“第  页”、页码域及模板已有页脚 run。

不把页眉标题重构成嵌套 `title_style`，也不增加单实现接口或字体配置对象。

### 2.3 内置默认值

`resources/template_configs/datasheet_template.yaml` 中每个文字样式显式保存：

- 原 `font_name` 值保持不变；
- `western_font_name: Arial`；
- `complex_script_font_name: Times New Roman`。

页眉使用对应 `title_*` 字段；页脚中文字体使用 `宋体`，西文和复杂文种使用上述默认值。`schema_version` 保持 `template-config/v1`，因为这是向后兼容的字段扩展。

## 3. OOXML 映射

在 `app/conversion/docx_rules/run_fonts.py` 新增一个共享函数，成为两条渲染链唯一的 run 字体槽位写入规则：

| 配置字段 | OOXML / python-docx 目标 |
|---|---|
| `font_name` | `w:rFonts/@w:eastAsia` |
| `western_font_name` | `run.font.name`、`w:rFonts/@w:ascii`、`@w:hAnsi` |
| `complex_script_font_name` | `w:rFonts/@w:cs` |

直接字体属性优先于模板主题字体，因此不删除 `asciiTheme`、`hAnsiTheme`、`eastAsiaTheme` 或 `cstheme`。显式空字符串表示该槽位继续继承 Word 模板；只有字段缺失（模型值为 `None`）时才执行旧配置回退。

兼容回退规则：

- `western_font_name is None` 时，使用 `font_name` 写入 `ascii/hAnsi`。
- `complex_script_font_name is None` 时，使用 `font_name` 写入 `cs`。
- `font_name` 本身缺失或为空时，不写 `eastAsia`。

`WordTextRendererMixin._apply_run_style` 与 legacy `apply_run_defaults` 只调用共享函数，字号、粗体、斜体和颜色逻辑保持原处不变。

## 4. 配置中心数据流与兼容

```text
旧/新 layout_config.yaml
  → TemplateReadService 读取并补齐编辑合同
  → field_schema + config 返回通用 Vue 表单
  → 管理员保存完整三字体字段
  → 新 draft layout_config.yaml
  → TemplateConfigPackage / legacy loader
  → 共享 run 字体槽位写入函数
  → DOCX w:rFonts
```

`TemplateReadService` 在拆分 meta/config 时完成一次确定性的旧配置归一化：

- 段落类分组缺少两个新增字段时，用该组原 `font_name` 补齐。
- 页眉缺少新增字段时，用原 `title_font_name` 补齐。
- 旧页脚没有任何字体字段，读取时补齐为空字符串，以保持模板继承行为；内置新配置则显式提供默认字体。
- 已存在的新增字段原样保留，包括显式空字符串。
- 完整 GET→POST 往返还必须保留 seed 已有的 `page_width_cm`、`page_height_cm`，并为严格 schema 已声明但 seed 缺失的 `header_fill` 补上现有模型默认值；否则管理员只修改字体也会丢页面尺寸或收到 400。

归一化只影响 API 返回和随后创建的新草稿版本，不原地修改仓库 YAML 或历史版本。提交仍沿用现有严格字段校验，不增加第二套宽松校验。

## 5. 文档语言覆盖

新渲染链现有 `language_overrides` 深合并机制可直接覆盖新增字段，无需新增分支。

legacy 英文整文档覆盖只在 `western_font_name is None` 的旧配置上保留原行为：继续把旧 `font_name` 改为 `Arial`，使缺少新字段的历史配置仍把三个槽位写成 Arial。新配置已显式声明西文字体时，不再改写中文字体；正文首行缩进的既有英文覆盖保持不变。

## 6. 前端影响

生产前端无需新增逻辑：`WordPageStyleDetailPage.vue` 已按后端 `field_schema` 通用渲染 `text` 字段。后端把标签调整为“中文字体”，并增加“西文字体”“复杂文种字体”；页眉使用对应标题字体标签，页脚增加三项字体字段。

更新已有 smoke mock 与断言，防止配置中心未来漏掉三字段。不开发表字体选择器：仓库没有权威字体目录，文本输入也允许管理员填写目标 Word 环境已安装的字体。

## 7. 验证设计

- 共享/legacy 单元测试：分别设置三种字体，断言 `eastAsia/ascii/hAnsi/cs`；再用仅含 `font_name` 的旧配置断言四槽位保持旧行为。
- 正式 DocumentIR 集成测试：用中西文及阿拉伯文混排内容生成 DOCX，直接检查 `document.xml` 的四个字体属性。
- 配置 API 测试：旧 YAML 读取时补齐字段，`field_schema` 暴露中文标签，POST 后新草稿显式保存三种字体且不改原文件。
- legacy 加载/英文覆盖测试：新增字段能从 YAML 加载；显式西文字体时不再改写中文字体，旧配置仍保留原英文覆盖。
- 前端契约：smoke mock 显示三种字体字段；执行前端构建验证模板与 TypeScript。

## 8. 风险与回滚

- 风险：目标系统未安装配置字体时，Word 仍会自行替换字体；本任务只保证 OOXML 声明正确，不承诺操作系统字体可用。
- 风险：显式空字符串会保留模板继承；测试需区分“字段缺失”和“字段为空”。
- 风险：代码回滚后，已保存的新字段会被 Pydantic 忽略，但旧配置中心严格校验会拒绝再次保存这些字段；因此部署前可直接回滚代码和 seed，部署后若已有新草稿则需同时回滚或迁移这些草稿。
- 无数据库 schema 迁移、无原地历史配置改写、无自动发布或默认版本切换。
