---
doc_type: technical-design
status: target
component: table-pipeline
last_reviewed: 2026-10-23
---

# 表格处理设计

## 1. 目标

表格处理必须同时满足：

- HTML 是可编辑主输入；
- MinerU 参考图用于质量核对；
- `rowspan/colspan` 尽量完整保留；
- 表格文本可翻译、做术语和技术 Token 检查；
- 结构失真时仍生成可编辑表格；
- 严重错误通过质量状态阻止发布，而不是自动改成图片。

## 2. 当前实现基线

当前代码已有：

- `app/conversion/runtime/table_html_parser.py`：将 HTML 解析为 `HtmlTable/HtmlCell`；
- `app/services/renderer/table_renderer.py`：创建 Word Table、处理 `rowspan/colspan`、caption 和 footnote；
- 大表超过行数或 HTML 长度阈值时，会展开跨行跨列合并；
- `docx_quality.py`：提取表格数、形状、表头行、不可拆行等 OOXML 证据。
- IR-201 在正式 MinerU→DocumentIR 前用 `artifact_validator.py` 对 HTML 基本可消费性和参考图安全作四分类，输出结构化报告；有效 HTML 仍走同一 Word 原生表格 renderer。报告单独进入 IR/事件/renderer evidence，不是 CanonicalTableGrid 或表格质量状态机。

