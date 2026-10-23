# 当前 Word 规则定向摘录（RND-504）

本文件仅摘录当前规范，避免 102309 字节全文在 context 注入时截断；不是第二份规范。源文件为 `.trellis/spec/backend/word-generation-rules.md`，HEAD `01e6c1a`，源 SHA-256 `aecc22bada0b8893b2e0fae1dea329ae42368f9936753b84d2917cd83d5ceadd`。实施前若源变化须重新读取对应原节；公式/图片来源认证还须按原规范后半部分和当前源码核验，不能只凭摘录推断。


原文定位：.trellis/spec/backend/word-generation-rules.md:38

### PIPE-001 正式转换链路唯一性

- 状态：`enforced-tested`
- 输入信号：本地 MinerU 目录/ZIP，或线上任务已下载的 MinerU 结果 ZIP。
- 正式 owner：`scripts/dev/formal_mineru_conversion.py::run_conversion`、`::convert_formal_mineru_package`；`app/domains/document_jobs/execution.py::DocumentJobExecutionService._convert_and_save_document_ir`、`._render_and_save_word`。
- 预期输出：先由 `MinerUToDocumentIRService.convert_zip()` 生成并持久化 DocumentIR，再由 `DocumentIRWordRenderer.render_to_result()` 一次生成 DOCX 和公式报告，再构建 renderer evidence（旧 `render_to_bytes()` 保持 bytes 兼容）；所有正式修复都落在该链路的唯一 owner。
- 冲突/例外：调试脚本可以包装正式 adapter，但不得切换到旧 runtime；`document-ir/v1` 的 renderer 顺序回退仍属于正式 renderer 内部兼容路径。
- 禁止：直接用 `full.md` 生成正式 Word；在 CLI、任务 worker 或样本 runner 中复制转换/渲染规则；以旧 runtime 的输出替代正式结果。
- 自动验证：`tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_main_calls_formal_conversion_adapter`、`.test_formal_adapter_converts_minimal_mineru_package_to_openable_docx`；`tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets`。
- 样本证据：已提交 `ti-opamp-opa228-p1-smoke` 最小 MinerU 包可离线运行；只证明正式链路可运行和 DOCX 可打开，不证明复杂版式。
- 来源/取代：commit `32edca58` 的正式链路 parity 收敛；取代把 `app/conversion/runtime/*` 编排视为正式生成入口的历史描述。


原文定位：.trellis/spec/backend/word-generation-rules.md:126

### IR-001 DocumentIR 是内容与版式事实的正式边界

- 状态：`enforced-tested`
- 输入信号：MinerU block type、page index、bbox、角色、物理页尺寸、caption/footnote、图片资产和源顺序。
- 正式 owner：`app/services/document_ir/models.py::DocumentIR`、`::DocumentIRPage`、`::DocumentIRBlock`、`::DocumentIRBlockLayout`；`app/services/document_ir/mineru_converter.py::MinerUToDocumentIRService._convert_blocks`。
- 预期输出：v2 IR 分离 block 语义和 layout 信号，记录原始 `source_index`、缺失 layout/bbox 的 quality flag，并把不支持的正文类型显式降级为 paragraph。
- 冲突/例外：IR 记录源事实，不决定模板字体、Word 绝对纸张尺寸或实际分页结果。
- 禁止：把渲染决策写回 MinerU 原始 JSON；在 renderer 重新猜另一套 block type；丢弃未知正文而不留标记。
- 自动验证：`tests.test_document_ir_layout_contract.DocumentIRLayoutContractTests.test_v2_payload_round_trips_page_and_block_layout`；`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_outputs_v2_pages_layout_roles_and_annotations`、`.test_convert_zip_records_missing_layout_source_and_bbox`。
- 样本证据：线上合成任务测试持久化 raw IR 和图片资产；没有当前复杂真样本 IR 基线。
- 来源/取代：commit `32edca58` 的正式 IR 收敛。


原文定位：.trellis/spec/backend/word-generation-rules.md:272

### COL-003 严格图片行与无边框布局表格

- 状态：`enforced-tested`（RND-503结构/内容与恢复本地验证通过；Word/部署预览尚待人工验收）。
- 输入信号：最终IR同页、源连续image run，具有有效有限bbox与页面尺寸；不跨正文/真实section，不猜caption归属。
- 正式owner：`app/services/renderer/layout_plan.py`拥有image-group/v1；image_renderer/word_renderer只消费其计划和单次有效输入。
- 预期输出：确认行用固定1×N无边框Word布局表格，每图inline且等比；各自caption/footnote在本cell完整独立渲染。共同纵向交集/max高≥0.80，高度比≥0.80，中心偏移/min高≤0.10，顶边偏移/页高≤0.015，相邻横向间隔/页宽≤0.08且不重叠；全部成立、源序与x序一致并无竞争才接受。连通分量须全组复核，不能传递猜配。
- 冲突/例外：替代旧COL-003的25%/75%制表位图片例外；普通正文COL-002继续原生栏。IR-204 uncertain/evidence-only竞争否决并排；正常多annotation不是拒绝理由；不确定按源序单图并标记。
- 禁止：全局bbox重排，复制/拆分或搬独立段落caption，仅凭marker/总数豁免数据表对账；布局表不能伪造数据表可编辑性。
- 自动/样本验证：可靠图5/6与24/25、单图/阈值/OOXML/历史恢复/冻结输入/B1有定向测试；全新critical复审另覆盖原生栏混合单图、全部报告键缺失、模板继承定位及真实旧产物兼容。各轮unit/component/direct/release/B1和LibreOffice辅助预览的准确结果见任务implementation-validation.md与post-implementation-review.md；Word/部署预览/Golden未验边界仍独立记录，不以本条代签。
- 来源/取代：2026-10-23用户接受的RND-503 v2；原制表位行为仍保留在旧测试/历史证据中，不再约束新图片writer。


