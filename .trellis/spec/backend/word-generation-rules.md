# Word 生成规则

## 1. 适用范围与权威边界

本文是当前正式 MinerU → DocumentIR → Word 输出行为的唯一权威规范。正式本地适配入口是
`scripts/dev/formal_mineru_conversion.py::run_conversion`，实际执行函数是同文件的
`::convert_formal_mineru_package`；线上入口由
`app/domains/document_jobs/execution.py::DocumentJobExecutionService` 调用
`app/services/document_ir/mineru_converter.py::MinerUToDocumentIRService`，再由
`app/services/renderer/word_renderer.py::DocumentIRWordRenderer` 生成 DOCX。

`full.md` 不属于正式输入；正式链路只从 MinerU content list JSON 构造 DocumentIR。旧
`app/conversion/runtime/*` 的编排、页面 renderer 和 Word writer 不是并列真相源，也不能用其
characterization tests 证明正式链路已实现某条规则。正式 renderer 当前复用的共享纯规则以及
`app/conversion/runtime/table_html_parser.py` 仍是实际代码依赖；其行为只有经过正式
`MinerUToDocumentIRService → DocumentIRWordRenderer` 测试后，才能成为本文的自动化证据。

模板 API、schema、版本和发布合同由 [模板布局配置合同](./template-layout-configuration.md) 管理；
本文只规定模板配置与源版式进入 Word 输出时的优先级和结果。通用测试纪律由
[质量指南](./quality-guidelines.md) 管理，本文补充 Word 专项回归门禁。

### 规则状态

| 状态 | 含义 |
|---|---|
| `enforced-tested` | 当前正式代码存在，且有正式链路自动测试直接证明该输出合同。 |
| `enforced-sample` | 当前正式代码存在，且有当前真样本或人工验收证据；不代表已自动化。 |
| `implemented-gap` | 当前正式代码已实现部分或全部行为，但缺直接测试、长期样本或存在已确认边界缺口。 |
| `planned` | 是明确的目标合同，但当前正式代码尚未满足，或产品意图仍需在后续任务裁决。 |
| `historical` | 仅记录旧 runtime 或历史版本行为，不约束当前正式输出。 |
| `superseded` | 已被本文另一条正式规则明确取代。 |

状态按当前可证明的最低层级填写；“测试文件存在”不等于真样本已回归，“历史验收通过”不等于
当前 commit 仍通过。规则 ID 按行为域固定，不按 PDF 型号新增特例。

## 2. 正式链路与输入

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

### PIPE-002 DocumentIR v2 布局与 v1 顺序兼容

- 状态：`enforced-tested`
- 输入信号：`document-ir/v2` 且存在 pages/layout，或旧 `document-ir/v1`/缺少布局字段。
- 正式 owner：`app/services/renderer/layout_plan.py::build_layout_plan`、`::_build_legacy_plan`；`app/services/renderer/word_renderer.py::DocumentIRWordRenderer.render_to_bytes`。
- 预期输出：v2 使用分页、角色和分栏布局计划；v1 或无任何 layout 的 IR 以一个顺序页面渲染，内容不因缺少新字段而丢失。
- 冲突/例外：v2 只要存在 pages 且至少一个 block 有 layout 就不会整体回退；此时单个无法归属页面的 block 受 IR-003 缺口约束。
- 禁止：把 v1 兼容回退误称为旧 runtime；为某个样本静默切换两套 Word writer。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_keeps_v1_sequential_fallback`；`tests.test_document_ir_layout_contract.DocumentIRLayoutContractTests.test_v1_payload_defaults_layout_fields_to_empty`、`.test_v2_payload_round_trips_page_and_block_layout`。
- 样本证据：无直接真样本；当前证据为合成 IR。
- 来源/取代：commit `32edca58` 正式 renderer 合同；旧 runtime 的兼容行为不作为证据。

### INPUT-001 content_list_v2 优先且仅无 v2 时回退

- 状态：`enforced-tested`
- 输入信号：MinerU 包内同时存在 `*_content_list_v2.json` 与 legacy `*_content_list.json`，或只存在其中一个。
- 正式 owner：`app/services/document_ir/mineru_package.py::find_content_list`、`::load_content_blocks`。
- 预期输出：候选按 v2 优先、路径深度和名称稳定选择；只有没有 v2 时才读取 legacy content list；支持顶层 list、`content_list` 字段和嵌套 page list。
- 冲突/例外：此规则不读取 `full.md`；legacy JSON 只是输入兼容，不等于切换旧 runtime。
- 禁止：因单个 v2 字段处理失败而偷偷改用 legacy JSON；按绝对文件名或 PDF 型号硬编码选择。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_prefers_v2_content_and_keeps_legacy_only_fallback`、`.test_convert_zip_accepts_nested_v2_pages_and_rich_content_fields`。
- 样本证据：已提交 `ti-opamp-opa228-p1-smoke` 使用 `component_content_list_v2.json`；没有已提交的 v2/legacy 双份真包。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；取代 legacy-first 选择导致 CM4112 读取错误产物的历史行为。

### INPUT-002 MinerU 包边界与显式失败

- 状态：`implemented-gap`
- 输入信号：ZIP 条目、目录路径和 content list JSON 结构。
- 正式 owner：`app/services/document_ir/mineru_package.py::extract_zip`、`::find_content_list`、`::load_content_blocks`；`scripts/dev/formal_mineru_conversion.py::_materialize_mineru_zip`、`::_validate_request_paths`。
- 预期输出：拒绝绝对路径、空/`.`/`..` ZIP 条目、缺失 content list 和非 list 内容；错误显式暴露，不返回伪成功。
- 冲突/例外：目录输入由正式 adapter 物化成 ZIP 后进入同一服务；旧 runtime 的路径穿越 characterization test 不能证明这里已覆盖。
- 禁止：猜测邻近文件、静默返回空文档、以宽泛异常吞掉输入错误。
- 自动验证：正式 adapter 的 `tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_missing_input_fails_before_runtime_call` 仅覆盖入口路径；尚无直接正式 `extract_zip` 恶意条目测试。
- 样本证据：OPA228 最小包只覆盖正常目录输入。
- 来源/取代：当前正式代码审计；安全边界已实现但正式自动证据不足。

### INPUT-003 最终宣传页保守过滤

- 状态：`enforced-tested`
- 输入信号：仅源文档最后一个物理页面，同时出现下载/关注等 CTA、图片/figure 资产，且没有长正文、表格、公式、列表、编号标题或题注等实质结构。
- 正式 owner：`app/conversion/docx_rules/mineru_content.py::find_final_promotional_page`；`app/services/document_ir/mineru_converter.py::MinerUToDocumentIRService._convert_blocks`。
- 预期输出：同时删除该页 blocks、DocumentIR page 和关联图片资产，并记录 `final_promotional_page_filtered:<page>`；条件不完整时保留页面。
- 冲突/例外：内容保真优先于清理；非末页或含实质结构的末页不得过滤。
- 禁止：按页数、短文本、图片存在或品牌固定语句单条件删除；删除非末页。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_shared_final_promotional_page_rule_is_conservative`、`.test_convert_zip_removes_final_promotional_page_blocks_pages_and_assets`、`.test_convert_zip_uses_physical_final_page_from_layout_metadata`、`.test_convert_zip_filters_final_promotional_page_without_layout_metadata`。
- 样本证据：SC2167 为 external historical evidence，不能作为当前可运行 fixture。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption/research/final-promotional-page-filter.md`；取代按模型/品牌写死尾页删除。

