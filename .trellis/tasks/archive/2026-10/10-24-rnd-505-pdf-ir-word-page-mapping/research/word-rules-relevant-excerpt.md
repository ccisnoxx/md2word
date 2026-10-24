# G0后Word规则最小上下文

权威来源：`.trellis/spec/backend/word-generation-rules.md`，SHA256：`be5be3abccd662ac6f1afd0a6d2b70cdab7ce1db9ee49ebde145f907d5f4b956`。组合基线及RND505当前定向摘录；超出范围的修改继续读取正式Spec。

## 源文件第330–389行

### PAGE-001 模板绝对页面设置与源方向分工

- 状态：`implemented-gap`（来源合同已验收；G0组合候选验证以RND-505任务的g0-integration.md为准，历史结果不替代新候选或真实环境证据）。
- 输入信号：模板 page setup（纸张宽高、边距、装订线）和 DocumentIR page 宽高方向。
- 正式 owner：`app/services/renderer/render_plan.py::build_render_plan`（方向决策）；`app/services/renderer/word_renderer.py::_apply_page_setup`、`::_apply_page_setup_to_section`、`::_configure_layout_page_section`（执行）。
- 预期输出：显式 layout config 决定 Word 的绝对纸张尺寸和边距；源页只决定 portrait/landscape。宽表本身不改变方向，源页宽大于高时才使用横向节。
- 冲突/例外：v2 没有显式 page size 时当前使用 A4，可能覆盖 DOCX 模板自身的非 A4 尺寸；这是未裁决缺口。方向变化按 PAGE-002 分节。
- 禁止：用 MinerU/PDF 物理数值直接重写 Word 纸张；见到宽表就横向；忽略显式源页方向。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_configured_page_size_and_header_bold_flag`、`.test_render_to_bytes_preserves_portrait_section_for_wide_table_page`、`.test_render_to_bytes_keeps_source_landscape_page_landscape`。
- 样本证据：OPA228 P7 manifest 声明宽表焦点，但当前没有正式当前版本的实际转换证明。
- 来源/取代：commit `32edca58` parity 审计和归档任务 `08-18-fix-mineru-first-page-layout`。

### PAGE-002 仅方向变化创建新页分节

- 状态：`implemented-gap`（来源合同已验收；G0组合候选验证以RND-505任务的g0-integration.md为准，历史结果不替代新候选或真实环境证据）。
- 输入信号：相邻 LayoutPage 的 portrait/landscape 状态不同。
- 正式 owner：`app/services/renderer/render_plan.py::build_render_plan`；`app/services/renderer/word_renderer.py::DocumentIRWordRenderer.render_to_result`、`::_configure_layout_page_section`。
- 预期输出：方向变化时创建 `WD_SECTION_START.NEW_PAGE` 并应用目标方向；相同方向不因源物理页边界自动新建页面节。
- 冲突/例外：双栏区域内部使用 continuous section，由 COL-002 约束；语义分页由 FLOW-002 单独触发。
- 禁止：每个 MinerU page 都新增 `NEW_PAGE`；用 break-only 段落模拟方向节。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_starts_new_section_when_page_orientation_changes`、`.test_render_to_bytes_does_not_force_break_between_same_orientation_source_pages`。
- 样本证据：CM4112 为 external evidence；没有 committed 纵横向混合真样本。
- 来源/取代：commit `5d4a02d7` 删除逐源页硬分页；commit `674ce937` 保留方向分节。

### FLOW-001 同方向源页自然流动

