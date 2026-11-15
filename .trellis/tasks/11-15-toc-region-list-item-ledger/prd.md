# 目录合并区域约束与列表项级账本

## 背景与证据

预审问题 gs-004（见 `../11-11-datasheet-quality-baseline-contracts/issues.md`）：OPA228 第 2 页修订历史 Revision B→C 源有 14 条，DOCX 只剩 4 条；Revision A→B 的 1 条段落也缺失。

2026-11-15 用本地 MinerU 产物 `mineru_result/OPA228_P2.pdf-7cb51602…` 只读复现，逐环节对账结果如下：

| 环节 | Revision B→C 列表 |
|---|---|
| MinerU `content_list` / `content_list_v2` 源块 `/7` | 14 项 |
| 当前 `MinerUToDocumentIRService` 输出 `block_0008` | 14 项，完整 |
| 当前 `DocumentIRWordRenderer` 输出 DOCX | 13 项，缺 "Changed format of thermal information tables…​.. 6" |
| 预审 DOCX `gs-004-docjob_88b99a87d22e.docx` | 4 项，A→B 段落也缺 |

根因：`render_plan.py::build_render_plan` 把**全文档**所有能被 `parse_toc_entry_text` 认出的文本（标题 + 点引导符 + 页码）都设为 `toc`/`coalesced`，并入唯一的原生 TOC 字段。修订记录同样带页码，被吞进目录字段。渲染证据把 `coalesced` 当作合法去向，`render_evidence_validation` 只核对"证据与计划一致"，不核对"计划选择合并是否合理"，所以完整性门放行。

附带确认的合同缺口：`integrity.py::build_source_integrity` 对列表只检查 `list_items` 非空，不对账项数。`content_list_v2` 的空项会在 `mineru_list_items` 中被静默过滤，没有任何记录。

预审 DOCX 丢 10 条、当前代码复现只丢 1 条，差异来源（代码版本、模板或模式）未追溯。两者机制一致，本任务以当前代码的复现为准。

## 目标

- G1：TOC 合并只发生在目录区域内。区域外看起来像目录项的文本按普通正文或列表项输出，保留原文。
- G2：在 MinerU→DocumentIR 边界冻结每个列表块的项数账本，之后在转换出口和渲染入口两处对账。
- G3：渲染阶段校验每个 `toc`/`coalesced` 文本策略都落在独立重算的目录区域内，否则阻断。

## 非目标

- 表格几何账本（行列、rowspan/colspan、单元格哈希）。现有 `ir_docx_integrity:table_geometry_mismatch` 继续生效；gs-008 列合并另行立项。
- 题注/表注数量账本（`annotation_count_mismatch`）。
- 跨翻译的列表项内容哈希对账。翻译会改写文本；转换边界上用同一函数算哈希属于同义反复，不能证明什么。
- 重新判定或回填历史产物。历史 IR 没有账本时跳过对账，历史计划不重放。
- 改变目录区域内部的既有行为（区域内无页码项仍按列表项输出，仍只写一个 TOC 字段）。
- 追溯预审 DOCX 与当前复现之间的差异来源。

## 需求

- R1 目录区域：按写入顺序扫描正文操作，区域从第一个目录锚点开始，到其后第一个"非目录正文标题"结束，全文只有一个区域。
  - 目录锚点：文本满足 `is_toc_title_text` 的标题或段落，或第一个被 `parse_toc_entry_text` 识别的文本项。
  - 区域终止：`heading` 块或被推断为 heading 的段落，且其文本既不是目录标题，也不是目录项。
  - 区域外禁止产生 `toc_title`、`toc`、`coalesced`、`toc_formula`、`toc_formula_first`。
- R2 列表项账本 `list-item-ledger/v1`：转换器在每个主列表块的 `metadata["list_item_ledger"]` 中记录选中字段、读取模式、源项数、空项数和 IR 项数（源指针沿用 `metadata.mineru_source`）。`v2_items` 与 legacy 字符串项必须满足 `源项数 = IR 项数 + 空项数`，否则转换失败；legacy dict 展开项和 `selected_text` 模式只记录 IR 项数。不修改 `DocumentIRMetadata` 模型，以免改变历史 render-plan/v2 产物的 IR 身份哈希。
- R3 账本对账：`build_source_integrity` 在任一主列表块带账本时，要求所有主列表块都带账本，且 `len(list_items)` 等于账本项数，否则报 `source_ir_integrity:list_item_count_mismatch`。转换出口和渲染元数据（翻译之后）两处共用该函数。历史 IR 的 `source_integrity` 输出结构保持不变。
- R4 渲染去向：生成期渲染结果校验（`validate_render_result`）独立重算目录区域。区域外出现目录类文本策略时报 `ir_docx_integrity:toc_coalesced_outside_region`，并阻断发布。持久化读取路径不加此检查。
- R5 证据不含正文：新证据只含指针、块 ID、计数和稳定码。
- R6 新阻断码登记进 `review.py::_SAFE_FLAGS` 与 `render_event_summary.py` 的固定码集合。
- R7 Spec：更新 `word-generation-rules.md` 的 FIELD-001（区域规则与禁止项）和 INPUT-004（列表账本），并登记新阻断码。
- R8 清理 `mineru_content.py` 中重复定义的 `select_mineru_list_source` 与 `mineru_list_items`（内容相同，保留一份）。

## 验收标准

- [ ] AC1：OPA228 P2 本地产物渲染后，Revision B→C 14 项与 Revision A→B 段落全部可见；TOC 字段仍为 1 个；目录区域内条目仍并入字段。
- [ ] AC2：`test_render_to_bytes_uses_one_native_toc_field_for_toc_like_entries` 及既有 TOC 公式、表格上下文、预览映射用例不改断言即通过。
- [ ] AC3：新用例——目录区域后的正文标题下，带点引导符和页码的列表项渲染为可见列表项，计划中该项不是 `toc`/`coalesced`。
- [ ] AC4：新用例——篡改 IR 某列表块的项数后，转换出口抛 `DocumentIntegrityError`，渲染证据含 `source_ir_integrity:list_item_count_mismatch`。
- [ ] AC5：新用例——`content_list_v2` 含空项时账本记录空项数，转换成功；源项数与 IR 项数加空项数不等时阻断。
- [ ] AC6：新用例——人工构造区域外的 `coalesced` 计划，渲染证据校验报 `ir_docx_integrity:toc_coalesced_outside_region`。
- [ ] AC7：无账本的历史 IR 不报列表账本相关阻断码。
- [ ] AC8：新阻断码在 review 与 render event summary 中按固定码投影，不计入 unknown。
- [ ] AC9：Spec 已更新，文字与实现一致。

## 已确认（2026-11-15，用户按默认方案确认）

- Q1：区域外目录样式文本按普通列表项/段落输出，**保留**点引导符和源页码原文（不删除、不改写）。已接受。
- Q2：全文只允许一个目录区域；后续再出现的目录样式区域一律按正文输出（会显示静态点线文本，不会丢失）。已接受。
- Q3：不提升 `word-renderer-policy` 版本。理由：持久化计划逐项显式记录 mode，历史计划不重放，`plan_sha256` 已区分新旧输出。已接受，不新增 policy 版本。
