# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

### DOCX 原生结构

- DocumentIR 语义明确时，正式 Word 渲染器应使用 Word 原生结构：分节/分栏、OMML、字段、书签、可编辑表格和 inline drawing；不得以无边框表格模拟双栏。
- 题注、目录和交叉引用的字段状态必须限定在单次 `render_to_bytes()`，不得存入可并发复用的 renderer 实例。
- 双栏结束应以 `CONTINUOUS` section 恢复单栏；同方向源页不得隐式写入分页符，方向变化才新建 `NEW_PAGE` section。空续表占位必须在 MinerU 输入边界合并，不得交给渲染器制造空正文页。
- 普通文字双栏使用一次 `w:cols` 和 column break；严格成对、题注数量可确定的纯图片网格使用单栏正文中的原生中心制表位和 inline drawing，避免 WPS 对逐行连续分节做栏平衡而拆页。两种路径都不得回退为布局表格。
- 页眉页脚沿用 Word 的标准分节继承，不复制 relationship；输入题注归属不明确时保留并报告，不在渲染器猜测重配。

### MinerU 最终推广封底过滤

- 内容策略归一化必须发生在 MinerU 输入到 DocumentIR/PageData 的共享边界，不得在 renderer 隐藏页面或资产；正式路径命中后须同步排除该页的 pages、blocks、assets/image_assets，并写入 `final_promotional_page_filtered:<page_index>`。
- 只检查最后物理源页：优先使用 `layout/middle` 的 `pdf_info` 最大页号，缺失时才回退到 raw blocks 最大页号。倒数第二页及更早页面即使含推广文案也必须保留。
- 只有“明确微信/扫码/小程序行动组合 + 可解析的 `image/figure` 资产路径 + 无实质正文结构”全部成立才过滤。HTML 表格、公式、列表、编号标题、编号图表题注、长篇技术或法律正文任一出现时保留整页；不得新增页码/产品特例、模糊评分、二维码解码依赖或第二套关键词规则。
- 正式 DocumentIR 与仍受支持的兼容输入适配必须调用同一纯判定；变更需覆盖扁平 legacy、嵌套 v2、物理空尾页、无资产和合法技术/法律封底负样本。

### 已发布模板 seed 不可变性

- manifest 已登记并进入生产的模板版本，其版本号、资源路径和文件字节不可原地修改；新增可选 schema 字段应依靠模型默认值兼容旧 YAML，需要新的非默认内容时创建新版本。
- 每个 published bundled seed 都必须有固定 SHA-256 回归；当前 `default@2` 的 `datasheet_template_v2.yaml` 固定为 `132d0bb76e71c807912031199e894dfc0e3d50bd7534180f8ceaba7a5fa20b4d`。发布门禁不得只锁定 v1 而遗漏当前默认版本。
- hash 不匹配必须继续失败关闭；不得更新生产数据库 hash、放松读取校验或增加备用路径来掩盖 seed 被改写。

## Scenario: MinerU v2 公式输入与 TeX 预处理

### 1. Scope / Trigger

- 修改 MinerU 公式提取、普通文本/内联公式归一化或 OMML 解析前预处理时，必须同时保护 v2 元数据边界和普通正文反斜杠。

### 2. Signatures

- `MinerUToDocumentIRService._formula_text(raw_block: dict[str, Any]) -> str | None`
- `collapse_double_escaped_tex_commands(text: str) -> str`

### 3. Contracts

- v2 `equation_interline.content` 只接受非空字符串 `math_content` 作为公式正文；`math_type`、`image_source` 和其他元数据不得参与文本回退。
- v2 形状存在但 `math_content` 缺失、为空或类型非法时返回 `None`，不得再递归扫描 `content`。
- 双反斜杠只对 `GREEK_AND_TEXT_COMMANDS` 或 `STRUCTURAL_TEX_COMMANDS` 中已支持的 TeX 命令收敛；未知命令和普通 UNC 路径保持原字节语义。

### 4. Validation & Error Matrix

- `content.math_content` 为非空字符串 -> 去除首尾空白后进入 DocumentIR `latex`。
- `content.math_content` 缺失、为空或非字符串 -> 返回 `None`，不从元数据推导正文。
- `\\\\frac`、`\\\\Omega` 等已支持双转义命令 -> 收敛为单个 TeX 控制符后解析。
- `\\\\server\\datasheet` 或未知双转义控制词 -> 原样保留。

### 5. Good/Base/Bad Cases

- Good：`{"math_content": "\\\\frac{1}{2}", "math_type": "latex"}` 只产生分式正文。
- Base：legacy block 继续按顶层 `latex/math_content/equation_content/text/content` 明确字段回退。
- Bad：把整个 v2 `content` 递归拼接成 `"\\frac{1}{2} latex images/a.png"`，或用任意字母控制词正则改写 UNC 路径。