- 状态：`implemented-gap`（来源合同已验收；G0组合候选验证以RND-505任务的g0-integration.md为准，历史结果不替代新候选或真实环境证据）。
- 输入信号：相邻源页方向相同，且下一页首内容不满足 FLOW-002 的语义起页信号。
- 正式 owner：`app/services/renderer/render_plan.py::build_render_plan`；`app/services/renderer/word_renderer.py::DocumentIRWordRenderer.render_to_result`。
- 预期输出：不插入 `document.add_page_break()`、`w:br type="page"` 或只含分页符的空段落，让 Word 按内容自然分页。
- 冲突/例外：FLOW-002 精确的页顶内容组可在真实内容段落设置 `pageBreakBefore`；方向变化按 PAGE-002。
- 禁止：恢复“每个 PDF 页一个 Word 硬分页”；以空段落承载分页；为修某个标题破坏长表自然跨页。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_does_not_force_break_between_same_orientation_source_pages`、`.test_render_to_bytes_anchors_semantic_page_breaks_to_real_content`。
- 样本证据：SC2167 为 external historical evidence，曾验证无 blank body pages；当前版本没有 committed 视觉基线。
- 来源/取代：commit `5d4a02d7`；取代旧逐物理页分页行为。

### FLOW-002 页顶标题与独立表格组语义起页

- 状态：`implemented-gap`（来源合同已验收；G0组合候选验证以RND-505任务的g0-integration.md为准，历史结果不替代新候选或真实环境证据）。
- 输入信号：非首 LayoutPage 的第一个可见 body block 是 heading、带 caption 的 table，或 `table_context` paragraph。
- 正式 owner：`app/services/renderer/render_plan.py::semantic_page_break_block_id`、`::build_render_plan`；`app/services/renderer/word_renderer.py::_render_block`；`app/services/renderer/table_renderer.py::_render_table_captions`。
- 预期输出：把 `pageBreakBefore` 放在标题段落、表格组首个 caption 或 context 真实内容段落上；普通段落和无 caption table 不强制起页。
- 冲突/例外：优先于 FLOW-001，但只对精确页顶内容组生效；不得创建独立 break-only paragraph。当前目标按 layout plan 的首 block 选择，而 two-col region 随后按左栏再右栏重排；若目标来自右栏，分页可能落在已渲染的左栏内容之后，现有测试未覆盖该组合。
- 禁止：按标题文字（如“工作原理”）或型号硬编码；所有 heading 无条件分页；在表格本体前额外插入空页。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_anchors_semantic_page_breaks_to_real_content`。
- 样本证据：CM4112“工作原理”和表格组是 external negative/acceptance evidence；未提交当前回归 fixture，且最新整本文档仍有页数增长风险。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；补充 FLOW-001 而非恢复逐页硬分页。

### FLOW-003 内容组保持与表格跨页

