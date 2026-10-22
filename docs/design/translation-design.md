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
- TR-402 提供独立纯内存 ProtectedTokenCodec；TR-403 将其接入共享请求准备和完整性 Validator，供同步、Worker 与正式本地 adapter 使用。受控 batch result 保存恢复文本及绑定 evidence，fan-in 重新核对后才回填；离线证据不代表生产实译保持率已经验收。

目标差距：

- captions/footnotes 需要明确进入翻译单元；
- 表格短文本缺少行头/列头上下文；
- 术语/目标语言/源语言残留后验检查仍未由 TR-403 实现；
- 四种语言方向的正式样本不完整。

## 3. 流程

下图含尚待相邻任务完成的目标能力；TR-403 的实际链路为：原文有序 items → 实际编码预算计划 → Codec encode/未保护跨度术语匹配 → Provider 严格 JSON → ID/ledger/占位符 → 一次 decode → 逐 item 技术多重集 → 成功 evidence → 回填。Worker 在成功 Artifact 消费时另核对权威来源、当前 generation/attempt、checksum、ID/hash 和技术 inventory，不因文件自报 passed 而跳过。目标语言及术语后验校验仍属 TR-405。

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
- ledger 映射只保存在当前调用内存，不新增导出或 debug 映射 Artifact；
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

Codec 在整批通过后一次恢复，恢复出的源文占位符字面量不再次替换；同 item 内移动完整占位符允许，跨 item 移植拒绝。Codec 本身不判断未编码内容；TR-403 的 Validator 再对恢复文本 encode，并逐 item 比较 Counter((kind, original_text))，拒绝在完整占位符之外追加裸数字/单位/地址/型号/公式，重复值按次数核对。

实际编码文本决定预算，plan/record 原有 char_count 仍表示源文；单项编码后超限在调用前显式失败。术语只在不与保护跨度相交的原文位置匹配。Provider 追加固定 translation-integrity-instructions/v1 协议，不修改绑定 Prompt 正文/hash 或历史 Profile，不新增 feature flag。具体接口、机器码和证据字段见 [Validator Spec](../../.trellis/spec/backend/translation-integrity-validator.md)。

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

前 6 项失败为阻断；TR-403 当前实现的 ID 首错优先级为 duplicate→missing→extra→order，随后验证占位符及恢复后的逐 item 技术 inventory。所有 item 通过才返回恢复结果；一个 item 失败则整批无可消费 replacements，不自动修复、不补原文。后 3 项为 TR-405 的目标能力，本任务不新增相关 quality flag 或改变主任务最终失败产品语义。

## 12. 部分失败

- 任一有效叶子批次最终失败，主任务立即失败，`failed_stage=translating`、顶层错误为 `translation_failed`；不等待尚在排队或运行的兄弟批次，不将执行失败改记为质量 `blocked`。
- 已持久化的终态失败或无效批次树本身就是停止本代工作的依据。即使主任务尚未写为 failed，enqueue/claim 也不得继续；终态批次自身或排队兄弟重放时，均在拒绝新工作后幂等推进主任务失败。重复收口不重复记录终态事件。
- 全部有效叶子成功且证据、来源、attempt/generation 和有序覆盖通过后，才进入 `translation_validating` 并一次回填。`split` 父节点是被替代的计划节点；其子树必须完整覆盖父项，不计为失败叶子。残缺根计划、残缺 split 或非法叶子不能当作零单元成功。
- 同代自动重试只处理失败叶子，保留已成功兄弟；领取时在同 job 锁/事务内核对 attempt、唯一 lease 和全代调用预算。终态失败后不得新领取或晋升在途结果，旧 attempt/lease 不能写入当前账本。
- 用户 retry 使用既有原子入口换代，从权威不可变 source IR 重建全部本代批次，默认沿用原配置快照；不得改写或重新包装旧代成功译文。source 的创建代次可以早于当前消费代次，仍须核对真实来源和字节身份。
- 部分成功的 batch result 仅作为内部诊断证据，不登记为目标 IR 或主 DOCX，不增加普通下载或发布来源；失败响应不能保存成成功 batch result。不用源文补齐目标文档，不自动转 direct。
- 失败全文只沿现有部署开关、Admin 显式启用、短 TTL、授权和审计 debug 路径保留。完整译文产生后的质量 blocked / 翻译 unreviewed 草稿继续沿已有内部下载与批准/发布可用性合同处理。

每代根计划以权威 source/config 计算的完整确定性根集合一次安装；迟到初始化只能观察已有现态，不得覆盖 status、attempt、lease、结果指针或调用预算。数据库完整提交或回滚；file 中断后发现非空残缺根集合时明确失败，不补根后继续消费。生产写者启用前仍须满足真实 MySQL/InnoDB 和部署文件锁门禁，本地测试不替代这些证据。

## 13. 审计与隐私

常规审计只保存：

- batch/item 数量；
- 内容哈希；
- model/prompt/term snapshot；
- usage/耗时/错误；
- 术语上下文长度/哈希，不保存上下文片段正文；
- translation-integrity/v1 的版本、阶段、结果/错误码、分类计数、内容哈希及批次权威关联。

每次真实 Provider 调用只保存一份成功或失败审计，验证失败属于失败调用；预算等调用前失败不伪造 AI 调用。外部异常使用固定安全描述，未经验证的返回 ID 只记录哈希。既有正文 DTO、嵌套 Prompt/trace 及上游 _TermMatch.context_snippet 都隐藏敏感 repr 字段；真实值和序列化保持，不能直接输出 asdict。

生成件新 key 在 file_type/filename 之间加入本次登记的 file_id，避免迟到 generation/attempt 或同 attempt 重复登记覆盖字节；CAS 仍仅负责选择记录，不替代物理隔离。历史 key/字节保留并按记录读取，无迁移/backfill。既有 retry 可以继承 job 权威指针下的不可变 source IR，验证源归属/角色/IR 来源及真实 checksum 后，新批次绑定当前 generation/attempt；源创建代次不能被误作消费代次，也不能以此复用旧译文批次。上线前暂停翻译入队、排空旧 Worker/活跃旧代后同步部署调用端与 Worker；活跃旧中间结果缺 evidence 必须拒绝，已完成历史件不重跑。回退先停执行，不恢复无验证回填或固定路径覆盖。

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
