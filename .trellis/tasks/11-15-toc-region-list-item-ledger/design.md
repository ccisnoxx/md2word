# 设计：目录合并区域约束与列表项级账本

## 1. 现状与约束

- `render_plan.py::build_render_plan` 中 `representative` 是全文档范围的状态：第一个 `toc` 项成为代表，之后任何 `toc` 项都改成 `coalesced`（第 527-535 行）。`_plan_toc_formula_paragraphs` 在已选策略上重排，不独立判定区域。
- `render_evidence_validation.py::_validate_render_evidence` 同时服务于生成期（`validate_render_result`，`require_ownership=True`）和持久化读取（`validate_persisted_render_evidence`）。它只校验证据与计划一致。
- `base_quality` 读取持久化计划并与 trace 比对，不从 IR 重建计划。因此修改区域规则不会让历史计划失效。
- **身份约束**：render-plan/v2 的 `input_ir_sha256` 等于完整 `DocumentIR.model_dump(mode="json")` 的哈希。只有 v1 才通过 `legacy_document_ir_payload` 剔除后增的 metadata 字段。给 `DocumentIRMetadata` 新增字段，会让所有历史 v2 产物的持久化校验报 `ir_render_evidence:binding_mismatch`。所以本设计**不修改 IR 模型**。
- 翻译器 `document_ir_translator.py` 按下标原位替换 `list_items`（第 695-696 行），不改变项数，也不改动 block metadata。
- 验证器已对 `content/list_items` 中缺少 `item_content` 列表的项失败关闭（`artifact_validator.py:755`）。`v2_items` 唯一的静默丢弃路径是"规范化后文本为空"。

## 2. 目录区域（G1）

### 2.1 Owner

在 `render_plan.py` 新增纯函数 `toc_region_block_ids(document_ir, operations) -> frozenset[str]`。按写入顺序遍历 `kind == "block"` 的操作，返回目录区域内的块 ID 集合。`build_render_plan` 与生成期校验都调用它。

状态机：

| 状态 | 输入 | 转移 |
|---|---|---|
| before | 标题/段落文本满足 `is_toc_title_text`，或任一文本项满足 `parse_toc_entry_text` | → inside，当前块入区 |
| inside | `heading` 块，或 v1 IR 中被推断为 heading 的段落，且文本既非目录标题也非目录项 | → after（终态），当前块不入区 |
| inside | 其他块（段落、列表、公式、表格、图片） | 留在 inside；段落/列表入区 |
| after | 任意 | 不再入区 |

`decoration`、`section`、`configure_page`、`column_break` 等非正文操作，以及 `layout.role != "body"` 的块（页眉、页脚、页码）不影响状态。所以跨页目录中间的页眉页码不会截断区域；RS2G04 中被 `parse_toc_entry_text` 认出的页码段落也不会提前开启区域。

### 2.2 策略选择

`select_text_policy` 新增关键字参数 `allow_toc: bool = True`。为 `False` 时跳过 `toc_title` 与 `toc` 分支，按原优先级落到 `bullet`/`heading`/`paragraph`。`build_render_plan` 对不在区域内的块传 `allow_toc=False`。`representative` 逻辑不变，只在区域内生效。

区域外目录样式文本原样输出，保留点引导符和页码（PRD Q1）。

### 2.3 版本

不新增 `word-renderer-policy` 版本（PRD Q3）。持久化计划逐项写明 `mode`，`plan_sha256` 已区分新旧输出。历史计划不重放。FIELD-001 中"普通目录沿用原计划身份"的表述保持不变。

## 3. 列表项账本 `list-item-ledger/v1`（G2）

### 3.1 存放位置

账本写入每个主列表块的 `block.metadata["list_item_ledger"]`，不进 `DocumentIRMetadata`（见第 1 节的身份约束）。历史 IR 的块没有该键，哈希不受影响。

```json
{
  "version": "list-item-ledger/v1",
  "selected_field": "content/list_items",
  "mode": "v2_items",
  "source_item_count": 14,
  "empty_item_count": 0,
  "item_count": 14
}
```

源指针沿用已有的 `metadata.mineru_source.json_pointer`，不重复存储。

### 3.2 生成

`mineru_content.py` 新增 `mineru_list_item_ledger(block) -> dict`，与 `mineru_list_items` 共用 `select_mineru_list_source` 选择分支：

