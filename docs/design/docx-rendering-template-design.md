---
doc_type: technical-design
status: target
component: docx-renderer-template
last_reviewed: 2026-10-03
---

# DOCX 原生渲染与模板设计

## 1. 目标

生成内容可编辑、结构正确、符合公司模板且可被质量检查的 DOCX。视觉接近 PDF 是目标之一，但不以牺牲可编辑性为代价。

## 2. 当前模块

```text
app/services/renderer/
├── layout_plan.py
├── word_renderer.py
├── text_renderer.py
├── table_renderer.py
├── image_renderer.py
├── semantic_text.py
├── template_config.py
├── evidence.py
└── docx_quality.py
```

目标是在现有模块上增量收口，不建立第二套 Renderer。

## 3. RenderPlan

在创建 Word 对象前生成确定性计划：

```text
RenderPlan
├── document metadata
├── sections[]
│   ├── orientation
│   ├── margins
│   ├── columns
│   ├── header/footer policy
│   └── block IDs
├── block render decisions[]
└── quality expectations
```

`RenderPlan` 不需要长期持久化，但应能输出 debug JSON。

## 4. 渲染模式

```text
native_heading
native_paragraph
native_list
native_table
inline_image
native_formula
noneditable_table_placeholder   # 仅 HTML 缺失异常
skip_margin_artifact
```

不允许正常 block 使用 `page_image`。

## 5. 文本

- 保留源 run 顺序；
- inline equation 在原位置生成 OMML/受控 run；
- 标题使用模板 style；
- 列表使用 numbering，不保留手工 `■/◆/-` 作为正文标记；
- 段落合并只发生在 DocumentIR 规范化阶段；
- Renderer 不推断技术语义。

## 6. 公式

优先级：

1. 支持的 LaTeX → OMML；
2. 简单变量 → Word run + 上下标；
3. 当前无法转换 → 原位置显示 `【公式降级，需复核】` 与逐字原式，生成 `formula_text_fallback` warning；本版本不新增图片引擎。

大表沿用既有展开几何；`docx_rules/table_expansion.py` 仅拥有共享内容投影，保留源 HTML 和重复出现的源坐标，渲染与公式库存使用同一投影，避免大表独立丢失上下标。

共享入口为 `app/conversion/docx_rules/formula.py`。支持子集必须完整消费输入；纯数字强公式正常登记；显式 group 的脚本基底保持完整。合法简单 `\tag{7}` 保留编号、`x^2+3` 仅对 `2` 上标、`\text{A B}` 保留空格。未知命令、畸形语法、不支持结构、无法安全归一化分别记录稳定 reason。合法 semantic sub/sup 内的 b/i/换行保留；畸形 HTML 及不能保真的嵌套数学组合整体原文降级，不能静默丢掉脚本。原式和已识别数学片段不经过术语替换，公式不得被翻译、改值或因失败删除。

正式调用 `render_to_result()` 一次取得 DOCX 与 `formula-render/v1` 报告；`render_to_bytes()` 保持兼容。源位置取自真实 block/field 的单次上下文，重复同式不靠 hash 猜位置。每次出现的源位置/哈希、bookmark、mode/reason 与写 DOM 前确定的 `formula-output/v1` 预期投影绑定，最终 OOXML 重建投影校验值、次序、上下标及数学结构。受控降级仅在匹配报告、可见提示与完整原式后豁免静默残留扫描；未登记 LaTeX 继续报告残留。

逐公式报告存于授权内部文件 metadata，普通事件只给 `formula_summary`，不展开原式或旧 `latex_residue_examples`。新报告在 legacy 扫描、明确历史主件及 receipt 恢复三入口均严格核验；无报告旧件保持原恢复合同，明确历史指针允许按原文件 IR 跨代复用。完成时仅从当前已选 receipt 合并质量摘要，不提升 pending/blocked，passed 遇降级只降为 warning，不自动批准或发布。

翻译准备排除明确 `<eq>` 数学子树，保留其它正文及原节点索引；其它数学必须被现有 Codec 完整保护，否则 Provider 前以内部码 `translation_formula_boundary_unprotected` 失败，顶层沿用 `translation_failed`。不改变 Codec 规则或覆盖同代已安装根计划。上线及回退前需排空相关旧任务或使用兼容执行器；不回写已发布件、历史报告或审计。

## 7. 图片

- 使用 MinerU 资产；
- 保持比例；
- 根据页面可用宽度缩放；
- 默认 inline；
- 并排图使用无边框布局表格；
- caption/footnote 独立段落；
- 禁用 Word 图片自动压缩（能控制时）；
- 记录 block→inline shape evidence。

## 8. 表格

由 `CanonicalTableGrid` 驱动；详细见表格设计。

Renderer 只负责：

- 创建 Word 网格；
- 应用合并；
- 填充 run；
- 样式、宽度、横向节和分页；
- 生成 evidence。

## 9. 页面和 Section

### 横向页

当表格按模板最小字号仍无法容纳时：

- 表前建立横向 section；
- 表后恢复纵向；
- 页眉页脚继承策略由模板控制。

### 双栏

- 仅在 DocumentIR 有足够 column hint/region 证据时使用 Word section columns；
- 复杂并排内容可使用布局表格；
- 不用空格和文本框模拟。

### 分页

- 标题 `keep_with_next`；
- caption 与对象保持；
- 表头重复；
- 关键小表尽量不拆；
- 长表允许自然分页；
- 不用大量空行控制分页。

## 10. 公司模板

模板版本由：

```text
template.docx
layout_config
render_policy
snapshot metadata
```

组成。

### 样式语义

```text
document_title
heading_1/2/3
normal
list
figure_caption
table_caption
table_context
table_header
table_content
table_note
warning_placeholder
```

配置中心可编辑白名单字段，Renderer 不直接读取前端表单。

## 11. 页眉页脚

默认：

- 源 PDF 重复页眉页脚不进入正文；
- 公司模板提供页眉页脚；
- 源型号、版本和发布日期可写入封面或文档属性；
- Word 页码使用 field；
- 不能把源页码作为正文段落。

## 12. Document Properties

建议写入：

- title；
- subject；
- company；
- source file hash；
- job ID；
- mode；
- template version；
- renderer version；
- generation time。

不写 API Key、对象路径或完整 Prompt。

## 13. Evidence

渲染后至少输出：

```text
paragraph_count
heading_count
numbering_count
table_count/table_shapes
image_count
formula_count
landscape_section_count
block_render_map
quality_flags
```

`block_render_map` 用于三栏审核定位，可以存为独立 JSON Artifact，不必写入 DocumentIR 核心。

## 14. Word 预览

定义可替换端口：

```python
class WordPreviewProvider(Protocol):
    def render(self, docx: bytes) -> PreviewResult: ...
```

输出：

- preview PDF；
- 每页 PNG（可选）；
- 页数；
- 失败摘要。

在线主链路可配置 preview required；发布必须要求 preview 成功。

## 15. 质量目标

- DOCX 可打开；
- 正文可搜索；
- 表格可编辑；
- 图片存在；
- 无整页截图正文；
- 无明显 LaTeX 残留；
- 标题和列表使用原生结构；
- 宽表可读；
- blocked 占位清晰可见但不可发布。

## 16. 测试

- OOXML 单元测试；
- Word 打开性；
- 标题、编号、表格、图片和公式计数；
- 横向 section；
- 模板 style 存在与 fallback；
- Microsoft Word 人工验收；
- 现有 OPA228 和 ZK7044 回归。
