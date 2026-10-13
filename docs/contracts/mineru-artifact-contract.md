---
doc_type: data-contract
status: target
contract: mineru-artifact-package
last_reviewed: 2026-10-03
---

# MinerU 产物合同

## 1. 目的

本合同定义 md2word 从 MinerU 接收的输入边界。系统不重新决定 OCR、扫描识别或解析器路线；只验证 MinerU 结果包是否足以进入 DocumentIR 和 DOCX 流水线。

## 2. 结果包

推荐结构：

```text
mineru-result/
├── content_list_v2.json
├── images/
│   ├── <sha>.jpg
│   └── ...
├── source.pdf                 # 若 MinerU 包含
└── metadata.json              # 可选
```

系统同时必须保留任务原始 `source_pdf`，不依赖 MinerU 包内 PDF。

## 3. 顶层 JSON

`content_list_v2.json` 允许以下两种输入形式：

1. 页数组：`list[list[block]]`；
2. legacy flat blocks：每个 block 带 `page_idx/page_index`。

规范化后必须得到：

```text
page_index
source_index_in_page
raw_block
```

页数组的数组顺序是主要阅读顺序，不允许把同一页所有块简单按 `(y, x)` 全局重排。

## 4. 通用块字段

| 字段 | 必填 | 说明 |
|---|---:|---|
| `type` | 是 | MinerU 块类型 |
| `content` | 是 | 类型相关内容 |
| `bbox` | 建议 | `[x1,y1,x2,y2]` |
| `page_idx/page_index` | flat 模式需要 | 源页面 |

`bbox` 仅用于：

- 页面定位；
- 分栏和并排判断；
- 页眉页脚识别；
- caption 归属；
- 表格/图片参考裁切；
- QA 高亮。

## 5. 支持类型

### 5.1 `title`

示例：

```json
{
  "type": "title",
  "content": {
    "title_content": [{"type": "text", "content": "主要性能"}],
    "level": 2
  },
  "bbox": [65, 156, 163, 179]
}
```

注意：MinerU `level` 只视为解析事实，不直接等同最终 Word Heading 级别。

### 5.2 `paragraph`

`paragraph_content` 是有序 run 列表，可混合：

- `text`；
- `equation_inline`。

不得先拼成纯文本后丢失公式位置。

### 5.3 `image` / `chart`

```json
{
  "type": "image",
  "content": {
    "image_source": {"path": "images/<sha>.jpg"},
    "image_caption": [{"type": "text", "content": "图 1 功能模块示意图"}],
    "image_footnote": []
  },
  "bbox": [76,111,924,869]
}
```

要求：

- 图片路径必须解析到结果包内部；
- 禁止路径穿越；
- 资源缺失产生 quality flag；
- 图片、chart 统一进入 DocumentIR image block，但保留 `source_type`。

### 5.4 `table`

```json
{
  "type": "table",
  "content": {
    "image_source": {"path": "images/<sha>.jpg"},
    "table_caption": [{"type": "text", "content": "表 1 电源电压及功耗"}],
    "table_footnote": [{"type": "text", "content": "1 ..."}],
    "html": "<table>...</table>",
    "table_type": "complex_table",
    "table_nest_level": 1
  },
  "bbox": [68,301,924,719]
}
```

解释：

- `html`：可编辑和翻译的主输入；
- `image_source`：参考图；
- `table_caption`/`table_footnote`：独立可翻译文本；
- `table_type`：参考信息，不能直接决定是否原生化；
- `table_nest_level`：保留 metadata。

### 5.5 页面边缘类型

```text
page_header
page_footer
page_number
```

原始类型不能作为最终保留/丢弃的唯一依据。样本中存在页脚文本被识别为 `paragraph`、运行页眉被识别为 `title`、正文标题被识别为 `page_header` 的情况。

## 6. 产物验证

### 6.1 结构验证

- 顶层类型受支持；
- page/block 为对象；
- `type` 非空；
- `bbox` 是 4 个有限数值且 `x2>x1, y2>y1`；
- 页面索引不为负；
- 路径为包内相对路径。

### 6.2 资产验证

- image/chart 路径存在且是普通文件；
- MIME 可识别或可安全读取；
- 表格 reference image 路径可为空，但必须记录；
- `images/` 目录本身不是有效文件路径。

### 6.3 表格验证

分类：

```text
html_present_and_parseable
html_present_but_suspicious
html_missing_reference_present
html_missing_reference_missing
```

处理：

| 分类 | 行为 |
|---|---|
| HTML 正常 | 进入 CanonicalTableGrid |
| HTML 可解析但可疑 | 进入 Grid，增加 QA flags |
| HTML 缺失、有参考图 | 生成内部占位，blocked |
| HTML 和参考图都缺失 | 可从 source PDF+bbox 裁图占位，blocked；无法裁图则任务失败 |

样本中的空表块：

```json
{
  "image_source": {"path": "images/"},
  "html": ""
}
```

必须识别为无有效 HTML、无有效参考图，不得视为正常空表。

## 7. 规范化规则

### 7.1 阅读顺序

- 保持页内数组顺序；
- 只在有确定证据时调整连续媒体 caption；
- `bbox` 不用于全局重排。

### 7.2 运行页眉页脚

使用跨页重复、固定区域和文本相似度识别：

```text
高频重复 + 顶部/底部固定位置 → margin artifact
一次性正文标题 → body candidate
```

### 7.3 列表

MinerU 可能把 `■`、`◆`、`-`、`1.` 识别为 paragraph。规范化器按标记、缩进和邻接关系生成 list block。

### 7.4 跨页段落

上一页尾段未结束、下一页首段语义连续时可合并为一个逻辑 block，但保留多个 source spans。

### 7.5 跨页表格

根据 caption、列数、表头、页面边界和内容连续性生成 logical table group。各页仍保留 fragment 和来源位置。

### 7.6 Caption 重新绑定

连续图片组中出现“一个图片携带多个连续图号、相邻图片无 caption”时，仅在编号连续且数量一致时自动重新绑定；否则标记人工复核。

## 8. 安全

- 解压防 Zip Slip；
- 限制文件数、单文件大小和总展开大小；
- 路径标准化后必须位于临时根目录；
- 不执行结果包中的脚本或宏；
- 图片解码失败不得导致 Worker 进程崩溃；
- 原始结果包只读保留，规范化不得回写。

## 9. 质量标记建议

```text
mineru_json_invalid
mineru_page_invalid
mineru_bbox_invalid
missing_image_asset
missing_table_reference
empty_table_html
invalid_table_html
margin_role_uncertain
caption_binding_uncertain
cross_page_paragraph_merged
cross_page_table_grouped
unsupported_block_type
```
