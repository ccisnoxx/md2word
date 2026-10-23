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
├── image_evidence.py
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

### 7.1 RND-503 图片行边界

`layout_plan.py` 的 `image-group/v1` 只消费最终 IR 的同页、源连续图片序列。不跨正文、页面或实际 section，不按图号、型号、语义或全页最近邻猜配，也不按 bbox 重排源块。页面尺寸和 bbox 必须有限、有效且同坐标系。

确认行需同时满足：共同纵向交集除以最大高度 ≥0.80；最小/最大高度 ≥0.80；中心纵向差除以最小高度 ≤0.10；顶边差除以页高 ≤0.015；源序与横坐标递增一致，横向不重叠，相邻间隔除以页宽 ≤0.08。先找成对纵向关系的连通分量，再证明整个分量；不能把 A/B、B/C 的关系传递成 A/B/C 成组。

IR-204 的 uncertain 或 evidence-only 外部题注关系否决并排；renderer 只消费最终 IR 已绑定的 caption/footnote，不承担重新绑定。普通多注释可以成组，普通单图不产生分组 warning。不确定保留源序单图及受控原因；缺失/损坏图片保留可见诊断和全部注释，同时仍由完整性门禁拒绝缺图成功件。

### 7.2 布局与注释

确认行写成固定宽度 1×N Word 原生布局表格，六类边框明确为 nil，每图一 cell；显式限定表格网格、cell 宽度和 margin。图片为 `wp:inline`，按真实资产比例和当前有效区域等比缩放，不使用 `wp:anchor`、浮动文本框或整页截图。页面/栏宽从 root context 显式传入，不能在 cell 中猜测 document.sections。

图片段明确归零首行/左右缩进，inline 的 distT/distB/distL/distR 也显式为零，并认证外层及图片 transform 的尺寸。实际 LibreOffice 26.2.4.2 对省略左右距离的导入会增加约 9.05pt 图距，令原本按 cell 内宽计算的图片裁切；单改表级边距或段对齐不能解决。四距归零的产物对照保持原尺寸并恢复完整边界。OOXML 子节点按安装库 schema 顺序写入，不能把结构属性追加到任意尾部。

每图完整 caption/footnote 按已接受来源/去重合同逐项独立成段，位于同 cell 图片下方；复用现有富文本、公式、SEQ/REF 和 bookmark。图到注释保持链、行 cantSplit 用于降低漂移，最后一注不强行绑定下一组。普通正文双栏继续 Word 原生 section columns，布局表格不承载正文或替代数据表。 普通混合栏内单图和不确定顺序图在图片源序与栏读序一致时继续原region逐图消费，保持列宽及一次消费；确认组才抽出为原子布局。源序冲突时保守按源序单图，不为栏序重排。布局表显式左对齐、零dxa缩进，认证direct/basedOn/默认表样式后的有效定位并拒绝exact行高；旧无直接定位属性但有效零缩进且left/center/right对齐的产物仍支持（缩进dxa按实际值；pct/auto按Word忽略值的零位移解释，nil按无宽解释；type省略按dxa、宽度省略按0；未知单位拒绝）。Word对非left对齐仍可能应用非零缩进，因此不按ISO通则直接豁免非零dxa，新writer默认left不成为旧产物硬条件。

### 7.3 冻结输入与结果恢复

`render_to_result()` 返回同次图片报告。写 DOM 前固定 `image-render-inputs/v1`：实际模板版本/hash、语言、已知投影版本、必要规范化符号格式规则及每个 span 的有效几何。配置和 hash 来自同一次实际读取；配置 owner 提供 bytes 解析入口并共享原校验，不再读取可变路径验证历史文件。 同一不确定span的成员确实跨不同section几何时，可选image_geometries按block_id仅保存相对首图geometry的差异，并由实际OOXML逐图认证；无此字段的旧报告仍按原span.geometry读取。该附加输入只在内部私有报告，不新增API/数据库列；兼容回退必须携带当前reader。

`image_evidence.py` 内聚报告和重验。expected 必须从原 IR 与冻结输入重算；实际 DOCX 独立提取 marker、cell、inline/关系资产 hash、逐项注释来源/投影和 section 几何。只在完整认证后把布局表从原生内容表计数中排除；总表格字段保留旧含义。纯图片布局表不构成可编辑数据表，伪造 marker 或总数相同不能绕过内容完整性。

