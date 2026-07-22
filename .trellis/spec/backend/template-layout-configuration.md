# 模板版式配置合同

本规范约束页面样式 YAML、配置中心 API、通用前端表单和 Word 渲染器之间的同一份配置合同。

## 场景：多文种字体配置与草稿往返

### 1. Scope / Trigger

- 修改 `TemplateConfigPackage`、legacy `RenderConfig`、页面样式 `field_schema`、版式 YAML 或 run 字体写入时适用。
- 新增、删除或重命名页面样式字段时，必须从 YAML → GET → 表单 → POST 草稿 → 正式/legacy 渲染完整追踪。
- 只改变 Word 内部排版但不经过页面样式配置的逻辑，不属于本合同。

### 2. Signatures

- 读取：`GET /api/v1/templates/{template_id}/layout-config`
- 新建草稿：`POST /api/v1/templates/{template_id}/layout-config/versions`
- 请求主体：`{"config": {<group>: {<field>: <value>}}}`
- 段落类字体字段：
  - `font_name: string`：中文/东亚字体。
  - `western_font_name: string`：西文字体。
  - `complex_script_font_name: string`：复杂文种字体。
- 页眉使用 `title_font_name`、`title_western_font_name`、`title_complex_script_font_name`；页脚使用普通三字段。
- 唯一 OOXML 写入入口：

```python
apply_run_fonts(
    run,
    *,
    font_name: str | None,
    western_font_name: str | None,
    complex_script_font_name: str | None,
) -> None
```

### 3. Contracts

- `font_name` → `w:rFonts/@w:eastAsia`。
- `western_font_name` → `run.font.name`、`w:rFonts/@w:ascii`、`@w:hAnsi`。
- `complex_script_font_name` → `w:rFonts/@w:cs`。
- 正式 DocumentIR 和 legacy conversion 必须调用同一个 `app/conversion/docx_rules/run_fonts.py`，不得各自重写槽位映射。
- 字段缺失（模型值 `None`）时，西文和复杂文种沿用旧 `font_name`；显式空字符串表示继续继承 Word 模板，不能触发回退。
- 配置 API 读取旧 YAML 时补齐新增字段，POST 后显式保存；不得原地修改源 YAML 或历史版本。
- 页眉缺失新增字段时沿用 `title_font_name`；旧页脚没有字体字段时 API 补为空字符串。
- `schema_version` 保持 `template-config/v1`；这是兼容字段扩展，不要求全量迁移。
- 完整 GET→POST 必须保留 seed 已有 `page_width_cm`、`page_height_cm`，并包含严格 schema 要求的 `table_style.header_fill`，否则仅修改字体也可能丢页面尺寸或返回 400。
- 内置 seed 的西文字体为 `Arial`，复杂文种字体为 `Times New Roman`；字体是否已安装由目标系统负责。

### 4. Validation & Error Matrix

| 条件 | 行为 |
|---|---|
| 旧段落分组只有 `font_name` | GET 用该值补齐西文和复杂文种字段；渲染四槽位保持旧单字体行为 |
| 新字段显式为 `""` | GET、POST 和渲染均保留空值，对应槽位继承模板 |
| 页眉只有 `title_font_name` | 新增页眉字体字段补为该值 |
| 旧页脚没有字体字段 | API 返回三个空字符串，不改变模板继承 |
| 请求缺少 schema 声明的字段/分组 | 返回 400，指出缺少项 |
| 请求含未知字段/分组 | 返回 400，指出不支持项 |
| 字体字段不是 string | 返回 400，指出字段必须是 string |
| 目标系统未安装配置字体 | DOCX 仍写入配置值；Word 可自行替换，不伪造成功安装状态 |

### 5. Good / Base / Bad Cases

- Good：同一段包含“中文 Latin العربية”，DOCX 同一 run 的 `eastAsia/ascii/hAnsi/cs` 分别等于配置值，配置草稿保存后可完整读回。
- Base：旧 YAML 只有 `font_name: 宋体`，无需迁移即可读取和生成，四个字体槽位继续使用宋体。
- Bad：在两个 renderer 中分别调用 `rFonts.set()`，或用 `value or font_name` 处理新字段；前者会再次漂移，后者会把显式空字符串误当成缺失。

### 6. Tests Required

- `tests.test_text_render_characterization`：断言正式三字体、旧单字体和显式空字符串的四槽位行为。
- `tests.test_render_config_characterization`：断言 legacy YAML loader 读取新增字段，英文整文档覆盖不改写显式新字体。
- `tests.test_document_ir_word_renderer_layout`：生成真实 DOCX，断言正文、页眉、页脚及装饰块的 OOXML 字体槽位；装饰块继续继承 `normal` 的非字体样式。
- `tests.test_fastapi_jobs_backend`：用旧 YAML 验证 GET 补齐、空字符串保留、POST 草稿显式持久化且源文件不变。
- 配置 API 或 schema 变化后运行前端构建；smoke mock 应至少验证三种字体标签可见。

### 7. Wrong vs Correct

#### Wrong

```python
font = western_font_name or font_name
run_fonts.set(qn("w:ascii"), font)
```

显式空字符串会错误回退，而且另一条渲染链仍可能复制不同实现。

#### Correct

```python
apply_run_fonts(
    run,
    font_name=font_name,
    western_font_name=western_font_name,
    complex_script_font_name=complex_script_font_name,
)
```

缺失和显式空值语义分开，最终槽位写入仍由一个共享函数负责。
