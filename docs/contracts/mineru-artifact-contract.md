---
doc_type: data-contract
status: target
contract: mineru-artifact-package
last_reviewed: 2026-10-23
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

IR-205 在既有验证后，从同一个原始 JSON 按可信 locator 捕获归一化前 fragment，再根据 caption、可靠列统计/显式表头、页面边界和明确连续性建立 logical group。原始 JSON/HTML、页/bbox 和全局/页内索引永久保留在受控 DocumentIR 源 metadata，不写入受限 validation report。

严格空续页仍按 IR-201 归并并对账，空项保留为来源 fragment，主 block/source inventory/Word 表格数不变。归并回执只证明执行事实，不自动成为已验证的语义续表；孤立或含内容空表、非空坏 HTML 仍失败。相邻独立表不能只因同表头归组，证据不足留独立组并记非致命 table_continuation_uncertain。这里只建立元数据，不实现 Word 合并、补行、网格或截图回退。详细字段和兼容边界见 [DocumentIR 合同](document-ir-contract.md)。

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

## 10. IR-201 验证报告与执行边界

正式线上 Worker 和本地 adapter 均通过同一个 `MinerUToDocumentIRService.convert_zip()` 入口，在扁平化和语义规范化前验证输入。报告 schema 为 `mineru-artifact-validation/v1`，支持 JSON 序列化，区分原始节点 inventory 和规范化后的 source inventory。

当前规则版本为 `mineru-artifact-validator/v3`；schema v1 与包 policy v2 保持兼容。报告保存 `warnings`、`blockers`，问题包含稳定机器码、`severity`、`stops_conversion`、原始 JSON Pointer、页号及源索引；无合法页号时不伪造位置。普通 warning 不直接成为 fatal，但报告达到问题明细或 JSON 字节预算时必须停止，以 `report_limit_exceeded`、`complete=false`、`can_convert=false` 明示未完成检查，不能截断后宣称通过。已有全量计数、截断字段及首个 fatal 保留兼容；未完成报告的计数只表示已检查范围。报告不包含正文、原始 HTML、图片字节、凭据或临时绝对路径。未知源类型使用受控 `unsupported` 标签；未知字段名使用哈希，问题按原始位置及 code 稳定排序。

JSON 解码后在 validator 的原始 payload 入口检查 keys、values 与嵌套数组中的孤立 Unicode surrogate；以 mineru_json_invalid 和安全 reason 停止，坏字符串不能进入报告或正文。合法 surrogate pair、中文和 emoji 保持原文；不在包读取层重复扫描或用转义序列改变报告字节计量。

`can_convert` 仅表示输入验证完整且没有 fatal，不表示内容完整性、Word 视觉、复核或发布已经通过。坏 JSON/page/block、显式非法 bbox、非法路径和必需 image/chart 无法安全读取会停止；缺 bbox 或 legacy flat 缺页号保留位置化 warning，不猜坐标/页码，后续布局 integrity 仍有效。不修改原包或技术内容。正常 legacy 字段和 wrapper 继续兼容，选中 v2 损坏时不得回退 legacy。

历史 OPA228 包包含合法的空 `page_header_content/page_footer_content/page_number_content` 数组。这类已确认的边缘装饰空内容保留源块并记录 mineru_margin_payload_empty warning，不等于正文或技术 payload 缺失；类型错误的 runs 仍须拒绝，不能把这个兼容例外扩展到空正文、标题、列表或公式。

验证与转换共用有效块类型和实际文本选择规则。根级 img_path/image_path、table_body/table_html 的既有 legacy 推断保持原优先级；实际成为图片或表格的块必须进入对应验证，表格不能被误要求普通正文。v2 content.list_items 的 item_content 必须符合被 converter 消费的 runs 形态；根级 legacy items 字符串和实际可保留多个文本叶字段的普通 dict 继续兼容。空的权威 rich 字段、列表容器/item 或 typed run 的非空已知语义文本/runs/list/content 旁支不能被当作已消费正文；不可保留时输出 mineru_block_payload_invalid，避免“报告通过但 Word 丢技术内容”。

image/chart 除安全 raster 读取外，还需满足正式 Word 图片头消费能力；表格 reference 只作为验证/QA 事实，不因 HTML 正常但 reference 缺失阻断原生表格。目录 `images/` 永远不是有效图片，路径不允许全包 basename 猜测回退。

允许的 raster 格式为 PNG、JPEG、GIF、BMP、TIFF、WEBP；在解码前拒绝 EPS 等可能启动外部辅助程序的格式。允许 raster 并不代表 Word 支持该图：必需图像仍须通过 python-docx 图片头与实际 native/scaled dimensions 计算，零 DPI 或不可计算尺寸明确拒绝；table reference 只检查 raster 能力，不能通过自动转码绕开失败。

