# Research: 正式本地 MinerU→DOCX 字体配置根因

- Query: 追踪当前 CM4112 正式本地命令实际加载的模板/字体配置，核对 body、heading、caption、table、field、formula 的 `w:rFonts` 写入路径，并区分配置未传、配置被忽略、字体槽缺失和 WPS 缺字替换。
- Scope: internal（代码、规范、当前 DOCX OOXML、本机/WPS 字体环境）
- Date: 2026-08-19

## Findings

### 1. 结论

当前候选字体没有按 `datasheet_template_v2.yaml` 生效的首要根因是：**用于生成该候选的正式 CLI 没有传 `--layout-config`，本地 formal adapter 也没有像线上链路一样补当前默认配置；`None` 最终被解释为“空 `TemplateConfigPackage`”，而不是内置 v2 配置。**

这不是 `apply_run_fonts()` 忽略了已加载配置。使用同一份 CM4112 DocumentIR、显式传入 v2 YAML 做内存渲染时，666/666 个带可见 `w:t` 的 Word run 都写入了 `eastAsia=宋体`、`ascii/hAnsi=Arial`、`cs=Times New Roman`。当前正式候选则是 0/734 个可见 Word run 带直接 `w:rFonts`。

线上 Document Job 不受这个 CLI 默认值缺口影响：它先解析任务固化的 Template Version，再把该版本的 `layout_config_path` 原样交给 renderer；不能在共享 renderer 内增加全局配置 fallback，否则会破坏线上“指定版本缺失即失败关闭”的合同。

即使补上 v2 YAML，本机仍存在第二层字体可用性问题：`Arial`、`Times New Roman` 已安装；配置的精确字体名 `宋体` 未安装（本机是 `Songti SC/宋体-简`），因此 WPS 仍可能显示缺失字体并替换。公式又由独立的 `m:mathFont=Cambria Math` 控制，不属于当前三类段落字体槽；本机也没有 Cambria Math。

### 2. 精确命令与配置流

当前验证记录中的命令没有 `--template`、`--layout-config` 或 `--subscript-config`：

```bash
.venv/bin/python scripts/dev/run_local_mineru_conversion.py \
  '/Users/sc/Downloads/mineru_raw_result 2' \
  --output /tmp/md2word-cm4112-structural-fix/cm4112-fixed.docx \
  --translation-mode direct
```

实测 `parse_args()` + `build_conversion_kwargs()` 得到：

```text
template_path=None
layout_config_path=None
subscript_config=None
no_template=False
document_language='auto'
```

代码链如下：

1. `scripts/dev/run_local_mineru_conversion.py:113-132` 直接把 CLI 的三个可选路径放入 kwargs，没有读取 `Settings` 默认路径。
2. `scripts/dev/formal_mineru_conversion.py:141-146` 只做可选路径解析，`None` 保持为 `None`。
3. `scripts/dev/formal_mineru_conversion.py:317-337` 把 `request.layout_config_path` 原样作为 `config_path` 传给 `DocumentIRWordRenderer`；`no_template=False` 也不会自动补默认模板。
4. `app/services/renderer/word_renderer.py:66-70,167-184` 调用 `TemplateConfigPackage.load(config_path)`。
5. `app/domains/templates/layout_config_schema.py:151-170` 明确定义 `load(None) -> cls()`；这会得到所有段落字体、字号、间距均为 `None` 的空配置。

仓库实际默认配置并不为空：

- `app/core/config.py:203-213,261-272` 的默认模板和 layout config 分别指向 `resources/templates/default/datasheet_template.docx` 与 `resources/template_configs/datasheet_template_v2.yaml`。
- `resources/template_configs/templates_manifest.yaml:1-9` 的 `default@2` 绑定同一 DOCX/YAML。
- `resources/template_configs/datasheet_template_v2.yaml:142-144` 正文配置为 `宋体/Arial/Times New Roman`，`:195-197` 图注也相同；标题、目录、表格和表注均声明三类字体。
- `.trellis/spec/backend/template-layout-configuration.md:59-65` 已规定 `Settings.layout_config_path` 与本地正式转换工具的“当前内置配置”都应指向 v2。当前 CLI 行为与这条已归档合同不一致。
- `docs/dev/local-conversion-sandbox.md:156-168` 的正式 CLI 示例也省略 layout config，进一步说明省略参数应使用当前内置配置，而不是空配置。