### INPUT-004 v2 富文本、列表换行与脚注归一化

- 状态：`enforced-tested`
- 输入信号：v2 `content` 节点、inline equation、显式 `list_items`、以列表标记起始的多行文本、目录点线和碎片化脚注。
- 正式 owner：`app/conversion/docx_rules/mineru_content.py::join_text_fragments`、`::split_multiline_list_items`、`::split_toc_like_lines`、`::merge_footnote_fragments`；`app/services/document_ir/mineru_converter.py::_list_items`、`::_rich_text_nodes`。
- 预期输出：保留 inline equation 数学边界；多行列表拆成独立 item，未标记续行仍保留在同一 item；目录样式文本仅在足够高比例点线项时拆分；脚注按明确连续信号合并。
- 冲突/例外：普通多行正文不拆列表；单行负温度或减号文本不得当作列表。
- 禁止：对所有换行统一空格化；只保留列表第一行；在普通正文全局执行无差别或破坏性的 TeX 清理。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_structures_v2_multiline_lists_and_preserves_math_sources`、`.test_convert_zip_accepts_nested_v2_pages_and_rich_content_fields`。
- 样本证据：OPA228 最小 fixture 有列表，但 runner 尚未断言 manifest 的列表验收焦点。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；取代把列表换行全部压平的行为。

富文本 caption 的逻辑分组不由本规则的通用文本拍平函数推断，单独受 TEXT-004 约束。

## 3. DocumentIR、页面与正文流

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

### IR-002 页面尺寸与 bbox 使用同一 MinerU 坐标系

- 状态：`enforced-tested`
- 输入信号：layout/middle JSON 的物理页宽高，以及该页 block bbox 最大范围。
- 正式 owner：`app/services/document_ir/layout_signals.py::build_pages`、`::_bbox_extents_by_page`。
- 预期输出：当物理尺寸有效时，以单一比例同时放大宽高，使页尺寸覆盖 bbox 并保持原物理纵横比；无物理尺寸时才使用 bbox extent；方向由归一后的宽高确定。
- 冲突/例外：归一尺寸用于相对布局和方向，不直接覆盖模板配置的 Word 绝对纸张尺寸。
- 禁止：宽高分别缩放造成比例失真；将 PDF point 与 MinerU bbox 像素直接比较；由某个宽表单独强制横向。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_scales_physical_page_size_uniformly_to_cover_bbox`、`.test_convert_zip_uses_physical_final_page_from_layout_metadata`。
- 样本证据：CM4112 为 external negative evidence：旧实现坐标错配曾把 A4 portrait 误判为 landscape；当前未提交回归 fixture。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；取代宽高独立补齐和坐标系混用。

### IR-003 v2 block 不得因缺少页索引而静默丢失

- 状态：`enforced-tested`
- 输入信号：v2 IR 已有 pages/部分 layout，但某个可见 block 的 `layout.page_index` 与 `block.page_index` 均为 `None`。
- 正式 owner：布局归属由 `app/services/renderer/layout_plan.py::build_layout_plan` 负责；期望/实际对账和阻断由 `app/services/renderer/evidence.py::build_renderer_evidence`、`::ensure_renderer_integrity` 负责。
- 预期输出：可见 block 无法进入 layout 时记录 expected/actual/差值和稳定 `ir_layout_integrity:missing_blocks`，正式本地与线上边界在发布 DOCX 前失败关闭，不能让可见内容无声消失。
- 冲突/例外：整个文档无 layout 时按 PIPE-002 顺序回退；不能把单个 block 的缺页索引等同于全局无 layout。
- 禁止：继续用 `sorted(index for index in page_indices if index is not None)` 后忽略未归页 block；猜测任意页面而不留证据。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_renderer_evidence_blocks_missing_layout_drawing_and_table`；本地/线上阻断见 QUALITY-004。
- 样本证据：当前证据为合成 IR；尚无 committed 真样本专门构造缺页索引。
- 来源/取代：当前正式代码审计发现；不是 legacy 待迁移项。

### IR-004 v2 声明结构必须携带源清单并完成映射对账

- 状态：`enforced-tested`
- 输入信号：完成末页过滤、题注重关联和续表归一化后的 MinerU v2 blocks，及 converter 生成的主 DocumentIR blocks/assets。
- 正式 owner：`app/services/document_ir/mineru_converter.py::MinerUToDocumentIRService._convert_blocks`；完整性证据与阻断由 `app/services/document_ir/integrity.py` 唯一负责。
- 预期输出：DocumentIR metadata 记录归一化后的 source block 总数和按 source type 计数；每个主 block 通过既有 `metadata.source_type` 对账。`chart/image/figure` 必须生成带有效 `asset_ref` 的 `image`，table/formula/heading/list 必须生成对应显式类型和必要 payload；确定性缺失以稳定 flag 失败关闭。
- 冲突/例外：旧 IR 没有 source inventory 时跳过无法证明的 source→IR 对账，但仍执行 IR→layout/DOCX 对账；table context 等合成辅助 block 不计为主 block；不新增第二套 MinerU JSON parser。
- 禁止：把 `chart` 降级为 paragraph；只记录 `unsupported_block_type` 后继续成功；用媒体文件数替代一个 image block 对应一个 drawing 的合同。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_maps_nested_v2_chart_to_image_and_records_source_inventory`、`.test_convert_zip_fails_closed_when_declared_formula_payload_is_missing`；`tests.test_document_ir_layout_contract.DocumentIRLayoutContractTests.test_v1_payload_defaults_layout_fields_to_empty`。
- 样本证据：CM4112 当前 external 样本对账为 196 个归一化 source blocks，其中 38 chart + 15 image → 53 image blocks/assets；最终 DOCX 为 53 drawings，阻断标记为空。完整记录见本任务 `research/cm4112-validation.md`。
- 来源/取代：任务 `08-18-fix-formal-word-structural-regressions`；补足 IR-001 与 IMAGE-001 未覆盖的跨边界完整性合同。

### PAGE-001 模板绝对页面设置与源方向分工