单次 validator 按安全解析后的规范文件路径复用原字节及 raster 检查结果，避免重复引用放大读取、解码和字节副本。每个源引用仍有独立定位、计数和问题；每块 IR asset/drawing 合同继续保持。Word 必需图能力单独检查，作为 table reference 可读的 WEBP 不能通过缓存变成有效 Word 图片。

HTML 的四种分类沿用第 6.3 节。validator 与 converter 共享 table_body/table_html/html/content 的既有字段优先级，报告针对真正被消费的 HTML。空/坏 HTML 留下原始 blocker，但不能在前置验证中拦截已由既有 INPUT-005 严格识别的空表续页归并。converter 依据既有归一化的真实结果记录有效 inventory、被归并的原始 locator 和已解决问题，后续质量聚合必须区分 raw 与未解决证据；不删除原始事实或复制归并算法。孤立或包含正文的空表仍受现有内容完整性门禁约束，不伪造成功 IR/DOCX。IR-201 不实现第 6.3 节的 source PDF 裁图和 blocked 草稿占位；这些行为由 TAB-306 与质量状态任务完成，不得通过删除 integrity 检查提前模拟。

`effective_inventory` 包含 `block_count` 和 `type_counts`。`normalization` 包含 `filtered_promotional_page_index`、`filtered_block_count`、`filtered_blocks`（原始 locator、规则与原因）、`merged_table_placeholder_count`、`merged_table_placeholders`（原始 locator、target、rule_id、reason）和 `resolved_issue_counts`（按 severity/code 计数）。例如被确定归并的空续表可记录 `resolved_issue_counts.blocker.empty_table_html`，原 `issue_counts`、`blocker_count` 和 `table_checks` 仍保留。失败摘要压缩定位时用 `omitted_merged_table_placeholder_count`、`omitted_filtered_block_count` 或 `omitted_type_count` 明示省略，不能把压缩后的报告当作通过证据。

成功报告进入 DocumentIR metadata、任务事件和 renderer evidence 的独立 section；fatal 或后续完整性失败也携带报告。事件绑定原始 ZIP ID/hash、`retry_count` 和 trace；已知与未预期异常、包括没有 report 的旧 IR 异常，也不得刷新新 retry 后回写旧失败。质量 blocker 不直接加入既有必然抛错的 `blocking_quality_flags`，统一质量/复核/发布资格仍由相应后续后端合同管理。

### 10.1 原始安全检查与保留内容门禁

所有原始显式资产路径都要完成包根安全检查，包括公式的可选参考图；支持的 image_source 等资产载体内多个字符串引用逐个检查，不得只校验首项，也不扫描任意正文字符串；末页过滤或空续表归并不能豁免路径攻击。安全路径下的可选参考图缺失不等于公式 LaTeX 缺失，仍按角色区分必需图片和参考图。

结构与路径安全先检查，媒体可用性及 HTML 的最终阻断针对既有规则实际保留的对象。只有明确的末页过滤或空续表归并回执可以解释原始问题已解决，不能把任意消失块推定为已处理。被保留的非空不可消费 HTML 必须在 DocumentIR 构建及登记前显式失败，不能先保存 IR 再等 renderer 拦截。原 source/renderer integrity 仍然有效。

空续表归并回执只能解释 `empty_table_html`，不能解除非空 `invalid_table_html`。例如 `html="12 V"` 即使被旧 HTML 提取器视为没有表格，也必须阻断，不能借目录图片标记被并入前表；不为此复制或放宽旧归并算法。

显式 `table_placeholder` 只承载既有空续页信号；若包含可见正文（含 typed text/content）、任意非空原始 html/table_html/table_body（含支持的嵌套载体）、caption 或 footnote，输入边界按 `mineru_block_payload_invalid` 拒绝，不能无条件并入前表而静默丢内容。正常 `table` 的有效 HTML 仍作为独立原生表格输入，纯空占位符仍受既有严格归一化规则处理。普通 `table` 若被既有归并器实际移除，validator 还需核对原始字符串/typed text/content，存在正文就拒绝且不记为已解决；已知content字段的嵌套字符串数组同样是正文，数组间继承该语义，普通字典的任意结构字段不因此被当作正文；已知typed text/inline formula节点先验证必需content为字符串，畸形类型不能当作空内容，显式占位符的HTML字段也必须满足字符串类型合同；共享分类helper前检查不支持的dict/list型type，按expected_type_string返回定位失败，不泄出TypeError；保留对象沿用原完整性失败，不复制候选判据。

ZIP 全包预检必须包含普通文件与目录的祖先冲突，两种条目顺序都不能先展开前面的合法文件再发现冲突；它与重复目的路径检查共同保护“完整预检先于实际展开”的边界。路径身份使用目标文件系统中自动清理的临时命名空间探测，只创建空节点、不读取或展开成员内容；识别大小写及其他真实别名碰撞，不能全局casefold误拒大小写敏感文件系统的合法不同路径。探测命名空间在成功或失败后清理。

