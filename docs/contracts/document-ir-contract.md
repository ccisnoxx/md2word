---
doc_type: data-contract
status: target-compatible-extension
contract: document-ir
current_schema: document-ir/v2
last_reviewed: 2026-10-23
---

# DocumentIR 合同

## 1. 设计目的

DocumentIR 是 MinerU 与翻译、DOCX 渲染、QA 之间的稳定内部合同。

原则：

- 保存文档语义和来源事实；
- 不保存数据库连接、Provider secret 或 Word 对象；
- Parser facts 与 Word 渲染决策分离；
- 结构字段在翻译前后保持不变；
- 可以序列化为 JSON Artifact；
- 老版本读取端对新增字段采用安全默认值。

## 2. 当前 v2 根结构

```json
{
  "schema_version": "document-ir/v2",
  "metadata": {},
  "pages": [],
  "blocks": [],
  "assets": [],
  "quality_flags": []
}
```

## 3. Metadata

现有字段：

```text
job_id
source_file_id
document_language
parser
parser_version
source_block_count
source_type_counts
```

建议追加：

```text
source_content_sha256
normalizer_version
translation_mode
language_pair
source_document_ir_sha256
```

新增字段必须可选，避免破坏 v2 历史 Artifact。

### IR-201 源产物验证报告

`metadata.mineru_validation` 是可选的 `mineru-artifact-validation/v1` 报告。缺省为 `null`；历史 v1/v2 没有该字段表示没有这份验证证据，不能投影成“验证通过”。不为新增报告升级 v3，也不回填或重新序列化历史 IR。execution 另以可选 metadata.mineru_validation_input 保存原始 ZIP file ID/hash 与 retry_count，纯报告本身不依赖任务/数据库。

报告记录原始结果包和选中 content list 的哈希、原始节点 inventory、结构化 warnings/blockers、表格分类及有界问题定位。它描述语义规范化前的输入；既有 `source_block_count/source_type_counts` 仍描述完成末页过滤、题注处理和空续页归并后的源清单，两者不能互相替代。

validator/policy v2 增加 `complete`（旧报告默认兼容），报告超限不能生成可转换 IR；已归一化空续表的原始问题保留，并通过有效 inventory 和 normalization evidence 与未解决问题区分。读取历史 v1 报告不触发重验证、回填或状态提升。

当前 validator v3 在上述兼容报告中补充精确过滤来源，以及空续表的目标、规则和原因回执；原始路径安全检查先于过滤，保留对象的必需图片和不可消费 HTML 在 IR 构建前完成门禁。新增细节不改变 schema v1、policy v2 或 DocumentIR v2，历史报告仍保持原样。

源 locator 使用原始 JSON Pointer、页号、页内索引和全局索引；规范化后的 `block_XXXX` 不是原始节点索引。块 metadata 可保存 `mineru_source` 追溯本块原始位置，IR-205 的跨页 `source_spans` 和 logical table group 是下述独立源事实扩展，不改变本报告的预算或计数。

翻译只改变允许的语言字段，必须保留源报告与来源关联。`severity=blocker` 是质量事实；`stops_conversion` 才描述当前输入边界是否必须停止。它不等于任务质量/复核/交付状态，也不能给前端提供自行批准或发布的依据。完整的输入分级与路径合同见 [MinerU 产物合同](mineru-artifact-contract.md)。

### IR-205 逻辑表格与原始 fragment

`metadata.logical_table_groups_version` 可选，缺省为 `null`；新转换写 `logical-table-groups/v1`。`metadata.logical_table_groups` 缺省为空列表。继续使用 DocumentIR v2，不新增 block type、数据库字段、公开 API 或独立 Artifact 类型。 `logical_table_group_counts` 保存group_count/fragment_count/normalized_empty_fragment_count/uncertain_count；它是可校验的源账本摘要，不替代有效block计数。版本缺失表示没有该证据，不猜造历史来源，不回填或覆写历史 IR。