- 状态：`implemented-gap`
- 输入信号：模板 page setup（纸张宽高、边距、装订线）和 DocumentIR page 宽高方向。
- 正式 owner：`app/services/renderer/word_renderer.py::_apply_page_setup`、`::_apply_page_setup_to_section`、`::_configure_layout_page_section`、`::_layout_page_requires_landscape`。
- 预期输出：显式 layout config 决定 Word 的绝对纸张尺寸和边距；源页只决定 portrait/landscape。宽表本身不改变方向，源页宽大于高时才使用横向节。
- 冲突/例外：v2 没有显式 page size 时当前使用 A4，可能覆盖 DOCX 模板自身的非 A4 尺寸；这是未裁决缺口。方向变化按 PAGE-002 分节。
- 禁止：用 MinerU/PDF 物理数值直接重写 Word 纸张；见到宽表就横向；忽略显式源页方向。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_configured_page_size_and_header_bold_flag`、`.test_render_to_bytes_preserves_portrait_section_for_wide_table_page`、`.test_render_to_bytes_keeps_source_landscape_page_landscape`。
- 样本证据：OPA228 P7 manifest 声明宽表焦点，但当前没有正式当前版本的实际转换证明。
- 来源/取代：commit `32edca58` parity 审计和归档任务 `08-18-fix-mineru-first-page-layout`。

### PAGE-002 仅方向变化创建新页分节

- 状态：`enforced-tested`
- 输入信号：相邻 LayoutPage 的 portrait/landscape 状态不同。
- 正式 owner：`app/services/renderer/word_renderer.py::DocumentIRWordRenderer.render_to_bytes`、`::_configure_layout_page_section`。
- 预期输出：方向变化时创建 `WD_SECTION_START.NEW_PAGE` 并应用目标方向；相同方向不因源物理页边界自动新建页面节。
- 冲突/例外：双栏区域内部使用 continuous section，由 COL-002 约束；语义分页由 FLOW-002 单独触发。
- 禁止：每个 MinerU page 都新增 `NEW_PAGE`；用 break-only 段落模拟方向节。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_starts_new_section_when_page_orientation_changes`、`.test_render_to_bytes_does_not_force_break_between_same_orientation_source_pages`。
- 样本证据：CM4112 为 external evidence；没有 committed 纵横向混合真样本。
- 来源/取代：commit `5d4a02d7` 删除逐源页硬分页；commit `674ce937` 保留方向分节。

### FLOW-001 同方向源页自然流动

- 状态：`enforced-tested`
- 输入信号：相邻源页方向相同，且下一页首内容不满足 FLOW-002 的语义起页信号。
- 正式 owner：`app/services/renderer/word_renderer.py::DocumentIRWordRenderer.render_to_bytes`、`::_render_layout_page`。
- 预期输出：不插入 `document.add_page_break()`、`w:br type="page"` 或只含分页符的空段落，让 Word 按内容自然分页。
- 冲突/例外：FLOW-002 精确的页顶内容组可在真实内容段落设置 `pageBreakBefore`；方向变化按 PAGE-002。
- 禁止：恢复“每个 PDF 页一个 Word 硬分页”；以空段落承载分页；为修某个标题破坏长表自然跨页。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_does_not_force_break_between_same_orientation_source_pages`、`.test_render_to_bytes_anchors_semantic_page_breaks_to_real_content`。
- 样本证据：SC2167 为 external historical evidence，曾验证无 blank body pages；当前版本没有 committed 视觉基线。
- 来源/取代：commit `5d4a02d7`；取代旧逐物理页分页行为。

### FLOW-002 页顶标题与独立表格组语义起页

- 状态：`implemented-gap`
- 输入信号：非首 LayoutPage 的第一个可见 body block 是 heading、带 caption 的 table，或 `table_context` paragraph。
- 正式 owner：`app/services/renderer/word_renderer.py::_semantic_page_break_block_id`、`::_render_block`；`app/services/renderer/table_renderer.py::_render_table_captions`。
- 预期输出：把 `pageBreakBefore` 放在标题段落、表格组首个 caption 或 context 真实内容段落上；普通段落和无 caption table 不强制起页。
- 冲突/例外：优先于 FLOW-001，但只对精确页顶内容组生效；不得创建独立 break-only paragraph。当前目标按 layout plan 的首 block 选择，而 two-col region 随后按左栏再右栏重排；若目标来自右栏，分页可能落在已渲染的左栏内容之后，现有测试未覆盖该组合。
- 禁止：按标题文字（如“工作原理”）或型号硬编码；所有 heading 无条件分页；在表格本体前额外插入空页。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_anchors_semantic_page_breaks_to_real_content`。
- 样本证据：CM4112“工作原理”和表格组是 external negative/acceptance evidence；未提交当前回归 fixture，且最新整本文档仍有页数增长风险。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；补充 FLOW-001 而非恢复逐页硬分页。

### FLOW-003 内容组保持与表格跨页

- 状态：`implemented-gap`
- 输入信号：heading、表题/表格/表注、长表行和连续表格 placeholder。
- 正式 owner：`app/services/renderer/word_renderer.py::_render_block`；`app/services/renderer/table_renderer.py::_render_table_captions`、`::_configure_data_table_rows`；`app/services/document_ir/layout_signals.py::merge_table_placeholder_continuations`。
- 预期输出：heading/table caption 使用 `keep_with_next`；表头可重复，表格行使用 `cantSplit`；空 table placeholder 只并入前一真实表格，不另渲染重复空表。
- 冲突/例外：`DocumentIRBlockLayout.continuation_heights` 当前只写入、没有 renderer 消费者，不能声称续页高度已参与 Word 排版；Word 最终分页仍由客户端决定。
- 禁止：把整张长表放进不可跨页容器；因 placeholder 创建第二张空表；把“有 continuation 元数据”写成“已验证不挤压”。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_merges_table_placeholder_continuation_and_landscape_orientation`、`.test_convert_zip_merges_real_mineru_empty_table_continuations`；`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_html_table_spans_and_annotations`。
- 样本证据：SC2167、CM4112 第 3/4 页表格均为 external evidence；没有自动排版后的表格挤压/分页断言。
- 来源/取代：两个 08-18 归档任务；明确降级“续表已解决”的历史结论。

## 4. 分栏、文本、表格与图片

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
- 冲突/例外：COL-003 的严格图片对用制表位；continuous section 的实际栏平衡需要 Word/WPS 视觉验收。
- 禁止：按全局 y 顺序交错左右栏；渲染完双栏后不恢复单栏；用 1×2 表格包装普通正文。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_native_columns_for_v2_region`、`.test_render_to_bytes_prefers_column_hint_when_ordering_native_columns`、`.test_render_to_bytes_keeps_continuous_restore_when_wide_content_follows_columns`。
- 样本证据：SC2167 为 external historical WPS/LibreOffice evidence；没有 committed 当前视觉回归。
- 来源/取代：commit `5d4a02d7` 与 `32edca58`；取代布局表格模拟普通栏。

### COL-003 严格成对图片行例外

- 状态：`enforced-tested`
- 输入信号：同一 two-col region 中可严格配对的 left/right image blocks，且配对不会吞并多题注/非图片内容。
- 正式 owner：`app/services/renderer/word_renderer.py::_split_two_column_image_rows`；`app/services/renderer/image_renderer.py::_render_two_column_image_row`、`::_configure_image_row_tabs`。
- 预期输出：单栏段落用 25%/75% 制表位放置一对图片，并按行顺序保留各自题注字段；不创建布局表格。
- 冲突/例外：多 annotation 或无法严格成对的图片留在 COL-002 原生栏中。
- 禁止：把任意两张图强行配对；合并/错配题注；恢复 1×2 布局表格。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_keeps_paired_image_caption_fields_in_row_order`、`.test_render_to_bytes_keeps_multi_annotation_images_in_native_columns`。
- 样本证据：SC2167 图片网格为 external historical evidence；当前 fixture 不含图片。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption`。