包安全使用版本化代码 policy v2：10,000 条目、128 MiB 单文件、1 GiB 总展开、64 MiB 选中 JSON。报告问题定位明细总计最多 1,000 条，JSON 总预算 512 KiB，table checks 和归一化 evidence 同样受字节预算约束。测试可注入低限额，字节预算至少 4096，以便保存固定失败摘要；低于此值显式 ValueError，不静默抬高。计量使用 json.dumps(..., ensure_ascii=False, allow_nan=False) 的默认空白与 UTF-8 字节。实际展开字节也受限，拒绝特殊文件、越界和同一路径覆盖；不靠 ZIP 声明或上传 PDF 的大小上限证明展开安全。调整 policy 必须同步版本、测试和文档；不新增可静默关闭安全验证的 feature flag。已有 v1 报告仍可读，不重写历史 Artifact。

六个额度字段都要求非 bool 的正整数；NaN、Infinity、float、字符串、None、零或负值构造策略时显式 ValueError，不回退默认值。报告额度另有 4096 的下限。这是内部代码策略，未新增用户可配置开关。

### 10.2 当前报告机器码

以下是 IR-201 报告中的问题码；它们没有自动新增到既有 `quality_flags` 或 `blocking_quality_flags` 数组。消费者必须同时读取 severity 和 stops_conversion，不能仅凭 code 推断发布资格。

| code | 含义 | severity / stops_conversion |
|---|---|---|
| mineru_package_invalid | ZIP 损坏、CRC/压缩读取失败、加密或不可消费的归档 | blocker / true |
| mineru_package_limit_exceeded | 条目数、实际/声明展开字节、图片或 JSON 超限 | blocker / true |
| mineru_path_invalid | 非法原始路径、symlink、根目录越界、规范路径覆盖或歧义 | blocker / true |
| mineru_content_list_missing | 没有选中的 content list | blocker / true |
| mineru_json_invalid | JSON 读取/解码失败、孤立 Unicode surrogate 或顶层容器不受支持 | blocker / true |
| mineru_content_empty | 没有源块，不能构造伪成功空文档 | blocker / true |
| mineru_page_invalid | 页容器、显式页号或同块页号冲突 | blocker / true |
| mineru_page_missing | legacy flat 没有页号；保留原位置和顺序，不猜页码 | warning / false |
| mineru_page_empty | nested 页数组为空；保留原页索引，全空文档仍失败 | warning / false |
| mineru_page_gap | 相邻有效 flat 页号向前跳过至少一页；只诊断，不推断物理页数或重排 | warning / false |
| mineru_block_invalid | 非对象块、缺失/非法 type | blocker / true |
| mineru_block_payload_invalid | 类型相关文本、runs、annotations、公式或 legacy 表格 payload 不可安全保留，含未被选中消费的非空语义叶字段 | blocker / true |
| unsupported_block_type | 未知类型；可保留正文时继续，不可保留时失败 | warning / false，或 blocker / true |
| legacy_page_index_coerced | 合法十进制字符串页号被明确转换为整数 | warning / false |
| mineru_page_order_nonmonotonic | flat 页号倒退；保留源数组顺序 | warning / false |
| mineru_bbox_missing | 没有可用 bbox | warning / false |
| mineru_bbox_invalid | 显式 bbox 的长度、类型、有限性或面积不合法 | blocker / true |
| report_limit_exceeded | 问题明细或报告 JSON 超过预算，未完成检查，报告本身仍有界 | blocker / true |
| mineru_margin_payload_empty | 已确认的空页眉/页脚/页码 runs 兼容例外 | warning / false |
| missing_image_asset | 必需图像引用没有文件 | blocker / true |
| invalid_image_asset | 必需图像为目录、空/坏/不支持图片或 Word 尺寸不可计算 | blocker / true |
| missing_table_reference | 表格没有参考图片 | warning / false |
| invalid_table_reference | 表格参考为目录、空/坏/不支持图片 | warning / false |
| empty_table_html | 没有表格 HTML，保留事实供后续 integrity/质量判定 | blocker / false |
| invalid_table_html | HTML 类型错误或没有可消费行/单元格；原始分类留证，保留对象在 IR 构建前阻断 | blocker；原始观察不直接拦截严格空续表，最终内容门禁阻断保留的不可消费 HTML |
| suspicious_table_html | 可解析 HTML 有基本标记/span 等可疑信号 | warning / false |

`facts.reason` 仅保存有限分类值；图片实际格式被拒绝也归入 invalid_image_asset/invalid_table_reference，不打印文件内容。新增机器码必须同时更新此表、直接观察合同测试和 Spec。

## 当前分支集成边界（RND-501）

本次候选从c56e128复用IR-201/205与TAB-301必要来源合同，不引入IR-206、TAB-302以后生产算法或RND-504。当前TR-402/403/406的翻译、完整性和批次生命周期以及CON-104下载/发布规则继续由既有owner管理；输入报告和Grid flags不提供批准/发布资格。实际验证以RND-501当前实施记录为准，历史验收不等于新候选已通过。