每组有稳定 `logical_group_id`、有序 `fragments`、`continuation_relations` 和诊断。fragment 保存稳定 ID、可信 JSON Pointer/原始全局及页内索引/page/bbox、原始 JSON、副本中 HTML 的定位/状态/hash、主 block/归并 owner、header signature 和 repeated-header hint。`raw_fragment` 保存原始字段及空白，`raw_html` 从原始副本读取；消费 HTML 的清理结果及有效 block 的 `html` 不能冒充 raw HTML。原始输入自带的 `_mineru_source` 同名字段仍保存在副本，但定位HTML及比较题注/脚注必须使用可信locator覆盖后的消费者视图，不能将这些原字段当续表证据。源字段缺失、空串/空白和非空 HTML 分开保存，不能从内容缺失猜造行列或 fragment。

ID 对同一 content list hash、源 Pointer 和算法版本稳定，不依赖任务 UUID、时间或译文。输入修订或算法版本变化可改变身份。page/bbox 缺失如实保留未知，坐标使用 MinerU 空间，不按 bbox 重排。table 类型集合复用既有验证/分类规则，支持有效的 legacy 载体；原始副本从同一验证 payload 精确取回，不信任输入自带内部 locator。

两种关系必须区分：`normalized_empty_placeholder` 只表示 IR-201 严格空续页实际已被归并；`verified_continuation` 表示本版保守规则确认的非空续表。后者要求相邻页和数组 body 边界、可信几何、可解释列统计、没有新表/正文冲突，并有明确同表续标记或精确表头与明确序号连续的正证据。相同列名本身不是充分依据。未支持的复合编号、字母/括号后缀、单题注多个表号均不能按整数前缀确认同表，也不能回落到表头序号路径绕过矛盾。重复表头仅保存 hint，不能删除源行或改变 Word 表格。

每个有效 table block 的 metadata 保存 `logical_group_id/table_fragment_id/source_spans`，spans只含本块和原规则归并到它的空片段；全组来源通过 fragments 读取。有效 blocks、ID/order/layout/HTML、`source_block_count/source_type_counts` 以及主块→Word Table 对账保持原合同。空 fragment 不重新进入渲染主块，原始片段集合另行一一对账。

有候选而证据不足时保持独立组，`table_continuation_uncertain:<fragment_id>` 是非致命诊断，不提升质量/复核/交付资格。孤立空表、有正文空表、非空坏 HTML 继续失败关闭；内部 blocked 占位与 Word 合并渲染留给后续任务。重读时 verified 关系必须连接源正文中的直接前驱、保持相邻页，并按原始源事实核对对应正证据；空项关系仍按receipt指向owner，不强制串成链。组首必须关联有效主block；归一化空片必须通过同组真实owner的receipt关系进入组，不允许独立空片组，即使计数与owner spans同步修改也应拒绝；多空片星状关系仍合法。源账本或关联损坏显式失败，线上沿既有 `ir_converting/document_ir_failed` 映射。

翻译必须保留全部源组、raw JSON/HTML、signature、关系和 spans，不向 Provider 发源副本，不随目标 block.html 重算。普通日志、事件和 API 质量摘要不透传全文；沿用原 IR 文件授权、保留和不可变边界。旧 reader 可忽略新字段渲染，但不能保证其重新序列化保留未知字段，禁止用旧 reader 覆写新 IR。启用采用版本化 metadata，无新增环境开关或任务快照；回滚停止新写入并保留读兼容和历史证据。

## 4. Page

```json
{
  "index": 0,
  "width": 1000,
  "height": 1000,
  "coordinate_unit": "mineru",
  "metadata": {}
}
```

建议 metadata 保存：

- source page number；
- page orientation hint；
- column regions；
- page-level quality flags。

## 5. Block

### 5.1 当前类型

```text
heading
paragraph
table
image
list
formula
```

