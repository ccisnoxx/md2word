# RND-502 必要 Word 合同摘录

实施基线：c56e128；2026-10-23；用户已审核 v2 并授权实施。真源：`.trellis/spec/backend/word-generation-rules.md`；SHA-256：`3fbdf75bf6e13e0ba75912c7416fa5480dc7461b2b632bba1f78488c0da89251`。

原文件超过注入上限 32768 bytes；以下逐字摘录当前任务必要规则，不是第二真源。实施/检查还须分段读取原文件冲突矩阵及末尾 RND-502 可执行合同；本摘录随本任务实际 Spec 修改同步。当前验证状态以任务 validation 记录为准，不以规则标签代替实际证据。

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

### TEXT-003 富文本与普通正文保真

- 状态：`enforced-tested`
- 输入信号：v2 rich text、inline HTML 的 sub/sup/bold/italic、普通文字和术语配置。
- 正式 owner：`app/services/renderer/text_renderer.py::_fill_paragraph`、`::_render_mixed_math`、`::_render_inline_children`、`::_prepare_text_for_rendering`；`app/services/renderer/semantic_text.py`。
- 预期输出：支持的 inline 标记转为 Word run 语义；数学先分段，普通文本单独进行术语替换；数学与降级原式不经过术语替换或有损归一化，普通正文和未知路径字符保持可见。
- 冲突/例外：原生 OMML 只在共享扫描识别的数学片段或显式 formula block 生成；普通正文不因包含分式而整体进入 OMML，新增识别规则必须覆盖非数学负例。不支持的 inline markup 应保持可见文本。
- 禁止：为公式清理全局删除反斜杠/括号/空格；静默丢弃未知 inline node；在表格、正文和题注维护不同清理实现。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_inline_rich_text_markup`、`.test_render_to_bytes_applies_subscript_config_to_formal_renderer_outputs`。
- 样本证据：无当前 committed 富文本真样本。
- 来源/取代：commit `32edca58` 和 `674ce937` 的共享文本路径。

### TEXT-004 富文本题注节点不得拆成多条题注

- 状态：`enforced-tested`
- 输入信号：v2 table/image/figure/chart caption 字段中的 flat inline-node list，或 legacy string list/多个 nested rich-node groups。
- 正式 owner：`app/services/document_ir/mineru_converter.py::MinerUToDocumentIRService._captions`；现有文本/公式清理 helper 只作为片段归一化依赖。
- 预期输出：一个 flat `text/equation_inline/text` 节点数组形成一个完整 `DocumentIRBlock.captions` 元素，进入 Word 后只占一个题注段落；string list 和多个 nested rich groups 继续形成多条独立题注。可见 inline 语义、SEQ/bookmark、fallback、table context 和 COL-003 annotation 数量判断均基于完整逻辑题注。
- 冲突/例外：footnote 继续按现有 marker/连续性规则合并；无可靠结构时保持原分组，不按图号、标点、页码或 bbox 猜测。renderer 继续坚持“一 caption 元素一段落”，不负责恢复 converter 已丢失的边界。
- 禁止：用 `collect_text_from_fields()` 把 flat rich nodes 直接拍成多条 captions；在 image/table renderer 合并相邻题注；修改 continuous section 或 `pageBreakBefore` 掩盖孤立题注行。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_maps_nested_v2_chart_to_image_and_records_source_inventory`、`.test_convert_zip_preserves_multiple_logical_caption_groups`、`.test_rich_chart_captions_render_without_isolated_fragments_and_keep_paired_layout`、`.test_convert_zip_demotes_table_condition_caption_to_context_paragraph`。
- 样本证据：CM4112 新候选的图 33 为单条 `['图 33 通道隔离度 (± 18V)']`，OOXML 不含仅为 `±`/`18V)` 的段落；WPS GUI 第 12 页实际包含图 31～33 及完整题注，第 13 页直接以“工作原理”起页，旧碎片极稀疏页消失。完整记录见当前任务 `research/cm4112-validation.md`。
- 来源/取代：当前任务新增目标；取代把富文本 inline node 数量当作 annotation 数量的行为。

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

### TABLE-002 表题、条件正文、表体和表注顺序

