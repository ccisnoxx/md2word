# 当前Word图片相关规则快照

2026-10-23，真源`.trellis/spec/backend/word-generation-rules.md`，源SHA-256：`aecc22bada0b8893b2e0fae1dea329ae42368f9936753b84d2917cd83d5ceadd`。完整Spec超32768字节注入上限，仅摘录当前规则与结果合同。修改源后须刷新；实际验证见implementation-validation.md和post-implementation-review.md，不代表Word视觉签字。

### IR-005 严格题注关系与原始证据

- 状态：`enforced-tested`；正式ZIP/OOXML和定向证据仅证明结构与内容，未代表Word视觉。

- caption 统一由 document_ir/caption_reconciler.py 负责逻辑分组、可靠换行拆分、严格编号和关系回执；converter 只消费最终结果，禁止再递归读回旧 nested 字段。
- 自动修复限同页、原源索引连续、同对象族、标签一致、编号唯一连续、数量相等及原分布失衡；image/chart/figure 与 table 分族，已有一对象一题注保持。
- flat rich nodes 仍是一个逻辑题注，仅完整标签/编号起始的可靠显式换行或既有逻辑组可以拆分；无边界连写图5/6不猜拆。原始值/runs/locator 保留在专用 metadata，不使用可见 caption 别名。
- 独立 paragraph 不搬移或复制可见文本，仅在唯一相容对象、同页直接邻接和有效 bbox 下建立 evidence-only；歧义记录 caption_binding_uncertain，普通无候选对象不全局误报。
- 表题/条件保持 TABLE-002 的唯一 classifier，明确边界分别处理，混合边界不明保留原 annotation 并标不确定；合法 HTML 继续原生表格。
- 原始证据只由主源块保存，table_context 派生块不复制；renderer 摘要不包含原文。拟自动修复必须守恒且唯一消费，损坏按 QUALITY-004 失败关闭，普通 uncertainty 不升级 fatal。最终可见caption列表也纳入守恒门禁；重复条件保留出现次数，重复编号表题保持原annotation并uncertain，防止下游既有去重静默丢次。范围/共享标签续号不按首号绑定。
- 自动验证：`tests.test_caption_reconciler`、converter 的 nested/sequence/accepted redacted/table/paragraph/damage/legacy 联合测试、IR contract roundtrip 与 translation metadata 保真。真实Word/WPS和字段更新结果仍未验证；FIELD-002 的跳号限制不由本任务修复。

### COL-001 局部双栏检测

- 状态：`enforced-tested`
- 输入信号：同一页 body block 的 bbox、page width、显式 `column_hint`、实际纵向重叠和 wide block。
- 正式 owner：`app/services/renderer/layout_plan.py::_build_regions`、`::_detect_two_col_bands`、`::_detect_stable_two_col_bands`、`::_classify_body_block`。
- 预期输出：优先使用真实左右栏纵向重叠 band；只有没有真实 band 时才使用稳定非重叠提示；宽度至少页宽 60% 或显式 wide 的 block 保持单栏，局部单栏间隙不被吞入双栏。真实双栏流结束后、同侧且证据完整的正文尾部可并入前一双栏区域，直到 wide block、真实单栏间隙或新的左右正文流；严格图片对仍保持独立区域。
- 冲突/例外：严格成对图片行由 COL-003 例外渲染；缺页面宽度时不猜双栏。
- 禁止：整页只因出现左右 block 就全页双栏；把 wide 表格放入一栏；按固定 x 像素适配某型号。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_build_layout_plan_separates_decorations_and_two_column_regions`、`.test_build_layout_plan_prefers_column_hint_for_stable_non_overlapping_regions`、`.test_build_layout_plan_keeps_explicit_wide_blocks_out_of_stable_two_column_regions`、`.test_build_layout_plan_keeps_single_column_gap_between_real_two_column_bands`、`.test_layout_merges_single_side_tail_before_paired_images_into_one_column_flow`。
- 样本证据：OPA228 P1/P2 manifest 声明双栏焦点但当前 Golden 未实际运行；CM4112 当前 external 样本首页单侧栏尾已并入前一双栏区域，LibreOffice/WPS 均观察到概述与引脚图可见；客户端栏平衡仍归 QUALITY-003 人工判断。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；取代全页宽松双栏判定。

### COL-002 Word 原生栏与阅读顺序

- 状态：`enforced-tested`
- 输入信号：layout plan 的 `two_col` region 及其 left/right blocks。
- 正式 owner：`app/services/renderer/word_renderer.py::_render_layout_region`、`::_set_section_columns`、`::_split_two_col_blocks`。
- 预期输出：通过 continuous section 的 `w:cols` 进入两栏，按左栏自上而下、column break、右栏自上而下渲染，再用 continuous section 恢复单栏；不使用布局表格承载普通双栏正文。
- 冲突/例外：COL-003 的严格图片组使用无边框布局表格；continuous section 的实际栏平衡需要 Word/WPS 视觉验收。
- 禁止：按全局 y 顺序交错左右栏；渲染完双栏后不恢复单栏；用 1×2 表格包装普通正文。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_native_columns_for_v2_region`、`.test_render_to_bytes_prefers_column_hint_when_ordering_native_columns`、`.test_render_to_bytes_keeps_continuous_restore_when_wide_content_follows_columns`。
- 样本证据：SC2167 为 external historical WPS/LibreOffice evidence；没有 committed 当前视觉回归。
- 来源/取代：commit `5d4a02d7` 与 `32edca58`；取代布局表格模拟普通栏。