- 状态：`implemented-gap`（来源合同已验收；G0组合候选验证以RND-505任务的g0-integration.md为准，历史结果不替代新候选或真实环境证据）。
- 输入信号：heading、表题/表格/表注、长表行和连续表格 placeholder。
- 正式 owner：`app/services/renderer/word_renderer.py::_render_block`；`app/services/renderer/table_renderer.py::_render_table_captions`、`::_configure_data_table_rows`；`app/services/document_ir/layout_signals.py::merge_table_placeholder_continuations`。
- 预期输出：heading/table caption 使用 `keep_with_next`；表头可重复，表格行使用 `cantSplit`；空 table placeholder 只并入前一真实表格，不另渲染重复空表。
- 冲突/例外：`DocumentIRBlockLayout.continuation_heights` 当前只写入、没有 renderer 消费者，不能声称续页高度已参与 Word 排版；Word 最终分页仍由客户端决定。IR-006逻辑组同样只是源metadata，不实现Word表合并、删重复表头或版式修改。
- 禁止：把整张长表放进不可跨页容器；因 placeholder 创建第二张空表；把“有 continuation 元数据”写成“已验证不挤压”。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_merges_table_placeholder_continuation_and_landscape_orientation`、`.test_convert_zip_merges_real_mineru_empty_table_continuations`；`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_html_table_spans_and_annotations`。
- 样本证据：SC2167、CM4112 第 3/4 页表格均为 external evidence；没有自动排版后的表格挤压/分页断言。
- 来源/取代：两个 08-18 归档任务；明确降级“续表已解决”的历史结论。


## 源文件第905–1031行

## RND-502：公式报告与结果绑定的可执行合同

### 1. 范围与触发

修改公式解析、混排、renderer/evidence 或新报告恢复时适用。该机制证明写入保真，parser 数学正确性仍由精确节点测试保护。

### 2. 接口

- `render_to_result(...) -> DocumentIRRenderResult(content, formula_report)`；旧 `render_to_bytes(...) -> bytes` 委托同一核心。
- `build_renderer_evidence(ir, content, layout_plan=None, *, formula_report=None)`；未提供报告时保持旧 evidence 字段集合。
- `validate_formula_report(report) -> dict`：校验版本化持久化报告并派生安全摘要，不执行文件 I/O。
- `docx_rules.table_expansion.expanded_table_rows(HtmlTable)`：共用既有大表展开内容投影；`TableCellOccurrence` 保留原 `HtmlCell` 及源 row/column。阈值仍为 >400 行或 HTML >30000 字符；跨行重复、跨列尾格空白规则保持，renderer 与源公式库存共用该投影。

### 3. 合同

`formula-render/v1` 每次出现记录源位置/sha256、确定性 bookmark、mode/reason、`formula-output/v1` 与写 DOM 前确定的预期输出哈希。投影保留数学节点/顺序/语义属性、文本值、上下标和编号；忽略 prefix/bookmark ID/rsid/容器及非语义字体尺寸。最终 OOXML 从完整 bookmark 范围重建并比较。run 内所有可见/行为节点与全部 rPr（包括重复属性节点）均进入投影，只有明确的字体/字号和 rsid 等非语义属性排除；追加 noBreakHyphen/cr/sym/field 或 vanish/webHidden 等不能被忽略。报告不含原式全文或路径。

metadata=`formula_report/formula_summary`；摘要含 schema、formula/OMML/semantic/fallback 次数、warning/reason counts、report hash。普通事件排除逐式报告和旧 `docx_quality.latex_residue_examples`。报告仍遵守既有 `/files/{id}` 内部 owner/admin 权限，没有新端点。

单次 RenderContext.formula_location 从真实 block/field 调用点绑定来源，包含 list、cell、caption/note 和 image annotation；不能只按源 hash 或库存遍历次序猜位置。相同原式跨入口必须由实际 anchor 所在位置回查正确 source。

超阈值表格每次实际显示均登记 occurrence；跨行重复保留同一源 cell 坐标并各有独立锚点，不把原式先压成纯文本，也不放宽重复计数对账。

完成时在既有 job 锁内仅由匹配 generation/最终 IR/结果 ID 的选中 receipt 合并 `quality_summary.formula`，保留其它摘要；pending/blocked 不提升，passed 遇 fallback 降 warning。不扩展状态机/DDL。三恢复入口均对新报告读取实际字节及文件原始 IR 重验，I/O 在 job 锁外；历史明确指针跨代复用不导入旧报告到新代摘要。无新字段旧件维持原合同，新字段损坏不能降级 legacy。已发布件和审计不回写。

空 m:t 在保存前后的空字符串/None 统一投影为 None；节点本身仍保留，不能因此忽略追加空 run、删除字符或结构变化。上下标参数的纯文本压缩不得重建带显式数学样式的节点而丢弃 i/b 等语义属性。有限解析尚不支持的 \left./\right. 不可见 delimiter 整式按 unsupported_structure 降级，不能把句点作为可见符号输出并报告成功。

### 4. 校验与错误矩阵

| 情形 | 行为 |
|---|---|
| 支持且完整消费 | OMML/semantic run，逐式登记 |
| 非空不支持输入 | literal 原式+提示，formula_text_fallback warning |
| 空源或输出丢失 | 既有输入/输出完整性失败 |
| 新渲染报告/字节不符 | quality_checking/render_failed，不登记候选 |
| 新报告恢复损坏 | uploading/oss_failed，保留 receipt/历史件 |
| 非公式 LaTeX 残留 | 保持原 flag，不豁免普通正文 |

### 5. 正常、历史与失败场景

正常：重复原式按出现次数登记，同一 renderer 并发调用不共享 collector。历史：缺报告旧件按既有证据恢复，不自动补字段。失败：相同 anchor/source/mode/count 下改数字、移动脚本、截断原式或删除提示仍须拒绝。

### 6. 必要测试

`tests.test_formula_rendering`、`tests.test_document_ir_word_renderer_layout`、`tests.test_formula_translation_boundary`、`tests.test_document_job_result_persistence`、`tests.test_document_job_delivery_state`；分别断言精确结构、原生表格/正文顺序、最终输出篡改、三恢复入口、选中摘要及三 adapter 状态列往返。fake MySQL 不证明真实 InnoDB；OOXML 不代替 Word 视觉签字。

### 7. 错误与正确做法

错误：从最终 XML 生成“expected”哈希后再比较自身；仅按一个 OMML 对一个 formula block 计数；从迟到 renderer 的内存报告更新质量。

正确：先由转换结果计算 expected，再写 DOM；最终 analyzer 独立读取锚点范围并核对源 inventory/投影；完成只消费当前选定不可变 receipt 的摘要。部署/回退先暂停或排空相关旧任务，只有理解新报告和旧计划边界的兼容执行器可继续在途工作，不删除历史字段/文件/审计。

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


## RND-505：非可见block书签与独立创建证明

通用marker仅由同次实际输出对象创建，在最终save/freeze前完成，所有locator和报告绑定最终字节。RND-501 v1首名/内容targets/Reason不变；独立block-anchor-evidence/v1仅记录成功创建事实。图片报告兼容投影只忽略精确命名且合法配对的新非可见marker，原run/drawing/尺寸/图cell认证不变。完整合同见[页映射Spec](./page-mapping-contract.md)。