空/坏 HTML 的质量 blocker 不自动改成执行 fatal；既有空续页归并和内容完整性检查继续决定当前链路能否生成。可确定续页保留原始缺失事实，孤立/含正文空表继续失败关闭；当前没有实现 TAB-306 的占位 DOCX、source PDF 裁图或统一 blocked 下载/发布状态。分类与分级的当前字段见 [MinerU 产物合同](../contracts/mineru-artifact-contract.md#10-ir-201-验证报告与执行边界)。

TAB-301 增加 `services/tables/models.py` 的版本化独立 Grid/cell/run/source/quality 合同及 JSON/ID/hash 校验；它尚未接入生产流程。完整模型字段、身份与逐片/集合 hash 定义由 [DocumentIR 合同 §9](../contracts/document-ir-contract.md#9-canonicaltablegridtab-301) 管理。

主要差距：

1. parser 只有行和 cell，没有确定性的二维占位网格；
2. 大表展开会丢失合并语义，不符合目标；
3. 没有系统化的结构质量检查和表格级状态；
4. IR-205 增加逻辑组和原始 fragment 元数据，尚不合并 Word 渲染；
5. table reference image 没有成为明确的一等 QA Artifact；
6. HTML 为空时的占位和 blocked 状态需要统一合同。

## 3. 目标流水线

```mermaid
flowchart LR
  A[Raw MinerU Table] --> B[Raw HTML/Reference Asset 保存]
  B --> C[HTML Normalize]
  C --> D[CanonicalTableGrid Build]
  D --> E[Structure Validation]
  E --> F[Translation Unit Extraction]
  F --> G[Target Runs Apply]
  G --> H[Word Native Table Render]
  H --> I[OOXML/Table Layout QA]
```

## 4. 模块边界与后续计划

```text
app/services/tables/
├── models.py                # TAB-301 独立模型合同
├── html_normalizer.py       # 非破坏性规范化
├── grid_builder.py          # rowspan/colspan 占位算法
├── validator.py             # 结构、内容和连续性检查
├── translation_units.py     # cell/run 翻译单元
└── evidence.py              # 参考图和质量报告
```

当前只有 models.py 由 TAB-301 提供；其他模块是后续目标，不是已实现能力。续表分组继续由 document_ir/logical_table_group.py 唯一管理。tables 单向复用 DocumentIR 的 SourceSpan/RepeatedHeaderHint，DocumentIR 不反向导入 tables，不建立平行转换流水线。

## 5. HTML 规范化

### 允许修复

- 标签大小写；
- 缺失的闭合标签（解析器可确定时）；
- `rowspan/colspan` 非法值归一为 1，并记录 flag；
- `<br>` 转逻辑换行；
- HTML entity 解码；
- 去除纯样式或危险标签；
- 保留 `<sup>/<sub>/<i>/<b>` 语义；
- 单元格内 `$...$` 识别为 formula run。

### 禁止自动修复

- 猜测新增/删除行列；
- 根据文本语义拆分粘连单元格；
- 修改数值；
- 自动把一行拆成多行；
- 根据截图推断合并关系。

原始 HTML 和规范化 HTML 都保存；原始内容不可覆盖。

## 6. CanonicalTableGrid 与后续算法

TAB-301 仅校验版本、类型、身份/源顺序、引用、run target 和 hash 自洽；不生成 occupancy，不做几何质量判断。零/负/非整数 span 拒绝；不同来源锚点冲突和正 span 尾端越界均无损保存，供后续 validator 诊断。空 flags 不代表质量通过；模型不包含 Word 对象，也不改变现有 renderer。

以下占位/冲突算法归 TAB-302/303 后续实现。

### 6.1 占位规则

按行顺序处理 HTML cell：

1. 找到当前行第一个未被先前 rowspan 占用的列；
2. 验证目标矩形未与已有 cell 冲突；
3. 记录 cell 起始坐标及跨度；
4. 将跨度覆盖区域标记为同一 owner；
5. 计算最大逻辑列数；
6. 行结束后记录缺口，但不自动补内容。

### 6.2 冲突

出现冲突时：

- 不静默覆盖；
- 记录 `table_span_collision`；
- 尽可能保留已解析 cell；
- `quality_status=blocked`；
- Renderer 可以生成诊断表格，但不得发布。

### 6.3 CellRun

```text
text
protected_token
formula
superscript
subscript
line_break
```

翻译只处理 `text` run；其他 run 保持原值和顺序。

## 7. 结构质量检查

### 阻断

- HTML 为空；
- 无法解析出任何行；
- span 冲突或越界导致内容覆盖；
- 逻辑列数为 0；
- 关键续表 fragment 缺失；
- Word 渲染后 cell 数/文本显著丢失。

### 严重警告，默认 blocked

- 异常连续数字：例如 `1510030150`；
- 单位重复拼接：例如 `pspsMHz`；
- 同一 cell 同时包含多个不同参数名称且数据列不足；
- 表头 6 列、数据行大量只占 1–2 列且无 span 解释；
- 跨页 fragment 列数变化；
- 地址或编号序列出现大范围跳跃。

### 一般警告

- 空单元格比例高；
- caption 缺失；
- 参考图缺失但 HTML 正常；
- 宽表需要横向页；
- 字号降至配置下限。

## 8. 异常数字和单位检测

检测只产生标记，不修改内容。

建议规则：

- 连续数字长度超过阈值，且相邻列/单位存在多值迹象；
- 单元格命中多个单位 token 且没有分隔符；
- 重复单位正则：`(ps|ns|MHz|GHz|mA|V){2,}`；
- 同一 cell 中出现多组 Min/Typ/Max 数值但表格只有一个数值列；
- 参数文本出现多个已知行标签连续拼接。

规则必须可配置，避免对寄存器长数字或合法料号误报。

## 9. 跨页表格

### 9.1 LogicalTableGroup（IR-205）

分组唯一 owner 为 `app/services/document_ir/logical_table_group.py`，模型由现有 DocumentIR models 管理，正式 converter 接线。存储使用 document-ir/v2 可选 metadata；不另建第二个 tables continuation owner。每个原始 table/placeholder 以 content list hash + JSON Pointer 稳定标识，原始 JSON/HTML、页/bbox、索引及关系保留；有效主 blocks 和 source inventory 与原渲染合同不变。

非空片段仅在数组 body 邻接、页码相邻、前页尾/后页顶和水平对齐、可靠列统计一致且没有新表号/普通独立 caption/正文隔断时作为候选。还须明确同表续标记，或精确显式表头及首列完整整数/十六进制 token 严格+1；不猜地址步长、表格语义或缺失内容。几何按可信页尺寸归一化，本版前表底边≥0.75H、后表顶边≤0.25H，水平端点差≤0.05W；未知或冲突不自动归组。

复用现有 HTML parser 提取显式 th 签名，不构造 CanonicalGrid；其 max_columns 不可当复杂 rowspan 表的权威逻辑列数。重复表头只记 start_row/row_count/signature hint，不删源行。相同列名不足以证明同表。

严格空续页复用 IR-201 source/target/rule/reason 回执，关系为 normalized_empty_placeholder，只说明既有归并事实。空项保留为 source fragment，不重新进入 Word blocks；原失败边界不变。确定非空关联为 verified_continuation。候选不确定时保留独立组，附 `table_continuation_uncertain:<fragment_id>` 与受控原因；不把警告当批准或发布依据。

测试分开记录表3多空续页、表9/10邻接独立表、表10空/缺片、表24多页/重复表头；合成合同、SC2167表3历史与真实授权样本分层，不能拿OPA228可打开代替四表真实验收。

### 9.2 Word 输出（TAB-305 后续目标）

逻辑续表尽量输出为一个 Word Table：

- caption 只输出一次；
- 删除完全重复的续页表头；
- 第一行设置重复表头；
- Word 自然分页；
- 必要时设置 `cantSplit`；
- 保留 fragment source spans 用于 QA 定位。

## 10. 大表策略

取消“超过阈值就展开合并关系”的默认行为。

目标顺序：

1. 使用 CanonicalTableGrid 保留 span；
2. 流式创建 Word 行，降低内存峰值；
3. 使用低层 OOXML `gridSpan/vMerge`；
4. 固定布局和列宽；
5. 横向节；
6. 紧凑表格样式；
7. 仍失败时任务失败或生成 blocked 诊断表格。

不得因为表格大就变成截图或无合并平铺。

## 11. 列宽

列宽来源按优先级：

1. 模板/表格类型显式规则；
2. header 语义（参数、Min、Typ、Max、单位、说明）；
3. 内容长度和数字列识别；
4. 等宽兜底。

输出必须：

- 明确 `tblGrid`；
- `autofit=false`；
- 单位/数值列窄，说明列宽；
- 表格字体不得低于模板下限；
- 超宽后切横向，不用图片替代。

## 12. 翻译

- 不翻译 HTML 字符串；
- 按 cell/run 抽取稳定 ID；
- 提供表题、行头、列头和章节上下文；
- 结构修复若只改 span，不使翻译失效；
- cell 内容变化由 `content_sha256` 决定是否重新翻译。

## 13. 缺失 HTML

```text
html == empty
→ 查找有效 reference image
→ 无 reference 时从 source PDF+bbox 裁图
→ Word 插入“非编辑表格占位”与明显 QA 注释
→ quality_status=blocked
→ 允许内部下载
→ publish 禁止
```

不得伪造空 Word 表格让任务看起来成功。

## 14. Word 渲染

- 先创建完整行列网格；
- 设置 `tblGrid`；
- 再写入文本和 run；
- 使用 `gridSpan/vMerge` 应用合并；
- 表头、分组行、普通 cell 使用不同样式；
- caption 在表前，footnote 在表后；
- 公式转 OMML；
- 记录 table ID 到 bookmark 或自定义 evidence map。

## 15. 测试

### 单元测试

- 规则/不规则 rowspan/colspan；
- 重叠和越界；
- `<sup>/<sub>/<br>`；
- 公式 run；
- 空 HTML；
- 1000+ 行流式渲染；
- 跨页 fragment 归并；
- 数字/单位粘连标记。

### 回归样本

- OPA228 宽表/长表；
- ZK7044 表 2 多行合并；
- ZK7044 表 6 粘连；
- ZK7044 表 10 缺失续页；
- ZK7044 表 24 多页寄存器映射。

### 验收

- HTML 存在时 Word table count 对应；
- 合并关系不因大表阈值展开；
- 表格可编辑；
- blocked 文档可下载但不可发布。

## 当前分支集成边界（RND-501）

本次候选从c56e128复用IR-201/205与TAB-301必要来源合同，不引入IR-206、TAB-302以后生产算法或RND-504。当前TR-402/403/406的翻译、完整性和批次生命周期以及CON-104下载/发布规则继续由既有owner管理；输入报告和Grid flags不提供批准/发布资格。实际验证以RND-501当前实施记录为准，历史验收不等于新候选已通过。