### COL-003 严格图片行与无边框布局表格

- 状态：`enforced-tested`（RND-503结构/内容与恢复本地验证通过；Word/部署预览尚待人工验收）。
- 输入信号：最终IR同页、源连续image run，具有有效有限bbox与页面尺寸；不跨正文/真实section，不猜caption归属。
- 正式owner：`app/services/renderer/layout_plan.py`拥有image-group/v1；image_renderer/word_renderer只消费其计划和单次有效输入。
- 预期输出：确认行用固定1×N无边框Word布局表格，每图inline且等比；各自caption/footnote在本cell完整独立渲染。共同纵向交集/max高≥0.80，高度比≥0.80，中心偏移/min高≤0.10，顶边偏移/页高≤0.015，相邻横向间隔/页宽≤0.08且不重叠；全部成立、源序与x序一致并无竞争才接受。连通分量须全组复核，不能传递猜配。
- 冲突/例外：替代旧COL-003的25%/75%制表位图片例外；普通正文COL-002继续原生栏。IR-204 uncertain/evidence-only竞争否决并排；正常多annotation不是拒绝理由；不确定按源序单图并标记。
- 禁止：全局bbox重排，复制/拆分或搬独立段落caption，仅凭marker/总数豁免数据表对账；布局表不能伪造数据表可编辑性。
- 自动/样本验证：可靠图5/6与24/25、单图/阈值/OOXML/历史恢复/冻结输入/B1有定向测试；全新critical复审另覆盖原生栏混合单图、全部报告键缺失、模板继承定位及真实旧产物兼容。各轮unit/component/direct/release/B1和LibreOffice辅助预览的准确结果见任务implementation-validation.md与post-implementation-review.md；Word/部署预览/Golden未验边界仍独立记录，不以本条代签。
- 来源/取代：2026-10-23用户接受的RND-503 v2；原制表位行为仍保留在旧测试/历史证据中，不再约束新图片writer。

### TEXT-004 富文本题注节点不得拆成多条题注

