# Word 模板样式配置合同

## Scenario：Admin 版本治理与多文种字体配置

### 1. Scope / Trigger

- 触发：修改 `template-config/v1`、页面样式字段、样式编辑 API、Template Version 默认指针、DOCX/YAML 绑定、验证任务权限或 Word 字体槽位。
- 唯一结构 owner：`app/domains/templates/layout_config_schema.py`；renderer、管理 API 和前端表单不得各自维护字段集合或兼容规则。
- 唯一 OOXML 字体写入 owner：`app/conversion/docx_rules/run_fonts.py`；正式 DocumentIR 和 legacy conversion 必须共同调用。

### 2. Signatures

- `GET /api/v1/templates/{template_id}/layout-config?version={int}`：admin-only 读取默认或指定版本。
- `POST /api/v1/templates/{template_id}/layout-config/versions`：admin-only 创建不可变 draft。
- 保存请求：

```json
{
  "base_template_version_id": "default@1",
  "expected_config_sha256": "sha256:...",
  "expected_active_template_version_id": "default@1",
  "changes": {"normal": {"western_font_name": "Arial"}},
  "change_note": "调整正文西文字体"
}
```

- 字体字段：
  - 段落类：`font_name`、`western_font_name`、`complex_script_font_name`。
  - 页眉：`title_font_name`、`title_western_font_name`、`title_complex_script_font_name`。
  - 页脚：`font_name`、`western_font_name`、`complex_script_font_name`。
- `ResourceVersionRepositoryProtocol.create_resource_version(record)`：只插入，不覆盖。
- `ResourceVersionRepositoryProtocol.allocate_next_version(type, id, minimum_next)`：MySQL 事务内分配不复用整数。

### 3. Contracts

#### 3.1 版本与权限

- `changes` 只能出现编辑 schema 中 `readonly=false` 的叶子字段，服务从 exact base 合并后做完整严格模型校验。
- `schema_version`、`template_name`、`output_filename`、`sample_content`、隐藏 renderer 字段和页面宽高不允许修改。
- 保存只创建 draft；只有真实验证任务成功后才能 publish，只有 published 才能 set-default。
- MySQL 模式下 `resource_default_versions` 是版本默认指针唯一来源；manifest 只登记 seed，`template_state.json` 只登记默认 template id。
- Job 创建时固化 Template Version；普通用户只能选 published，admin 可显式创建 draft 验证任务，Worker 只消费已固化版本。
- 版本 YAML 缺失、损坏、schema 不支持或 hash 不匹配时失败关闭，不回退其他 YAML 或 renderer 默认值。

#### 3.2 多文种字体

- `font_name` 写入 `w:rFonts/@w:eastAsia`。
- `western_font_name` 写入 `run.font.name`、`w:rFonts/@w:ascii` 和 `@w:hAnsi`。
- `complex_script_font_name` 写入 `w:rFonts/@w:cs`。
- 旧段落配置缺少新增字段时，西文和复杂文种补为同组 `font_name`；页眉对应补为 `title_font_name`。
- 旧页脚没有字体字段时补为三个空字符串，继续继承模板既有页脚字体。
- 兼容补齐只检查字段是否存在；显式空字符串必须保留，不能使用 `value or font_name`。
- 内置 seed 西文字体为 `Arial`，复杂文种字体为 `Times New Roman`；字体是否安装由目标系统负责。
- `schema_version` 保持 `template-config/v1`，无需批量改写历史版本；读取和创建新 draft 时由唯一 schema owner 归一化缺失字体字段。

### 4. Validation & Error Matrix

| 条件 | 状态/行为 |
|---|---|
| 非 admin 读取、列版本或保存 | `403`，前后端同时隐藏/拒绝 |
| 模板或版本不存在 | `404`，不 fallback 到其他 YAML |
| active version 或 base hash 变化 | `409`，返回当前 active version 与 config hash |
| 未知、只读、类型、范围、边距或 Word 表格样式错误 | `422`，返回 `field_errors[].path/code/message` |
| MySQL 版本服务或原子文件写入不可用 | `503`，不声明保存成功 |
| 旧段落只有 `font_name` | GET 补齐两种新增字体；新 draft 显式保存补齐值 |
| 新增字体字段显式为 `""` | GET、patch、保存和渲染均保留空值 |
| 页眉只有 `title_font_name` | GET 和新 draft 补齐两种新增字体 |
| 旧页脚没有字体字段 | API 返回三个空字符串，不改变模板继承 |
| 目标系统未安装配置字体 | DOCX 仍写入配置值，不伪造安装状态 |

### 5. Good / Base / Bad Cases

- Good：从 `default@1` 只提交 `normal.western_font_name`，生成 `default@2` draft，seed YAML 与默认指针不变；真实 DOCX 的 `eastAsia/ascii/hAnsi/cs` 分别匹配三类字体。
- Base：旧 YAML 只有 `font_name: 宋体`，无需迁移即可读取和生成，四个字体槽位继续使用宋体。
- Base：历史 published 版本通过 set-default 回滚，只移动 DB 指针，不改历史内容。
- Bad：提交完整 YAML、只读字段、未知字段或不存在的 Word table style。
- Bad：普通用户通过 create/clone/retry 注入 draft version。
- Bad：在 renderer 中再次直接写 `rFonts`，或用 truthy fallback 吞掉显式空字符串。

### 6. Tests Required

- `tests.test_template_layout_config_schema`：真实 seed、严格 schema、只读/未知/非有限数值/颜色/边距/Logo 路径、旧字体字段归一化和显式空字符串。
- `tests.test_fastapi_jobs_backend`：admin 权限、指定 draft 读取、dirty patch、409 CAS、结构化 422、seed 不变、旧 YAML GET 补齐和新 draft 显式持久化。
- `tests.test_text_render_characterization`：正式三字体、旧单字体和显式空字符串的四槽位行为。
- `tests.test_render_config_characterization`：legacy YAML loader 与语言 override 不改写显式新字体。
- `tests.test_document_ir_word_renderer_layout`：正文、页眉、页脚、装饰块和模板既有页码域的 OOXML 字体槽位。
- 持久化测试：create-only 冲突、整数序列单调、DB 失败清理 staging/目标目录。
- 配置 API/schema 变化后运行前端 unit/build；smoke mock 至少验证三种字体标签可见。

### 7. Wrong vs Correct

#### Wrong

```python
font = western_font_name or font_name
run_fonts.set(qn("w:ascii"), font)
```

显式空字符串会错误回退，且 renderer 重新拥有了字段映射。

#### Correct

```python
apply_run_fonts(
    run,
    font_name=font_name,
    western_font_name=western_font_name,
    complex_script_font_name=complex_script_font_name,
)
```

缺失与显式空值语义分开，结构、归一化和槽位写入各有唯一 owner。