### 6. Tests Required

- MinerU converter：断言合法 v2 `math_content` 精确保真，缺失/非法值不会生成 `latex`、`math_type` 或图片路径正文。
- 文本归一化：同时覆盖已支持双转义 TeX 命令和 `\\\\server\\datasheet` 保真。
- Renderer：公式 block、inline 和 HTML table cell 共享 OMML 入口，并断言未知/畸形输入仍可见且产生既有 LaTeX residue 质量证据。

### 7. Wrong vs Correct

#### Wrong

```python
formula = collect_all_strings(raw_block["content"])
text = re.sub(r"\\\\\\\\([A-Za-z]+)", r"\\\\\1", text)
```

#### Correct

```python
formula = content.get("math_content")
if not isinstance(formula, str):
    return None

if command in GREEK_AND_TEXT_COMMANDS or command in STRUCTURAL_TEX_COMMANDS:
    return f"\\\\{command}"
```

## Scenario: 模板页脚左右静态文字

### 1. Scope / Trigger

- 当模板配置需要左侧版本号、右侧官网域名，并可选居中页码时，沿用现有 `footer` 配置、字段 schema、模板管理 API 和前端通用表单链。

### 2. Signatures

- `TemplateFooterConfig.left_text: str = ""`
- `TemplateFooterConfig.right_text: str = ""`
- 既有 `enabled: bool`、`show_page_number: bool` 与字体字段保持不变；不新增 endpoint、数据库字段或 DocumentIR 字段。

### 3. Contracts

- `enabled=false`：保留模板自带页脚。
- `enabled=true` 且左右文字至少一项非空：显式自定义页脚优先于 MinerU 页脚装饰块；生成单段落，依次写左文字、相对 margin 的居中 `w:ptab`、可选原生 `PAGE` 域、相对 margin 的右对齐 `w:ptab`、右文字。
- 左右文字都是空字符串：保留既有 `enabled/alignment/show_page_number` 行为。
- 静态文字不自动提取、不自动转换为超链接；后续 section 使用 Word 标准页脚继承。

### 4. Validation & Error Matrix

- 缺失 `left_text/right_text` → 由模型默认成空字符串，旧配置继续可读。
- 字段不是字符串或超过模型既有限制 → 由 Pydantic/template-config 边界返回现有校验错误，不在渲染器猜测转换。
- `show_page_number=false` → 不生成 `PAGE` 域，但仍保留左右对齐位置。
- MinerU 同时提供页脚块 → 显式左右文字胜出，源页脚块不得覆盖。

### 5. Good/Base/Bad Cases

- Good：`enabled=true, left_text="版本号：V1.1", right_text="www.example.com"`，WPS 中左/中/右分别对齐且页码可更新。
- Base：旧 YAML 没有两个新字段，加载结果为空字符串并保持模板页脚。
- Bad：用 1×3 表格实现页脚，或每个 section 复制 footer relationship。

### 6. Tests Required

- 模型/schema：断言默认值、字段元数据和 draft/published 配置往返。
- renderer：断言 footer XML 含两个 `w:ptab`、可选复合 `PAGE` 域、左右文字且不含 `w:tbl`；断言显式自定义不被源装饰覆盖。
- 集成：WPS 检查左右对齐和页码；LibreOffice 用于正文分页回归，但其对 `w:ptab relativeTo="margin"` 的视觉定位不能替代 WPS/Word 验收。

### 7. Wrong vs Correct

#### Wrong

```xml
<w:tbl><!-- 左/中/右布局单元格 --></w:tbl>
```

#### Correct

```xml
<w:p>
  <w:r><w:t>版本号：V1.1</w:t></w:r>
  <w:r><w:ptab w:alignment="center" w:relativeTo="margin"/></w:r>
  <!-- PAGE complex field -->
  <w:r><w:ptab w:alignment="right" w:relativeTo="margin"/></w:r>
  <w:r><w:t>www.example.com</w:t></w:r>
</w:p>
```

---

## Testing Requirements

### DOCX 渲染验证

- 定向测试同时断言稳定 OOXML 结构和可见文本，不只断言 `python-docx` 的 `paragraph.text`。
- 涉及 section、column、page break、纯图片网格或页眉页脚的改动，须经 LibreOffice→PDF→PNG 检查目标页和相邻页，并在 WPS/Word 检查分栏平衡与原生对齐制表位；真样本验收还应排除页眉页脚后核对正文空白页、页数与关键内容所在页。
- 图片质量验收至少核对媒体原字节、显示尺寸和有效 DPI，并确认 `w:doNotAutoCompressPictures`。

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