### 5.2 当前字段

```text
id
type
order
page_index
text
level
html
latex
list_items
asset_ref
layout
captions
footnotes
metadata
```

### 5.3 Layout

```text
page_index
bbox
role: body/page_header/page_footer/page_number
source_index
continuation_heights
column_hint
```

### 5.4 建议的兼容扩展

不新增 block type，优先扩展 metadata：

```json
{
  "metadata": {
    "source_type": "table",
    "source_block_id": "...",
    "source_spans": [
      {"page_index": 14, "bbox": [42,638,942,917]}
    ],
    "logical_group_id": "table_group_001",
    "reference_asset_refs": ["asset_table_ref_001"],
    "quality_flags": [],
    "content_sha256": "..."
  }
}
```

当 metadata 过大或包含复杂 grid 时，使用独立 Artifact，并只在 block metadata 保存 `table_model_file_id/table_model_sha256`。

## 6. Asset

当前只支持 `kind=image`。目标继续保持简单：

```json
{
  "id": "asset_block_001",
  "kind": "image",
  "source_path": "images/x.jpg",
  "file_id": "...",
  "object_key": "...",
  "mime_type": "image/jpeg",
  "checksum_sha256": "..."
}
```

表格参考图也作为 image asset，但通过 block metadata 指明 `asset_role=table_reference`。

## 7. 翻译不变量

翻译服务可以修改：

- `block.text`；
- `block.list_items`；
- `block.html` 内可翻译文本节点；
- `block.captions`；
- `block.footnotes`。

翻译服务不得修改：

- schema version；
- pages；
- block ID、类型、order、page index；
- layout；
- table HTML 标签、行列和 span；
- asset 引用；
- source metadata；
- 公式和受保护 Token。

## 8. Translation Unit Contract

```json
{
  "id": "block_0100:table:r3:c5:run0",
  "text": "Typical value measured at {{PH_001}}",
  "kind": "table_cell",
  "context": {
    "section_title": "Electrical Characteristics",
    "table_caption": "Supply Voltage and Power Consumption",
    "row_header": "VCC2_OUT",
    "column_header": "Test Conditions/Comments"
  }
}
```

Provider 输出只返回：

```json
{"id":"...","text":"典型值在 {{PH_001}} 条件下测得"}
```

`kind/context` 不写回 Provider 输出。

## 9. CanonicalTableGrid（TAB-301）

独立数据模型位于 `app/services/tables/models.py`，代码类型为 `TableGrid`，schema 为必需的 `canonical-table/v1`。当前没有生产 parser/translation/renderer 接线，没有新 Artifact 注册或 DocumentIR 字段；既有 v1/v2 继续读取 block.html，无 Grid 不报错、不隐式构建或回填。后续构建、质量和 Word 接线分别由 TAB-302/303/304 等任务承担。

### 9.1 字段与来源

| 模型 | 字段 |
|---|---|
| TableGrid | schema_version、table_id、source_content_sha256、raw_html_sha256、rows、columns、source_fragments、cells、header_rows=[]、quality_flags=[]。 |
| TableSourceFragment | fragment_id、source_span（复用 SourceSpan）、html_state、raw_html、raw_html_sha256、repeated_header_hint（可选，复用既有类型）。 |
| TableCell | id、source_fragment_id、source_row_index、source_cell_index、row、column、rowspan、colspan、is_header、runs、content_sha256、quality_flags=[]。 |
| CellRun | id、source_run_index、type、source、target=null、bold=false、italic=false。 |
| TableQualityFlag | 有界机器 code、severity=warning/blocker，可选 fragment_id/cell_id/run_id，引用须存在且从属关系一致。 |

source_fragments 为非空有序来源快照，只从通过上游 DocumentIR 验证的 TableFragment 投影；SourceSpan 和 hint 不反向写回。完整 raw_fragment、归并 receipt 和关系仍由 IR-205 唯一管理。raw_html 永久保留逐字原文，不以 block.html、规范化 HTML、译文或 hash 代替；missing 为 null/null，empty 保留空串或纯空白及其真实 hash，present 为非空白字符串。