- 状态：`enforced-tested`
- 输入信号：v2 table/image/figure/chart caption 字段中的 flat inline-node list，或 legacy string list/多个 nested rich-node groups。
- 正式 owner：`app/services/document_ir/caption_reconciler.py::reconcile_captions`；现有文本/公式清理 helper 只作为片段归一化依赖。
- 预期输出：一个没有可靠换行标题边界的 flat `text/equation_inline/text` 节点数组形成一个完整 `DocumentIRBlock.captions` 元素；可靠显式换行拆分只按 IR-005 的严格规则执行，进入 Word 后只占一个题注段落；string list 和多个 nested rich groups 继续形成多条独立题注。可见 inline 语义、SEQ/bookmark、fallback、table context 和 COL-003 annotation 数量判断均基于完整逻辑题注。
- 冲突/例外：footnote 继续按现有 marker/连续性规则合并；无可靠结构时保持原分组，不按图号、标点、页码或 bbox 猜测。renderer 继续坚持“一 caption 元素一段落”，不负责恢复 converter 已丢失的边界。
- 禁止：用 `collect_text_from_fields()` 把 flat rich nodes 直接拍成多条 captions；在 image/table renderer 合并相邻题注；修改 continuous section 或 `pageBreakBefore` 掩盖孤立题注行。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_maps_nested_v2_chart_to_image_and_records_source_inventory`、`.test_convert_zip_preserves_multiple_logical_caption_groups`、`.test_rich_chart_captions_render_without_isolated_fragments_and_keep_paired_layout`、`.test_convert_zip_demotes_table_condition_caption_to_context_paragraph`。
- 样本证据：CM4112 新候选的图 33 为单条 `['图 33 通道隔离度 (± 18V)']`，OOXML 不含仅为 `±`/`18V)` 的段落；WPS GUI 第 12 页实际包含图 31～33 及完整题注，第 13 页直接以“工作原理”起页，旧碎片极稀疏页消失。完整记录见当前任务 `research/cm4112-validation.md`。
- 来源/取代：当前任务新增目标；取代把富文本 inline node 数量当作 annotation 数量的行为。

### IMAGE-001 图片资产绑定、显示宽度和可见失败

- 状态：`implemented-gap`（RND-503结构/内容与历史fallback测试已补，真实Word/部署预览仍独立待验）。
- 输入信号：IR image asset_id、MinerU 包内资产路径、bbox/page width、当前栏宽和 captions。
- 正式 owner：包路径 `mineru_package.resolve_asset_path`、输入资产 `artifact_validator`；图片计划 `layout_plan`；显示/fallback `image_renderer._render_image_span/_write_image`；冻结输入/实际包认证 `image_evidence`。
- 预期输出：资产位于包根内，原字节不转码/重采样，按有效区域等比缩放且inline，禁止自动压缩。每图全部注释与原来源保持；新组用COL-003布局表；缺/坏图显示受控诊断及全部已有注释，确定性缺图仍拒绝登记成功件。
- 冲突/例外：不承诺放大小图到某个历史最小宽度；清晰度取决于源像素和客户端。正式MinerU输入对必需坏图/非法bbox已失败关闭；历史IR仍有可见fallback。非有限历史bbox只禁并排，图片报告采用JSON安全确定投影；不扩大为修改IR模型/序列化合同。
- 禁止：静默丢图；无条件拉伸到全栏；用截图替换可编辑正文；按某个样本设置固定厘米宽度。
- 自动验证：`tests.test_image_group_rendering` 的横竖非方图/完整注释/资源失败/资产交换/比例/快照与恢复负例，既有bbox宽度测试和converter正常路径测试保留；源越界/歧义/坏图见INPUT-002。
- 样本证据：中性非方PNG、正式可靠图5/6及24/25 ZIP、已接受去标识不确定caption-pair；SC2167仍是外部历史清晰度证据，不能代签当前Word。
- 来源/取代：已批准RND-503 v2取代旧制表位writer，保留5d4a02d7的源字节/可见失败原则。

### IMAGE-002 编号图片及表题只做严格重关联

- 状态：`enforced-tested`
- 输入信号：同页原始源索引连续的 image/chart/figure 或独立 table group 的题注数量失衡，所有题注具有相同 label、唯一连续编号且数量与对象严格相等。
- 正式 owner：`app/services/document_ir/caption_reconciler.py::reconcile_captions`；converter 只消费统一结果。
- 预期输出：按连续编号为每个对象分配唯一题注；原来已一对象一题注时保持原关联，条件不完整时保持原文并按 IR-005 记录 uncertainty。
- 冲突/例外：此规则不通过视觉最近邻猜关联；多 annotation 渲染由 COL-003/IMAGE-001 保持，普通正文栏仍归COL-002。
- 禁止：只按出现顺序重排任意题注；跨页关联；丢弃无法识别的原题注。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_reassociates_only_strict_numbered_image_groups`。
- 样本证据：SC2167仍为external历史证据；RND-503复用已授权去标识caption-pair，并以可靠合成ZIP验证图5/6、24/25。原不可靠源串不预修，保留uncertainty及可见次数。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption/research/caption-reassociation.md`。

### FIELD-002 题注、书签与交叉引用唯一性

- 状态：`implemented-gap`
- 输入信号：可解析的 Figure/Table 单一整数题注，以及正文中对唯一题注目标的引用。
- 正式 owner：`app/services/renderer/text_renderer.py::_parse_caption_text`、`::_fill_caption_paragraph`、`::_render_mixed_math`；`app/services/renderer/word_renderer.py::_build_render_context`。
- 预期输出：题注编号使用 `SEQ`，目标使用唯一 bookmark，正文唯一匹配时使用 `REF`；复合编号保留普通文本，避免错误链接；bookmark 映射只属于单次 render context，不存入可复用 renderer 实例。
- 冲突/例外：同编号多目标、复合编号或不可解析题注不自动建立交叉引用。当前 `SEQ` instruction 未用 `\\r` 固定源编号；Word/WPS 更新字段后，非 1 起始或跳号题注可能被重新编号，现有 OOXML 测试不证明更新后的编号保真。
- 禁止：生成重复 bookmark；把所有数字都当引用；为复合编号创建错误 `SEQ`。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_links_unique_caption_references_with_native_fields`、`.test_render_to_bytes_keeps_compound_caption_numbers_as_plain_text`、`.test_render_to_bytes_keeps_paired_image_caption_fields_in_row_order`。
- 样本证据：SC2167 为 external historical evidence；无 committed captions/REF fixture。
- 来源/取代：commit `5d4a02d7` 与归档任务 `08-18-fix-layout-formula-image-caption`。

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