### TEXT-001 原生标题语义与内容组保持

- 状态：`enforced-tested`
- 输入信号：IR schema version、显式 IR heading、v1 heading-like paragraph、配置的 heading Word style 和层级。
- 正式 owner：`app/services/renderer/word_renderer.py::_render_block`；`app/services/renderer/text_renderer.py::_fill_heading_paragraph`；`app/conversion/docx_rules/text_semantics.py::infer_heading_level`。
- 预期输出：显式 heading 使用 Word heading 样式并 `keep_with_next`；`document-ir/v2` paragraph 不根据文本升级 heading，`document-ir/v1` 顺序兼容才允许可靠 heading-like 推断。编号图/表题注和正文引用不属于 heading-like。配置存在时使用配置的 named style。
- 冲突/例外：页顶分页由 FLOW-002；v1 推断得到的 heading-like paragraph 不设置 `keep_with_next`，也不能触发 FLOW-002。v2 paragraph 仍保留 TOC/list/bullet 识别，不因禁止标题推断而降级这些显式或可靠语义。
- 禁止：只加粗/放大而不使用标题语义；所有短句均升级；按“工作原理”等具体标题硬编码。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics`、`.test_render_to_bytes_keeps_v1_heading_like_paragraph_compatibility`、`.test_render_to_bytes_uses_explicit_v2_semantics_without_heading_guessing`、`.test_render_to_bytes_uses_configured_heading_word_style_when_available`；图/表反例见 `tests.test_text_render_characterization.TextRenderingCharacterizationTests.test_looks_like_heading_text_rejects_english_sentence`。
- 样本证据：OPA228 最小 fixture 包含 heading，但 runner 只断言标题文本可见；CM4112 当前 external 样本显式 heading 为 18，DOCX heading 段落为 18；WPS 实际观察“工作原理”从新页开始。
- 来源/取代：commit `32edca58` 正式 renderer 语义化。

### TEXT-002 列表必须使用原生编号且保留续行

- 状态：`enforced-tested`
- 输入信号：IR list block 或普通 paragraph 中可靠的 bullet marker；item level 和换行由 INPUT-004 产生。
- 正式 owner：`app/services/renderer/text_renderer.py::_fill_list_paragraph`、`::_fill_auto_list_or_paragraph`、`::_apply_bullet_numbering`；`app/conversion/docx_rules/text_semantics.py::normalize_list_item`。
- 预期输出：列表项使用 Word `numPr`/bullet numbering，不保留手写 marker；同一 item 的续行内容不丢失。
- 冲突/例外：负数、负温度和普通破折号句不判为列表；v2 explicit list 优先于文本推断。
- 禁止：用“• ”等字符模拟列表；全局拆分所有换行；为满足 analyzer 删除可见 marker 却不写 numbering。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics`、`.test_render_to_bytes_promotes_bullet_like_paragraphs_to_word_lists`；converter 测试见 INPUT-004。
- 样本证据：OPA228 最小 fixture 是 committed smoke，但当前 runner 未断言原生编号；OPA228 P2 历史 signoff 含手写列表风险，不能证明当前无回退。
- 来源/取代：commit `32edca58`；取代手写 bullet 输出。

### TEXT-003 富文本与普通正文保真

- 状态：`enforced-tested`
- 输入信号：v2 rich text、inline HTML 的 sub/sup/bold/italic、普通文字和术语配置。
- 正式 owner：`app/services/renderer/text_renderer.py::_fill_paragraph`、`::_render_inline_html`、`::_prepare_text_for_rendering`；`app/services/renderer/semantic_text.py`。
- 预期输出：支持的 inline 标记转为 Word run 语义；术语替换与公式文本归一化当前在所有共享文本入口应用，已知 TeX 模式才被改写，普通正文和未知路径字符保持可见。
- 冲突/例外：原生 OMML 只在明确数学边界或整段可解析公式路径生成；普通正文仍会经过 `normalize_formula_text()`，因此新增归一化规则必须同时覆盖非数学负例。不支持的 inline markup 应保持可见文本。
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

### TABLE-003 表头、行跨页、边框和列宽

- 状态：`enforced-tested`
- 输入信号：Word table 首行/后续 `th`、列数、配置的 border/header fill/font 和表格规模。
- 正式 owner：`app/services/renderer/table_renderer.py::_configure_data_table_rows`、`::_table_column_widths`、`::_template_config_for_table_columns`、`::_set_table_borders`。
- 预期输出：表头行标记 `tblHeader`，所有行标记 `cantSplit`；5 列数据手册表优先给描述列宽度，6 列及以上使用紧凑字号/等宽策略；应用配置边框与表头样式。
- 冲突/例外：XML 结构不能证明 Word/WPS 实际无挤压；整文档视觉门禁见 QUALITY-003。
- 禁止：把 `cantSplit` 写成“表格不会挤压”的证明；按源页缩放整表；为一个器件硬编码列宽。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_html_table_spans_and_annotations`、`.test_render_to_bytes_styles_later_th_cells_as_table_headers`、`.test_datasheet_five_column_table_widths_prioritize_description_column`、`.test_render_to_bytes_uses_configured_long_table_caption_and_border_color`。
- 样本证据：OPA228 P6/P7 与 CM4112 均缺当前排版后的自动/人工闭环。
- 来源/取代：commit `32edca58` 与两个 08-18 归档任务；明确不继承 legacy 页高估算器的已实现声明。

### TABLE-004 无效表格输入不得重复题注或静默伪装

- 状态：`planned`
- 输入信号：table HTML 缺失/不可解析，同时 `block.text` 与 `block.captions` 含相同题注文本。
- 正式 owner：当前缺口位于 `app/services/renderer/table_renderer.py::_render_table`；尚无满足合同的正式 owner。
- 预期输出：后续实现应只保留一份可见题注，并显式报告表格体缺失/解析失败；不得把题注再次当表体正文。
- 冲突/例外：如果 `block.text` 是与 captions 不同的真实 fallback 内容，应保持可见，不能简单全部删除。
- 禁止：先渲染 captions，再无条件渲染相同 `block.text`；静默生成看似成功但没有表体的 DOCX。
- 自动验证：无；现有正式表格测试只覆盖有效 HTML。
- 样本证据：无；需要最小无效 table HTML 正式回归。
- 来源/取代：当前正式代码审计发现。

### IMAGE-001 图片资产绑定、显示宽度和可见失败

- 状态：`implemented-gap`
- 输入信号：IR image asset_id、MinerU 包内资产路径、bbox/page width、当前栏宽和 captions。
- 正式 owner：`app/services/document_ir/mineru_converter.py::_resolve_image_path`；`app/services/renderer/image_renderer.py::_render_image`、`::_available_width`、`::_image_fallback_text`。
- 预期输出：资产路径必须位于包根内；renderer 使用原图片字节，按 bbox/page 相对宽度限制在当前栏/页面内，写入 `w:doNotAutoCompressPictures` 并保留题注；缺失或无效图片输出可见 fallback 文本。
- 冲突/例外：不承诺放大小图到某个历史最小宽度；Word 显示清晰度仍取决于原图像素和客户端。现有正式测试直接覆盖正常图片字节、相对宽度、题注和禁止自动压缩，但未直接覆盖越界/重名资产绑定及缺失、损坏图片 fallback。
- 禁止：静默丢图；无条件拉伸到全栏；用截图替换可编辑正文；按某个样本设置固定厘米宽度。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_bbox_width_for_images_and_annotations`；converter 的正常路径/资产输出由 `tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_outputs_v2_pages_layout_roles_and_annotations` 间接覆盖。
- 样本证据：正式测试仅用 1×1 PNG；SC2167 清晰度为 external historical evidence，缺当前真实像素/DPI fixture。
- 来源/取代：commit `5d4a02d7`；取代 legacy 固定最小宽度策略。

