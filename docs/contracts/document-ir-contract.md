---
doc_type: data-contract
status: target-compatible-extension
contract: document-ir
current_schema: document-ir/v2
last_reviewed: 2026-10-03
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

## 9. CanonicalTableGrid

建议作为独立模型：

```json
{
  "schema_version": "canonical-table/v1",
  "table_id": "block_0123",
  "raw_html_sha256": "...",
  "rows": 10,
  "columns": 6,
  "cells": [
    {
      "id": "r0c0",
      "row": 0,
      "column": 0,
      "rowspan": 1,
      "colspan": 1,
      "is_header": true,
      "runs": [
        {"type":"text","source":"Parameter","target":"参数"}
      ],
      "quality_flags": []
    }
  ],
  "quality_flags": []
}
```

DocumentIR table block 继续保留 raw HTML，以便兼容现有 Renderer 和审计。

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