## RND-503：图片布局与原文件输入的可执行合同

### 1. 范围与触发

修改图片同行判定、图片 writer、布局表计数或图片报告恢复时适用。几何阈值及源连续边界以 COL-003 为准；IR-204 仍拥有题注重关联。以下为已实现合同，实际验证状态由任务 implementation-validation 记录决定，不宣称 Word 视觉已通过。

### 2. 接口与 owner

- `layout_plan.build_image_plan(document_ir) -> tuple[ImageSpan, ...]`：纯附加决策，旧 `build_layout_plan()` 的结构/aggregate/历史解释保持。
- `DocumentIRRenderResult(content, formula_report, image_layout_report=None)`：兼容旧 bytes 调用，同次报告由正式 Worker 和本地 adapter 传递。
- `DocumentIRRenderOptions.template_version_id`：正式外层身份，恢复取自原文件 metadata，不能取当前 job 默认版本。
- `build_renderer_evidence(..., image_layout_report=None, expected_template_version_id=None, expected_generation_policy=None)`：新件认证；恢复不强求当前生成构建策略，只按原文件策略解释。
- `image_evidence.verify_image_report(...) -> dict`：源计划、冻结输入、实际包独立重验，返回有界安全摘要；不得反向依赖 word_renderer 或另建分组算法。
- `TemplateConfigPackage.load_content(bytes)` 与 `load(path)` 共享原归一化/校验；renderer 从一次实际读取同时取得解析值及内容 hash，不改公开 template-config/v1 schema。
- `TerminologyReplacer.freeze_rules()/from_frozen_rules()` 复用同一替换算法，保留生效规则顺序、pattern/replacement、regex flags 和作用域，不重读历史路径。

### 3. 私有报告与兼容合同

报告 `image-layout/v1` 绑定规则 `image-group/v1`、阈值、原 IR hash、span/block/page/order/bbox、实际 mode/reasons、布局表 marker、逐图资产 hash/尺寸、逐注 field/source hash/expected 投影和实际锚点。每次预期投影由原 IR 字段与冻结输入重建，不能仅比较报告内 expected 和输出自己生成的 hash。

`image-render-inputs/v1` 包含已知 `image-annotation-output/v1`、`image-writer/v1`、原文件生成构建身份、实际模板版本及 DOCX/配置内容 hash、语言、必要 caption style/格式规则、写 DOM 前每个 span 的有效 section 几何；整个输入 canonical hash 绑定到报告。builtin 来源必须显式标识。禁止保存任意 YAML、Settings、路径、翻译术语、Prompt、凭据；报告/必要规则只在现有 owner/Admin 文件 metadata 内，普通事件不展开报告或规则快照。

