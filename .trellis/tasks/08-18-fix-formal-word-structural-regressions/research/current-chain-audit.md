# 当前正式链路结构性回退审计

## 样本证据

- 原 PDF：`/Users/sc/Downloads/CM4112,CM4114数据手册_V1.1(1).pdf`，21 页 A4 portrait。
- MinerU v2：`/Users/sc/Downloads/mineru_raw_result 2/*_content_list_v2.json`，21 页、196 block：`page_header=41`、`chart=38`、`paragraph=35`、`page_footer=20`、`page_number=19`、`title=18`、`image=15`、`table=8`、`equation_interline=2`。
- 回退输出：`/tmp/md2word-cm4112-final.XhHq0T/cm4112-fixed.docx`；LibreOffice 26.2.4.2 渲染为 23 页，DOCX 只有 15 个 media/inline drawing，且没有 header/footer part。
- 回退 IR：149 paragraph、18 heading、15 image、8 table、4 list、2 formula、15 asset，并留下 `unsupported_block_type:chart`。
- 本机客户端：`/Applications/wpsoffice.app`、LibreOffice 26.2.4.2。

## 根因定位

### MinerU → DocumentIR

- `app/services/document_ir/mineru_converter.py:233-250`：`chart` 不在 image 映射集合。
- `app/conversion/docx_rules/mineru_content.py:342-364`：现有 `extract_first_asset_path()` 已递归识别嵌套 `image_source.path`，无需新 parser。
- `tests/test_document_ir_mineru_converter_layout.py` 现有 chart 正例使用顶层 `img_path`，因 `_map_block_type()` 的 payload fallback 偶然通过，没有覆盖真实 v2 形状。

### Paragraph → Heading

- `app/conversion/docx_rules/text_semantics.py:37-40`：`HEADING_NUMBER_RE` 明确包含图/表编号。
- `app/services/renderer/text_renderer.py:386-422`：paragraph 在 TOC/list 之后无条件执行 heading-like 推断。
- 实测 `looks_like_heading_text()` 对“图 1 输出电压……”和“图 13 显示了……”均返回 `True`。
- `app/services/renderer/docx_quality.py:288-336` 又维护了一份相近但不完全一致的 heading heuristic，当前只排除英文 Figure/Table，没有排除中文图/表。

### Layout plan → Word sections

- `app/services/renderer/layout_plan.py:86-132` 只按真实左右纵向重叠 band 标 two-col；任一栏提前结束后的单侧尾部被切回 one-col。
- `app/services/renderer/word_renderer.py:508-578` 为每个普通 two-col region 创建 enter/restore continuous sections；纯严格图片对已存在 section-free tab-stop 路径。
- CM4112 首页的 5 个 one-col block 都是 left column tail，不是 wide block；最后 2 个 image 可严格配对。当前区域切分会产生不必要的正文栏退出，再进入图片双栏候选。

### Evidence → Job state

- `app/services/renderer/evidence.py:11-39` 只记录 layout 数量与 DOCX analyzer flags，没有跨边界 expected/actual 对账。
- `app/services/renderer/docx_quality.py:77-107` 的 flags 只覆盖 DOCX 自身结构风险。
- `scripts/dev/formal_mineru_conversion.py:188-206` 先写 DOCX，再构造 evidence。
- `app/domains/document_jobs/execution.py:2210-2265` 构造 evidence 后直接推进 uploading；任何 flags 都不改变状态。

## 最小设计结论

1. chart 复用现有 image contract 与 asset extractor，不新增 DocumentIR block type。
2. v2 以显式 IR type 为准，v1 才保留 heading-like 兼容；不新增样本文本黑名单。
3. planner 只合并可证明为同侧栏尾的 one-col 区域；renderer 继续使用一次原生栏和现有严格图片制表位，不恢复布局表格。
4. 为归一化后的 source block 增加向后兼容的 metadata inventory，并利用每个主 block 现有的 `metadata.source_type` 做 MinerU→IR 映射校验；利用现有 layout plan 与 DOCX OOXML counts 做 IR→DOCX 对账。inventory 只保存计数证据，不复制原始内容或形成第二真相源。
5. 确定性内容丢失与视觉/人工风险分层；用户已裁决确定性丢失失败关闭，普通视觉/人工风险保持非阻断。
