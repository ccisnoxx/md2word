---
doc_type: technical-design
status: target
component: translation
last_reviewed: 2026-10-21
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
- TR-402 提供独立纯内存 ProtectedTokenCodec 原语及离线契约测试；尚未接入 Provider/Worker，不能据此认定生产技术保持率已经达标。

目标差距：

- captions/footnotes 需要明确进入翻译单元；
- 正式翻译链路的技术 Token 仍主要依赖 Prompt，需要 TR-403 接入已有 Codec 并在回填前验证；
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
TA = 25°C → {{MD2W_PT_v1_0_1}}
0x0028[4:0] → {{MD2W_PT_v1_0_2}}
VCC1_VCO → {{MD2W_PT_v1_0_3}}
```

要求：

- 占位符在一个批次内唯一；
- 占位符不与源文本已有内容冲突；
- 映射只保存在内存或受控 debug artifact；
- Prompt 明确禁止修改占位符。

TR-402 的具体内部接口和规则见 [ProtectedTokenCodec Spec](../../.trellis/spec/backend/protected-token-codec.md)。输入为完整有序 TranslationTextItem tuple，每次出现独立编号；扫描全部源文本选择不存在的命名空间前缀，不使用随机数/全局计数。已有占位符字面量同样被代理，避免源文碰撞。新模块的原始映射仅在内存保存，不新增 debug Artifact 出口。

检测在原文上执行，URL/邮箱与公式等完整结构优先，随后处理地址/位字段、型号/标准/版本、信号、数量单位、数字及有界技术缩写；不把普通大写词或任意自然语言吞为 Token。原始切片不做空白、Unicode 或单位规范化。上述示例命名空间为 0，实际遇到源文前缀冲突会确定性递增。

### 7.3 解码前校验

- 返回 item ID 序列与输入一致；
- 逐 item 验证占位符所属关系与次数，不能只比较全批集合；
- 每个占位符恰好出现一次；源中多次出现同值时也分配不同占位符；
- 不允许未知占位符；
- 不允许占位符被拆空格、改大小写或改括号。

失败时批次为确定性失败，不回填。

Codec 在整批通过后一次恢复，恢复出的源文占位符字面量不再次替换；同 item 内移动完整占位符允许，跨 item 移植拒绝。它不判断译文语义或未编码内容。生产失败映射、编码后的预算、Prompt 告知、术语顺序及同步/Worker 双入口接线由 TR-403 处理；本次不修改历史 Prompt/Profile 快照或新建 feature flag。

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