确认组为固定 1×N 原生布局表，每图一 cell，全部 `wp:inline` 且按真实像素比例缩放；六边 nil、显式 grid/tcW/margin，cantSplit，逐注独立段落并保持所属图。只有完整认证的表可排除在内容表计数外。旧 `table_count/table_count_delta` 仍表示实际总数/总数减 IR 内容表数；新 layout/content/total 字段各自对账。standalone analyzer 保守排除布局候选造成的虚假内容可编辑性，正式 evidence 必须完整认证，marker 本身不是通行证。

图片段首行/左右缩进和 inline distT/distB/distL/distR 必须显式0，内外两层图片尺寸一致；不能仅按 width/height 宣称没有裁切。LibreOffice 26.2.4.2省略inline距离会引入约9.05pt左右图距，实际右图clip小于绘制宽度；四距0产物对照恢复完整边界。tcMar在vAlign前、tblBorders在tblLayout/tblLook/tblCaption前，遵循安装库schema。跨span实际DOM源序、资源/尺寸降级依据及无额外正文也独立认证。 布局表显式左对齐、tblInd=0dxa；reader认证direct优先、basedOn/默认表样式继承后的有效定位，拒绝非零缩进、不支持的对齐及exact行高。有效零缩进下left/center/right均在已认证有效宽内；新writer固定left不构成旧件新硬条件。旧无direct属性但有效零和受支持对齐的已生成件继续接受（缩进dxa按实际值；pct/auto按Word忽略值的零位移解释，nil按无宽解释；type省略按dxa、宽度省略按0；未知单位拒绝）。Word对非left对齐仍可能应用非零缩进，因此不按ISO通则直接豁免非零dxa，不能把新增直接属性变成旧件必需字段。

cell宽度必须同时认证数值和dxa单位；源图矩形/填充矩形不得非零裁切，内部offset为0、无旋转/翻转，缺省和显式0等价。保持asset hash和外框extent不变的变换同样必须拒绝，不能以源字节未变推导显示保真。

历史无效bbox的报告源位置采用确定JSON安全投影（非有限坐标→null），writer与源重算共用，不修改原IR。报告经真实DocumentFileRecord JSON往返后证据必须一致。正式MinerU非法bbox仍在映射前拒绝；不承诺typed IR经model_dump_json把非有限值转null后可重新读取。私有快照模型/regex校验异常转换成无原输入的受控错误，普通error/event不得暴露必要格式规则值。

metadata 使用 `image_layout_report/image_layout_summary`；摘要只含版本、组/单图/不确定次数、受控 reason 计数、report hash 和有界 ID examples。`image_group_uncertain` 是复核 warning，不加入 blocking_quality_flags，不提升质量/审核/发布状态；确定性丢图/漏注/篡改仍失败。普通单图和 B1 主动单图不产生无意义不确定 warning。

legacy 发现、明确历史指针、receipt 三入口对新报告读取原文件字节/原始 IR/外层模板身份重验；当前配置变化或删除原临时路径不能影响合法旧件。历史无报告件保持原字段集合，不强制补写；新字段部分缺失不能降级旧合同。即使全部图片证据键和两项公式键都缺失，legacy扫描仍须在prepare/select receipt之前从实际DOCX识别新图片标记并拒绝；真正无marker旧件继续恢复。既有 formula 报告、选中 receipt、CAS、retry_count/generation 和原子边界保留，I/O 在 job 锁外。

普通混合原生双栏中的单图和不确定顺序图，若原生栏读序与图片源序一致，必须在原region实际位置逐图消费，保留栏流和列宽；只有确认并排组或真实图片读序冲突的span抽离。后者保留既有原因和源序单图，不能靠重排图像满足栏序。源计划/span成员不变，每图只写一次。

同一不确定span中已知bbox图片可位于two_col region、缺bbox成员位于后续one_col region，单一span几何不足以表达真实位置。冻结输入span的可选 `image_geometries` 仅保存与首图 `geometry` 不同的成员（block_id→geometry）；无此键的历史报告继续使用原span.geometry。报告hash覆盖该输入，每图从实际OOXML所属section独立重验，不能用新字段跳过源成员、尺寸、源序或注释校验。它是内部私有报告的兼容附加数据，无公开API/DB列/运行时开关；B1必须包含当前完整reader，不能以修复前旧B1二进制冒充当前回退构建。