- 状态：`enforced-tested`
- 输入信号：table captions、condition/context-like annotation、table HTML 和 footnotes。
- 正式 owner：`app/services/document_ir/table_annotations.py::split_table_annotation_texts`、`::is_table_context_annotation`；`app/services/renderer/table_renderer.py::_render_table_captions`、`::_render_table_notes`。
- 预期输出：真表题在表格前，条件/测试环境文字降为普通 context paragraph 并在表格前，表注在表格后；context 不生成 SEQ 题注。
- 冲突/例外：页顶表格组的分页挂在首个真实 caption/context；复合编号题注按 FIELD-002 处理。
- 禁止：把测试条件当作表题；把表注放到表格前；为修分页拆散 caption/table/note 内容组。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_demotes_table_condition_caption_to_context_paragraph`；`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_html_table_spans_and_annotations`、`.test_render_to_bytes_renders_context_like_table_caption_as_body_text`。
- 样本证据：CM4112 表格条件为 external evidence；线上合成 worker 测试覆盖 portrait wide table/context，但非视觉样本。
- 来源/取代：commit `32edca58` parity 审计。

### MATH-001 v2 公式输入只接受明确数学字段

- 状态：`enforced-tested`
- 输入信号：v2 block 的 `content` dict 及 `math_content`/公式字段；legacy block 的历史字段。
- 正式 owner：`app/services/document_ir/mineru_converter.py::_formula_text`、`::_text_for_block`。
- 预期输出：v2 公式只从非空字符串数学字段读取，避免把元数据 dict 序列化为公式；legacy JSON 才使用其兼容字段。
- 冲突/例外：缺失/无效 v2 math field 会返回 `None`，并由 IR-004 的 source inventory 对账产生稳定 `source_ir_integrity:payload_missing:*` 阻断标记；不得降级成普通文本继续发布。
- 禁止：对 v2 dict 执行 `str(content)`；因公式字段坏掉而回退读取 `full.md`；猜测任意 text 为公式。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_structures_v2_multiline_lists_and_preserves_math_sources`、`.test_convert_zip_accepts_nested_v2_pages_and_rich_content_fields`。
- 样本证据：CM4112 公式为 external evidence；没有 committed MinerU 真公式 fixture。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`。

### MATH-002 支持子集通过共享入口生成 OMML

- 状态：`enforced-tested`（有限子集；当前执行证据见 RND-502 任务 validation）
- 输入信号：显式 formula block、semantic formula、inline 分隔符及保守裸数学、HTML `<eq>` / sub/sup；不以任意反斜杠判断数学。
- 正式 owner：`app/conversion/docx_rules/formula.py` 的共享扫描和有限 parser；`WordTextRendererMixin` 按原顺序写 run/OMML，表格及题注复用同一入口。
- 预期输出：支持分式/根式/上下标/符号/样式/overline/boxed/left-right 子集；合法简单 tag 保留主体 OMML 与可见编号。裸脚本参数不吞运算符，显式 group 与命令产生的原子作为完整脚本基底保留（OMML box），text wrapper 保留空格，style wrapper 后接脚本不能重建成默认直立体，`\vee` 不得写成 V。闭合的纯数字数学分隔符和 MinerU numeric semantic formula 必须登记，未闭合金额继续作为普通正文。数学内容不经过普通术语替换，HTML 标签不进入公式字面内容。
- 冲突/例外：不是完整 TeX 引擎；matrix/cases/align、自定义宏等安全降级，不新增 TeX/AI/图片服务。不能只用零残留证明数学语义正确。
- 禁止：全局删反斜杠/dollar/空格；将含分式整段自然语言转为数学；公式编号静默丢失；建立第二套解析器。
- 自动验证：`tests.test_formula_rendering`、现有 renderer 公式矩阵、`tests.test_formula_translation_boundary` 合成 MinerU→IR→fake translation→原生表格 DOCX。
- 样本证据：committed 精确结构单测与合成链路；external 样本/Word 签字按任务记录分层，不冒用历史验收。
- 来源/取代：RND-502 v2；取代 parser 位于 text_renderer 和 tag 静默丢弃的旧行为。

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

RND-502 补充：`formula_text_fallback` 是内容完整、可见、可审计的 warning，不是 fatal。新报告中的源/锚点/预期输出投影不一致属于确定性完整性失败，必须阻断新候选；receipt 后损坏按 uploading/oss_failed 保留选件，不重渲染掩盖。详细版本合同见下方 RND-502 场景。