cell 的源行/cell 序号与网格 row/column 分离；span 为严格正整数，bool/字符串/浮点不能伪装为整数。每个 cell 记录一次，不持久化第二份 occupancy。不同来源 cell 可有同一锚点，正 span 尾端越界保留待诊断，不能裁切或覆盖内容；碰撞/越界质量检测不在 TAB-301。维度任一为零时 cells 为空。header_rows 有序、唯一且在声明维度内；is_header 为显式来源事实，不自动把首行当表头。

run 顺序类型为 text/protected_token/formula/superscript/subscript/line_break；仅 text 可有 target，其他类型保持原文与顺序，line_break 保存换行。formula 保存 LaTeX/数学源文本。bold/italic 是通用语义，不存 Word Run、OMML、样式、数据库或 Provider 对象。

### 9.2 稳定身份与哈希

令 C(x) 为 UTF-8 编码的 `json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`，H(x) 为 C(x) 的完整小写 SHA-256。

- table_id 原样复用 LogicalTableGroup.logical_group_id；source_content_sha256 继承报告 content_list_sha256，不复制上游私有身份算法。
- cell ID 为 `table-cell:` + H(["table-cell/v1", fragment_id, source_row_index, source_cell_index])。
- run ID 为 `table-run:` + H(["table-run/v1", cell_id, source_run_index])。
- source 序号从 0 开始，由后续 builder 提供；仅改 target、网格坐标或 span 不改变 ID。不同源修订可能改变上游 fragment ID，不承诺跨源修订追踪。
- 每片 raw_html_sha256 对原字符串 UTF-8 字节计算；根同名字段为 H(["table-raw-html-set/v1", [[fragment_id, html_state, raw_html_sha256], ...]])，单片也使用集合规则，不能当单一 HTML 的字节 hash。
- cell.content_sha256 为 H(["table-cell-content/v1", [[run.type, run.source, run.bold, run.italic], ...]])；不含 target、坐标、span、flags。源文本/marks/顺序变化须更新，译文变化只改变完整 Grid 内容 hash。

ID/hash 只保证模型内部一致性，不是原包真实性签名或访问授权。原始来源真实性仍由上游已验证 IR 保证。

### 9.3 读取、验证和失败

使用 Pydantic model_validate/model_validate_json 读取，model_dump(mode="json") 或 model_dump_json 输出；显式版本及必需字段不能省略，可选 header/flags/target/marks 有安全默认值。没有历史 Grid v0，不引入猜测迁移器。新模型 extra=forbid，缺/未知版本、非法 span/标量、重复身份/源位置、悬空引用、错误 hash 或非 text target 均显式拒绝。未知字段不得被丢弃后伪装成兼容成功。

模型 flags 不等同任务 quality_status；空 flags 不能证明 passed/可发布。模型可实例化不代表几何/内容质量已经通过。旧 v1/v2 的无 Grid 路径与 IR-205 原始来源账本保持；禁止旧 typed reader 回写覆盖含新数据的 Artifact。

自由 source/target 和来源定位/hint 字符串必须可编码为 UTF-8，孤立 surrogate 在模型验证时拒绝，不能推迟到 JSON 输出失败。安全诊断省略 input/context，只使用固定原因和字段/索引；任意字符串或非字符串 extra/invalid_key 定位统一为 __extra__，不回显用户键；不把完整 ValidationError/HTML/源译文写入日志、事件、API 摘要或 Provider。读取没有 I/O/网络/HTML 执行。无新 HTTP 错误码、状态机、权限、DDL、配置、generation 或事务；没有 feature flag 和生产写入，回滚撤回独立模型增量并保留历史来源。

## 10. 完整性证据

### 源 → IR