图片行之间的实际 DOM 顺序也必须符合源计划；完整交换两行不能因各自内部内容正确而通过。资源/尺寸降级原因从实际资产/slot 独立核对，图片段不能夹带未登记正文。报告中的无效历史 bbox 使用稳定 JSON 安全投影，非有限坐标为 null，重验从源做同一投影，不修改 IR；正式 MinerU 对显式非法 bbox 仍前置失败。历史 raw JSON 的非有限数可保守渲染不等于 typed IR 经 Pydantic 转 null 后可重新读取，后者是原 IR 序列化边界，未在本任务扩展。私有快照模型/规则校验错误转受控消息，不能经 error/event 泄露原输入。

显示认证同时限定 cell 的 dxa 单位以及图片源矩形、填充矩形、内部坐标和旋转/翻转。原资产字节与外框尺寸未变仍可能在 OOXML 中裁去半幅图，因此不能只凭图片 SHA/extent 放行；缺省与显式零变换等价。

报告及最小冻结输入沿原 candidate descriptor/receipt 保存在授权内部文件 metadata，普通事件只投影有界 summary。legacy 发现、明确历史指针和 receipt 三恢复入口均按原文件 IR/模板/输入重验；明确历史指针允许原合同中的跨代复用。新字段缺失、损坏、未知版本或错绑不能降级旧 reader；无报告历史件保持原字段合同，不补写。legacy扫描即使全部图片证据与公式字段均缺失，也须读取实际文件检查新图片标记，并在选择/物化receipt前拒绝；不能只在后续恢复完成时再失败。真正无新marker的旧文件继续按旧合同恢复。正式登记失败沿 `quality_checking/render_failed`，恢复损坏沿 `uploading/oss_failed`。不改权限、CAS、generation、文件不可变、下载或发布规则。

### 7.4 回退与证据层级

生成构建身份 `grouped/v1` 和兼容回退构建 `single-only/v1` 随原输入冻结，不新增运行时 feature flag、任务参数或前端业务状态。已有新报告后，回退必须保留 reader、表格分类、冻结输入解释、三恢复入口及原公式/receipt 接线，只把生成侧切到既有单图 writer。开发差异基线 B0 不能作为产生新文件后的部署回退版本；B1 必须以实际源码指纹及恢复测试证明。

自动验证分为纯几何、正式 ZIP→IR→DOCX、OOXML/质量证据、三入口历史恢复与兼容回退；ZK7044 图5/6、24/25 的可靠合成边界与已授权去标识不确定样本分开记录。Microsoft Word 字段更新前后和实际部署预览仍是独立视觉验收，不能由 OOXML 或 LibreOffice 代签。当前执行结果、输入/源码/产物 hash 及待验项以 RND-503 子任务的实施验证记录为准。

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
    def render(self, docx: bytes, *, policy: PreviewPolicy) -> PreviewResult: ...
```

输出：

- preview PDF；
- 每页 PNG（可选）；
- 页数；
- 失败摘要。

在线主链路可配置 preview required；发布必须要求 preview 成功。

RND-504 在当前选定 receipt 物化、公式/图片原件认证之后、最终 completed CAS 之前接入预览。Provider 只消费 DOCX bytes 和策略，不进入 DocumentIR 语义，不调用 MinerU、翻译或 renderer。PDF/可选页面图及诊断 manifest 登记为独立不可变 Artifact，保留当前共享含 file_id 的对象键。默认 backend=disabled、required=false，不把未检查当作通过。

固定 `word-preview-exec/v1` 协议由受控绝对 launcher 和 hash 固定的批准 profile 执行；shell=False、最小环境、单次私有目录、有界预算、输入输出完整验证。真实引擎/解码器/字体、隔离和 Word 视觉仍是生产启用门；协议子进程通过不代表生产已可用。

可靠预览失败保留主 DOCX 供内部下载，自身质量贡献 blocked，禁止批准/发布；登记存储不可确认保持原 oss_failed，不能伪装普通预览失败后完成。登记阶段和 manifest 必须属于当前 attempt。内部单独重试采用原 job 锁和持久幂等账本，不改 generation/result，不重渲染 DOCX；成功只解除自身 blocker。当前预览失效时新 key 可有界恢复，历史 key 只重放历史。完整合同见 [WordPreviewProvider 与任务预览合同](../../.trellis/spec/backend/word-preview-contract.md)。本项不实现页映射/页级质量、公开预览 API、前端或发布 API，现有后端 publish enabled=false 保持。

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