原文定位：.trellis/spec/backend/word-generation-rules.md:331

### TABLE-001 原生可编辑表格与 span 保真

- 状态：`enforced-tested`
- 输入信号：IR table block 的 HTML table、rowspan/colspan、表格规模和模板表格配置。
- 正式 owner：`app/services/renderer/table_renderer.py::_render_table`、`::_render_standard_html_table`、`::_render_expanded_table`；解析依赖 `app/conversion/runtime/table_html_parser.py::parse_html_table`。
- 预期输出：可解析 HTML 生成原生可编辑 Word table；标准路径保留 gridSpan/vMerge；超过规模阈值时展开为规则行列，而非图片化。
- 冲突/例外：parser 是正式 renderer 的实际依赖，但 legacy table writer/characterization tests 不是正式证据；无效 HTML 受 TABLE-004 缺口约束。
- 禁止：把表格截图作为默认输出；为某一列数复制新 renderer；以旧 runtime writer 的测试声称正式输出已覆盖。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_html_table_spans_and_annotations`、`.test_render_to_bytes_styles_later_th_cells_as_table_headers`。
- 样本证据：OPA228 P6/P7 manifest 包含表格焦点但当前 Golden 未实际转换；CM4112 表格为 external negative evidence。
- 来源/取代：commit `32edca58` 正式 renderer 收敛；保留共享 parser，取代旧 writer 权威性。


原文定位：.trellis/spec/backend/word-generation-rules.md:465

### MATH-003 解析失败保持原式且降级可审计

- 状态：`enforced-tested`
- 输入信号：非空数学中的未知命令、畸形语法、不支持结构或不能证明安全的归一化。
- 正式 owner：共享 `FormulaRenderResult` 与 renderer 单次 context；`docx_quality.py` / `evidence.py` 校验最终字节。
- 预期输出：原位置 literal run 写 `【公式降级，需复核】` 加逐字原式，mode=`text_fallback`、warning=`formula_text_fallback`；reason 仅 `unsupported_command/invalid_syntax/unsupported_structure/unsafe_normalization`。原式不再按 HTML 解析或术语替换。合法 semantic sub/sup 内 b/i 和换行保留原生样式；未闭合/错配 HTML 为 invalid_syntax，嵌套脚本或 semantic 脚本包裹显式/裸 TeX 数学的未支持组合为 unsupported_structure，整式降级，不能丢掉外层脚本。
- 冲突/例外：空源仍按输入完整性失败；缺内容、锚点或输出绑定损坏仍失败关闭。仅在报告、可见提示、原式与预期输出一致的受控区域允许原始 TeX；其他残留保持 `docx_latex_residue:*`。旧无报告 analyzer 仍保留原残留字段，不伪造通过。
- 禁止：失败删公式/空段落；用 broad catch 把 XML/文件/程序错误变成降级；将 warning 塞进 fatal flags；为清残留放宽全局扫描。
- 自动验证：`tests.test_formula_rendering` 的失败原因、精确保真和篡改测试；`tests.test_document_job_result_persistence` 的三入口恢复与质量投影。
- 样本证据：合成失败公式与当前本地报告；真 Word 视觉签字另行记录。
- 来源/取代：RND-502 v2；将原普通文本回退升级为有提示、逐式证据与预期输出绑定的受控文本降级。


原文定位：.trellis/spec/backend/word-generation-rules.md:527

### QUALITY-001 DOCX 结构证据与风险标记

- 状态：`enforced-tested`
- 输入信号：生成的 DOCX bytes/file 以及 DocumentIR/layout plan。
- 正式 owner：`app/services/renderer/docx_quality.py::analyze_docx_quality_bytes`、`::build_docx_quality_flags`；`app/services/renderer/evidence.py::build_renderer_evidence`。
- 预期输出：记录可编辑段落/表格、heading、numbering、TOC clue、keepNext、表头/cantSplit、宽表、横向节、图片和 LaTeX residue 等 OOXML 指标，并对无可编辑内容、图片化、手写列表、静态目录、未样式化标题、公式残留等风险生成 flag。
- 冲突/例外：指标或 flag 只证明包内结构，不证明 Word 实际页数、溢出、栏平衡、表格不挤压或图片清晰；`wide_table_count`/`landscape_sections` 当前不会自动形成方向风险 flag。
- 禁止：把 `quality_flags=[]` 当作视觉验收通过；把“可打开”当作质量通过；用 analyzer 指标替代真客户端排版。
- 自动验证：`tests.test_golden_sample_manifest.GoldenSampleManifestTests.test_docx_quality_analysis_reads_ooxml_structure_without_python_docx`、`.test_docx_quality_flags_obvious_word_semantics_risks`、`.test_docx_quality_analysis_flags_image_only_docx`；`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_renderer_evidence_summarizes_layout_and_docx_quality`。
- 样本证据：线上 worker 持久化 evidence；只有 `blocking_quality_flags` 触发失败关闭，既有非阻断 `quality_flags` 仍允许成功并进入人工复核。
- 来源/取代：commit `32edca58` 的 OOXML evidence 合同。


原文定位：.trellis/spec/backend/word-generation-rules.md:539

### QUALITY-002 样本证据必须分层

- 状态：`implemented-gap`
- 输入信号：Golden manifest、component MinerU manifest、验收记录、外部本地文件和历史报告。
- 正式 owner：`tests/fixtures/golden_samples/manifest.yaml`、`tests/fixtures/component_pdf_samples/manifest.yaml` 的治理合同；执行入口 `scripts/dev/run_component_pdf_regression.py::run_regression`。
- 预期输出：明确区分 committed runnable fixture、committed PDF 但执行依赖外部环境、external evidence 和 historical evidence；空验收模板不算验收记录，旧 commit 的 signoff 不证明当前版本。
- 冲突/例外：Golden governance tests 证明清单库存和签字协议，不证明 4 个 PDF 已被当前 renderer 转换；component runner 只证明最小包成功/可打开。`external`/`historical` 的分类目前仍依赖规范和 reviewer 纪律，没有自动化 owner 阻止错误升级证据层级。
- 禁止：把 `/Users/...` 文件、`tests/tmp` 未跟踪报告或历史哈希写成长期门禁；把 manifest 的 acceptance focus 写成已通过断言。
- 自动验证：`tests.test_component_pdf_sample_governance.ComponentPdfRegressionRunnerTests.test_regression_runner_converts_committed_minimal_mineru_sample`；`tests.test_golden_sample_manifest.GoldenSampleManifestTests.test_manifest_defines_required_sample_coverage`、`.test_current_sample_inventory_reports_four_runnable_samples`、`.test_admin_manual_signoff_requires_matching_job_and_docx_hash`。
- 样本证据：committed：OPA228 P1/P2/P6/P7 PDF、OPA228 P1 最小 MinerU 包；external：SC2167、CM4112/CM4114、TPL51200、BL0942、RS2G04；historical Golden 4/4 绑定旧 commit `20d496e...`。
- 来源/取代：Golden/component 样本 README、manifest 和归档 acceptance audit；取代把一次性本地结果写成当前回归通过。


原文定位：.trellis/spec/backend/word-generation-rules.md:563

### QUALITY-004 输入丢失与质量 flag 不得伪装成功

- 状态：`enforced-tested`
- 输入信号：有 source inventory 的 v2 source→IR 对账，及任意 DocumentIR→layout→DOCX 渲染结果。
- 正式 owner：source→IR 由 `app/services/document_ir/integrity.py`；IR→layout/DOCX evidence 由 `app/services/renderer/evidence.py`；发布边界由正式本地 adapter 和 `DocumentJobExecutionService` 负责。
- 预期输出：evidence 同时记录 expected、actual、差值和稳定 `blocking_quality_flags`。可见 body block 必须且只能进入 layout 一次；每个可渲染 image/table 和 v2 显式 heading 必须分别对应一个 DOCX drawing/table/heading。确定性丢失失败关闭：source→IR 在线任务归类 `document_ir_failed`，IR→DOCX 归类 `render_failed`，本地不发布最终 DOCX。
- 冲突/例外：LaTeX residue、实际分页、栏平衡、清晰度和其他现有 `quality_flags` 仍是非阻断人工复核风险；旧 IR 无 inventory 时只跳过 source 对账，不能跳过 IR→layout/DOCX 对账。
- 禁止：把全部 quality flags 升级为 fatal；先写入/上传最终 DOCX 再检查；吞掉完整性异常或返回伪成功。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_renderer_evidence_blocks_missing_layout_drawing_and_table`；`tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_formal_adapter_does_not_publish_docx_when_renderer_integrity_blocks`；`tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_integrity_gates_fail_before_ir_or_word_publication`。
- 样本证据：CM4112 当前 external 样本 expected/actual 为 53/53 drawings、8/8 tables、18/18 headings，`blocking_quality_flags=[]`；旧候选 15 drawings 的确定性丢失现会被阻断。
- 来源/取代：当前正式代码/调用链审计发现。

RND-502 补充：`formula_text_fallback` 是内容完整、可见、可审计的 warning，不是 fatal。新报告中的源/锚点/预期输出投影不一致属于确定性完整性失败，必须阻断新候选；receipt 后损坏按 uploading/oss_failed 保留选件，不重渲染掩盖。详细版本合同见下方 RND-502 场景。
