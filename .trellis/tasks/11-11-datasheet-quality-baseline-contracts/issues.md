# 当前质量问题状态

截至 2026-11-17，代码状态以本地 `main@9b537b3a` 为准。各项验收结论沿用对应记录的输入、版本和环境。

## 状态定义

- `open` 表示仍有质量问题或证据缺口待解决。
- `mitigated` 表示已有检测、修正或人工处理路径，覆盖仍有限。
- `closed` 表示列明的具体缺陷已修复，且有对应回归证据。
- `historical` 表示指定旧产物和原观察作为复现证据保留。

## 当前状态总表

| ID / 问题 | 状态 | 当前结论 | 剩余风险或待补证据 | 修复或复现证据 |
| --- | --- | --- | --- | --- |
| `gs-004` OPA228 第 2 页修订历史被 TOC 吸收 | `closed` | 区域外列表保留在正文，列表项有来源账本。 | 整页 P2 新 DOCX 缺少带指纹的验收记录。 | [修订历史回归](#gs-004-修订历史缺项) |
| RS2G04 第 6 页题注和英文脚注翻译遗漏 | `closed` | 题注和脚注纳入翻译。八组注释通过 Word 专项验收。 | 8.1 表前温度条件的译词待复核。 | [注释翻译验收](#rs2g04-英文脚注残留) |
| RS2G04 第 6 页脚注公式降级 | `closed` | `(1)(2)` 在原位置显示为 Word 原生上标。 | 其他不受支持的公式仍可降级。 | [脚注上标验收](#rs2g04-脚注公式降级) |
| `gs-008` OPA228 第 7 页参数值列合并 | `mitigated` | 完整同源样本自动修正 17/23，留存包自动修正 12/18。 | 两份输入各有 6 项带警告交付，仍需复核。 | [数值列合并验收](#gs-008-参数值列合并) |
| `row_ambiguous` 自动证据覆盖率 | `open` | 行取证可按缺失证据给出更具体的诊断。 | 多样本覆盖率待测。 | [覆盖缺口](#当前开放问题) |
| `source_pair_unverified` | `open` | 同源证据不足时保留原跨度和告警。 | 缺少提交证明或逐页对照失败的输入无法自动核定。 | [来源缺口](#当前开放问题) |
| 缺少可信表头语义 | `open` | 同源校核可补足有证据的表头。 | 部分输入仍缺少可信表头。 | [表头缺口](#当前开放问题) |
| 实际人工修改工时数据 | `open` | RS2G04 已有专项验收结论。 | 待补绑定 DOCX 和轮次的修正次数、编辑耗时及审核用时。 | [人工数据](en2zh-human-review.md) |
| `gs-004`、`gs-008` 的 2026-11-14 预审 DOCX | `historical` | 原产物分别复现修订历史缺项和数值跨列。 | 原缺陷随旧产物保留。 | [原观察、文件名及 SHA-256](#2026-11-14-审核副本预审) |

## 当前开放问题

- **`row_ambiguous` 自动证据覆盖率。** 历史报告仍可读取该原因。行取证新增更具体的原因码。两份 P7 固定输入各有六项未决，零基源行 21–24 缺少可靠单位证据（`unit_row_mismatch`），27–28 缺少可靠的跨行公式上下文（`rowspan_context_unresolved`）。多样本自动核定覆盖率待测。 [行取证验收](../archive/2026-11/11-17-table-value-row-evidence/validation.md)
- **`source_pair_unverified`。** 上传 PDF 与解析包的原件可按指纹匹配，符合来源要求的异指纹包可逐页核对。来源证明缺失或逐页结果不一致时，相关单元格保留为未决，可按警告交付合同处理。 [来源与未决回归](../../../tests/test_online_table_value_pdf_binding.py)
- **缺少可信表头语义。** RS2G04 第 6 页留存的 MinerU HTML 未声明 ESD 表首行，绑定同源校核后可生成重复表头。TPLD2001 两段完整 HTML 仍缺可信表头，四行标题保留，`w:tblHeader` 为空。 [表头来源合同](table-header-review.md) · [续表对照](continuation-contract-validation.md)
- **实际人工修改工时数据。** RS2G04 的专项 Word 验收已有结论。仍需按实际审阅的 DOCX 指纹和轮次，记录修正的独立缺陷数、实际编辑耗时及有效审核区间。 [人工记录](en2zh-human-review.md)

## 已缓解问题

### gs-008 参数值列合并

- **状态与提交。** `mitigated`。跨数值列检测 `3833fc7b`，人工核定 `1a416493`，PDF 自动核定 `2669e9b0`，Worker 同包新代 `e00fc24b`，表框取证修正 `8034ead5`。未决警告交付 `6fa8664e`（合并 `5bdea79e`），Word 布局证据对账 `4f80f3c7`（合并 `74157997`），行取证覆盖改进 `0b1c6885`（合并 `57772613`）。
- **当前行为。** 已检测数值格跨越同组独立的 MIN/TYP/MAX 等列。质量表格接口可输出具体表或片段、源页、行、单元格、数值、单位和候选列。来源、行列和数值可由 PDF 几何证实时，可自动修正对应单元格并用 Word 实物核验。符合开关、名单及同源接纳条件的管理员可在原解析包上逐格核定，生成新一代 DOCX。仍为 `unresolved` 的项（包括历史报告中的 `row_ambiguous`）保留原跨度与定位，仍可生成并下载带警告的内部 DOCX，交给用户在 Word 中修改副本。系统正式批准须确认当前表格报告摘要，发布还须满足其余发布条件。 [数值列合同](../../spec/backend/word-generation-rules.md#table-005-参数表数值列归属与复核)
- **对应回归。** `test_parameter_table_value_column_binding.py` 覆盖跨列识别及历史报告。`test_full_gs008_certifies_row_evidence_and_word` 和 `test_retained_p7_real_package_certifies_word_after_table_edge_recovery` 核对两份 P7 输入的源列和实际 DOCX。`test_unverified_row_word_can_be_downloaded_approved_and_published_with_warning` 和 `test_admin_replays_the_same_package_and_publishes_after_actual_word_certification` 覆盖未决交付和管理员同包新代。 [跨列检测回归](../../../tests/test_parameter_table_value_column_binding.py) · [Worker 与交付回归](../../../tests/test_online_table_value_pdf_binding.py)
- **新验收记录。** 行取证改进后的本地 Worker 回放，完整同源样本通过 17/23，DOCX SHA-256 为 `f346f139e4ae655c5ba1ef0e117fd5f37084f5f277e38d00acb020174bb294b5`。18 项留存包通过 12/18，DOCX SHA-256 为 `a14ceb7de147a45659cb9dc6d056ef08e3690f47f2f298a966dc384094017f35`。两份 DOCX 均按独立 PDF 标注逐格核对，观察到 0 项自动错修，各保留 6 项 warning，下载均返回 200。批准及发布 API 的真实 P7 证据来自较早的隔离回放。 [行取证验收](../archive/2026-11/11-17-table-value-row-evidence/validation.md) · [先前批准与发布回放](#gs-008-早期隔离回放)
- **剩余风险。** 自动修正覆盖有充分同源与几何证据的格子。未决格仍需逐格对照原 PDF。已验收的自动修正比例限于两份本地固定输入，生产新提交、线上 Worker、发布后最终件下载及 Word/WPS 视觉效果待验证。 [本地回放边界](../archive/2026-11/11-17-table-value-column-warning-delivery/implement.md#更新后的未验证范围)

## 已关闭问题

### gs-004 修订历史缺项

- **状态与提交。** `closed`。`5b353439`（合并 `ea16ebdd`）将 TOC 合并限制在目录区，新增 `list-item-ledger/v1` 并在生成期拒绝区域外的目录合并。修复前对账已确认 MinerU 和 IR 都保留 14 条 Revision B → C，丢失发生在渲染阶段。`29592706`（合并 `192cf195`）后续用 v2 账本核对真实顺序和逐项摘要。 [根因对账](../archive/2026-11/11-15-toc-region-list-item-ledger/prd.md#背景与证据) · [v2 账本定向验收](../archive/2026-11/11-17-source-item-annotation-ledger/validation.md)
- **对应回归。** `test_toc_like_items_after_body_heading_stay_visible` 检查带点引导符的修订项仍在正文且仅生成一个 TOC 域。`test_generation_rejects_toc_policy_outside_toc_region` 检查越区合并被拒绝。`test_list_item_ledger_blocks_item_count_drift` 检查列表项数漂移，`test_v2_list_ledger_checks_content_order_expansion_empty_slots_and_identity` 覆盖 v2 的逐项校验。 [Word 渲染回归](../../../tests/test_document_ir_word_renderer_layout.py) · [列表合同回归](../../../tests/test_document_ir_layout_contract.py)
- **新验收记录。** 本次核对 `main` 上的实物回归断言。测试以包含 `Added CDM in ESD Ratings` 和 `Changed format of thermal information tables` 的最小修订列表生成 DOCX，核对两项在正文可见、两个策略均为 `bullet`，目录仍为一个原生域。2026-11-15 留存的本地回归日志中，相关模块用例由 182 增至 188，修复前后的失败和错误项相同。 [合并回归](../../../tests/test_document_ir_word_renderer_layout.py)
- **剩余风险。** 归档实施计划列出整页实物验收标准，包括 B → C 全部 14 条、A → B 段落及唯一 TOC 域。当前未找到满足该标准且有新 DOCX 指纹的验收记录。旧预审产物保留原结论，目录刷新及版式仍按桌面客户端验收。 [原验收标准](../archive/2026-11/11-15-toc-region-list-item-ledger/prd.md#验收标准)

### RS2G04 英文脚注残留

- **状态与提交。** `closed`。`06650bd4`（合并 `318f91cb`）把题注和脚注纳入翻译批次、回填及审核证据。`29592706`（合并 `192cf195`）补充按来源位置和摘要核对译文的定向回归。 [注释账本定向验收](../archive/2026-11/11-17-source-item-annotation-ledger/validation.md)
- **对应回归。** `test_annotation_source_positions_and_alias_survive_round_trip_and_apply` 检查源位置和回填；`test_scoped_annotations_split_and_reassemble_in_original_positions` 和 `test_scoped_annotation_missing_or_changed_token_never_applies_partial_replacements` 检查批次重组及技术内容完整性。 [IR 回归](../../../tests/test_document_ir_translation.py) · [翻译完整性回归](../../../tests/test_translation_integrity_execution.py)
- **新验收产物。** 2026-11-15 同源表头校核稿 SHA-256 为 `1e29bc39ae1a8a5496a919a1f88cbbbfec1dbb718df9641c63e0653315bea9bb`。实际翻译响应覆盖八组注释，Microsoft Word 人工验收第 1–8 项全部通过。 [实译与 Word 验收](../archive/2026-11/11-15-datasheet-annotation-translation-superscript/validation.md#microsoft-word-人工验收)
- **剩余风险。** 8.1 表前温度条件中的工作状态与自由空气限定仍有独立译词差异待复核。实译证据使用留存解析包，其他三个翻译方向只有确定性回归。 [译词差异](../archive/2026-11/11-15-datasheet-annotation-translation-superscript/validation.md#温度范围译词差异)

### RS2G04 脚注公式降级

- **状态与提交。** `closed`。`06650bd4`（合并 `318f91cb`）将闭合的纯括号编号脚注标记输出为 Word 原生上标。
- **对应回归。** `test_only_plain_parenthesized_numeric_footnote_markers_use_native_superscript`、`test_numbered_footnote_marker_retains_native_run_position_and_evidence` 和 `test_old_table_note_fallback_replays_after_native_superscript_support` 覆盖支持范围、实际位置及旧报告兼容。 [原生上标回归](../../../tests/test_formula_rendering.py) · [旧报告回归](../../../tests/test_formula_rendering_compatibility.py)
- **新验收产物。** 同一 RS2G04 校核稿的 `block_0003_context_0001.text` 使用 `semantic_runs`，原位置的 `(1)(2)` 带 `w:vertAlign` 的 `superscript` 值，Microsoft Word 人工验收第 9 项通过。 [实物回归](../archive/2026-11/11-15-datasheet-annotation-translation-superscript/validation.md#rs2g04-rev-a4-第-6-页) · [Word 验收](../archive/2026-11/11-15-datasheet-annotation-translation-superscript/validation.md#microsoft-word-人工验收)
- **剩余风险。** 畸形和不受支持的公式仍会按合同降级，旧 DOCX 可重读其原 `text_fallback` 证据。 [公式合同](../../spec/backend/word-generation-rules.md#math-003-解析失败保持原式且降级可审计)

## 历史复现记录

以下保留各次运行的原观察、待核查项和当时的验收结论。

### gs-008 早期隔离回放

真实 P7 留存包回放确认 18 个原跨列发现中 5 项通过修正与实物核验，13 项为 `row_ambiguous`。`±5 µV` 仅占 TYP，`±100 µV` 在该输入中保持单列 MAX。内部 DOCX 下载返回 200。另一次 `main@74157997` 隔离回放中，未确认报告时批准返回 409，确认后批准返回 200，管理员发布返回 201，质量仍为 `warning`。该次主 DOCX SHA-256 为 `dc64c2d32272e8e19d2e05a4cc8ffd1a98058f7a5bccb8ee933f25eb02e06280`。 [P7 实物和新代对照](../archive/2026-11/11-15-table-value-pdf-binding-rollout/validation-table-edge.md) · [P7 下载定向复验](../archive/2026-11/11-17-table-value-column-warning-delivery/implement.md#pr-80-后续补验与-p7-基础质量修复) · [P7 批准与发布回放](../archive/2026-11/11-17-table-value-column-warning-delivery/implement.md#真实-p7-审批发布本地回放)

### 2026-11-14 审核副本预审

使用仓库外审核目录中通过 SHA-256 校验的副本。逐份对照源 PDF，以 LibreOffice 单页预览和 DOCX 的 OOXML 交叉核对。P0 产物来自隔离运行 `20261112T033741Z`。RS2G04 两稿来自同一份第 6 页源 PDF，实链稿和基于已保存中文 IR 的表头校核稿分别记录。预审未填写审核表或签字。[P0 隔离实链](metrics-implementation.md#固定清单隔离实链验收) · [RS2G04 实链与同源校核](en2zh-validation.md#rs2g04-完整链路复验)

#### 优先核查的 P0 内容问题

- **gs-004 · OPA228 第 2 页 · 修订历史缺 11 条。** 源 PDF 的 Revision B → C 小节共 14 条，DOCX 仅保留末 4 条删除重复电源电压或温度条目的记录。缺失的前 10 条涉及编号格式，绝对最大额定值新增双电源电压、输出短路符号、工作温度符号、结温符号，ESD 的 HBM 值更新和新增 CDM，推荐工作条件的单／双电源电压，热阻表格式及 OPA222xP／OPA222xPA 封装变更。Revision A → B 的 1 条新增章节及 ESD 表记录也缺失，只剩小标题。源 PDF 为 `P0/OPA228_P2.pdf`，DOCX 为 `P0/gs-004-docjob_88b99a87d22e.docx`，DOCX SHA-256 为 `e681eee1912d9fc3f1cfd51a21ae17accbe27d396c63164a10837a2f6eb4bf4d`。在 `word/document.xml` 的修订历史段落确认缺项，影响源内容完整性，待定位首次丢失的处理环节。
- **gs-008 · OPA228 第 7 页 · 电气特性表数值列合并。** 源 PDF 的 6.7 节独立区分 `MIN`、`TYP`、`MAX`。DOCX 的首行仍有三个独立列名，数据行却通过 `w:gridSpan` 跨列。例：普通条件下 `VOS` 的 `±5 µV` 从源 `TYP` 变为横跨 `MIN–TYP`，`−40 °C 至 +85 °C` 条件下的 `±100 µV` 从源 `MAX` 变为横跨 `MIN–MAX`。噪声和输入阻抗行也存在数值列合并。源 PDF 为 `P0/OPA228_P7.pdf`，DOCX 为 `P0/gs-008-docjob_3bf569b59c40.docx`，DOCX SHA-256 为 `50fbf7fc64059f1258fbb3ca72424c9a2886ebd118c3b117f7e8198e0891ac3e`。列归属问题已在 DOCX 结构中确认，影响典型值与限值判读，待对照来源 Grid 和渲染投影定位。

#### RS2G04 两稿共有的问题与表头差异

审核副本为 `RS2G04/RS2G04-p6.zh.docx` 和 `RS2G04/RS2G04-p6.zh.header-reviewed.docx`，共用源 PDF `RS2G04/sample_origin.pdf`。两稿及源 PDF 指纹见同源校核观测的 `artifacts`。[同源校核观测](en2zh-rs2g04-live-header-reviewed-observations.json)

- **英文残留。** 两稿 OOXML 均保留 8.1 的五条英文脚注、8.2 的英文使用说明及两条 JEDEC 英文脚注。待人工确认相关安全和使用条件的全译要求，以及“工作自然通风温度范围”“充电器件模型”等术语是否符合预期。
- **脚注标记公式降级。** 8.1 的工作温度条件后，两稿都显示 `【公式降级，需复核】` 和原始 `$^{(1)(2)}$`。源 PDF 在同一位置显示上标脚注标记。待核对上标、脚注编号和对应说明的呈现。
- **ESD 重复表头。** 校核稿给首行增加 `w:tblHeader`，两稿正文和单元格文字、4×4 网格及合并结构相同。HBM、CDM、MM 的 `±4000 V`、`±1500 V`、`±200 V` 与源页一致。两份单页预览画面相同。跨页重复行为待 Word 实物确认。[表头校核记录](en2zh-validation.md#使用本次-mineru-结果复验-esd-表头)

#### 待 Microsoft Word 确认

- **gs-003 · OPA228 第 1 页。** 预览中部分同级列表项变成下一级短横线，`Industrial AC-DC` 和前一项之间有大片留白。确认列表层级、图题归属及签字模板标出的 1 处疑似无样式标题。
- **gs-004 · OPA228 第 2 页。** 原生 `TOC` 域当前只有“更新目录”占位。用临时副本更新目录，确认单页样本应如何呈现原目录条目及页码。修订历史缺项另按正文完整性处理。
- **gs-006 · OPA228 第 6 页。** 三张原生热阻表的抽查数值、单位和封装与源页相符，脚注紧随对应表格。确认后两张表的料号表头换行、单元格可编辑性，以及目标版式分页时的表头要求。
- **gs-008 · OPA228 第 7 页。** 确认预览中显示异常的温度范围连接符及宽表可读性。数值列合并已通过 OOXML 确认。
- **RS2G04 两稿。** 在 Word 中确认中文字形、分页与表格可编辑性，对照图标、警告标题及脚注的版式，并检查校核稿的跨页重复表头。LibreOffice 预览有部分中文显示为方框，对应文字仍可从 OOXML 读取。

### 既有问题与复验记录

| 环节 | 已观察到的差异 | 影响和证据 | 归并方向 |
| --- | --- | --- | --- |
| 上游表头语义 | 多份样本的源 PDF 可确认表头，但 MinerU HTML 只有 `<td>`。RS2G04 实时结果在源 Grid、渲染 Grid 和 Word 都没有重复表头。 | 原生表格结构准确率。原排版三表原始 0/3，校核 3/3。RS2G04 英译中实时原始 0/1，使用绑定校核的同源复验 1/1。[三表对照](table-header-review.md) · [实时结果对照](en2zh-validation.md#使用本次-mineru-结果复验-esd-表头) | 归入表头来源及校核证据的接入问题。每次解析独立绑定其来源身份。 |
| Grid 与 Word 的表头投影 | 原生 `<th>` 完全跨盖下一行且该行没有单元格锚点时，旧源 Grid 只统计锚点行，Word 同时标记被覆盖行。 | 结构准确率及源/实物一致性。最小合成用例已复现，三张实表未触发。[兼容边界](table-header-review.md#三张表的同源对照) | 归入表头投影规则，纳入历史证据重读的兼容验证。 |
| 续表片段缺失 | SN74AC244 原 PDF 第 12 页的续表片段无 HTML，转换生成裁图占位并记录 `table_noneditable_placeholder`。 | 原生表格可编辑性。该页是预期阻断的负例，离线证据验证了表格质量阻断，任务发布状态另需对应证据。[缺表定位](toc-formula-verification.md#整份样本结果) | 归入上游片段完整性。保留负例和阻断行为。 |
| 解析输出的预合并 | TPLD2001 Table 4-1 的 MinerU v2 把两段合并到首页 HTML，次页为空。同次模型结果和预处理版面仍保留两段完整 HTML。 | 原排版回放主表已含全部 20 条引脚数据，次页另产生裁图占位并阻断表格质量。[跨页对照](cross-page-grid-validation.md) | 同包来源和行覆盖验证后只输出一次。SN74AC244 负例因缺少明确续表题注，继续保留裁图和质量阻断。[来源绑定复验](upstream-table-coverage-validation.md) |
| 续表归组的复合表号 | TPLD2001 的两段完整 HTML 均为 8 列，后一页保留 `Table 4-1 ... (continued)`，原分组器将 `4-1` 判为歧义并记录 `insufficient_evidence`。 | 原始对照输出 20×8、4×8 两张原生表，结构完整匹配 0/1。[跨页基线](cross-page-grid-validation.md) | 本批已验证同编号、相容题注和明确续表可归组为一张表。当前真实输入的四行标题因缺少可信表头证据继续保留，归入表头来源问题。[首批复验](continuation-contract-validation.md) |
| 上游图表类型 | TPLD2001 第 3 页 Figure 4-1 是引脚示意图，MinerU 将其归类为表格 `/0/0`。 | 两路 Word 均生成一张额外 10×4 原生表，独立记录意外多表 1。[跨页对照](cross-page-grid-validation.md) | 同块图题与已验证原包图片建立来源绑定。回放保留 Figure 4-1，Table 4-1 仍可编辑，意外多表为 0。[图表来源复验](table-figure-validation.md) |
| 翻译技术内容 | SN74AC244 原 PDF 第 5 页的译文批次触发 `translation_integrity_technical_mismatch`，147 项中 1 项失败。 | 转换成功率受阻。已离线定位到批次，历史记录缺少能归因到具体单元格的响应证据。[失败批次](en2zh-validation.md#sn74ac244-英译中失败批次的离线定位) | 归入翻译技术内容完整性，按相同错误类别收集可比较的证据。 |

已闭环的历史项继续作为回归证据。SN74AC244 目录公式修复已验证 118/118 写入及 LibreOffice 刷新后可定位，Word/WPS 客户端覆盖待补。MinerU 401 已通过更新过期凭据恢复，随后 RS2G04 成功运行完整链路。[目录公式记录](toc-formula-verification.md) · [完整链路记录](en2zh-validation.md)

指标缺测、样本量不足和客户端覆盖不足登记在[验收证据](validation.md#当前重点的验收证据)，用于决定补采顺序。