### IMAGE-002 编号图片题注只做严格重关联

- 状态：`enforced-tested`
- 输入信号：同页连续 image group 的题注数量失衡，所有可识别题注具有相同 label、连续编号且数量与图片严格相等。
- 正式 owner：`app/services/document_ir/mineru_converter.py::_reassociate_numbered_image_captions`、`::_reassociate_image_group`。
- 预期输出：按连续编号为每张图分配唯一题注；原来已一图一题注或条件不完整时保持原关联。
- 冲突/例外：此规则不通过视觉最近邻猜关联；多 annotation 渲染仍由 COL-002/IMAGE-001 保持。
- 禁止：只按出现顺序重排任意题注；跨页关联；丢弃无法识别的原题注。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_reassociates_only_strict_numbered_image_groups`。
- 样本证据：SC2167 为 external historical evidence；无 committed 图片组 fixture。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption/research/caption-reassociation.md`。

## 5. 原生字段与公式

### FIELD-001 目录只写一个原生 TOC 字段

- 状态：`implemented-gap`
- 输入信号：TOC 标题和足够可靠的目录点线 entry；renderer 当前文档尚未写 TOC 字段。
- 正式 owner：`app/services/renderer/text_renderer.py::_fill_toc_entry_if_needed`、`::_configure_toc_styles`；`app/services/renderer/word_renderer.py::_RenderContext.toc_written`。
- 预期输出：写入一个原生 `TOC` complex field 并应用配置的 TOC styles；后续目录 entry 不重复写静态点线目录；`toc_written` 只属于单次 render context。
- 冲突/例外：字段结果依赖 Word/WPS 更新；`updateFields` 只请求更新，不保证所有客户端打开即刷新。现有测试只覆盖单次 render 的一个 TOC 字段，未直接覆盖复用同一 renderer 的跨调用状态隔离。
- 禁止：整页目录逐行静态点线输出并同时插入 TOC；一个 entry 一个 TOC field。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_one_native_toc_field_for_toc_like_entries`、`.test_render_to_bytes_uses_configured_toc_styles`。
- 样本证据：OPA228 P2 manifest 有 TOC 焦点，但当前 Golden 未实际转换。
- 来源/取代：commit `5d4a02d7`；取代静态目录为正式目标。

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

### FIELD-003 页脚页码必须是 PAGE 字段

- 状态：`planned`
- 输入信号：模板配置 `footer.enabled=true` 且 `show_page_number=true`。
- 正式 owner：部分实现位于 `app/services/renderer/word_renderer.py::_apply_header_footer`、`::_add_complex_field`；纯页码无左右文字分支尚不满足合同。
- 预期输出：无论是否配置左右文字，页码都应使用原生 `PAGE` field；左右文字路径用 positional tab 布局，不把数字写死。
- 冲突/例外：明确禁用 footer 时保留模板继承；字段视觉位置需要 Word/WPS 验收，LibreOffice 对 `w:ptab` 展开不同。
- 禁止：输出只有“第  页”的静态占位；写死页码；以 LibreOffice positional tab 视觉替代 Word/WPS 结论。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_native_custom_footer_and_ignores_source_footer` 只覆盖配置左右文字的 PAGE field；纯页码分支无测试且当前会写“第  页”。
- 样本证据：SC2167 自定义 footer 为 external historical WPS evidence；没有纯页码当前真样本。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption/research/configurable-footer.md`；当前代码审计将完整合同降为 planned。

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

- 状态：`implemented-gap`
- 输入信号：公式 block、正文 inline math、表格 cell/notes 中的 TeX；支持分式、根式、上下标、常用符号、文本/样式 wrapper、overline、boxed 和 left/right 等当前解析子集。
- 正式 owner：`app/services/renderer/text_renderer.py::_OmmlParser`、`WordTextRendererMixin._render_mixed_math`、`._fill_formula_paragraph`；`app/conversion/docx_rules/text_semantics.py::normalize_formula_text`、`::collapse_double_escaped_tex_commands`。
- 预期输出：支持的数学结构写为原生 OMML；普通公式字符显式使用直立体，只有 `\\mathit` 等源公式明确要求时才使用斜体；正文、独立公式、表格 cell 和 note 共用同一归一化/解析路径；只折叠已知 TeX command 的双反斜杠，保留普通 UNC/路径文本。
- 冲突/例外：不是完整 TeX 引擎；matrix/cases/align、自定义 macro 等未实现结构不得写成“全部公式已支持”。当前 `\\tag{...}` 会被识别但不生成可见公式编号，现有公式矩阵只证明命令残留被移除，不能证明编号保真。
- 禁止：每遇到一个公式就在调用者加特例；全局删除反斜杠；仅在正文修复而遗漏表格/题注路径；声称支持任意 LaTeX。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_fraction_omml_in_formula_and_table_cells`、`.test_render_to_bytes_writes_extended_omml_in_all_shared_text_paths`、`.test_render_to_bytes_preprocesses_cm4112_formulas_without_tex_residue`、`.test_render_to_bytes_supports_datasheet_tex_matrix_in_all_math_entries`、`.test_render_to_bytes_normalizes_formula_text_in_table_cells_and_notes`、`.test_render_to_bytes_normalizes_manual_quality_record_formula_residue`。
- 样本证据：CM4112/RS2G04 为 external evidence；自动测试使用提炼公式矩阵，不是 committed 真 MinerU 包。
- 来源/取代：commit `674ce937`；取代按单个公式字符串兼容的修复方式。

### MATH-003 解析失败保持可见并留下质量信号

