---
doc_type: feature-acceptance
feature: 2026-06-03-word-renderer-editable-output-pass
status: current
summary: renderer editable output pass 的验收闭环，覆盖实现核对、架构/requirement/roadmap 回写和剩余边界。
---

# word-renderer-editable-output-pass 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-03
> 关联方案 doc：`.codestable/features/2026-06-03-word-renderer-editable-output-pass/word-renderer-editable-output-pass-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

**接口示例逐项核对**：

- [x] heading 示例（`app/services/renderer/word_renderer.py` + `app/services/renderer/text_renderer.py`）：`DocumentIRBlock(type="heading", level=2)` 输出 `Heading 2` 或配置样式；`tests/test_document_ir_word_renderer_layout.py::test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics` 和 `test_render_to_bytes_uses_configured_heading_word_style_when_available` 已取证。
- [x] list 示例（`app/services/renderer/text_renderer.py`）：`list_items=["• Low noise", "- Stable supply"]` 输出两个带 `w:numPr` 的段落，可见文本不含手写 marker；renderer OOXML 回归已取证。
- [x] formula 示例（`app/services/renderer/semantic_text.py` + `text_renderer.py`）：`$R_{\theta JA}$, $-40^{\circ}C$` 这类片段先归一化，再经现有 inline rich text 写出上下标；renderer 和 document_jobs 回归均检查 `w:vertAlign` 与常见 TeX 残留。

**名词层“现状 → 变化”逐项核对**：

- [x] `DocumentIRBlock`：未新增 block 类型或字段；实现只消费已有 `type/text/level/latex/list_items/html/captions/footnotes`。
- [x] `TemplateParagraphStyleConfig`：新增可选 `word_style_name`，旧配置缺字段时稳定 fallback。
- [x] `TemplateConfigPackage`：新增可选 `table_note` 和 heading named style fallback；旧 YAML 继续由 `extra="ignore"` 兼容。
- [x] renderer 语义写入：新增 `app/services/renderer/semantic_text.py`，并由 text/table renderer 消费，不把 legacy runtime 变成线上第二渲染入口。

**流程图核对**：

- [x] `DocumentIR block -> renderer semantic adapter -> paragraph/table writer -> DOCX artifact -> document_jobs OOXML regression` 均有落点；grep 命中集中在 `app/services/renderer/*`、`tests/test_document_ir_word_renderer_layout.py` 和 `tests/test_fastapi_jobs_backend.py`。

未发现需要修正 design 或代码的接口偏差。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] heading named style：`DocumentIRWordRenderer` heading 分支调用 `_fill_heading_paragraph()`，默认 `Heading 1/2/3`，可由 `word_style_name` 覆盖。
- [x] list numbering：list 分支调用 `_fill_list_paragraph()`，清理 MinerU marker 并写入共享 bullet numbering definition。
- [x] formula / rich text：formula block、table cell、table note 都经 `normalize_formula_text()`；可表达上下标时走 `<sub>/<sup>` 到 `w:vertAlign`。
- [x] table annotations：caption 在 `<w:tbl>` 前，设置 `keep_with_next`；footnote/table note 在 `<w:tbl>` 后，走 `table_note` 配置。
- [x] document_jobs 回归：fake MinerU fixture 经 eager worker 生成 Word artifact 后读取 OOXML 断言 heading/list/formula/table annotation 语义。

**明确不做逐项核对**：

- [x] 未改前端、HTTP API、Golden Sample manifest 或部署配置；`git diff --name-only` 只包含 renderer、测试和 CodeStable 文档。
- [x] 未声明 Golden Sample P0 正式通过；architecture / requirement / roadmap 均保留样本规模和人工质量阻塞。
- [x] 未把 `app/conversion/runtime` 挂成线上第二渲染入口；该目录只作为既有策略来源和既有测试兼容路径。
- [x] 未处理 TOC leader、完整 landscape section、长表分页视觉还原、扫描件 OCR、样本扩容或真实服务器部署。

**关键决策落地**：

- [x] 只迁移 DocumentIR 当前字段可驱动的策略：见 `word-renderer-editable-output-pass-parity-mapping.md`，heading/formula/table content 标为局部迁移，list/caption 标为直接迁移。
- [x] renderer 侧小型 semantic helper：公式/list 文本归一化放在 `app/services/renderer/semantic_text.py`，避免 `word_renderer.py` 承载大段细节。
- [x] 模板配置向后兼容：新增字段全为可选字段，缺少配置时使用内建 Word style 或 default config。

**挂载点反向核对（可卸载性）**：

- [x] `.codestable/features/2026-06-03-word-renderer-editable-output-pass/`：包含 design、checklist、parity mapping、implementation note 和本 acceptance。
- [x] renderer heading/list/formula/table annotation semantic 写入逻辑：落在 `word_renderer.py`、`text_renderer.py`、`table_renderer.py` 和 `semantic_text.py`。
- [x] 模板配置：落在 `template_config.py` 的 `word_style_name`、`table_note` 和 `heading_word_style_name_for_level()`。
- [x] OOXML 回归：落在 `tests/test_document_ir_word_renderer_layout.py` 和 `tests/test_fastapi_jobs_backend.py`。
- [x] CodeStable 状态回写：architecture、requirement、roadmap items/main 文档均已更新。
- [x] 反向 grep：`semantic_text|word_style_name|table_note|word-renderer-editable-output-pass` 未发现方案清单外的新运行挂载点。
- [x] 拔除沙盘推演：移除上述 renderer/helper/config/test/doc 挂载点即可回退本 feature；`app/conversion/runtime` legacy 本体不需要删除。

## 3. 验收场景核对

- [x] **S1 heading block**：生成段落带真实 Word named style。
  - 证据来源：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics`
  - 结果：通过。
- [x] **S2 list block**：生成段落带 `w:numPr`，可见文本不依赖手写 `• ` prefix。
  - 证据来源：同一 renderer OOXML 回归 + `word/numbering.xml`。
  - 结果：通过。
- [x] **S3 formula block / table cell**：常见 `$...$`、`\sqrt`、`\theta`、`E=mc^2` 残留被归一化，OOXML 有上下标。
  - 证据来源：renderer formula/table 回归与 document_jobs 回归。
  - 结果：通过。
- [x] **S4 table captions / notes**：caption 在 table XML 前，note 在 table XML 后，caption `keep_with_next`，table 仍是可编辑 Word table。
  - 证据来源：`tests.test_document_ir_word_renderer_layout` 表格回归检查 `<w:tbl>` 相对顺序、`w:gridSpan`、`w:vMerge`。
  - 结果：通过。
- [x] **S5 document_jobs eager worker**：fake MinerU / DocumentIR fixture 生成 Word artifact，任务 succeeded，OOXML 语义断言通过。
  - 证据来源：`tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_generated_word_keeps_renderer_ooxml_semantics`。
  - 结果：通过。
- [x] **反向核对**：未改前端，不需要浏览器肉眼验证；未扩 API，不需要 OpenAPI snapshot。

## 4. 术语一致性

- `Editable output pass`：文档中统一用于 renderer 可编辑 Word 语义，不等同完整视觉还原。
- `pipeline-parity-gap`：仍指 legacy runtime 与 API DocumentIR renderer 链路差异；本 feature 只收敛 heading/list/formula/table annotation 基础语义。
- `DocumentIR renderer editable semantic pass`：已在 architecture 中落为当前系统术语。
- 防冲突：未新增 `legacy renderer` 线上入口、未新增 DocumentIR block 类型、未改 HTTP API 术语。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`：已新增 `DocumentIR renderer editable semantic pass` 核心术语，补入 Document Jobs P0 流程描述，并更新 Golden Sample blocked 边界与变更日志。
- [x] `.codestable/architecture/backend-fastapi-service.md`：已补入 `document_jobs -> DocumentIR -> generated Word` 的 renderer 语义能力描述，明确 HTTP API 合同不变，并保留 P0 正式质量边界。
- [x] `.codestable/attention.md`：不需要更新；本 feature 未暴露新的每轮必踩环境/命令陷阱，现有 conda python 与线上 Golden Sample 复跑注意事项仍适用。

归并后，未读 design 的维护者也能从 architecture 知道 generated Word 现在有 heading/list/formula/table annotation 的可编辑 OOXML 语义，以及它不等同 P0 视觉质量通过。

## 6. requirement 回写

- [x] `requirement: fastapi-backend-productization` 指向 current req，本次改变用户可感的 generated Word 输出质量边界，已实际更新。
- [x] `.codestable/requirements/fastapi-backend-productization.md` 已在“怎么解决”补入 renderer generated Word semantic pass，在“边界”说明 `pipeline-parity-gap` 两层基础已接入，同时保留 10-20 样本、真实复跑、人工质量和视觉版面阻塞。

## 7. roadmap 回写

- [x] `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-items.yaml`：`word-renderer-editable-output-pass` 已从 `in-progress` 改为 `done`，`feature` 仍绑定 `2026-06-03-word-renderer-editable-output-pass`。
- [x] `.codestable/roadmap/pdf-to-word-delivery-hardening/pdf-to-word-delivery-hardening-roadmap.md`：子 feature 清单同步为 `done`，观察项和变更日志已同步剩余 P0 风险。
- [x] YAML 校验将作为退出验证执行。

## 8. attention.md 候选盘点

- [x] 无候选：本 feature 未暴露需要补入 `.codestable/attention.md` 的新内容。测试解释器、Golden Sample 线上复跑和部署入口核对注意事项已经存在。

## 9. 遗留

- 后续优化点：回到 Golden Sample live regression，用 `gs-003/004/006/008` 真实复跑观察人工质量是否改善。
- 已知限制：正式 P0 仍缺 10-20 份 manifest-matched PDF、真实复跑和人工质量验收。
- 已知限制：TOC leader、页码对齐、完整 landscape section、长表分页视觉还原、完整 LaTeX parser 和 OMML 公式对象仍不在本 feature 范围。
- 顺手发现：`tests/test_fastapi_jobs_backend.py` 已很大；本次按现有测试结构追加聚焦回归，没有在验收阶段扩大测试文件重组。