### 3. 当前 DOCX 的 OOXML 证据

检查对象：

- DOCX: `/tmp/md2word-cm4112-structural-fix/cm4112-fixed.docx`
- SHA-256: `baeb48749d06b3537f2f793789b1a52ebff57e38de58fac115eecb87138ad179`
- DocumentIR: `/tmp/md2word-cm4112-structural-fix/cm4112-fixed.document-ir.json`
- SHA-256: `32ef8f04721bc23e055958aa887bd0a7478b1a6a68d3c6e9d2c816815e5dc83c`

实测包内结构：

- `word/document.xml`：1523 个 `w:r`，其中 734 个含可见 `w:t`；这 734 个 run 中 **0 个**含直接 `w:rPr/w:rFonts`。
- `word/styles.xml`：`Normal` 没有直接字体；`docDefaults` 使用 `minorHAnsi/minorEastAsia/minorBidi` 主题字体；Heading 1–3 使用 `majorHAnsi/majorEastAsia/majorBidi`。
- `word/settings.xml`：`w:themeFontLang` 为 `w:val="en-US" w:eastAsia="ja-JP"`，公式默认 `m:mathFont="Cambria Math"`。
- `word/theme/theme1.xml`：major Latin 为 Calibri、minor Latin 为 Cambria；Jpan major/minor 分别为 `ＭＳ ゴシック`/`ＭＳ 明朝`，Hans major/minor 为 `宋体`。
- `word/fontTable.xml` 声明 Calibri、Cambria、`ＭＳ ゴシック`、`ＭＳ 明朝` 等，但声明字体不代表本机已安装。

因此当前 WPS 显示 `ＭＳ ゴシック`、Calibri 或“缺失字体”不是 v2 YAML 的结果，而是空配置后继承 python-docx 默认 Word 主题，再由 WPS 按本机字体环境解析/替换的结果。

对同一份 IR 仅显式传入 `datasheet_template_v2.yaml` 的内存对照结果：

```text
visible w:t runs: 666
with direct w:rFonts: 666
font slots: eastAsia=宋体, ascii=Arial, hAnsi=Arial, cs=Times New Roman
OMML m:r runs: 119
OMML runs with w:rFonts: 0
```

可见 Word run 数量与正式候选不同，是因为对照渲染未提供图片 bytes、图片走可见题注 fallback；字体结论只比较每次渲染内“有可见 `w:t` 的 run 是否带完整槽位”。

### 4. Renderer 字体 owner 与各内容路径

唯一槽位 owner 是 `app/conversion/docx_rules/run_fonts.py:10-35`：

- `font_name` → `w:eastAsia`
- `western_font_name` → `run.font.name` + `w:ascii` + `w:hAnsi`
- `complex_script_font_name` → `w:cs`
- 新槽为 `None` 才回退旧 `font_name`；显式空字符串保持继承语义。

正式 renderer 的普通可见文本没有发现另一套字体写入实现：

| 内容 | 路径 | 结果 |
|---|---|---|
| 正文、列表、heading | `text_renderer.py:318-423` → `_add_text_run()` → `_apply_run_style()` (`:709-767,839-853`) | 加载有效配置时写四槽 |
| 图注/表题 | `text_renderer.py:497-531`，image 调用见 `image_renderer.py:76-94`，table 调用见 `table_renderer.py:278-308` | 题注文字与可见 SEQ 结果写四槽 |
| 表格 cell、表注 | `table_renderer.py:207-225,310-323` → `_fill_paragraph()` | 写 `table_content`/`table_note` 四槽 |
| TOC/SEQ/REF/PAGE 字段 | `text_renderer.py:600-630` | 可见 field result run 写四槽；begin/instruction/separate/end run 不可见且不需字体 |
| 页眉/页脚 | `word_renderer.py:246-305,440-511` | 配置启用覆盖时写四槽；v2 seed 默认 `enabled:false`，此时按合同继承模板已有 decoration |
| 公式 OMML | `text_renderer.py:57-312,471-483,534-579` | 生成 `m:r`，不走 `w:rFonts`；由 `word/settings.xml` 的 `m:mathFont` 控制 |