- 状态：`enforced-tested`
- 输入信号：未知 command、括号不闭合或 `_OmmlParser` 无法完整解析的公式源。
- 正式 owner：`app/services/renderer/text_renderer.py::_OmmlParser.parse`、`WordTextRendererMixin._render_mixed_math`；`app/services/renderer/docx_quality.py::_unique_latex_residue`、`::build_docx_quality_flags`。
- 预期输出：不能安全生成 OMML 时保留原公式文本可见，并由 DOCX analyzer 报告 `latex_residue`/`latex_residue_detected`，而不是静默丢失。
- 冲突/例外：如果输入在进入 renderer 前已错误降级成普通字符，残留扫描可能发现不了，见 QUALITY-004。
- 禁止：解析失败返回空段落；捕获后伪装成功；为消除质量 flag 删除原文本。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_malformed_fraction_remains_visible_and_is_reported_as_latex_residue`。
- 样本证据：无 committed 失败公式 fixture。
- 来源/取代：commit `674ce937` 的失败合同。

## 6. 样式、页眉页脚与质量门禁

### STYLE-001 模板配置优先且版本合同独立

- 状态：`enforced-tested`
- 输入信号：绑定模板 DOCX、layout config、document language 和 subscript/terminology config。
- 正式 owner：`app/services/renderer/word_renderer.py::_create_document`、`::_load_template_config`；`app/services/renderer/template_config.py`；版本/API owner 见 [模板布局配置合同](./template-layout-configuration.md)。
- 预期输出：renderer 清空模板 body 但保留 sectPr 和模板 header/footer，应用绑定版本的页面、段落、表格、字体及术语配置；发布版本不可变性不在本文重复定义。
- 冲突/例外：模板决定 Word 样式和绝对页面设置，源 layout 决定内容顺序、分栏和方向；显式空字体值保留继承语义。
- 禁止：为适配 PDF 修改已发布 seed；在 renderer 猜另一套 schema；让源 bbox 覆盖模板字体/边距。
- 自动验证：`tests.test_template_layout_config_schema.TemplateLayoutConfigSchemaTests.test_real_seed_matches_editor_and_renderer_contract`、`.test_published_v2_hash_is_immutable`、`.test_legacy_font_fields_are_completed_without_overwriting_explicit_empty_values`；renderer 配置测试见 PAGE-001/TEXT-001。
- 样本证据：Golden 历史验收绑定旧 commit，不能证明当前版本；当前无模板组合视觉基线。
- 来源/取代：`template-layout-configuration.md` 和 commit `32edca58`。

### STYLE-002 页眉页脚优先级与 section 限制

- 状态：`implemented-gap`
- 输入信号：模板已带 decoration、配置 `header/footer.enabled`、自定义 footer 文本，以及 IR 的 page_header/page_footer/page_number blocks。
- 正式 owner：`app/services/renderer/word_renderer.py::_apply_header_footer`、`::_render_page_decorations`、`::_resolve_decoration_font`。
- 预期输出：配置禁用时保留模板 decoration；显式自定义 footer 高于源 footer；未自定义时才允许源 decoration 写入 section，并继承配置/legacy/template font 次序；后续 section 沿用 Word 标准 relationship 继承，不复制 header/footer relationship。
- 冲突/例外：Word decoration 属于 section；相同方向源页共享 section 时，当前逐页写源 header/footer 会互相覆盖，只剩该 section 最后一次内容，源 header 也可能覆盖 `_apply_header_footer` 先写入的配置 header 文本。正式本地请求的 `use_mineru_header_footer` 当前也未传入 renderer，不能视为有效开关。
- 禁止：声称支持每个同向源页不同页眉；在自定义 footer 后再写源 footer；把未消费的 request 字段写成已实现行为。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_template_decorations_when_config_disabled`、`.test_render_to_bytes_writes_native_custom_footer_and_ignores_source_footer`、`.test_extracted_decorations_keep_normal_style_and_legacy_font_inheritance`、`.test_decoration_font_resolution_preserves_explicit_empty_and_fallback_order`；没有同 section 多源页不同 header 的正式测试。
- 样本证据：SC2167 自定义 footer 为 external historical evidence；源页 header 逐页差异无样本门禁。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption`；当前代码审计补充 section 覆盖和未消费开关缺口。

### STYLE-003 四类字体槽独立写入

- 状态：`enforced-tested`
- 输入信号：eastAsia/legacy font、ascii、hAnsi 和 complex script 字体配置，包含显式空值。
- 正式 owner：`app/conversion/docx_rules/run_fonts.py::apply_run_fonts`；`app/services/renderer/text_renderer.py::_apply_run_style`；`app/services/renderer/word_renderer.py::_resolve_decoration_font`。
- 预期输出：分别写入 eastAsia、ascii、hAnsi、cs 槽；缺少新槽时回退 legacy font，显式空值保持继承，不被默认值覆盖。
- 冲突/例外：字段 schema/version 属于模板配置合同；本文只约束最终 run 输出。
- 禁止：只写 eastAsia 造成西文/公式字体漂移；用 truthy 判断覆盖显式空值；在表格/页眉维护独立字体逻辑。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_seed_config_declares_western_and_complex_fonts_for_all_text_groups`、`.test_render_to_bytes_writes_configured_body_header_and_footer_font_slots`、`.test_decoration_font_resolution_preserves_explicit_empty_and_fallback_order`。
- 样本证据：无当前跨 Word/WPS 字体视觉基线。
- 来源/取代：commit `5d4a02d7` 与模板 v2 合同。

### STYLE-004 正式入口必须绑定明确模板配置

- 状态：`enforced-tested`
- 输入信号：本地正式 CLI/adapter 的显式 template/layout config、缺省参数与 `no_template`，以及线上已固化 Template Version。
- 正式 owner：本地默认资源选择由 `scripts/dev/formal_mineru_conversion.py::run_conversion` 负责；默认路径来自 `app/core/config.py::Settings`；线上继续由 `TemplateReadService.resolve_template_version()` 与 `DocumentJobExecutionService._render_and_save_word()` 负责。
- 预期输出：本地显式路径优先；省略时使用当前 `Settings.default_template_path/layout_config_path`，`no_template=true` 只禁用 DOCX 模板而不禁用 layout config。本地所需默认资源不存在时显式失败，不以空配置继续；共享 renderer 只消费调用者传入路径，线上版本缺失/损坏继续失败关闭，不回退 bundled 配置。
- 冲突/例外：`DocumentIRWordRenderer` 的低层 `template_path=None/config_path=None` 仍表示无模板/空配置；字体安装由目标系统负责。可见 Word 文本受 STYLE-003 四槽约束，OMML 公式由独立 `m:mathFont` 控制。
- 禁止：省略本地参数时静默使用空 `TemplateConfigPackage`；在 renderer 读取全局 Settings；以本机字体别名改写已发布 seed；把 OMML run 错计为缺少段落字体槽。
- 自动验证：`tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_formal_adapter_converts_minimal_mineru_package_to_openable_docx`、`.test_formal_adapter_resolves_default_explicit_and_no_template_resources`；既有显式配置四槽测试继续保护 renderer。
- 样本证据：CM4112 新候选省略 template/layout config 后，666/666 个可见 `w:t` run 写入 `宋体/Arial/Arial/Times New Roman`，OMML 仍独立；WPS GUI 选中标题时显示请求字体“宋体”，同时提示“缺失字体”，WPS CLI 仍有单位/公式替换字符。本机字体安装边界不改写配置。完整记录见当前任务 `research/cm4112-validation.md` 与 `research/font-config-root-cause.md`。
- 来源/取代：模板布局配置合同中“本地当前内置配置指向 v2”的既有要求；补足正式 local adapter 的缺省绑定缺口。

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

## 7. 冲突优先级矩阵

