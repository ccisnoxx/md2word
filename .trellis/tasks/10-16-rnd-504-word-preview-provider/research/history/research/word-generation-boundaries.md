# Word 生成规则：RND-504 必要边界摘录

来源为 `.trellis/spec/backend/word-generation-rules.md`；源文件 SHA-256：`9e64119193165326b254fb1394a25c86ea5a156cb29d797831c86fd03c2fb720`。

完整规范为唯一权威。本摘录仅解决 32 KiB context 注入上限，不新增或取代规则；实现前按规则 ID 重核源文。RND-504 不修改布局/表格/字体/分页，若发现必须修改这些 owner，应先回到规划核对新增范围及对应规则，而非依赖本摘录推断。

### PIPE-001 正式转换链路唯一性

- 状态：`enforced-tested`
- 输入信号：本地 MinerU 目录/ZIP，或线上任务已下载的 MinerU 结果 ZIP。
- 正式 owner：`scripts/dev/formal_mineru_conversion.py::run_conversion`、`::convert_formal_mineru_package`；`app/domains/document_jobs/execution.py::DocumentJobExecutionService._convert_and_save_document_ir`、`._render_and_save_word`。
- 预期输出：先由 `MinerUToDocumentIRService.convert_zip()` 生成并持久化 DocumentIR，再由 `DocumentIRWordRenderer.render_to_bytes()` 生成 DOCX 和 renderer evidence；所有正式修复都落在该链路的唯一 owner。
- 冲突/例外：调试脚本可以包装正式 adapter，但不得切换到旧 runtime；`document-ir/v1` 的 renderer 顺序回退仍属于正式 renderer 内部兼容路径。
- 禁止：直接用 `full.md` 生成正式 Word；在 CLI、任务 worker 或样本 runner 中复制转换/渲染规则；以旧 runtime 的输出替代正式结果。
- 自动验证：`tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_main_calls_formal_conversion_adapter`、`.test_formal_adapter_converts_minimal_mineru_package_to_openable_docx`；`tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets`。
- 样本证据：已提交 `ti-opamp-opa228-p1-smoke` 最小 MinerU 包可离线运行；只证明正式链路可运行和 DOCX 可打开，不证明复杂版式。
- 来源/取代：commit `32edca58` 的正式链路 parity 收敛；取代把 `app/conversion/runtime/*` 编排视为正式生成入口的历史描述。

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

### QUALITY-003 版式行为变更必须过冲突与整文档视觉门禁

- 状态：`planned`
- 输入信号：任何改变分页、分节、分栏、表格、图片尺寸、字体/边距或公式文本长度的正式 owner 修改。
- 正式 owner：尚无自动化 owner；治理入口为本文“规则变更流程”，现有 Golden 回归和 component runner 只能提供部分基础设施。
- 预期输出：先运行受影响规则的正式单测，再运行冲突矩阵共同回归；用正式入口生成 committed 样本/受影响 external 样本，并在 Word/WPS（必要时 LibreOffice 辅助）检查实际页数、空白页、关键内容组落页、表格挤压、栏平衡和图片清晰度，记录当前 commit/hash。
- 冲突/例外：不默认要求 PDF 与 Word 页数完全一致；但页数变化和内容溢出必须解释并人工判断，不可被局部 OOXML 断言掩盖。
- 禁止：只凭一个新 PDF 或局部单测通过合并结构性布局变更；用 LibreOffice 单一结果替代 Word/WPS；旧验收记录跨 commit 复用。
- 自动验证：当前无整文档分页/视觉自动门禁。Golden preflight/signoff 测试只验证治理协议，component runner 只验证可打开。
- 样本证据：R6/R7 后 CM4112 候选经 LibreOffice 26.2.4.2 得到 23 页，图 33/“工作原理”分别位于第 14/15 页；WPS CLI 与 WPS 12.1.26055 GUI 均为 20 页，图 31～33 及完整题注位于第 12 页，“工作原理”直接从第 13 页开始，旧 `±/18V)` 碎片极稀疏页消失。WPS 仍提示“缺失字体”，CLI 仍存在单位/公式替换字符。由于 GUI 未逐页放大复核全部 20 页，且 LibreOffice/WPS 仍有 23/20 页客户端差异，本规则保持 `planned`，不能写成整文档视觉通过。完整边界见本任务 `research/cm4112-validation.md`。
- 来源/取代：本任务 PRD；明确补上 `674ce937` 后局部测试通过但整文档负优化的缺口。

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