另有两个应明确的合同边界：

1. `part_number` 和 `category` 虽存在于 schema，但当前 `DocumentIRWordRenderer` 没有引用；MinerU `title` 统一作为 heading 渲染。这是单独的样式语义缺口，不是本次整份文档字体失效的主因。
2. 图片 run、换行 run、tab run、field 控制 run 没有可见字体 glyph，不应被“所有 run 必须带 rFonts”的错误测试阻断；验收应只检查可见 `w:t` 与可见 field result。

### 5. Online 链路影响判定

线上链路没有复现本地 CLI 的空配置问题：

- `app/domains/document_jobs/execution.py:2219-2232` 调用 `template_read_service.resolve_template_version(...)`，并把 `template_selection.template_path`、`template_selection.layout_config_path` 传给 renderer。
- 模板配置合同 `.trellis/spec/backend/template-layout-configuration.md:39-46` 规定任务创建时固化版本，版本 YAML 缺失/损坏/hash 不匹配时失败关闭，不得回退 renderer 默认值。

因此修复应局限在 **formal local adapter 的参数默认解析边界**；不要修改 `TemplateConfigPackage.load(None)` 或 `DocumentIRWordRenderer._load_template_config()` 去读取全局 Settings，否则线上错误绑定可能被静默掩盖。

### 6. 本机与 WPS 字体可用性

- WPS Office: 12.1.26055（build 26055），安装路径 `/Applications/wpsoffice.app`。
- 本机 `fontconfig`：Arial 与 Times New Roman 能精确匹配系统字体。
- `宋体` 不能精确匹配；系统提供的是 `Songti SC/宋體-簡/宋体-简`。
- Calibri、Cambria、`ＭＳ ゴシック`、`ＭＳ 明朝`、Cambria Math 均不能精确匹配本机字体；`fc-match` 会返回其他字体。
- WPS 应用包自带 `ShuS-SC/书宋-简`、`Kingsoft Math`、`DejaVu Math TeX Gyre` 等，但没有精确名为 `宋体` 或 `Cambria Math` 的内置文件。
- 已有真样本记录 `.trellis/tasks/08-18-fix-formal-word-structural-regressions/research/cm4112-validation.md:41-54,62-70` 观察到 WPS GUI/CLI 的缺失字体、单位/公式字符替换和客户端分页差异。

配置合同已明确“目标系统未安装配置字体时，DOCX 仍写配置值，不伪造安装状态”（`.trellis/spec/backend/template-layout-configuration.md:48-57,67-85`）。所以代码可以保证 OOXML 请求了哪个字体，不能保证 WPS 在缺字体系统上不替换。

### 7. 最小修复建议

1. 在 `scripts/dev/formal_mineru_conversion.py::run_conversion` 这个共享本地 adapter 边界解析一次 `Settings` 默认资源：
   - 显式 `layout_config_path` 优先；省略时使用 `Settings.layout_config_path`。
   - `no_template=False` 且未传 `template_path` 时使用 `Settings.default_template_path`；`no_template=True` 仍明确禁用 DOCX 模板，但不应禁用 layout YAML。
   - 不在 renderer 增加 fallback，不改变线上 Template Version owner。
2. 不修改已发布 `datasheet_template_v2.yaml` 字节。若产品要让 macOS/WPS 在未安装 Windows `宋体` 时也不提示缺字，应创建新模板版本并选用目标部署环境实际安装的精确字体名，或由部署侧安装字体；不能在 renderer 猜别名。
3. 公式字体若也要可配置，应单独定义 `math_font_name` → `m:mathPr/m:mathFont` 合同并创建新模板版本；不要把 `western_font_name` 直接套到 OMML。当前最小修复只恢复已有三类文本字体合同。

### 8. 最小验证