- `v2_items`：`source_item_count = len(value)`；`empty_item_count` = 规范化后文本为空的项数。
- `legacy_items` 且全为非 dict 项：`source_item_count = len(value)`；`empty_item_count` = `clean_text` 后为空的项数。
- legacy 含 dict 项、`selected_text`、`content`：只能由同一函数推导，记录 `source_item_count = None`、`empty_item_count = None`。
- `item_count = len(mineru_list_items(block))`。

有源项数时，若 `source_item_count != item_count + empty_item_count`，转换器在构建 IR 前抛 `DocumentIntegrityError("MinerU→DocumentIR", {"blocking_quality_flags": ["source_ir_integrity:list_item_count_mismatch"]})`。

`mineru_converter.py` 在 `block_type == "list"` 时写入账本。图表转出的合成块（带 `source_block_id`）不写。

### 3.3 对账

`integrity.py::build_source_integrity` 在现有 payload 检查后增加：

- 主列表块集合 = `main_blocks` 中 `type == "list"` 的块。
- 若其中**任一**块带账本：所有主列表块都必须带有 `version == "list-item-ledger/v1"` 的账本，且 `len(block.list_items or []) == ledger["item_count"]`。否则加 `source_ir_integrity:list_item_count_mismatch`。
- 若都不带账本，视为历史 IR，跳过。
- 只有在带账本时，返回字典才新增键 `list_item_ledger: {"version", "block_count", "item_count", "mismatch_block_ids"}`。历史 IR 的 `source_integrity` 结构逐字节不变，否则 `validate_persisted_renderer_content` 对历史元数据的比对会失败。

整页降级会连块一起移除，账本随块消失，由现有块计数对账覆盖，不需要额外记账。

该函数在转换出口（`mineru_converter.py:409`）和渲染元数据（`render_evidence.py:96`，翻译之后）都会调用，所以翻译或后续处理改变项数时同样会被阻断。

## 4. 渲染项级去向（G3）

在 `render_evidence_validation.py::validate_render_result`（仅生成期）中，在 `_validate_render_evidence` 之后：

1. 用 `toc_region_block_ids(document_ir, plan.operations)` 独立重算区域。
2. 遍历 `plan.decisions`：任一 `text_policies[i].mode ∈ {toc_title, toc, coalesced, toc_formula, toc_formula_first}` 且 `block_id` 不在区域内，即抛 `DocumentIntegrityError("DocumentIR→DOCX", {"blocking_quality_flags": ["ir_docx_integrity:toc_coalesced_outside_region"]})`。

不放进 `_validate_render_evidence`，否则持久化读取会重新判定历史产物（PRD 非目标）。

`len(text_policies) == len(list_items)` 已由 `_plan_toc_formula_paragraphs` 的 `zip(strict=True)` 和证据校验第 205 行保证，不重复检查。

## 5. 阻断码登记

| 码 | 边界 | 登记位置 |
|---|---|---|
| `source_ir_integrity:list_item_count_mismatch` | MinerU→DocumentIR、DocumentIR→DOCX | `review.py::_SAFE_FLAGS`、`render_event_summary.py::FIXED_FLAGS` |
| `ir_docx_integrity:toc_coalesced_outside_region` | DocumentIR→DOCX | 同上 |

## 6. 备选方案与取舍

- **在 `DocumentIRMetadata` 存文档级账本**：结构更集中，但会破坏历史 v2 产物的 IR 身份；要么扩展 `legacy_document_ir_payload` 的剔除规则并覆盖 v2 路径，要么接受历史校验失败。放弃。
- **逐项内容哈希**：翻译改写文本，渲染又去掉项目符号前缀，没有独立的规范化定义可用；转换边界用同一函数算哈希属于同义反复。列为非目标。
- **按页限定目录区域**：跨页目录会被截断，并入字段的条目会变成重复的静态文本。按"下一个正文标题"截止更贴近数据手册结构。

## 7. 风险

- 有些文档的目录项被 MinerU 识别为 `heading` 块。按状态机，文本能被解析为目录项的标题不终止区域；不能解析的会提前结束区域。这样只会让剩余目录项按静态文本输出，不会丢内容。
- 没有目录标题、也没有正文标题的文档，区域从第一个目录项延伸到文末，行为与现状相同。