### 4. 校验与错误矩阵

| 情形 | 输出/错误 |
|---|---|
| 同页源连续且全组阈值成立、无绑定竞争 | 固定无边框布局表及逐图完整证据 |
| 几何不足、源序冲突、竞争或 IR-204 uncertain/evidence-only | 源序单图，`image_group_uncertain` 和受控 reason；不修改 IR 归属 |
| 单张正常图/清晰独立行 | 正常单图，不制造 warning |
| 已确认组资产/尺寸不可用 | 整组源序单图；缺/坏图显示诊断及全部已有注释，完整性仍拒绝缺图成功件 |
| marker 复制/伪造、交换资产/注释、漏注、浮动对象、宽度越界、源/快照错绑 | 新登记 `quality_checking/render_failed`，不登记候选 |
| 新报告缺必要字段、未知版本、hash/原身份不符、实际包损坏 | 恢复 `uploading/oss_failed`；保留 receipt/历史文件，不 fallback |
| 旧件缺三个依赖附加摘要键 | 只在旧 metadata 未保存该键时不强求新增键；已有摘要/核心必要字段仍严格比较 |
| 已有新报告后部署回退 | 使用 B1 保留 reader，只切生成侧 single-only/v1；不能卸载 reader 回 B0 |

受控 reason 集合：`geometry_unavailable`、`geometry_invalid`、`page_or_section_boundary`、`source_order_conflict`、`row_alignment_insufficient`、`horizontal_overlap`、`gap_too_large`、`competing_row_membership`、`caption_binding_uncertain`、`external_caption_binding`、`asset_unavailable`、`image_size_unfit`。

### 5. 正常、历史与失败场景

正常：两图/三图各有多 caption/footnote，按源序成组，各注仍在自己的 cell。历史：无图片报告但有旧公式报告的文件按旧必要字段恢复；有新报告的跨代明确指针按原文件冻结输入恢复。失败：保留表格和图片总数，仅交换两图关系或题注，也必须拒绝；新增内容表不能靠复制 marker 被豁免。

兼容构建 B1 仅把源码生成常量 `IMAGE_GENERATION_POLICY` 固定为 `single-only/v1`，没有运行时 feature flag 或用户任务参数。报告 reader 继续解释 `grouped/v1` 和 `single-only/v1`；两种构建互读原文件策略。必须记录 B1 源码指纹和三入口/旧公式/篡改拒绝验证，不以排空在途任务代替历史兼容。

### 6. 必要测试与证据

`tests.test_image_group_rendering`：阈值内/等/外、竞争及源序、固定布局表/比例/注释、实际 OOXML 篡改、冻结输入和并发隔离。`tests.test_document_ir_mineru_converter_layout`：正式可靠图5/6、24/25及去标识不可靠样本、单图。`tests.test_document_job_result_persistence`：三入口、跨代、当前配置变化后恢复、损坏拒绝、B1、公式/receipt/事件隐私。`tests.test_rnd503_dependency_integration`：缺字段/None/原 IR 非空旧 reader 忽略/已有非空摘要 × 三入口。

定向 unit、component、direct matrix、check_release、Golden 和客户端证据分别记账；实际新测试模块/选择以任务 validation 为准。OOXML 证明结构，不代签 Word 更新字段前后、长注释分页、目标图对及部署预览的视觉结论。没有触及 API/前端/DDL 时不得为该任务凭空生成迁移或前端业务状态。

### 7. 错误与正确做法

错误：只凭 marker 把表当布局表；从当前符号 YAML 生成历史 expected；以整篇最后 section 猜所有 span 宽度；B1 删除新 reader 后仅渲染单图；事件展开完整 frozen rules。

正确：源 IR/冻结输入/实际包三方认证后分类；使用原文件身份及已知投影版本重算；逐 span 比较写前和实际所属 section；B1 保留全部读取/拒绝与 receipt 接线，仅固定生成策略；事件只投影有界摘要。