1. `tests/test_conversion_sandbox_dev_tools.py`：formal adapter 不传 layout config、`no_template=True` 的最小 MinerU 包，输出正文可见 run 必须含 `宋体/Arial/Arial/Times New Roman` 四槽；该测试会在当前代码稳定失败。
2. 同模块确认显式 `--layout-config` 仍优先于 Settings 默认；`--no-template` 只禁用 DOCX 模板，不禁用布局/字体 YAML。
3. 保留现有 `tests/test_document_ir_word_renderer_layout.py:549-616` 的显式 body/header/footer 槽位测试和 `:1639-1714` 的 TOC style 测试，避免复制 renderer 单元测试。
4. 重新生成 CM4112 后做 OOXML 门禁：所有含可见 `w:t` 的正文/heading/caption/table/field-result run 均有预期四槽；OMML 按独立 `m:mathFont` 记录，不误报为段落槽缺失。
5. WPS 12.1.26055 人工复核至少记录：选中中文/西文 run 显示的请求字体、是否标“缺失字体”、公式字体替换符、总页数和图 33 稀疏页。OOXML 正确与客户端字体可用性必须分别下结论。

## Files Found

- `scripts/dev/run_local_mineru_conversion.py` — 参数型正式本地 CLI；当前省略路径时传 `None`。
- `scripts/dev/formal_mineru_conversion.py` — 正式本地共享 adapter；当前没有补 Settings 默认资源。
- `app/core/config.py` — 当前内置模板、v2 YAML、术语配置的默认路径 owner。
- `app/domains/templates/layout_config_schema.py` — `template-config/v1` 唯一 schema 与 `load(None)` 空配置语义。
- `app/conversion/docx_rules/run_fonts.py` — 四字体槽唯一 OOXML 写入 owner。
- `app/services/renderer/word_renderer.py` — template/config 加载、heading/body 分发、页眉页脚写入。
- `app/services/renderer/text_renderer.py` — 正文、标题、图注、字段与 OMML 渲染路径。
- `app/services/renderer/image_renderer.py` — 图片题注调用共享文本路径。
- `app/services/renderer/table_renderer.py` — 表格 cell、表题、表注调用共享文本路径。
- `app/domains/document_jobs/execution.py` — 线上 Template Version 解析和 renderer 调用。
- `resources/template_configs/datasheet_template_v2.yaml` — 当前 default@2 样式值。
- `resources/template_configs/templates_manifest.yaml` — default@2 的 DOCX/YAML 绑定。
- `tests/test_conversion_sandbox_dev_tools.py` — 本地 formal adapter 测试，当前只证明可打开/完整性，不证明省略参数时字体生效。
- `tests/test_document_ir_word_renderer_layout.py` — 显式 config 的四槽、TOC、页眉页脚测试。
- `.trellis/spec/backend/template-layout-configuration.md` — schema、版本、默认 v2 和字体安装责任合同。
- `.trellis/spec/backend/word-generation-rules.md` — STYLE-001/STYLE-003 正式输出合同。

## Related Specs

- `.trellis/spec/backend/template-layout-configuration.md:37-65` — 多文种字体、seed 不可变性、本地内置 v2。
- `.trellis/spec/backend/word-generation-rules.md:442-476` — 模板配置优先与四字体槽输出。
- `.trellis/spec/backend/quality-guidelines.md:33-52` — Word 结构/视觉证据分层与 v2 seed hash。
- `.trellis/spec/backend/directory-structure.md:104-124` — 本地工具必须复现正式 renderer core。

## External References

- 当前 DOCX/IR 及 hash：见“当前 DOCX 的 OOXML 证据”。
- WPS Office 12.1.26055（build 26055）。
- 本机字体枚举：macOS font files + Homebrew fontconfig (`fc-list`/`fc-match`/`fc-scan`)；未查询网络资料。

## Caveats / Not Found

- 没有声称 WPS 的字体替换算法等同于 fontconfig；fontconfig 只证明精确家族名是否在系统字体集中可匹配，WPS 仍可能使用自己的内置字体或替换表。
- 没有在本研究中修改产品代码、任务计划或规范，也没有重新生成最终候选；显式 v2 配置对照只在内存中渲染并检查 OOXML。
- 当前配置没有 `math_font_name`，因此不能说公式已按正文 `western_font_name` 配置；它们明确继承 DOCX 的 `Cambria Math` 数学设置。
- `part_number/category` 在正式 DocumentIR renderer 中未消费；若用户要求首页型号/品类分别使用这两组样式，需要另行定义 IR 语义映射和验收，不应混入本次 CLI 默认配置修复。