- source block count；
- source type counts；
- image asset coverage；
- table HTML coverage；
- formula coverage。

### 源 IR → 目标 IR

- block count/type/order；
- page/layout；
- asset refs；
- table DOM structure；
- translation item IDs；
- protected Tokens。

### IR → DOCX

- heading/list/table/image/formula counts；
- editable content；
- table shapes；
- image count；
- quality flags。

## 11. 版本演进

### 继续使用 v2 的条件

- 只增加可选 metadata；
- 老 reader 可以忽略新字段；
- block 类型和既有字段语义不变。

### 升级 v3 的条件

任一发生：

- 修改已有字段语义；
- 新增必须字段；
- 将 table model 内嵌为强制结构；
- 改变 order/page/layout 的解释；
- 旧 Reader 无法安全读取。

在没有上述必要性前，不为“版本看起来更新”而创建 v3。

## 12. 序列化和哈希

- UTF-8；
- JSON key 稳定排序用于内容哈希；
- 不把临时绝对路径写入 Artifact；
- 时间字段采用 ISO 8601 UTC；
- Artifact metadata 记录 schema version 和 SHA-256；
- 翻译后的 IR 保存源 IR 哈希。

## 13. IR-204 可选题注证据

DocumentIR继续使用v2。主源块可选metadata.caption_reconciliation保存caption-reconciliation/v1版本回执：本块原始caption值/字段locator和逻辑组、最终绑定的来源片段与donor/target、规则和受控原因，区分unchanged/rebound/evidence_only/uncertain。没有新字段的历史v1/v2照常读取；不回填或重写历史Artifact，不升级v3。

原始证据按源owner只保存一次，目标引用来源。独立paragraph的evidence-only不新增可见caption或翻译单元，保持源段落ID/order/text/layout。table_context派生paragraph不复制主块题注原文/回执。本任务保留现有编排：派生条件paragraph→主块表题→原生表体→脚注；验收要求条件和真表题均在表前、脚注在表后，不另改renderer布局。renderer evidence只聚合版本、status/reason计数和有界ID/locator，不包含原文，省略数量必须明示。

不确定关系在document.quality_flags中去重追加caption_binding_uncertain，不直接加入blocking_quality_flags，不自动批准/发布或改变下载权。拟自动修复的内容必须守恒且片段唯一消费；确定性损坏以既有DocumentIntegrityError拒绝输出，并保留IR201验证报告/输入关联，不能静默改为uncertainty继续。

处理发生在翻译单元ID提取前；translation保持来源metadata，不在已有generation内重新拆分。没有新数据库字段、迁移、OpenAPI schema、权限或前端状态机。原始caption可能含客户正文，只按既有Artifact授权边界访问。

### 回执字段和摘要

`reconcile_captions(raw_blocks)` 返回与保留源块索引对齐的结果。`caption_reconciliation` 的具体字段为：

- `rule_version`=`caption-reconciliation/v1`；`status` 为 unchanged/rebound/evidence_only/uncertain。
- `originals` 为 `{json_pointer,value,groups}` 数组，`value` 保留原始字符串或rich值，`groups`是原逻辑组pointer。原无题注目标为 `[]`。
- `bindings` 和可选 `candidates` 包含 source_locator、donor_block_id、target_block_id、label/number、rule_id、reason/reasons、evidence_only。真正消费的题注片段另有 group_pointer、source_spans（JSON pointer与原串start/end半开区间）。这些是caption片段坐标，不是跨页block source_spans。
- `reasons` 是去重的受控机器值；成功组有稳定group_id，完整members只存组锚点。

纯结果中的donor_index/target_index仅用于转换内部，converter映射成最终稳定block ID后持久化。renderer摘要中status/reason与binding/candidate总数独立统计；examples与relation_examples各至多40条，分别明示omitted数量，禁止投影originals、标题或rich原文。历史IR缺少此证据表示没有该项证据，不投影为修复通过。