| 冲突 | 基础规则 | 优先规则/裁决 | 必须共同保护的回归 |
|---|---|---|---|
| 同方向自然流 vs 章节/表格组起页 | FLOW-001 | FLOW-002 只对非首页页顶 heading、captioned table、table context 的真实段落设置 `pageBreakBefore` | SC2167 无 blank body pages；CM4112“工作原理”和独立表格组起页；整本文档页数变化须解释 |
| 自然流 vs 长表跨页 | FLOW-001 | FLOW-003 的 `tblHeader`/`cantSplit` 与 Word 自然分页；不得恢复逐源页硬分页 | CM4112 第 3/4 页、SC2167 长表不挤压且无空白页 |
| 源页方向 vs 宽表 | PAGE-001 | 源 page 宽高方向优先；宽表本身不触发横向 | OPA228 P7 portrait wide table；真实 landscape page |
| 普通原生双栏 vs 成对图片 | COL-002 | COL-003 仅对严格图片对使用单栏制表位 | 左→右阅读顺序、多 annotation 不错配、SC2167 图片网格 |
| 双栏 vs wide/局部单栏 | COL-001 | wide block 与真实单栏 gap 留在单栏 region；仅实际 band 进入双栏 | OPA228/CM4112 首页内容顺序与表格宽度 |
| 模板绝对样式 vs 源版式 | STYLE-001 | 模板决定纸张/边距/字体；源 IR 决定内容语义、相对布局和方向 | 模板版本测试 + PAGE/COL/FLOW 共同回归 |
| 模板/自定义 decoration vs 源 decoration | STYLE-002 | 配置禁用保留模板；显式自定义 footer 高于源 footer；同 section 逐页源 decoration 及源 header 覆盖配置 header 是已知缺口 | 模板继承、自定义 footer PAGE field、同向页不同 header 缺口样本 |
| 可编辑结构 vs 源像素外观 | TABLE-001、FIELD-001、FIELD-002 | 原生 table/TOC/SEQ/REF 优先，但不得改变内容顺序或静默丢失 | OOXML 结构 + Word/WPS 视觉检查 |
| 数学归一化 vs 普通正文保真 | TEXT-003 | 所有共享文本入口都会归一化，但只允许证据充分的 TeX 模式改写；OMML 限于数学边界/整段公式，普通路径/UNC 保持，失败按 MATH-003 可见 | CM4112 公式矩阵 + 普通反斜杠正文 |
| 富文本题注 vs 多条真实 annotation | TEXT-004 | flat rich-node list 是一条逻辑题注；string list/多个 nested groups 保持多条，renderer 不重猜边界 | v2 rich chart/table caption + 多题注负例 + COL-003 + WPS 图 33 |
| 正式入口默认配置 vs 版本化配置 | STYLE-004 | 本地 adapter 省略参数时使用 Settings 当前默认；线上只用固化 Template Version，renderer 无全局 fallback | local 缺省/显式/no-template + 线上模板版本 + STYLE-003 四槽 |
| 尾页清理 vs 内容保真 | INPUT-003 | 实质内容保真优先；过滤必须同时满足末页、CTA、视觉资产和无实质结构 | 保守负例 + SC2167 external evidence |
| OOXML 指标 vs 实际视觉质量 | QUALITY-001 | QUALITY-003 的当前 commit 真客户端验收决定视觉结论 | CM4112 21→23 页负例；表格/栏/图片实际排版 |

## 8. 规则回归矩阵

“自动测试”列只列正式 converter/renderer/pipeline 证据；legacy characterization 不计入。

| 规则 | 正式 owner 层 | 自动测试层 | Committed 样本 | External/人工证据 | 当前缺口 |
|---|---|---|---|---|---|
| PIPE-001、INPUT-001、INPUT-004 | formal adapter、MinerU package/converter | conversion sandbox、converter layout、component runner | OPA228 P1 最小 MinerU v2 包 | 无 | fixture 不含表格/图片/公式/双栏；runner 只断言可打开 |
| PIPE-002、IR-001 | models、layout plan、renderer | IR contract、converter/renderer layout | 无复杂 IR 基线 | 线上合成 worker | 无当前真样本 IR snapshot |
| INPUT-002 | package extraction、formal adapter | 仅入口正常/缺路径 | OPA228 P1 正常包 | 无 | 无正式 ZIP traversal/坏 JSON 定向测试 |
| INPUT-003 | shared content rule、converter | conservative/filter converter tests | 无 | SC2167 historical | 无 committed 宣传尾页包 |
| IR-002、PAGE-001、PAGE-002 | layout signals、section setup | converter/renderer layout | OPA228 PDF 仅作为输入资产 | CM4112 external | 没有当前真实纵横向/页数视觉基线 |
| IR-003、IR-004、QUALITY-004 | integrity、converter、renderer evidence、正式发布边界 | converter/IR contract/renderer/formal adapter/document job | 无 | CM4112 当前 external 对账 | 无 committed 含 chart 的 MinerU fixture；实际分页不属于阻断计数 |
| TABLE-004 | 当前缺口 | 无 | 无 | 无 | 无效 HTML/空有效表格的失败策略待实现 |
| FLOW-001、FLOW-002 | renderer page loop、semantic break | renderer layout | 无 | SC2167、CM4112 external | 无实际落页和空白页自动断言；双栏重排可能使语义分页目标晚于左栏内容 |
| FLOW-003、TABLE-001、TABLE-002、TABLE-003 | layout signals、table renderer | converter/renderer table tests | OPA228 P6/P7 PDF 未执行 | CM4112、SC2167 external | continuation height 无消费者；无表格挤压/跨页视觉门禁 |
| COL-001、COL-002 | layout plan、renderer columns | renderer layout | OPA228 P1/P2 PDF 未执行 | CM4112 当前 LibreOffice/WPS、SC2167 external | 无自动 Word/WPS 栏平衡断言；WPS 分页仍与 LibreOffice 不同 |
| COL-003、IMAGE-001、IMAGE-002 | image renderer、converter | renderer/converter image tests | 无真实图片 MinerU fixture | SC2167 external | 仅 1×1 PNG；无越界/重名绑定和损坏 fallback 定向测试；无 DPI/清晰度基线 |
| TEXT-001、TEXT-002、TEXT-003、TEXT-004 | converter caption owner、text renderer、shared semantics | converter/renderer layout、shared text characterization | OPA228 P1 最小包 | CM4112 当前 heading 18/18；图 33 单题注与 WPS GUI 关键页；OPA228 historical signoff | component runner 未断言 heading/list/unit focus；无 committed 富文本 caption 包 |
| FIELD-001、FIELD-002 | text renderer、render context | renderer layout | OPA228 P2 PDF 未执行 | SC2167 external | 字段更新和视觉仅客户端可确认；SEQ 更新可能重排非 1 起始/跳号编号 |
| FIELD-003、STYLE-002 | renderer header/footer | custom footer/template tests（部分） | 无 | SC2167 historical | 纯页码无 PAGE field；同 section source header 覆盖；adapter 开关未消费 |
| MATH-001、MATH-002、MATH-003 | converter、shared semantics、OMML parser | converter/renderer formula matrix | 无 MinerU 公式 fixture | CM4112、RS2G04 external | 非完整 TeX；`\\tag` 不生成可见编号；无真实输入包；预 renderer 降级可能漏 flag |
| STYLE-001、STYLE-003、STYLE-004 | formal adapter、renderer/template config/fonts | template schema、formal adapter、renderer layout | 模板 seed 与 OPA228 PDF | CM4112 当前四槽与 WPS 请求字体/缺失字体边界；Golden old-commit signoff | 目标系统未安装精确宋体/Cambria Math；OMML 字体独立 |
| QUALITY-001、QUALITY-002 | analyzer/evidence、sample governance | Golden/component governance | 4 个 OPA228 PDF + 1 个最小 MinerU 包 | 历史/外部样本分层 | Analyzer 不测实际分页；Golden 当前不离线 deterministic；外部/历史层级未自动强制 |
| QUALITY-003 | 尚无 | 无整文档视觉自动门禁 | 仅输入资产 | CM4112 当前 LibreOffice/WPS 有界记录 | 图 33 碎片稀疏页已消失；仍无 WPS GUI 全 20 页、自动栏平衡/清晰度门禁，LibreOffice 与 WPS 为 23/20 页 |

