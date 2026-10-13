---
doc_type: technical-design
status: target
component: translation
last_reviewed: 2026-10-03
---

# 翻译流水线设计

## 1. 范围

仅支持：

```text
en2zh
ru2zh
zh2en
zh2ru
```

`direct` 永远不进入翻译服务。不存在 `zh2zh` Prompt。

## 2. 当前基线

现有实现已经具备：

- 四种语言方向和 Prompt 文件；
- Translation Profile 和 Prompt 内容哈希；
- Translation Term Set；
- DocumentIR 文本、列表和 table HTML 文本节点抽取；
- 稳定 ID 回填；
- Provider JSON 结构化输出；
- ID 数量/缺失/重复/额外项校验；
- 批次计划、重试、拆分和调用审计。

目标差距：

- captions/footnotes 需要明确进入翻译单元；
- 技术 Token 主要依赖 Prompt，缺少确定性 codec；
- 表格短文本缺少行头/列头上下文；
- 翻译后技术完整性检查不足；
- 四种语言方向的正式样本不完整。

## 3. 流程

```mermaid
flowchart LR
  A[Source DocumentIR] --> B[Translation Unit Builder]
  B --> C[Context Builder]
  C --> D[ProtectedTokenCodec.encode]
  D --> E[Term Matcher]
  E --> F[Batch Planner]
  F --> G[LLM Provider]
  G --> H[Response Shape Validator]
  H --> I[ProtectedToken Validator]
  I --> J[Term/Language Validator]
  J --> K[ProtectedTokenCodec.decode]
  K --> L[Apply to Target DocumentIR]
```

## 4. Translation Unit

```json
{
  "id": "block_0010:caption:0",
  "kind": "table_caption",
  "text": "Table 1. Supply Voltage and Power Consumption",
  "context": {
    "section_title": "Electrical Characteristics",
    "table_caption": null,
    "row_header": null,
    "column_header": null
  }
}
```

`kind` 可取：

```text
heading
paragraph
list_item
image_caption
image_footnote
chart_caption
chart_footnote
table_caption
table_cell
table_footnote
```

Provider 输出只包含 `id/text`。

## 5. 单元抽取

### 普通 block

- heading/paragraph：`block.id:text`；
- list：`block.id:list:<index>`；
- caption：`block.id:caption:<index>`；
- footnote：`block.id:footnote:<index>`。

### 表格

优先从 CanonicalTableGrid 的 translatable text run 抽取：

```text
block.id:table:r<row>:c<col>:run<index>
```

兼容路径可继续从 HTML `NavigableString` 抽取，但新逻辑必须保证 `<sup>/<sub>/formula` 不被拆成失去上下文的独立翻译项。

## 6. 上下文

上下文只用于输入，不可由 Provider 返回或修改。

### 正文

- 最近 Heading 1/2/3；
- 前一段短摘要（可选，受字符预算限制）；
- 内容类型。

### 表格

- 所属章节；
- 表题；
- 当前列头；
- 当前行头；
- 最近分组行。

短单元格如 `Typical/Reserved/High/Low` 必须优先携带上下文。

## 7. ProtectedTokenCodec

### 7.1 保护类型

- 数字、科学计数法、范围；
- 数字+单位；
- 正负号和比较符；
- 十六进制地址；
- 位字段；
- 引脚/信号/变量；
- 型号、封装、协议、标准；
- URL、邮箱、版本号；
- 公式和 LaTeX。

### 7.2 编码

```text
TA = 25°C → {{PH_0001}}
0x0028[4:0] → {{PH_0002}}
VCC1_VCO → {{PH_0003}}
```

要求：

- 占位符在一个批次内唯一；
- 占位符不与源文本已有内容冲突；
- 映射只保存在内存或受控 debug artifact；
- Prompt 明确禁止修改占位符。

### 7.3 解码前校验

- 集合完全相等；
- 每个占位符恰好出现一次，除非源中本就多次出现且编码模型明确允许；
- 不允许未知占位符；
- 不允许占位符被拆空格、改大小写或改括号。

失败时批次为确定性失败，不回填。

## 8. 术语

### 匹配

- 只注入当前批次实际命中的术语；
- 最长匹配和优先级优先；
- 避免重叠；
- 记录 segment/batch trace；
- 不把符号排版规则当翻译术语。

### 输出校验

- `mandatory/active` 术语必须使用目标译法；
- forbidden translation 出现则 warning 或 blocked；
- 同一批次相同源术语译法一致；
- 术语校验不作用于受保护 Token。

## 9. Provider 合同

输入：

```json
{
  "source_lang": "en",
  "target_lang": "zh-CN",
  "terms": [{"source_term":"...","target_term":"..."}],
  "items": [{"id":"...","text":"...","context":{}}]
}
```

输出：

```json
{
  "items": [{"id":"...","text":"..."}]
}
```

禁止自由文本、Markdown、说明或多余字段。

## 10. 批次

优先按页和字符预算切分；同时限制 item 数量。

批次必须记录：

- root/parent batch；
- page range；
- item IDs；
- item/char count；
- attempt/split level；
- model、Prompt、术语快照；
- usage、finish reason、response ID；
- duration、error 和 retryable。

## 11. 校验顺序

1. Provider 响应 JSON 可解析；
2. item 数量；
3. ID 集合；
4. 重复 ID；
5. 占位符；
6. 数字、单位、地址、位字段和公式；
7. 目标语言；
8. 术语；
9. 源语言残留；
10. 回填。

前 6 项失败为阻断；后续项根据规则分 warning/blocked。

## 12. 部分失败

- 叶子批次最终失败 → 主任务失败或质量 blocked；
- 不允许用源文补齐目标文档并标记成功；
- 可以保存部分结果作为 debug evidence；
- 重新执行只处理失败批次，但最终组装必须来自同一 generation 和同一配置快照。

## 13. 审计与隐私

常规审计只保存：

- batch/item 数量；
- 内容哈希；
- model/prompt/term snapshot；
- usage/耗时/错误；
- 短且脱敏的术语命中上下文。

全文 debug：

- 默认关闭；
- Admin 显式开启；
- 短保留期；
- 下载和查看写审计。

## 14. 测试

### 单元

- 每类 token；
- placeholder collision；
- ID 缺失/重复/额外；
- caption/footnote 抽取和回填；
- table cell context；
- forbidden term；
- split/retry。

### 语言方向

每个方向独立样本：正文、列表、表格、caption、footnote、公式、单位、地址、位字段。

### 验收

- direct 任务翻译调用为 0；
- 四种模式使用正确 Prompt；
- 受保护 Token 100% 一致；
- 表格 DOM 和结构字段不变；
- 未复核译文允许内部下载但不可发布。
