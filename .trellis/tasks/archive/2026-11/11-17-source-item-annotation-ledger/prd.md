# 来源账本 v2 与注释账本

## 目标

当 MinerU 的列表项、题注或脚注在转换、翻译回填或持久化后被删除、替换、错误合并或重排时，阻止不完整的 Word 进入交付。同文内容只要来源位置独立，就分别保留。账本只保存 SHA-256、序号及映射。

## 背景

- `app/conversion/docx_rules/mineru_content.py::mineru_list_item_ledger` 和 `app/services/document_ir/integrity.py::_list_item_ledger_summary` 只对列表项数，无法发现等量替换和重排。持久化渲染校验会重算这份证据。
- `app/services/document_ir/caption_reconciler.py::reconcile_captions` 和 `app/services/document_ir/mineru_converter.py::_footnotes` 存在按文本去重。若在去重之后建立账本，已被合并的独立注释无法发现。
- `app/domains/translation/document_ir_translator.py::apply_replacements` 已按字段与下标回填，正式 Worker 的批次已校验有序 item ID。现有证据可用于确认目标位置和产物，无需建立另一套翻译 ID。

## 需求

- **R1 列表。** 新产物写 `list-item-ledger/v2`。保留源字段、读取模式与计数，记录每个源项的下标、源摘要、规范化摘要、空项标记及输出位置。legacy dict 展开记录一对多区间。序列摘要绑定来源和输出顺序。direct 严格核对项数、位置、内容和序列。
- **R2 注释。** 为 DocumentIR 的 `captions`、`footnotes` 写 `annotation-ledger/v1`，记录 `block_id`、`field`、`source_index`、`source_sha256`、`target_index`、`target_sha256`。保留独立同文位置。已有可证实的题注修复、富文本分片拼接和注释角色转换仍可按各自合同处理。
- **R3 翻译。** 每个应译输出位置使用已有 item ID 接收且只接收一个结果，并写入非空目标摘要。源身份、项数及顺序保持。legacy 一对多的每个实际输出位置都有一个独立译文位置。译文可以与源文不同。
- **R4 发布与历史读取。** 正式转换、回填和持久化重读校验同一账本合同。只在可信冻结源项或已认证的同位置译文仍可用、且恢复能完整复核时恢复并记 warning。其余确定性不一致属于 `source_ir_integrity`，禁止成功登记或交付当前产物。历史 v1 和无账本 IR 延用各自校验、序列化和渲染证据形状。

## 验收

| 编号 | 可观察结果 |
| --- | --- |
| AC1 · R1 | 删除中间列表项、同数替换或交换两项均被检出。原样 direct 通过。两条相同文本占两个位置，删其中一条或将一个位置重复引用均被检出。 |
| AC2 · R1 | 空项保留源下标但不占输出位置。legacy dict 展开多个输出项的范围及逐项摘要可验证，覆盖第二个子项替换或换位。 |
| AC3 · R2 | 删除题注、合并两条独立脚注或交换注释位置均被检出。两条同文脚注在 MinerU 转换后仍有两个位置，同文题注也按可核验的来源位置保留。合法富文本拼接、题注跨块归属及表前条件拆出仍通过。 |
| AC4 · R3 | 原文与译文不同且映射正确时通过。列表项或注释目标缺失、重复、错序、错绑或回填后内容被替换时失败。同文脚注收到两个 ID，即使译文也相同仍独立回填。 |
| AC5 · R4 | 对有可信冻结值的缺项或替换，恢复后重新校验并留 warning。对无可信恢复值的损坏，拒绝持久化或交付。合法的 v2/注释账本在 JSON 往返及持久化重读校验中通过，历史 v1 和无账本样本沿原行为读取。 |
| AC6 · R4 | `row_ambiguous` 仍走表格参数列 warning 路径。表格单元格继续使用既有 `TableCell.content_sha256` 与表格 evidence。 |

## 范围边界

普通段落、标题、作为正文段落承载的 `page_footnote`、表格单元格及其他正文元素不加入账本。既有表前条件和图题拆出的标题继续由原规则证明其去向。翻译校验覆盖位置和结果身份，译文语义质量继续由既有翻译流程处理。