## 9. 规则变更流程

1. 先找到受影响规则 ID；没有稳定通用规则时新增 ID，不以 PDF 型号命名。
2. 在改代码前更新输入信号、唯一 owner、冲突和回归矩阵；产品意图不明确时标 `planned`，不得把当前 bug 写成合同。
3. 只修改正式 owner；调用者只传递合同需要的数据，不复制规则。复用 legacy 目录中的 parser/纯函数时，必须由正式链路测试证明。
4. 先运行该规则最小正式测试，再运行冲突矩阵中的共同回归。共享布局/文本/表格 owner 变更必须检查所有行为不同的正式调用路径。
5. 使用正式入口生成受影响的 committed fixture 和必要 external sample；记录当前 commit、输入/输出 hash、工具版本和验收结论。
6. OOXML analyzer 用于结构检查；Word/WPS 用于最终分页和视觉判断，LibreOffice 可辅助但不得替代 Word/WPS 特有字段/栏行为。
7. 只有证据随当前版本更新后才能提升状态；单个新 PDF 通过不能覆盖旧样本失败。若出现整文档回退，先回到冲突矩阵和共同 owner，不继续堆叠型号特例。

## 10. 非权威 legacy runtime 历史附录

本节只记录差异和迁移线索，不定义正式输出。下面的 legacy tests 除非测试的是被正式链路直接复用的纯函数，且同时有正式 renderer 测试，否则不能提升任何规则状态。

| 历史 owner/证据 | 历史行为 | 对应正式规则/历史行为状态 | 迁移或取代结论 |
|---|---|---|---|
| `app/conversion/runtime/input_adapter_runtime.py` 与 `tests.test_input_adapter_characterization` | legacy/v2 输入、页面清理、visual block 适配 | INPUT-001/003/004 已由正式 converter 测试；其余 `historical` | 不迁移编排；共享 `docx_rules` 纯函数由正式测试证明后使用 |
| `app/conversion/runtime/page_layout_runtime.py` 与 `tests.test_page_layout_characterization` | 页面分区、TOC continuation、dense visual page、1×2 或 section 布局 | PAGE-001/002、FLOW-001/002、COL-001/002 | 旧页面 renderer 已取代；dense visual/appendix 细分没有正式证据时保持 historical |
| `app/conversion/runtime/page_flow_runtime.py` 与 `tests.test_page_flow_characterization` | 基于估算高度为 heading/table unit 规划分页 | FLOW-003 `implemented-gap` | 正式 renderer 未迁移页高估算；不得把 legacy 测试写成当前长表已解决 |
| `app/conversion/runtime/table_render_runtime.py` 与 `tests.test_render_table_from_html_characterization` | legacy 长表拆分、caption、table writer | TABLE-001/002/003 | writer 非权威；`table_html_parser.py` 是正式 renderer 当前实际依赖，但 legacy writer 测试仍不算正式证据 |
| `app/conversion/runtime/text_rendering.py` 与 `tests.test_text_render_characterization` | legacy paragraph/TOC/title/list writer | TEXT、FIELD、MATH、STYLE 正式规则 | writer 非权威；指向 `app/conversion/docx_rules/text_semantics.py` 的共享纯规则测试只能作为补充证据 |
| legacy static TOC/caption/page number | 静态点线、普通题注或静态页码 | FIELD-001/002 已取代；FIELD-003 尚有纯页码缺口 | 不恢复静态字段；缺口进入正式 owner 后续任务 |
| legacy 每源页硬分页 | 物理页与 Word 页一一硬切 | FLOW-001/002；历史行为为 `superseded` | commit `5d4a02d7` 明确取代；章节/表格组只走 FLOW-002 |
| legacy 固定/最小图片宽度 | 以固定尺寸提高可见性 | IMAGE-001；历史行为为 `superseded` | 正式 renderer 使用 bbox 相对宽度；清晰度问题应通过真实图片样本处理 |
| legacy 1×2 布局表格 | 用表格模拟正文双栏或图片对 | COL-002/003；历史行为为 `superseded` | 普通正文用原生栏；严格图片对用制表位 |

## 11. 已确认但本任务不修复的产品缺口

- `DocumentIRBlockLayout.continuation_heights` 在正式转换中写入，但 renderer 没有消费者；不能证明续表高度已影响分页。
- 同方向源页共享一个 section；反复写源页 header/footer 会覆盖为该 section 最后一次内容，源 header 也会覆盖同 section 中先写入的配置 header 文本。
- `FormalMinerUConversionRequest.use_mineru_header_footer` 当前未被 `_render_document` 消费。
- footer 仅启用页码、没有左右文字时，当前输出静态“第  页”而不是 `PAGE` field。
- 无效/缺失 table HTML 且 `block.text` 与 caption 相同时，当前会重复输出题注。
- 多套 MinerU 结果共存时，content list 与 layout JSON 没有绑定同一结果根目录；basename 重名图片也可能选中错误资产。
- heading-like paragraph 的样式推断不会获得显式 heading 的 `keep_with_next` 和页顶语义分页。
- 双栏页的语义分页目标在栏重排前选取；目标位于右栏时，`pageBreakBefore` 可能出现在已渲染的左栏内容之后。
- v2 无显式 page size 时会使用 A4，可能覆盖 DOCX 模板自身的非 A4 页面尺寸。
- TOC 只保留一个原生字段并按合同抑制后续静态目录项，但尚无 Word/WPS 更新后目录内容的当前验证；SEQ 未使用 `\\r` 保留源编号，Word 更新字段后跳号/非 1 起始题注可能被重新编号；源 `page_number` block 仍只是普通页脚文本。
- `\\tag{...}` 当前会被公式 parser 消费但不生成可见编号，且不会留下 LaTeX residue 质量信号。
- 可选翻译当前不处理 captions 和 footnotes，可能产生正文已翻译而题注/表注仍为原文的混合输出。
- `build_docx_quality_flags()` 只记录结构风险；线上任务当前不会仅因这些 flags 自动失败。
- 没有当前版本的整文档页数、空白页、实际落页、表格挤压、栏平衡和图片清晰度自动门禁；CM4112 最新 external 结果已证明局部测试不足。
