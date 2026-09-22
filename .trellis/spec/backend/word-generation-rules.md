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
- 正式 owner：`app/services/renderer/layout_plan.py::build_layout_plan`、`::_build_legacy_plan`；`app/services/renderer/word_renderer.py::DocumentIRWordRenderer.render_to_bytes`；正式传递 owner 为 `scripts/dev/formal_mineru_conversion.py::convert_formal_mineru_package` 和 `app/domains/document_jobs/execution.py::DocumentJobExecutionService._render_and_save_word`。
- 预期输出：v2 使用分页组、角色和分栏布局计划；正式本地和线上入口各自只构造一次最终 LayoutPlan，并把同一实例传给 renderer 与 evidence。v1 或无任何 layout 的 IR 以一个顺序页面渲染，内容不因缺少新字段而丢失；测试/兼容调用未传计划时 renderer 调用同一公共 builder。
- 冲突/例外：v2 只要存在 pages 且至少一个 block 有 layout 就不会整体回退；此时单个无法归属页面的 block 受 IR-003 缺口约束。
- 禁止：把 v1 兼容回退误称为旧 runtime；为某个样本静默切换两套 Word writer。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_keeps_v1_sequential_fallback`；`tests.test_document_ir_layout_contract.DocumentIRLayoutContractTests.test_v1_payload_defaults_layout_fields_to_empty`、`.test_v2_payload_round_trips_page_and_block_layout`。
- 样本证据：无直接真样本；当前证据为合成 IR。
- 来源/取代：commit `32edca58` 正式 renderer 合同；旧 runtime 的兼容行为不作为证据。

### INPUT-001 唯一 MinerU 结果根内 v2 优先且资源同根绑定

- 状态：`enforced-tested`
- 1. Scope / Trigger：正式目录或 ZIP 输入中发现 MinerU content list 时，必须先确定唯一结果根，再读取 content、layout 和图片资产；不能让三个调用点各自在整个解压目录独立搜索。
- 2. Signatures：`app/services/document_ir/mineru_package.py::find_content_list(package_root: Path) -> Path` 返回唯一选中的 content-list 路径；`app/services/document_ir/mineru_converter.py::MinerUToDocumentIRService.convert_zip(...)` 以其 `parent` 作为后续 `package_root`；`::load_content_blocks(content_list_path)` 支持顶层 list、`content_list` 字段和嵌套 page list。
- 3. Contracts：同一目录内允许 v2 与 legacy 同时存在并优先选择唯一 v2；没有 v2 时使用唯一 legacy。`build_pages()`、表图关系归一化和图片解析只消费该目录，目录外 layout/资产不得参与当前文档。
- 4. Validation & Error Matrix：没有 content list → `FileNotFoundError`；候选分属多个目录 → `ValueError`；同一目录存在多个首选版本候选 → `ValueError`；图片在绑定根内零命中或 basename 多命中 → 返回无资产并由 `source_ir_integrity:payload_missing:image` 失败关闭。所有错误均在正式本地/线上发布前暴露。
- 5. Good/Base/Bad Cases：Good＝同根 v2+legacy、layout、assets，选择 v2 且其余资源同根；Base＝同根只有一个 legacy，正常兼容；Bad＝多结果根、同根多个 v2/legacy、仅跨根资产或 basename 重名，均不得猜选。
- 6. Tests Required：`test_convert_zip_prefers_v2_content_and_keeps_legacy_only_fallback` 断言同根优先级；`test_convert_zip_binds_layout_and_assets_to_content_list_result_root` 断言 layout/asset 不跨根；`test_convert_zip_rejects_multiple_mineru_result_roots` 覆盖多根及同根多个同版本候选；资产路径边界由 IMAGE-001 测试覆盖。
- 7. Wrong vs Correct：错误做法是分别对解压总根执行 `rglob()` 并按路径排序取第一个；正确做法是先调用 `find_content_list()`，再把 `content_list_path.parent` 作为唯一搜索根传给正式 converter/layout/asset 链。
- 冲突/例外：此规则不读取 `full.md`；legacy JSON 只是输入兼容，不等于切换旧 runtime。仅有目录外 layout 时应按既有缺失 layout 安全降级，不得跨根补齐。
- 禁止：因单个 v2 字段处理失败而偷偷改用 legacy；按路径深度、绝对文件名、PDF 型号或排序第一项裁决多个结果根；在 layout 或图片调用点恢复解压总根 fallback。
- 样本证据：已提交 `ti-opamp-opa228-p1-smoke` 使用单根 `component_content_list_v2.json`；2026-08-21 external SN54/SC2167 正式重跑分别保持 38/24 个图片资产、19/29 张表且完整性阻断为空。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout` 与任务 `08-20-refine-word-generation-rules` R-06；取代 legacy-first 以及 content/layout/assets 跨结果根拼接行为。

### INPUT-002 MinerU 包边界与显式失败

- 状态：`enforced-tested`
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
- 样本证据：2026-08-20 使用 external SC2167 MinerU 包完成正式转换，34 个源物理页中的末页宣传页按本规则过滤，33 个内容页保留且 source→IR/DOCX 阻断标记为空；原包与生成物不纳入仓库。
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

### INPUT-005 空表续页占位符只按语义叶字段归一化

- 状态：`enforced-tested`
- 输入信号：MinerU table block 的 HTML、题注、脚注、明确正文叶字段，以及 `image_source.path="images/"`、`table_type`、`table_nest_level` 等结构元数据。
- 正式 owner：`app/services/document_ir/layout_signals.py::_is_mineru_empty_table_placeholder`、`::merge_table_placeholder_continuations`；保守判定复用 `app/conversion/docx_rules/mineru_content.py::is_empty_table_placeholder`。
- 预期输出：只有 HTML、题注、脚注和明确正文均为空，且资产标记满足既有空表证据的 table 才能在 source inventory 建立前并入上一真实表；通用 JSON 容器、schema 枚举、类型标签和资产路径不是正文证据。真实 HTML、题注、脚注或 `text`、`description` 等明确正文必须阻止合并。
- 冲突/例外：没有前置真实表的孤立空 table 不得静默删除；未被确定归一化的 table 继续由 IR-004/QUALITY-004 以 `source_ir_integrity:payload_missing:table` 失败关闭。
- 禁止：递归扫描整个 `content` 容器判断是否有正文；按 `simple_table`、任务 ID、页码或 PDF 型号写特例；放宽完整性门禁掩盖分类错误。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_merges_real_mineru_empty_table_continuations`、`.test_convert_zip_keeps_contentful_or_orphan_empty_tables_fail_closed`；nested 正例必须保留真实 MinerU v2 层级和结构元数据，负例必须证明明确正文及孤立空表不会被静默删除。
- 样本证据：线上任务 `docjob_cfcdfa737312` 的失败包为 external evidence，不提交用户原始 ZIP；2026-08-20 使用当前修复对该 ZIP 做只读临时回归，归一化后 420 个 source blocks、19 个 table、38 个图片资产且 blocker 为空，临时文件已删除；自动测试只保留脱敏最小结构。
- 来源/取代：任务 `08-20-fix-mineru-table-placeholder-regression`；补足只覆盖顶层简化字段、未覆盖 nested v2 结构元数据的历史测试缺口。

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
- 预期输出：DocumentIR metadata 记录归一化后的 source block 总数和按 source type 计数；每个主 block 通过既有 `metadata.source_type` 对账。`chart/image/figure` 必须生成带有效 `asset_ref` 的 `image`，table/formula/list 必须生成对应显式类型和必要 payload；源 title 可按 IR-005 的明确竞争角色降级，但可见文本不得丢失；确定性缺失以稳定 flag 失败关闭。
- 冲突/例外：旧 IR 没有 source inventory 时跳过无法证明的 source→IR 对账，但仍执行 IR→layout/DOCX 对账；旧 v2 IR 不反填不存在的语义证据；table context、TOC anchor 等合成辅助 block 不计为主 block；不新增第二套 MinerU JSON parser。
- 禁止：把 `chart` 降级为 paragraph；只记录 `unsupported_block_type` 后继续成功；用媒体文件数替代一个 image block 对应一个 drawing 的合同。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_maps_nested_v2_chart_to_image_and_records_source_inventory`、`.test_convert_zip_fails_closed_when_declared_formula_payload_is_missing`；`tests.test_document_ir_layout_contract.DocumentIRLayoutContractTests.test_v1_payload_defaults_layout_fields_to_empty`。
- 样本证据：CM4112 当前 external 样本对账为 196 个归一化 source blocks，其中 38 chart + 15 image → 53 image blocks/assets；最终 DOCX 为 53 drawings，阻断标记为空。完整记录见本任务 `research/cm4112-validation.md`。
- 来源/取代：任务 `08-18-fix-formal-word-structural-regressions`；补足 IR-001 与 IMAGE-001 未覆盖的跨边界完整性合同。

### IR-005 源块必须经过唯一语义裁决且内容优先保留

- 状态：`enforced-tested`
- 输入信号：MinerU source type、文本、页索引、bbox、物理页宽高、同文档重复文本、同页结构主体和明确 TOC 区域。
- 正式 owner：`app/services/document_ir/semantic_normalization.py::normalize_semantics`；机械 schema 映射与裁决落盘由 `app/services/document_ir/mineru_converter.py::MinerUToDocumentIRService._convert_blocks` 负责。
- 预期输出：每个新 converter 主块都携带唯一 `semantic_decision_reason`。`page_header/page_footer/page_number` 只作为候选：跨页重复且位置稳定的边缘行、通用日期/URL/页码标记或同页对齐的短顶带组可成为 decoration，并保留稳定原因；重复文本允许首页等少量异常位置，但只有落在稳定位置簇的实例才按重复装饰处理。大图/表格主导页中与主体相连且没有在普通页重复的技术标签、长文本、主体区域文本及其他歧义候选提升为 body；仅有装饰候选的源页也先裁决可靠重复行与明确页码，再把其余不确定文本提升为 body。MinerU bbox 与 layout.page_size 缩放不一致时，接近页底但未到常规阈值的候选只凭跨页重复或明确页码成为 decoration，孤立文本继续保全。歧义 body 记录 `semantic_decoration_ambiguous:*`，主体关系提升记录 `semantic_decoration_promoted:*`；不得把非阻断风险当作删除歧义文本的理由。`page_footnote` 成为可见 `page_note`。源 title 默认保留 heading，仅明确图表题、修订范围、局部分组标签或首物理页唯一的顶部宽幅文档身份降为对应 paragraph annotation；文档身份只保存最终整段文本和 `annotation_role=document_identity`，不缓存型号/品类拆分副本。普通 `text_level` 不得单独晋升 heading。
- 冲突/例外：`toc_source`、`filtered` 和真实 decoration 是显式非正文去向，不要求正文 payload，但必须保留裁决理由；合成 TOC anchor 不计 source 主块。真实 decoration 只作为语义与风险证据保留，最终 Word header/footer 由模板与配置拥有。
- 禁止：把 MinerU 物理坐标直接变成 Word 绝对定位；仅凭 `source_type=page_header` 删除正文；要求所有标题必须有章节号；按品牌、型号、页码或具体文本写特例。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_semantic_normalization_distinguishes_true_decorations_from_body_content`、`.test_repeated_margins_survive_first_page_outlier_and_decoration_only_pages`、`.test_semantic_normalization_resolves_title_page_note_and_explicit_toc_roles`；`tests.test_document_ir_heading_hierarchy.DocumentIRHeadingHierarchyTests.test_converter_marks_only_unique_top_wide_first_page_product_title`；`tests.test_document_ir_layout_contract.DocumentIRLayoutContractTests.test_source_integrity_accepts_explicit_toc_disposition_and_requires_complete_new_semantics`。
- 样本证据：2026-08-20 对 external `sn54ac244` MinerU 包只读临时回归：第 38 源页 8 个免责声明 `page_header` 候选全部提升为 body；常规页眉、页脚、页码仍保持 decoration；两条 revision range 降为 `group_label`。原包和临时 ZIP 不纳入仓库。
- 来源/取代：任务 `08-20-refine-word-generation-rules` 的 D5 与内容完整性裁决；取代 converter 直接信任 source role、所有 title 强制 heading 的行为。

### PAGE-001 模板绝对页面设置与源方向分工

- 状态：`implemented-gap`
- 输入信号：模板 page setup（纸张宽高、边距、装订线）和 DocumentIR page 宽高方向。
- 正式 owner：`app/services/renderer/word_renderer.py::resolve_template_config`、`::_apply_template_page_size_defaults`、`::_apply_page_setup`、`::_apply_page_setup_to_section`、`::_configure_layout_page_section`、`::_layout_page_requires_landscape`。
- 预期输出：显式 layout config 决定 Word 的绝对纸张尺寸和边距；未显式配置纸张尺寸时，以清空正文后仍保留的模板末节宽高补齐最终 `TemplateConfigPackage`，供正式 worker、本地转换、LayoutPlan、renderer 和 evidence 共用；模板也没有可用尺寸时才使用产品 A4 默认。源页只决定 portrait/landscape，宽表本身不改变方向，源页宽大于高时才使用横向节。
- 冲突/例外：模板 section 宽高按短边/长边归一为 portrait 基准，最终方向仍由 DocumentIR 页面决定；本规则只补齐纸张尺寸，不把 PDF/MinerU 物理数值或模板方向当成最终 Word 方向。方向变化按 PAGE-002 分节。
- 禁止：用 MinerU/PDF 物理数值直接重写 Word 纸张；见到宽表就横向；忽略显式源页方向。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_template_page_size_defaults_feed_layout_plan_and_renderer`、`.test_render_to_bytes_uses_configured_page_size_and_header_bold_flag`、`.test_render_to_bytes_preserves_portrait_section_for_wide_table_page`、`.test_render_to_bytes_keeps_source_landscape_page_landscape`。
- 样本证据：18×25 cm 合成非 A4 模板证明最终 section 与表格 `available_width` 共用模板尺寸；当前 `sn54ac244`、`SC2167` 配置均显式 A4，因此本修复不改变两个真样本输出，也不新增客户端不确定性。
- 来源/取代：commit `32edca58` parity 审计、归档任务 `08-18-fix-mineru-first-page-layout` 和当前任务 R-09；取代 v2 缺少显式 page size 时无条件回退 A4 的行为。

### PAGE-002 仅页面组方向变化创建新页分节

- 状态：`enforced-tested`
- 输入信号：LayoutPlan 完成软页面分组后，相邻页面组的 portrait/landscape 状态。
- 正式 owner：`app/services/renderer/word_renderer.py::DocumentIRWordRenderer.render_to_bytes`、`::_configure_layout_page_section`。
- 预期输出：方向变化时创建 `WD_SECTION_START.NEW_PAGE` 并应用目标方向；相同方向不因源物理页边界创建页面节，也不附加段落 `pageBreakBefore`。目录语义起页由 FLOW-002 另行处理。
- 冲突/例外：双栏区域内部使用 continuous section，由 COL-002 约束；同方向页面组的软分页不得升级为 section。
- 禁止：每个 MinerU page 都新增 `NEW_PAGE`；用 break-only 段落模拟方向节。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_starts_new_section_when_page_orientation_changes`、`.test_render_to_bytes_does_not_force_break_between_same_orientation_source_pages`。
- 样本证据：CM4112 为 external evidence；没有 committed 纵横向混合真样本。
- 来源/取代：commit `5d4a02d7` 删除逐源页硬分页；commit `674ce937` 保留方向分节。

### FLOW-001 同方向源页保留出处并自然续排

- 状态：`enforced-tested`
- 输入信号：相邻同方向源页、两侧最终阅读顺序、明确 table continuation、同一 `content_group_id`、页边缘 list 续接、decoration-only 页，以及因内容保全提升为正文且仍位于源页底边的页脚候选。
- 正式 owner：`app/services/renderer/layout_plan.py::_build_soft_page_groups`、`::_continuation_reason`。
- 预期输出：存在明确续接证据时合并为一个 LayoutPage 页面组，并在 `continuation_reasons` 保存稳定原因；没有续接证据的新源页仍形成新页面组并保留 `source_page_indices`，但普通组边界不强制分页。`break_reason=source_page_boundary` 只描述源页出处，不表示 Word 分页命令；显式 `toc_title` 位于新源页首块时另标记 `toc_start`。Word 页数由客户端按模板与内容流决定。
- 冲突/例外：方向变化由 PAGE-002 创建 `NEW_PAGE` section；已识别 decoration-only 的源页可并入相邻页面组。只有同时具有 `decoration_candidate_promoted_to_body`、页脚源角色和源页底边位置证据的保全块才可证明同一源页面组；没有可见 body 且不能证明为 decoration-only 的页面仍须在完整性证据中保留不确定性。
- 禁止：把同方向当作语义续接证据；恢复“一页 PDF 一个 Word 硬分页”；按图号、标题文字、型号或页码建立分页特例。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_does_not_force_break_between_same_orientation_source_pages`、`.test_render_to_bytes_flows_across_source_pages_without_forced_breaks`、`.test_toc_title_at_source_page_start_uses_inline_break_without_empty_page_marker`、`.test_soft_page_group_keeps_source_provenance_and_explicit_continuation_reason`、`.test_paired_figures_flow_after_two_columns_regardless_of_caption_reference`、`.test_soft_page_group_continues_after_promoted_page_edge_footer`。
- 样本证据：2026-08-20 external SC2167 既有候选形成 32 个软页面组，WPS 为 36 页；2026-08-21 external SN54AC244 既有定向修复把首页末尾声明与目录保留在同一 WPS 第 2 页。2026-09-21 external CM1348 原 PDF 37 页，旧 v8 WPS 58 页且 22 页正文底部空白超过 40%；v10 WPS 为 32 页、仅 1 页超过该阈值，目录从第 2 页开始。v11 与 v10 全部 DOCX ZIP member 内容一致，图 11/12 后的空白仍未关闭。完整视觉签字仍缺失。
- 来源/取代：commit `5d4a02d7`；取代旧逐物理页分页行为。

### FLOW-002 普通源页边界自然续排，目录语义起页与栏切换使用真实内容锚点

- 状态：`enforced-tested`
- 输入信号：FLOW-001 未合并的同方向源页面组、组首块是否有显式 `toc_title` annotation，以及该组完成 one-col/two-col/paired row 规划后的最终左栏→右栏顺序。
- 正式 owner：`app/services/renderer/layout_plan.py::_build_soft_page_groups`；消费 owner 为 `app/services/renderer/word_renderer.py::_render_layout_page`、`::_render_layout_region`、`::_render_block`。
- 预期输出：普通同方向新页面组的 `break_before_block_id` 为空，不向首块写入 `pageBreakBefore`；显式 `toc_title` 是新源页首块时，记录 `toc_start` 并在同一标题段落首 run 中写原生 page break。WPS 对目录标题的 `pageBreakBefore` 属性曾在前置 continuous section 后多造空白页，内联 break 的本地诊断可从第 2 页起目录而不多造该页。方向变化只由 `NEW_PAGE` section 承载；若 renderer 已在当前边界创建该新页分节，须消费 `toc_start` 起页意图，不再写第二个 page break。双栏 column break 仍附着于右栏第一个真实内容块，不生成 break-only 空段落。
- 冲突/例外：目录标题不在新源页首块时不强制起页；前页宽表降级为 `landscape_table` 再恢复纵向目录时，方向恢复分节优先，禁止叠加目录起页。Word 客户端可因 widow/orphan、keep-with-next 和内容高度调整最终页数。源 PDF 物理页边界本身不是 Word 的语义分页指令。
- 禁止：仅凭 MinerU 源页索引为普通 paragraph、image 或 table 设置 `pageBreakBefore`；按标题文字识别目录；创建只含 page/column break 的空段落。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_flows_across_source_pages_without_forced_breaks`、`.test_toc_title_at_source_page_start_uses_inline_break_without_empty_page_marker`、`.test_toc_title_does_not_double_break_after_landscape_table_fallback`、`.test_soft_page_group_keeps_source_provenance_and_explicit_continuation_reason`。
- 样本证据：CM1348 v8 的 29 个源页分页属性会在 WPS 生成大量无法通过删除空格消除的空白；v10 去除这些属性并把显式目录起页改为内联 break 后，WPS 为 32 页且目录始于第 2 页。v11 增加横向表格恢复纵向时的双重起页抑制，CM1348 的 DOCX ZIP member 与 v10 全同，该分支仅有合成回归验证。尚未提交整文档视觉 fixture。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；补充 FLOW-001 而非恢复逐页硬分页。

### FLOW-003 内容组保持与表格跨页

- 状态：`implemented-gap`
- 输入信号：heading、表题/表格/表注、长表行和连续表格 placeholder。
- 正式 owner：`app/services/renderer/word_renderer.py::_render_block`；`app/services/renderer/table_renderer.py::_render_table_captions`、`::_configure_data_table_rows`；`app/services/document_ir/layout_signals.py::merge_table_placeholder_continuations`；续页页面组由 `app/services/renderer/layout_plan.py::_continuation_reason` 消费。
- 预期输出：heading/table caption 使用 `keep_with_next`；表头可重复，表格行使用 `cantSplit`；空 table placeholder 只并入前一真实表格，不另渲染重复空表。
- 冲突/例外：`DocumentIRBlockLayout.continuation_heights` 只证明相邻源页属于同一长表内容组，用于抑制组间软分页；具体高度仍不参与 Word 表格尺寸或分页计算，最终分页由客户端决定。
- 禁止：把整张长表放进不可跨页容器；因 placeholder 创建第二张空表；把“有 continuation 元数据”写成“已验证不挤压”。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_merges_table_placeholder_continuation_and_landscape_orientation`、`.test_convert_zip_merges_real_mineru_empty_table_continuations`；`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_html_table_spans_and_annotations`。
- 样本证据：SC2167、CM4112 第 3/4 页表格均为 external evidence；没有自动排版后的表格挤压/分页断言。
- 来源/取代：两个 08-18 归档任务；明确降级“续表已解决”的历史结论。

## 4. 分栏、文本、表格与图片

### COL-001 双栏成员按纵向覆盖和明确栏归属规划

- 状态：`enforced-tested`
- 输入信号：同一页 body block 的 bbox、page width/page height、显式 `column_hint`、实际纵向重叠和 wide block。
- 正式 owner：`app/services/renderer/layout_plan.py::_build_regions`、`::_is_two_col_member`、`::_extend_same_column_membership`、`::_finalize_region`、`::_extract_short_visual_preludes`。
- 预期输出：先确定可信左右栏 band 和 wide barrier；left/right block 只要与 band 有实际纵向覆盖即保留栏归属，高表格不因中心点落在 band 外或另一栏局部空白而提升为 wide。与可信 band 短距离连续且不跨 wide barrier 的同侧尾块可留在双栏。最终 two-col region 必须同时含左右栏并写入 `column_break_index`，否则安全降级为单栏并记录 reason。仅由普通文本组成、高度低于源页边缘阈值且紧邻后续 wide 图片的短双栏前导可降级为 `visual_prelude` 单栏连续组，避免 continuous section 把标签与视觉主体拆页；该 reason 必须进入 renderer evidence。
- 冲突/例外：严格成对图片行由 COL-003 例外渲染；缺页面宽度或高度时不猜短视觉前导，保留既有安全路径。具有表格、图片、题注角色或实质高度的双栏内容不得使用该降级。
- 禁止：用单块 bbox 中点决定其是否属于双栏；让 renderer 再次按 bbox 重判栏位；因表格高度、列数或另一栏空白把明确右栏表格提升为全宽。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_build_layout_plan_separates_decorations_and_two_column_regions`、`.test_build_layout_plan_prefers_column_hint_for_stable_non_overlapping_regions`、`.test_build_layout_plan_keeps_explicit_wide_blocks_out_of_stable_two_column_regions`、`.test_build_layout_plan_keeps_single_column_gap_between_real_two_column_bands`、`.test_layout_merges_single_side_tail_before_paired_images_into_one_column_flow`、`.test_layout_keeps_tall_right_column_table_in_its_column`、`.test_short_two_column_visual_prelude_degrades_to_kept_single_column_flow`。
- 样本证据：OPA228 P1/P2 manifest 声明双栏焦点但当前 Golden 未实际运行；CM4112 当前 external 样本首页单侧栏尾已并入前一双栏区域，LibreOffice/WPS 均观察到概述与引脚图可见。2026-08-21 external SN54AC244 的短机械图标签前导在 WPS 与主体图片同页，首页实质双栏和右栏表格仍保持原生双栏；客户端栏平衡仍归 QUALITY-003 人工判断。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；取代全页宽松双栏判定。

### COL-002 LayoutPlan 固定阅读顺序，renderer 只执行 Word 原生栏

- 状态：`enforced-tested`
- 输入信号：layout plan 已按左栏自上而下、右栏自上而下排列且携带有效 `column_break_index` 的 `two_col` region。
- 正式 owner：计划 owner 为 `app/services/renderer/layout_plan.py::_finalize_region`；消费 owner 为 `app/services/renderer/word_renderer.py::_render_layout_region`、`::_set_section_columns`。
- 预期输出：只在真实 two-col region 前后用 continuous section 进入和恢复栏数；column break 附着于右栏首个真实内容。单侧 region 预先降级，不创建没有右栏内容的无意义 section；普通双栏正文不使用布局表格。bundled 默认模板直接声明 `w:cols/@w:space=720` twips；进入多栏时，其他模板继承的空值或零栏距也改为 720，已有正栏距保持不变，栏宽计算使用最终值。
- 冲突/例外：COL-003 的严格图片对不进入 columns section；continuous section 的实际栏平衡需要 Word/WPS 视觉验收。
- 禁止：renderer 使用 bbox/页面中线兜底重判左右栏；按全局 y 交错左右栏；用空段落承载 column break；用 1×2 表格包装普通正文。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_native_columns_for_v2_region`、`.test_two_column_section_replaces_zero_template_gutter_only`、`.test_render_to_bytes_prefers_column_hint_when_ordering_native_columns`、`.test_render_to_bytes_keeps_continuous_restore_when_wide_content_follows_columns`。
- 样本证据：2026-08-20 external SC2167 当前候选包含 2 个原生 `two_col` region，WPS 首页确认双栏阅读与后续全宽模块图正常；没有 committed 视觉回归。
- 来源/取代：commit `5d4a02d7` 与 `32edca58`；取代布局表格模拟普通栏。

### COL-003 严格成对图片行使用有标记的无边框布局表格

- 状态：`enforced-tested`
- 输入信号：同一可信纵向带中数量相等、bbox 实际重叠、每侧只有 image 且 annotation 唯一可归属的 left/right blocks。
- 正式 owner：计划 owner 为 `app/services/renderer/layout_plan.py::_paired_visual_rows`；消费 owner 为 `app/services/renderer/image_renderer.py::_render_paired_visual_row`；计数 owner 为 `app/services/renderer/docx_quality.py::_is_paired_visual_table`。
- 预期输出：LayoutPlan 输出独立 `paired_visual_row` region；renderer 用无边框原生 1×2 Word table，每个单元格独立承载图片及自己的 caption/footnote。整行 `cantSplit` 负责保持图和题注；单元格段落须显式关闭 `keepNext`，覆盖模板样式继承，避免 WPS 把连续成对图片行当成不可分页的大组。布局表写入 `w:tblDescription="md2word:paired_visual_row"`，analyzer 计入 `layout_table_count` 并从语义 `table_count` 排除。
- 冲突/例外：多 annotation 或无法严格成对的图片留在 COL-002 原生栏中。
- 禁止：把任意两张图、普通正文、文本卡片或宽表强行配对；合并/错配题注；使用同段落 25%/75% 制表位模拟独立图片容器。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_keeps_paired_image_caption_fields_in_row_order`、`.test_render_to_bytes_keeps_multi_annotation_images_in_native_columns`。
- 样本证据：2026-08-20 external SC2167 既有候选包含 4 个 `paired_visual_row`，结构证据均为带标记的无边框布局表，LibreOffice 辅助渲染未发现题注串列。2026-09-21 external CM1348 对照原 PDF 的图 9–14 行：v11 WPS 第 9 页只到图 11/12；去除成对图片单元格 `keepNext` 的消融、v12 和模板继承修订后的 v13 均使图 13–18 填入第 9 页，且 WPS 总页数仍为 32。其他页仍需视觉复核，当前 committed fixture 不含真实图片。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption`。

### TEXT-001 原生标题语义与内容组保持

- 状态：`enforced-tested`
- 输入信号：IR schema version、显式 IR heading、MinerU 顶层或 v2 `content.level`、标题最终文本、v1 heading-like paragraph、配置的 heading/`part_number`/`category` Word style 和层级。
- 正式 owner：标题层级与文档身份结构由 `app/conversion/docx_rules/text_semantics.py::infer_heading_level`、`::resolve_source_heading_level`、`::split_document_identity` 和 `app/services/document_ir/semantic_normalization.py::normalize_semantics` 唯一裁决；`app/services/renderer/word_renderer.py::_render_block` 与 `app/services/renderer/text_renderer.py::_fill_heading_paragraph` 只消费最终裁决。
- 预期输出：显式 heading 使用 Word heading 样式并 `keep_with_next`。编号标题按编号深度生成 H1/H2/H3，超过模板能力时限制为 H3；`chapter/section/part/附录/appendix` 保持 H1；未编号 source title 优先保留 MinerU 显式层级，缺失时使用通用 H2。首物理页唯一的顶部宽幅产品标题不进入 Heading/TOC，而是在渲染时根据翻译后的最终 `block.text` 拆成两个 Word 原生段落，分别使用 `part_number` 与 `category` 样式；第一段只与第二段 `keep_with_next`。`document-ir/v2` 普通 paragraph 不根据文本升级 heading，`document-ir/v1` 顺序兼容才允许可靠 heading-like 推断。
- 冲突/例外：源物理页边界不触发 FLOW-002 的强制分页；v1 推断得到的 heading-like paragraph 不设置 `keep_with_next`。身份候选必须同时满足首物理页、唯一、顶部、宽幅和通用产品标题结构；任一证据缺失时仍按 D5 保留 source heading。翻译后最终文本无法再次拆分时显式失败，不回退成普通段落或 Heading。v2 只消费 converter 明确产生的 heading、TOC/身份 annotation 和 list，不再从普通点线 paragraph 重新推断 TOC。
- 禁止：只加粗/放大而不使用标题语义；所有短句均升级；按“工作原理”等具体标题硬编码。
- 自动验证：`tests.test_document_ir_heading_hierarchy` 覆盖编号/无编号层级、首页身份正负例、翻译后动态拆分、专用样式、TOC/evidence 对账和失败关闭；既有回归为 `tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics`、`.test_render_to_bytes_keeps_v1_heading_like_paragraph_compatibility`、`.test_render_to_bytes_uses_explicit_v2_semantics_without_heading_guessing`、`.test_render_to_bytes_uses_configured_heading_word_style_when_available`；图/表反例见 `tests.test_text_render_characterization.TextRenderingCharacterizationTests.test_looks_like_heading_text_rejects_english_sentence`。
- 样本证据：2026-08-21 external SN54 R-04 候选为 32/32 Heading，层级分布 H1/H2/H3=11/19/2，首页身份两段可见 payload 与 TOC cache 对账通过且 `blocking_quality_flags=[]`；WPS 首页确认 `part_number/category` 两段样式，正文抽查确认 `5`/`5.1`/`8.2.1` 分别为 Heading 1/2/3，完整品类名称只在首页出现一次。SC2167 候选为首页身份 1 个、其余 51 个无编号 Heading 均保留 source level 2，WPS 首页样式和“产品概况”Heading 2 通过，`blocking_quality_flags=[]`。
- 来源/取代：commit `32edca58` 正式 renderer 语义化。

### TEXT-002 列表必须使用原生编号且保留续行

- 状态：`enforced-tested`
- 输入信号：IR list block、普通 paragraph 中可靠的 bullet marker，或同页源顺序相邻且序号严格连续的至少两个十进制 marker；item level 和换行由 INPUT-004 产生。
- 正式 owner：十进制 marker 解析由 `app/conversion/docx_rules/text_semantics.py::parse_decimal_list_marker` 唯一负责，文档级连续序列由 `app/services/document_ir/semantic_normalization.py::_mark_decimal_list_runs` 裁决；渲染由 `app/services/renderer/text_renderer.py::_fill_list_paragraph`、`::_fill_auto_list_or_paragraph`、`::_apply_bullet_numbering`、`::_apply_decimal_numbering` 负责。
- 预期输出：列表项使用 Word `numPr` 原生 bullet/decimal numbering，不保留手写 marker；decimal 序列按源起始值和中断重启编号，并用原生 `w:suff=space` 分隔编号与正文；同一 item 的续行内容不丢失。
- 冲突/例外：负数、负温度和普通破折号句不判为列表；孤立十进制 marker 保留原 heading/paragraph 语义；ASCII `.` 后直接跟数字属于小数而不是列表 marker，`1. text`、`1.中文`、`1.$...$` 及中文 `．/、` marker 仍可解析；v2 explicit list 优先于文本推断。
- 禁止：用“• ”等字符模拟列表；全局拆分所有换行；为满足 analyzer 删除可见 marker 却不写 numbering。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics`、`.test_render_to_bytes_promotes_bullet_like_paragraphs_to_word_lists`、`.test_render_to_bytes_uses_native_decimal_numbering_and_restarts_sequences`、`.test_render_to_bytes_keeps_decimal_values_inside_explicit_list_items`；converter 测试见 `tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_semantic_normalization_promotes_only_continuous_decimal_sequences_to_lists`、`.test_decimal_list_marker_distinguishes_markers_from_decimal_values` 及 INPUT-004。
- 样本证据：2026-08-20 external SC2167 当前候选把产品特色和故障清除步骤等 19 个连续数字项渲染为原生 decimal numbering；WPS 36 页重验确认编号后有可见空格且描述图题保持正文。OPA228 最小 fixture 仍未断言原生编号。
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
- 正式 owner：通用分组由 `app/services/document_ir/mineru_converter.py::MinerUToDocumentIRService._captions` 负责；mixed visual run 的局部试算由 `::_reassociation_caption_candidates` 负责。现有文本/公式清理 helper 只作为片段归一化依赖。
- 预期输出：一个 flat `text/equation_inline/text` 节点数组形成一个完整 `DocumentIRBlock.captions` 元素，进入 Word 后只占一个题注段落；string list 和多个 nested rich groups 继续形成多条独立题注。inline equation 保留 `$...$` 数学边界，供翻译分段和 OMML 共用；可见 inline 语义、SEQ/bookmark、fallback、table context 和 COL-003 annotation 数量判断均基于完整逻辑题注。
- 冲突/例外：footnote 继续按现有 marker/连续性规则合并。IMAGE-002 已识别含稀疏 table 的 mixed visual run 时，可把 flat rich nodes 中第二个明确编号 Figure/图 text node 作为候选边界；只有整组题注数量、label、编号唯一连续全部成立后才提交分界和类型归一化。IMAGE-003 的真实表格错挂图题恢复可以试算唯一显式 Figure→Table text node 边界，但只有同页唯一主体及前后连续图号均成立才提交，内联公式留在所属片段。其他证据不足的输入保持原分组并提示复核。renderer 继续坚持“一 caption 元素一段落”。
- 禁止：全局按图号、标点、页码或 bbox 拆 flat rich caption；用 `collect_text_from_fields()` 把 flat rich nodes 直接拍成多条 captions；在 image/table renderer 合并相邻题注；修改 continuous section 或 `pageBreakBefore` 掩盖孤立题注行。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_maps_nested_v2_chart_to_image_and_records_source_inventory`、`.test_convert_zip_preserves_multiple_logical_caption_groups`、`.test_rich_chart_captions_render_without_isolated_fragments_and_keep_paired_layout`、`.test_convert_zip_keeps_flat_rich_caption_group_for_plain_charts`、`.test_convert_zip_normalizes_sparse_visual_tables_after_strict_caption_reassociation`、`.test_convert_zip_demotes_table_condition_caption_to_context_paragraph`。
- 样本证据：CM4112 的图 33 在 IR 中为保留数学边界的单条题注，Word 可见结果仍为完整 `图 33 通道隔离度 (± 18V)`，OOXML 不含仅为 `±`/`18V)` 的段落；既有 WPS GUI 第 12 页实际包含图 31～33 及完整题注，第 13 页直接以“工作原理”起页。该 GUI 记录早于本轮数学边界调整，不能替代当前整文档复验。完整历史见当前任务 `research/cm4112-validation.md`。
- 来源/取代：当前任务新增目标；取代把富文本 inline node 数量当作 annotation 数量的行为。

### TEXT-005 可选翻译覆盖全部可见 annotation 且不发送公式片段

- 状态：`enforced-tested`
- 输入信号：DocumentIR paragraph/heading text、list items、table HTML 文本节点、captions、footnotes，以及其中 `$...$` 或 `\(...\)` 明确 inline math。
- 正式 owner：`app/domains/translation/document_ir_translator.py::DocumentIRTranslationService`；分段 owner 为 `app/conversion/docx_rules/text_semantics.py::split_mixed_math_segments`。
- 预期输出：翻译 target 按 block id、字段、index 和必要的 segment index 唯一定位；caption/footnote 与正文、列表、table cell 一起翻译。provider 只收到普通文本段，应用替换时按原顺序恢复未修改的数学片段；block/page/layout/asset/公式字段和 annotation 数量不变。
- 冲突/例外：旧的无数学边界字符串只能作为普通文本处理，不能靠猜测重建公式；只含公式的字段不会产生 provider item。术语匹配和 batch 切分继续基于实际发送的普通文本 item。
- 禁止：把整个 DocumentIR 或结构 JSON 交给 provider；翻译/改写 `$...$`、`\(...\)`；漏掉 captions/footnotes 形成中英混排；按文本内容而非稳定 target 回写。
- 自动验证：`tests.test_document_ir_translation.DocumentIRTranslationTests.test_document_ir_translation_rewrites_text_nodes_without_touching_structure_or_assets`、`.test_translation_covers_captions_and_footnotes_without_sending_inline_math`、`.test_document_ir_translation_batches_provider_requests_and_preserves_order`。
- 样本证据：当前只有合成 DocumentIR 自动测试；尚无启用翻译的 Word/WPS 真样本验收。
- 来源/取代：任务 `08-20-refine-word-generation-rules`；补齐可见题注/表注未翻译及公式被 provider 改写的缺口。

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

### TABLE-003 表头、行跨页、边框、内容适配和容器降级

- 状态：`enforced-tested`
- 输入信号：翻译和术语替换后的最终 IR/HTML、HTML cell 宽度提示、源 table bbox/所属栏、Word 容器宽度、`table_content.font_size` 首选字号和可选 `min_font_size`。
- 正式 owner：`app/services/renderer/layout_plan.py`、`app/services/renderer/table_layout.py`、`app/services/renderer/table_renderer.py`、`app/conversion/runtime/table_html_parser.py`。
- 预期输出：表头行标记 `tblHeader`，所有行标记 `cantSplit`；列宽由最终 cell 内容、不可断片段和 HTML 相对宽度提示分配。先在既定栏内选择不低于最小字号的最大可适配字号；缺少 `min_font_size` 表示不得隐式缩字。最小字号仍不可读时，按“当前栏→受控单栏全宽→横向”逐级安全降级，并在 LayoutPlan/evidence 记录稳定 reason 和非阻断 quality flag；绑定的 `table_context` 必须与表格整组迁移。应用配置边框与表头样式，题注和表注不随表体缩字。
- 冲突/例外：字符宽度算法是无客户端依赖的保守估算，不承诺 Word/WPS 精确换行；`autofit=False` 不等于客户端不会重新分页或挤压。`source_width_ratio` 只记录源表在源栏/页面中的 bbox 占比证据，不证明单元格列宽，当前明确不参与 fit 或 Word 列宽计算。
- 禁止：按 6/7/8 等列数硬压 8pt/7pt 或等宽；把 bbox 绝对坐标映射为 Word 列宽；绕过 LayoutPlan 在 renderer 再次提升表格容器；把 `cantSplit` 写成“表格不会挤压”的证明；为一个器件硬编码列宽。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_html_table_spans_and_annotations`、`.test_render_to_bytes_styles_later_th_cells_as_table_headers`、`.test_datasheet_five_column_table_widths_prioritize_description_column`、`.test_short_six_column_table_keeps_preferred_font_size`、`.test_table_fit_uses_bundled_minimum_to_keep_right_column_membership`、`.test_table_fit_without_minimum_moves_bound_context_and_table_to_full_width`、`.test_landscape_fallback_moves_single_column_context_with_table`、`.test_two_column_landscape_fallback_keeps_context_bound_and_records_each_step`。
- 样本证据：OPA228 P6/P7 与 CM4112 均缺当前排版后的自动/人工闭环。
- 来源/取代：任务 `08-20-refine-word-generation-rules`；取代按列数固定缩字/等宽策略，仍明确不继承 legacy 页高估算器。

### TABLE-004 无效表格输入不得重复题注或静默伪装

- 状态：`enforced-tested`
- 输入信号：显式或由字段推断得到的 table block、缺失/空白/无法由正式 parser 得到行列结构的 table HTML、`block.text`、captions。
- 正式 owner：`app/conversion/runtime/table_html_parser.py::parse_html_table` 是唯一结构判定；`app/services/document_ir/integrity.py::build_source_integrity` 负责 source→IR 阻断；`app/services/renderer/table_renderer.py::_render_table` 负责无效表格的可见诊断降级；`app/services/renderer/evidence.py::build_renderer_evidence` 与 `::ensure_renderer_integrity` 负责 IR→DOCX 发布阻断。
- 预期输出：正式 converter 产物中的 table 必须解析为具有行列结构的可编辑表体，否则写入 `source_ir_integrity:payload_missing:table` 并停止发布。没有 source inventory 的旧 IR 可保留唯一题注和与题注不同的诊断 fallback，但不得生成伪表格；由于实际 semantic table 数不足，必须以 `ir_docx_integrity:table_count_mismatch` 停止发布。与已渲染题注相同的 `block.text` 不得重复输出。
- 冲突/例外：结构有效但单元格内容为空的 HTML 是合法表格；正式 parser 能恢复出真实行列结构的宽松 HTML 仍按合法表格处理。与 captions 不同的真实 fallback 应保持可见，但不能作为表体成功证据。
- 禁止：仅凭 HTML 非空认定存在表体；先渲染 captions 再无条件渲染相同 `block.text`；用 fallback paragraph 冒充 semantic table；在调用方引入第二套表格 parser 或绕过发布门禁。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_rejects_nonempty_html_without_a_table_body`、`.test_convert_zip_accepts_structural_table_with_empty_cells`；`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_invalid_table_body_deduplicates_caption_but_keeps_distinct_fallback`。
- 样本证据：R-04 正式 SN54 与 SC2167 回归分别有 19/19、29/29 个合法表格通过新 source gate，`blocking_quality_flags=[]`；R-05 只改变无效输入失败路径，不需要 Word/WPS 视觉验收。
- 来源/取代：任务 `08-20-refine-word-generation-rules` R-05；取代“HTML 非空即视为表体”和无效表格重复题注的行为。

### IMAGE-001 图片资产绑定、显示宽度和可见失败

- 状态：`implemented-gap`
- 输入信号：INPUT-001 绑定的唯一结果根、MinerU 原始资产路径、IR image asset_id、bbox/page width/page height、当前栏宽和 captions。
- 正式 owner：结果根由 `app/services/document_ir/mineru_package.py::find_content_list` 和 `MinerUToDocumentIRService.convert_zip` 确定；资产绑定由 `app/services/document_ir/mineru_converter.py::_resolve_image_path`；渲染由 `app/services/renderer/image_renderer.py::_render_image`、`::_available_width`、`::_available_height`、`::_image_fallback_text`。
- 预期输出：先接受绑定根内不含空段、`.`、`..` 的精确相对路径；精确路径不存在时，只允许在该根内 basename 唯一命中。零命中、越界、跨根或多命中不得返回资产，并由 source→IR 完整性门禁阻断。renderer 使用已绑定的原图片字节，以 bbox/page 的相对宽度和相对高度作为双重上限约束在当前栏/页面内；高度超限时只等比缩小，不放大或拉伸，写入 `w:doNotAutoCompressPictures` 并保留题注。
- 冲突/例外：精确相对路径优先于同根其他重名 basename；唯一 basename fallback 仅用于源路径缺少目录信息的既有 MinerU 输入。不承诺放大小图到历史最小宽度，Word 显示清晰度仍取决于原图像素和客户端；损坏图片的最终可见 fallback 仍缺直接正式测试。
- 禁止：在解压总根或其他结果根搜索；basename 多命中时按排序取第一项；允许 `..` 越界；静默丢图；无条件拉伸到全栏；按样本设置固定厘米宽度。
- 自动验证：converter 的 `test_convert_zip_binds_layout_and_assets_to_content_list_result_root`、`test_convert_zip_rejects_cross_root_or_ambiguous_basename_assets`、`test_convert_zip_prefers_exact_asset_path_and_limits_basename_fallback_to_one_match`；renderer 的 `tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_bbox_width_for_images_and_annotations`、`.test_render_to_bytes_caps_normal_and_paired_images_by_source_relative_height`。
- 样本证据：2026-08-20 external SC2167 当前候选完成 24/24 drawing asset identity/checksum 对账，WPS 关键页图片可见；仍缺真实像素/DPI 的 committed fixture 和逐图清晰度门禁。
- 来源/取代：commit `5d4a02d7` 与任务 `08-20-refine-word-generation-rules` R-06；取代 legacy 固定最小宽度及跨根/basename 首项绑定策略。

### IMAGE-002 编号图片题注只做严格重关联

- 状态：`enforced-tested`
- 输入信号：同页连续 image group 的题注数量失衡；或连续 mixed visual run 同时包含 image/chart 与严格水平对齐的稀疏 table pair。稀疏 table 必须有结果根内有效图片资产、可解析的单行且不超过三列 HTML、至少一个明确编号 Figure/图题注，并且不属于 IMAGE-004 表图复合或未决 overlap。
- 正式 owner：`app/services/document_ir/mineru_converter.py::_reassociate_numbered_image_captions`、`::_sparse_visual_table_indices`、`::_reassociate_image_group`；HTML 结构继续复用 `app/conversion/runtime/table_html_parser.py::parse_html_table`。
- 预期输出：只有整组题注数量等于视觉块数、label 相同、编号唯一且连续时，才按编号重分配题注，并把已证明误标的稀疏 table 转为 chart/image 语义和资产；普通 image group 的 flat rich caption 仍受 TEXT-004 约束。任一条件不足时不提交试算结果。
- 冲突/例外：未对齐、数量不足、label 不一致、编号重复/不连续、真实单行表或主体不唯一时保持原类型和题注分组；Figure-on-table 无唯一主体路径写入 `caption_owner_unresolved` 并进入非阻断人工复核。此规则不通过视觉最近邻猜关联；多 annotation 渲染仍由 COL-002/IMAGE-001 保持。
- 禁止：只凭 `simple_table`、`image_source`、单行 HTML 或 Figure 题注任一单条件把 table 转图片；只按出现顺序重排题注；在纯 image/chart group 拆 flat rich caption；跨页关联；丢弃无法识别的原题注。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_reassociates_only_strict_numbered_image_groups`、`.test_convert_zip_normalizes_sparse_visual_tables_after_strict_caption_reassociation`、`.test_convert_zip_does_not_normalize_unaligned_sparse_visual_tables`、`.test_convert_zip_keeps_real_single_row_table_with_image_source`、`.test_convert_zip_keeps_flat_rich_caption_group_for_plain_charts`。
- 样本证据：2026-08-27 external CM4226 的同页三图被 MinerU 输出为 `table/table/chart`，且第三块 flat rich caption 同时包含图 19/21。当前规则恢复为三个 image asset 和图 19/20/21 独立题注；正式本地 source→IR、IR→DOCX 门禁为空，WPS 确认图 19/20 并排、图 21 位于下方且无重叠。SC2167 继续作为 historical evidence。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption/research/caption-reassociation.md`。

### IMAGE-003 跨类型与共享图题只绑定唯一图片主体组

- 状态：`enforced-tested`
- 输入信号：同一源页内明确的 Figure 题注被挂到后续非图片 block，或严格对齐图片对中只有一个标题型 annotation；同时存在可由源顺序、纵向先后、水平覆盖或 IMAGE-004 已确定的唯一表图包含关系证明的视觉主体组。
- 正式 owner：`app/services/document_ir/mineru_converter.py::_recover_displaced_figure_captions`、`::_reassociate_visual_group_captions`、`::_bind_group_caption`；人工复核 owner 为 `app/services/document_ir/integrity.py::build_source_review_issues`。
- 预期输出：先完成 IMAGE-004 的唯一表图包含关系裁决，再重关联图题。普通图片组共享同一 `content_group_id`；已确定的表图复合组以 image 与 table 共同作为 subject。题注统一成为一个带 `subject_block_ids` 的 `standalone_caption`，原错误 annotation 清空且最终只可见一次；满足 COL-003 严格条件的双图继续使用成对视觉行，题注位于布局表外。
- 冲突/例外：真实多行多列表格不因 Figure 题注转为图片。同页唯一无题注图片、唯一错挂图题、前后图片同 label 连续编号且页内无重复编号、有效 bbox/资产、无已确定复合组时，可跨栏恢复独立图题，保留真实表格、表题、脚注与公式并记录 `caption_reassociated` 供复核。主体不唯一时保留源解析内容和原题注位置，写入 `caption_owner_unresolved`；只要内容完整便生成可下载 Word 和源页复核提示，不把不确定归属宣告成功。
- 禁止：按品牌、型号、页码、固定题注全文或任意最近邻猜测主体；跨页关联；复制题注到每张图片。
- 自动验证：`tests.test_document_ir_mineru_converter_layout` 的跨类型 Figure 题注、共享双图题注、包含表图复合题注、跨栏连续图号恢复及无唯一主体保全复核用例；`tests.test_document_ir_word_renderer_layout` 的成对视觉行与 annotation evidence 回归。
- 样本证据：2026-08-21 external `sn54ac244` 中 page 6 的 Figure 6-1 绑定 `block_0083/0084/0085` 图片组，page 0 的 `block_0016/0018` 共享一个独立题注；SC2167 末页“图 23 LQFP48 封装图”绑定 `block_0376` image 与 `block_0377` table 的唯一复合组，WPS 确认题注位于复合区域之后且只可见一次。

### IMAGE-004 可编辑表格与包含整图只在唯一关系下消除视觉重复

- 状态：`enforced-tested`
- 输入信号：同一源页只有一个 HTML table 被一张 image bbox 完全包含，反向也只有这一组关系；HTML 可解析、两方资产存在，且表区不超过整图面积的保守上限。
- 正式 owner：关系裁决为 `app/services/document_ir/mineru_converter.py::_normalize_contained_table_images`；互补区域与 DrawingML 坐标的共享 owner 为 `app/services/document_ir/integrity.py::complement_crop_rects`、`::drawingml_crop_offsets`；消费 owner 为 `app/services/renderer/image_renderer.py::_add_cropped_picture`。
- 预期输出：保留一个可编辑语义表和一个原 image block/asset；表图两端写入相同 `visual_overlap_group_id` 与 normalization，image 保存表区之外有序、互不重叠且精确互补的 `visual_crop_rects`。renderer 使用原图片字节和 DrawingML `a:srcRect` 输出保留片段，不重写栅格资产。
- 冲突/例外：关系歧义或表区过大时不执行裁剪，保留原图与可编辑表格并记录 `visual_overlap_unresolved` 供人工复核，允许局部视觉重复。HTML 无效导致无有效表内容、图片资产缺失、已提交裁剪组的互补合同损坏仍按 QUALITY-004 阻断。裁剪片段与表格按 Word 流式内容重排，不承诺绝对定位，最终视觉仍受 QUALITY-003 约束。
- 禁止：关系已确定且已提交裁剪归一化时又输出重复整图；静默删除歧义表格或图片；复制 IR image/asset 身份；仅凭 drawing 总数宣告裁剪正确；用 PDF 绝对定位覆盖 Word 原生流。
- 自动验证：`tests.test_document_ir_mineru_converter_layout` 覆盖唯一关系、JSON round-trip、歧义、无效 HTML、缺资产和面积上限；`tests.test_document_ir_layout_contract` 覆盖精确互补与 group 两端合同；`tests.test_document_ir_word_renderer_layout` 覆盖 `a:srcRect` 输出及片段缺失、重复、坐标错误和顺序错误阻断。
- 样本证据：2026-08-21 external `sn54ac244` 仅归一化 `block_0292+0293`、`block_0316+0317` 两组，共 8 个 `a:srcRect`；OOXML evidence 无片段缺失、意外或顺序错配，WPS 第 35、39 页确认复合组同页、无裁剪断线、大空洞、独立重复表或遮挡。

## 5. 原生字段与公式

### FIELD-001 目录只写一个原生 TOC 字段

- 状态：`implemented-gap`
- 输入信号：converter 识别出的“目录标题 + 连续高比例目录项”区域、`toc_source` 去向、合成 `toc_anchor`，以及可选翻译后的最终 IR headings。
- 正式 owner：识别与 anchor 由 `app/services/document_ir/semantic_normalization.py` 和 `app/services/document_ir/mineru_converter.py` 负责；字段与缓存由 `app/services/renderer/text_renderer.py::_fill_toc_anchor`、`::_configure_toc_styles` 和 `app/services/renderer/word_renderer.py::_RenderContext` 负责。
- 预期输出：v2 只在 anchor 处写一个原生 `TOC` complex field 并应用配置的 TOC styles；字段可见缓存来自最终 IR headings，保留层级和标题文字但不携带源 PDF 页码；`toc_source` 不逐行重复输出。Word/WPS 更新字段后由客户端生成实际 Word 页码；v1 顺序兼容仍允许旧点线入口。
- 冲突/例外：字段结果依赖 Word/WPS 更新；`updateFields` 只请求更新，不保证所有客户端打开即刷新。普通点线文本、修订记录和 table cell 不形成明确区域时按正文保留。
- 禁止：整页目录逐行静态点线输出并同时插入 TOC；一个 entry 一个 TOC field；把源 PDF 页码写入字段缓存；v2 renderer 再按单行点线重猜 TOC。
- 自动验证：`tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_semantic_normalization_resolves_title_page_note_and_explicit_toc_roles`；`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_v2_toc_anchor_uses_final_headings_as_cache_without_source_page_numbers`、`.test_render_to_bytes_uses_one_native_toc_field_for_toc_like_entries`、`.test_render_to_bytes_uses_configured_toc_styles`。
- 样本证据：OPA228 P2 manifest 有 TOC 焦点，但当前 Golden 未实际转换。
- 来源/取代：commit `5d4a02d7`；取代静态目录为正式目标。

### FIELD-002 题注、书签与交叉引用唯一性

- 状态：`enforced-tested`
- 输入信号：最终实际生成的 Figure/Table 简单整数题注，包括 image/table annotation 与 `standalone_caption`，以及正文中对唯一题注目标的引用。
- 正式 owner：`app/services/renderer/text_renderer.py::_parse_caption_text`、`::_fill_caption_paragraph`、`::_render_mixed_math`；`app/services/renderer/word_renderer.py::_build_render_context`；table context 排除复用 `app/services/document_ir/table_annotations.py::is_table_context_annotation`。
- 预期输出：每个简单整数题注写入 `SEQ <label> \\r <source_number> \\* ARABIC`，字段缓存也使用同一源编号，因此 Word/WPS 更新后仍保留非 1 起始、跳号和重复号。单次 render context 只统计最终会生成的题注字段：纳入独立题注、排除按正文渲染的 table context，并使用与最终题注相同的预处理后解析；只有唯一 `(kind, source_number)` 目标建立 bookmark，正文唯一匹配时才写 `REF`。复合编号保留普通文本，不生成 `SEQ` 或 bookmark。
- 冲突/例外：同编号多目标、复合编号、不可解析题注和 table context 不自动建立交叉引用。重复简单整数题注各自写入带相同 `\\r` 的 `SEQ` 以保持可见源号，但不能生成歧义 bookmark/REF。bookmark 映射只属于单次 render context，不存入可复用 renderer 实例。LibreOffice 26.2.4.2 重存会删除 `\\r` 并重新编号，这是已确认的客户端差异，不得据此移除 Word/WPS 所需的源号合同。
- 禁止：省略 `\\r` 而只把源号写进缓存；生成重复 bookmark；把所有数字都当引用；把 table context 计为字段目标；漏算 `standalone_caption`；为复合编号创建错误 `SEQ`。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_caption_sequence_fields_preserve_source_integer_numbers` 断言 `begin → instrText(SEQ ... \\r ...) → separate → 源号结果 → end` 的 OOXML 顺序及非 1 起始、连续、跳号、重复、复合编号边界；`.test_caption_bookmarks_follow_only_actual_caption_fields` 断言独立题注与 table context 的真实目标口径；既有 `.test_render_to_bytes_links_unique_caption_references_with_native_fields`、`.test_render_to_bytes_keeps_compound_caption_numbers_as_plain_text`、`.test_render_to_bytes_keeps_paired_image_caption_fields_in_row_order` 继续共同回归。
- 样本证据：最小候选 SHA-256 `cb5a967113d4cb6539a3cbffa6255fa0f22fab73f77276f1ff237cb89e5ce931` 在 WPS 12.1.26055 执行 `Cmd+A`、`F9` 后，Figure 保持 5、6、9、9，Table 保持 3、4、7、7，唯一引用保持 5、9、3、7，复合编号 1.1/2-1 保持普通文本；该临时文件不纳入仓库。
- 来源/取代：commit `5d4a02d7`、归档任务 `08-18-fix-layout-formula-image-caption` 与任务 `08-20-refine-word-generation-rules` R-07；取代仅靠字段缓存保留源编号的行为。

### FIELD-003 页脚页码必须是 PAGE 字段

- 状态：`enforced-tested`
- 输入信号：模板配置 `footer.enabled=true` 且 `show_page_number=true`。
- 正式 owner：`app/services/renderer/word_renderer.py::_apply_header_footer`、`::_add_complex_field`。
- 预期输出：无论是否配置左右文字，页码都应使用原生 `PAGE` field；左右文字路径用 positional tab 布局，不把数字写死。
- 冲突/例外：明确禁用 footer 时保留模板继承；字段视觉位置需要 Word/WPS 验收，LibreOffice 对 `w:ptab` 展开不同。
- 禁止：输出只有“第  页”的静态占位；写死页码；以 LibreOffice positional tab 视觉替代 Word/WPS 结论。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_native_custom_footer_and_ignores_source_footer`、`.test_render_to_bytes_writes_configured_body_header_and_footer_font_slots`。
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

- 状态：`enforced-tested`
- 本轮数学入口扩展：明确公式与 inline math 可解析常见函数 `ln/log/exp/sin/cos/tan`、符号 `Sigma/pi/tau` 和转义下划线。新增命令不得进入普通文本的全局控制词替换表；普通正文、表格文本、题注中的路径与 UNC 保持原文。`array` 等未支持环境仍按 MATH-003 可见回退，不宣称全 TeX 支持。
- 输入信号：公式 block、正文 inline math、表格 cell/notes 中的 TeX；支持分式、根式、上下标、常用符号、文本/样式 wrapper、overline、boxed、left/right、`\\tag{...}` 和已确认的 `\,` thin-space 等当前解析子集；当前 DOCX 模板可声明、缺失或留空 `word/settings.xml/m:mathFont`。
- 正式 owner：`app/services/renderer/text_renderer.py::_OmmlParser`、`WordTextRendererMixin._render_mixed_math`、`._fill_formula_paragraph`、`._bind_math_font_context`；当前文档字体上下文绑定由 `app/services/renderer/word_renderer.py::DocumentIRWordRenderer.render_to_bytes` 触发；输入归一化由 `app/conversion/docx_rules/text_semantics.py::normalize_formula_text`、`::collapse_double_escaped_tex_commands` 负责。
- 预期输出：支持的数学结构写为原生 OMML，独立公式、正文 inline math、表格中未被 MATH-004 分流的复杂片段和 note 共用同一解析路径。字母/希腊字母变量 run 不写默认 `m:sty` 或具体 `w:rFonts`，继承客户端数学斜体；数字、运算符和标点按数学语义分成直立 run，写 `m:sty=p` 并从当前文档 `m:mathFont` 派生 `w:rFonts/@w:ascii` 与 `@w:hAnsi`，避免 WPS 隐藏纯数字分式和顶层运算符。显式 `\\mathit`、`\\mathbf`、`\\boldsymbol` 写对应 `i/b` 并移除与其竞争的派生 run 字体；`\\mathrm`、`\\mathsf`、`\\text` 使用同一 `p + 当前数学字体`。无花括号上下标参数只消费一个 TeX token，不吞入后续字母或运算符。合法 `\\tag{...}` 在同一 OMML 内生成可见括号编号；不承诺右对齐、原生公式编号状态或独立定位。
- 字体 owner：当前输出 DOCX settings 是唯一数学字体 owner；模板已有非空 `m:mathFont` 时原值不变，缺失或空值时在当前输出补 `Cambria Math`。最终值只绑定到本次 `document.part`，nested parser 继承同一值，不存入可复用 renderer 或全局状态，不新增生产 config/API/schema 或修改 bundled/published 模板。
- 冲突/例外：不是完整 TeX 引擎；matrix/cases/align、自定义 macro 等未实现结构不得写成“全部公式已支持”。WPS 12.1.26055 会隐藏仅含 `m:sty=p` 且没有可用 run 字体的 OMML，因此不得恢复所有基础 run 的默认 `p`；当前 DOCX settings 值是唯一来源，renderer 只为数字/运算符/标点和显式直立命令复制同值，不探测或替换系统字体。`STIX Two Math + m:sty=p` 在当前 WPS 中表现不稳定，属于模板字体与客户端兼容边界，不能据此用 Cambria/Arial 覆盖模板非空值，也不能声称任意模板字体均已通过。
- 禁止：每遇到一个公式就在调用者加特例；全局删除反斜杠；仅在正文修复而遗漏表格/题注路径；为全部 math run 强制 `m:sty=p`；用系统字体探测、别名或除缺省 `Cambria Math` 以外的常量覆盖模板数学字体；新增与当前 DOCX settings 竞争的字体来源；声称支持任意 LaTeX。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_fraction_omml_in_formula_and_table_cells`、`.test_thin_space_tex_command_renders_as_omml_without_latex_residue`、`.test_render_to_bytes_writes_extended_omml_in_all_shared_text_paths`、`.test_render_to_bytes_preprocesses_cm4112_formulas_without_tex_residue`、`.test_render_to_bytes_supports_datasheet_tex_matrix_in_all_math_entries`、`.test_render_to_bytes_preserves_template_math_font_for_tagged_formulas`、`.test_render_to_bytes_adds_default_math_font_when_template_omits_it`、`.test_math_font_context_is_scoped_to_each_concurrent_document_part`、`.test_render_to_bytes_styles_only_upright_math_tokens_for_wps_visibility`、`.test_render_to_bytes_normalizes_formula_text_in_table_cells_and_notes`、`.test_render_to_bytes_normalizes_manual_quality_record_formula_residue`。
- 样本证据：WPS 12.1.26055 独立候选 SHA-256 `f190610632824fb09437419765247c1342ad92b1f25115f3849c567b0887e35f` 证明 `V_{OUT}=1`、纯数字分式、根号数字、`x^2+y^2`、复杂分式/根式/根指数/上下标、粗斜体、直立命令和 tag 在 standalone/inline/table 三路可见可编辑。CM4112/RS2G04 仍为 external evidence；无 committed 真 MinerU 公式包。
- 来源/取代：commit `674ce937` 与任务 `08-20-refine-word-generation-rules` R-08；取代按单个公式字符串兼容、静默吞掉 tag、全部基础 run 强制 `m:sty=p` 以及把客户端空白误归因于缺少 Cambria Math 的行为。

### MATH-003 解析失败保持可见并留下质量信号

- 状态：`enforced-tested`
- 输入信号：未知字母/标点 command、括号不闭合、空 `\\tag{}`、未支持的 `\\tag*`、tag 参数含不支持命令，或 `_OmmlParser` 无法完整解析的公式源。
- 正式 owner：`app/services/renderer/text_renderer.py::_OmmlParser.parse`、`WordTextRendererMixin._render_mixed_math`；`app/services/renderer/docx_quality.py::_unique_latex_residue`、`::build_docx_quality_flags`。
- 预期输出：不能安全生成 OMML 时整条公式保留原文本可见，并由 DOCX analyzer 对反斜杠后的字母或标点 command 报告 `latex_residue`/`latex_residue_detected`，而不是输出部分 OMML 或静默丢失；已支持的 `\,` 与合法 `\\tag{...}` 进入 OMML 后不得留下残留。
- 冲突/例外：如果输入在进入 renderer 前已错误降级成普通字符，残留扫描可能发现不了，见 QUALITY-004。
- 禁止：解析失败返回空段落；捕获后伪装成功；为消除质量 flag 删除原文本。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_malformed_fraction_remains_visible_and_is_reported_as_latex_residue`、`.test_invalid_formula_tag_remains_visible_with_quality_signal`；后者同时覆盖独立公式、inline math 和 table cell。
- 样本证据：无 committed 失败公式 fixture。
- 来源/取代：commit `674ce937` 的失败合同。

### MATH-004 表格内简单数学标识使用普通 Word 富文本

- 状态：`enforced-tested`
- 输入信号：语义 table cell 内由明确 inline math 边界包围的单一技术标识片段；允许字母、数字、已支持希腊字母命令和一层“下标后上标”，例如 `V_{CC}`、`R_{\\theta JA}`、`t_{ON}`、`I^2C`。
- 正式 owner：分类与片段替换由 `app/conversion/docx_rules/text_semantics.py::simple_table_math_identifier_html`、`::replace_simple_table_math_identifiers` 负责；`app/services/renderer/table_renderer.py::_fill_table_cell` 只在进入唯一 `_fill_paragraph` 前调用该预处理，最终 `<sub>/<sup>` 仍由 `WordTextRendererMixin._render_inline_html` 写入普通 `w:r/w:vertAlign`。
- 预期输出：命中片段不生成 OMML，而是继承 `table_content` 字体/字号、表头居中/表体左对齐、换行和普通文本编辑能力。简单片段可单独占据 cell，也可与普通文字和未命中的复杂 OMML 处于同一 cell；`I^2C` 只把 `2` 设为上标。
- 冲突/例外：`A^2_B`、关系式、多项运算、frac/sqrt/overline/boxed/tag、嵌套脚本和不支持命令不允许部分富文本化，保留原数学边界给 MATH-002/003。正文、题注、note 和独立公式不启用此分流。
- 禁止：以“处于表格”为由禁用 OMML；将不支持表达式转成带裸露 `_{...}`/`^{...}` 的半成品；新增第二套 TeX parser 或第二个 table cell writer；让普通 run 绕过表格样式和术语处理。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_uses_word_runs_for_simple_table_math_identifiers`、`.test_simple_table_math_classifier_rejects_complex_or_unsupported_script_order`、`.test_render_to_bytes_styles_only_upright_math_tokens_for_wps_visibility`。
- 样本证据：WPS 12.1.26055 独立候选 SHA-256 `f190610632824fb09437419765247c1342ad92b1f25115f3849c567b0887e35f` 确认简单标识为普通表格文本可编辑，`I^2C` 上标边界正确，混合 cell 完整，表头居中、表体左对齐；同一候选的复杂公式仍为可见可编辑 OMML。
- 来源/取代：任务 `08-20-refine-word-generation-rules` D8；取代表格内所有明确数学边界都无条件生成 OMML 的行为。

## 6. 样式、页眉页脚与质量门禁

### STYLE-001 模板配置优先且版本合同独立

- 状态：`enforced-tested`
- 输入信号：绑定模板 DOCX、layout config、document language 和 subscript/terminology config。
- 正式 owner：`app/services/renderer/word_renderer.py::_create_document`、`::_load_template_config`；`app/services/renderer/template_config.py`；版本/API owner 见 [模板布局配置合同](./template-layout-configuration.md)。
- 预期输出：renderer 清空模板 body 但保留 sectPr 和模板 header/footer，应用绑定版本的页面、段落、表格、字体及术语配置；发布版本不可变性不在本文重复定义。
- 冲突/例外：模板决定 Word 样式和绝对页面设置，源 layout 决定内容顺序、分栏和方向；显式空字体值保留继承语义。
- 禁止：为适配 PDF 修改已发布 seed；在 renderer 猜另一套 schema；让源 bbox 覆盖模板字体/边距。
- 自动验证：`tests.test_template_layout_config_schema.TemplateLayoutConfigSchemaTests.test_real_seed_matches_editor_and_renderer_contract`、`.test_bundled_versions_preserve_v1_and_select_v2_seed`、`.test_legacy_font_fields_are_completed_without_overwriting_explicit_empty_values`；renderer 配置测试见 PAGE-001/TEXT-001。
- 样本证据：Golden 历史验收绑定旧 commit，不能证明当前版本；当前无模板组合视觉基线。
- 来源/取代：`template-layout-configuration.md` 和 commit `32edca58`。

### STYLE-002 页眉页脚优先级与 section 限制

- 状态：`enforced-tested`
- 输入信号：模板已带 decoration、配置 `header/footer.enabled`、自定义 footer 文本，以及 IR 的 page_header/page_footer/page_number blocks。
- 正式 owner：`app/services/renderer/word_renderer.py::_apply_header_footer`、`::_normalize_template_header_spacers`。
- 预期输出：模板与配置共同拥有最终 decoration。配置禁用或仅 enabled 但没有标题、有效 logo、footer 文字或页码覆盖内容时，保留模板既有 header/footer；配置明确提供内容时才重建对应 part。纵向页面若遇到模板页眉以长空格占位配合分散对齐定位尾部标题，输出时仅把该占位符改为相对页边距的右对齐 tab，保留图标与标题文字；纯横向文档不改动原页眉。IR 的 page_header/page_footer/page_number 不逐源页写入共享 section，后续 section 沿用 Word 标准 relationship 继承，不复制关系。
- 冲突/例外：Word decoration 属于 section，无法表达同一 section 内每个源物理页不同 decoration；这类源差异保留在 IR/layout/evidence，但不能覆盖模板或配置。混合纵横向文档若共用同一 header part，纵向安全定位会同时作用于继承该 part 的横向节，不能声称只改变纵向节。无效的正式本地 `use_mineru_header_footer` 参数已移除，不保留兼容开关。
- 禁止：逐源页清空或覆盖共享 section decoration；配置无覆盖内容时擦除模板 footer；在配置 footer 后再写源 footer；静默接受已移除开关。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_template_decorations_when_config_disabled`、`.test_portrait_template_header_replaces_long_space_spacer_without_changing_landscape`、`.test_enabled_config_without_content_preserves_template_decorations_and_ignores_source_decorations`、`.test_render_to_bytes_writes_native_custom_footer_and_ignores_source_footer`；`tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_formal_adapter_rejects_removed_mineru_header_footer_switch`。
- 样本证据：SC2167 自定义 footer 为 external historical evidence；源页 header 逐页差异无样本门禁。
- 来源/取代：归档任务 `08-18-fix-layout-formula-image-caption`；当前代码审计补充 section 覆盖和未消费开关缺口。

### STYLE-003 四类字体槽独立写入

- 状态：`enforced-tested`
- 输入信号：eastAsia/legacy font、ascii、hAnsi 和 complex script 字体配置，包含显式空值。
- 正式 owner：`app/conversion/docx_rules/run_fonts.py::apply_run_fonts`；`app/services/renderer/text_renderer.py::_apply_run_style`；header/footer 配置消费由 `app/services/renderer/word_renderer.py::_apply_header_footer` 负责。
- 预期输出：分别写入 eastAsia、ascii、hAnsi、cs 槽；缺少新槽时回退 legacy font，显式空值保持继承，不被默认值覆盖。
- 冲突/例外：字段 schema/version 属于模板配置合同；本文只约束最终 run 输出。
- 禁止：只写 eastAsia 造成西文/公式字体漂移；用 truthy 判断覆盖显式空值；在表格/页眉维护独立字体逻辑。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_seed_config_declares_western_and_complex_fonts_for_all_text_groups`、`.test_render_to_bytes_writes_configured_body_header_and_footer_font_slots`。
- 样本证据：无当前跨 Word/WPS 字体视觉基线。
- 来源/取代：commit `5d4a02d7` 与模板 v2 合同。

### STYLE-004 正式入口必须绑定明确模板配置

- 状态：`enforced-tested`
- 输入信号：本地正式 CLI/adapter 的显式 template/layout config、缺省参数与 `no_template`，以及线上已固化 Template Version。
- 正式 owner：本地默认资源选择由 `scripts/dev/formal_mineru_conversion.py::run_conversion` 负责；默认路径来自 `app/core/config.py::Settings`；线上继续由 `TemplateReadService.resolve_template_version()` 与 `DocumentJobExecutionService._render_and_save_word()` 负责。
- 预期输出：本地显式路径优先；省略时使用当前 `Settings.default_template_path/layout_config_path`，`no_template=true` 只禁用 DOCX 模板而不禁用 layout config。本地所需默认资源不存在时显式失败，不以空配置继续；共享 renderer 只消费调用者传入路径，线上版本缺失/损坏继续失败关闭，不回退 bundled 配置。
- 冲突/例外：`DocumentIRWordRenderer` 的低层 `template_path=None/config_path=None` 仍表示无模板/空配置；字体安装由目标系统负责。可见 Word 文本受 STYLE-003 四槽约束，OMML 数学字体由当前输出 DOCX settings 的独立 `m:mathFont` 控制；模板非空值优先，缺失或空值时 MATH-002 在当前输出补 `Cambria Math`，不新增页面样式字段或第二字体 owner。
- 禁止：省略本地参数时静默使用空 `TemplateConfigPackage`；在 renderer 读取全局 Settings；以本机字体别名改写已发布 seed；把 OMML run 错计为缺少段落字体槽。
- 自动验证：`tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_formal_adapter_converts_minimal_mineru_package_to_openable_docx`、`.test_formal_adapter_resolves_default_explicit_and_no_template_resources`；既有显式配置四槽测试继续保护 renderer。
- 样本证据：CM4112 新候选省略 template/layout config 后，666/666 个可见 `w:t` run 写入 `宋体/Arial/Arial/Times New Roman`，OMML 仍独立；WPS GUI 选中标题时显示请求字体“宋体”，同时提示“缺失字体”，WPS CLI 仍有单位/公式替换字符。本机字体安装边界不改写配置。完整记录见当前任务 `research/cm4112-validation.md` 与 `research/font-config-root-cause.md`。
- 来源/取代：模板布局配置合同中“本地当前内置配置指向当前 bundled seed”的要求；补足正式 local adapter 的缺省绑定缺口。

### QUALITY-001 DOCX 结构证据与风险标记

- 状态：`enforced-tested`
- LaTeX 残留扫描只覆盖普通 Word `w:t`；原生 OMML `m:t` 内的字面下划线不是残留，解析失败回退到普通文本后仍必须被扫描。
- 输入信号：生成的 DOCX bytes/file 以及 DocumentIR/layout plan。
- 正式 owner：`app/services/renderer/docx_quality.py::analyze_docx_quality_bytes`、`::build_docx_quality_flags`；`app/services/renderer/evidence.py::build_renderer_evidence`。
- 预期输出：记录可编辑段落/语义表格、布局表、heading、numbering、TOC field/cache、keepNext、表头/cantSplit、宽表、横向节、图片 asset marker/relationship/checksum/srcRect 和 LaTeX residue 等 OOXML 指标；renderer evidence 另记录 soft page groups、break/continuation reason、明确 column downgrade、table fit decisions。无可编辑内容、图片化、手写列表、静态目录、未样式化标题、公式残留等仍生成非阻断风险 flag。
- 冲突/例外：指标或 flag 只证明包内结构，不证明 Word 实际页数、溢出、栏平衡、表格不挤压或图片清晰；`wide_table_count`/`landscape_sections` 当前不会自动形成方向风险 flag。
- 禁止：把 `quality_flags=[]` 当作视觉验收通过；把“可打开”当作质量通过；用 analyzer 指标替代真客户端排版。
- 自动验证：`tests.test_golden_sample_manifest.GoldenSampleManifestTests.test_docx_quality_analysis_reads_ooxml_structure_without_python_docx`、`.test_docx_quality_flags_obvious_word_semantics_risks`、`.test_docx_quality_analysis_flags_image_only_docx`；`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_renderer_evidence_summarizes_layout_and_docx_quality`、`.test_renderer_evidence_proves_visible_payloads_and_image_asset_identity`。
- 样本证据：线上 worker 持久化 evidence；只有 `blocking_quality_flags` 触发失败关闭，既有非阻断 `quality_flags` 仍允许成功并进入人工复核。
- 来源/取代：commit `32edca58` 的 OOXML evidence 合同。

### QUALITY-002 样本证据必须分层

- 状态：`implemented-gap`
- 输入信号：Golden manifest、component MinerU manifest、验收记录、外部本地文件和历史报告。
- 正式 owner：`tests/fixtures/golden_samples/manifest.yaml`、`tests/fixtures/component_pdf_samples/manifest.yaml` 的治理合同；执行入口 `scripts/dev/run_component_pdf_regression.py::run_regression`，人工记录校验为 `::evaluate_manual_signoff`、`::apply_manual_signoff`。
- 预期输出：明确区分 committed runnable fixture、committed PDF 但执行依赖外部环境、external evidence 和 historical evidence；component runner 记录当前 commit/dirty 状态、MinerU 包哈希和 DOCX 哈希，并生成只接受 Word/WPS 的机器可读签字模板。空验收模板不算验收记录，旧 commit、输入包或 DOCX 不匹配的 signoff 不证明当前版本。
- 冲突/例外：Golden governance tests 证明清单库存和签字协议，不证明 4 个 PDF 已被当前 renderer 转换；component runner 只证明最小包成功/可打开。`external`/`historical` 的分类目前仍依赖规范和 reviewer 纪律，没有自动化 owner 阻止错误升级证据层级。
- 禁止：把 `/Users/...` 文件、`tests/tmp` 未跟踪报告或历史哈希写成长期门禁；把 manifest 的 acceptance focus 写成已通过断言。
- 自动验证：`tests.test_component_pdf_sample_governance.ComponentPdfRegressionRunnerTests.test_regression_runner_converts_committed_minimal_mineru_sample`、`.test_manual_visual_signoff_binds_revision_artifact_and_target_client`；`tests.test_golden_sample_manifest.GoldenSampleManifestTests.test_manifest_defines_required_sample_coverage`、`.test_current_sample_inventory_reports_four_runnable_samples`、`.test_admin_manual_signoff_requires_matching_job_and_docx_hash`。
- 样本证据：committed：OPA228 P1/P2/P6/P7 PDF、OPA228 P1 最小 MinerU 包；external：SC2167、CM4112/CM4114、TPL51200、BL0942、RS2G04；historical Golden 4/4 绑定旧 commit `20d496e...`。
- 来源/取代：Golden/component 样本 README、manifest 和归档 acceptance audit；取代把一次性本地结果写成当前回归通过。

### QUALITY-003 版式行为变更必须过冲突与整文档视觉门禁

- 状态：`implemented-gap`
- 输入信号：任何改变分页、分节、分栏、表格、图片尺寸、字体/边距或公式文本长度的正式 owner 修改。
- 正式 owner：协议生成和签字校验为 `scripts/dev/run_component_pdf_regression.py::format_manual_signoff_template`、`::evaluate_manual_signoff`、`::apply_manual_signoff`；当前验收事实记录在任务 research，客户端视觉判断仍不能自动化。
- 预期输出：先运行受影响规则的正式单测，再运行冲突矩阵共同回归；用正式入口生成 committed 样本/受影响 external 样本，并在 Word/WPS（必要时 LibreOffice 辅助）检查实际页数、空白页、关键内容组落页、表格挤压、栏平衡、图片清晰度和字体替换。记录当前 commit/dirty 状态、输入包与 DOCX 哈希、客户端版本和逐项结论；自动回归状态与人工视觉记录分开，`conditional` 必须说明边界。
- 冲突/例外：不默认要求 PDF 与 Word 页数完全一致；但页数变化和内容溢出必须解释并人工判断，不可被局部 OOXML 断言掩盖。
- 禁止：只凭一个新 PDF 或局部单测通过合并结构性布局变更；用 LibreOffice 单一结果替代 Word/WPS；旧验收记录跨 commit 复用。
- 自动验证：`tests.test_component_pdf_sample_governance.ComponentPdfRegressionRunnerTests.test_manual_visual_signoff_binds_revision_artifact_and_target_client` 只验证当前版本/输入/输出/客户端签字协议；仍无整文档分页或视觉自动断言。
- 样本证据：2026-08-21 当前 dirty 候选在 WPS 12.1.26055 完成 OPA228 P1/P2/P6/P7 代表页记录；committed runnable 最小包另有哈希绑定的 1 页 WPS 条件签字。external SN54AC244 修复候选覆盖 19 张语义表、12 个原生双栏 section、1 个横向 section、38 个图片资产和 38 页源文档，WPS 实际为 50 页；首页实质双栏及右栏表格保持，第 2 页同时容纳声明和 TOC，机械图标签与主体位于第 35 页。完整哈希和逐项结论见本任务 `research/r10-visual-governance.md`。该结论是针对两个已证实缺陷的有界 `conditional` 复核，不冒充 50 页逐页签字；本规则因视觉判断不能自动化而保持 `implemented-gap`，committed runnable 的真实布局覆盖不足只表示证据不可离线重复，不表示缺少实际代表性样本。
- 来源/取代：本任务 PRD；明确补上 `674ce937` 后局部测试通过但整文档负优化的缺口。

### QUALITY-004 输入丢失与质量 flag 不得伪装成功

- 状态：`enforced-tested`
- 输入信号：有 source inventory 的 v2 source→IR 对账，及任意 DocumentIR→layout→DOCX 渲染结果。
- 正式 owner：source→IR 由 `app/services/document_ir/integrity.py`；IR→layout/DOCX evidence 由 `app/services/renderer/evidence.py`；发布边界由正式本地 adapter 和 `DocumentJobExecutionService` 负责。
- 预期输出：evidence 同时记录 expected、actual、差值和稳定 `blocking_quality_flags`。新 converter 的每个主源块必须有语义裁决；body 块保留可见 payload，decoration/`toc_source`/`filtered` 保留显式去向。可见 body block（含空文本 TOC anchor）必须且只能进入 layout 一次；正文、列表项、语义表格 cell、caption/footnote 和可规范化公式必须在 DOCX 可见内容中得到证明；图片必须由 block asset id 经 drawing marker、relationship 对到媒体 checksum。IMAGE-004 的裁剪图片还必须按 asset、`srcRect` 坐标、multiplicity 和同资产片段顺序逐项对账；v2 TOC 的 source/anchor、字段数量及无源页码 heading cache 必须一致。确定性内容缺失、重复 layout、资产或裁剪片段错配、不可见 payload 或 TOC disposition 违反失败关闭：source→IR 在线任务归类 `document_ir_failed`，IR→DOCX 归类 `render_failed`，本地不发布最终 DOCX。
- 冲突/例外：两级策略固定为“内容损坏阻断、版式不确定安全降级”。术语替换使用 renderer 同一最终配置；Word field 的分 run 文本先合并；可解析 OMML 以其可见数学文本规范化证明，避免把合法公式判为丢失。LaTeX residue 但内容仍可见、decoration 歧义、soft page group、栏/表格容器或字号降级、实际分页、栏平衡、清晰度和其他现有 `quality_flags` 是非阻断人工复核风险；无法确定性证明的客户端行为不得伪装成阻断。旧 IR 无 inventory/语义证据时只跳过无法证明的 source 对账，不能跳过 IR→layout/DOCX 对账。
- 人工复核合同：未决题注、未决表图重叠及自动恢复题注写入 `review_issues`，每项为 `code`、`source_page`（源 PDF 的 1-based 页码，未知为 null）、`block_id`、`message`。renderer evidence 随 generated_word metadata 持久化，files API 仅白名单投影四字段；任务详情只展示当前 result_file_id 的复核位置，不能称为 Word 实际页码。本地正式入口同步生成 `.review.json`。警告不改变成功状态和下载权限，确定性完整性阻断仍优先。
- 禁止：把全部 quality flags 升级为 fatal；先写入/上传最终 DOCX 再检查；吞掉完整性异常或返回伪成功。
- 自动验证：`tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_renderer_evidence_blocks_missing_layout_drawing_and_table`、`.test_renderer_evidence_proves_visible_payloads_and_image_asset_identity`、`.test_renderer_evidence_blocks_missing_visible_payload_and_asset_identity_mismatch`；`tests.test_conversion_sandbox_dev_tools.LocalMinerUConversionCliTests.test_formal_adapter_does_not_publish_docx_when_renderer_integrity_blocks`；`tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_integrity_gates_fail_before_ir_or_word_publication`。
- 样本证据：CM4112 当前 external 样本 expected/actual 为 53/53 drawings、8/8 tables、18/18 headings，`blocking_quality_flags=[]`；旧候选 15 drawings 的确定性丢失现会被阻断。
- 来源/取代：当前正式代码/调用链审计发现。

## 7. 冲突优先级矩阵

| 冲突 | 基础规则 | 优先规则/裁决 | 必须共同保护的回归 |
|---|---|---|---|
| 同方向源页边界 vs 明确内容续接 | FLOW-001 | 明确续表、内容组、列表续接，或具有保全原因、页脚源角色和源页底边位置三重证据的正文块合并页面组；其他普通边界保留出处但不强制 Word 分页，显式目录首块按 FLOW-002 起页 | CM1348 源页边界不制造大面积空白且目录从第 2 页开始；SC2167 与 SN54 目录/正文流动；整本文档页数变化须解释 |
| 软页面分组 vs 长表跨页 | FLOW-001 | FLOW-003 的续表元数据抑制组间分页，`tblHeader`/`cantSplit` 交给 Word 分页；不得恢复逐源页硬分页 | CM4112 第 3/4 页、SC2167 长表不挤压且无空白页 |
| 源页方向 vs 宽表 | PAGE-001 | 源 page 宽高方向优先；宽表本身不触发横向 | OPA228 P7 portrait wide table；真实 landscape page |
| 普通原生双栏 vs 成对图片 | COL-002 | COL-003 仅对严格图片对使用有标记的无边框 1×2 布局表 | 左→右阅读顺序、多 annotation 不错配、SC2167 图片网格 |
| 成对视觉行/表图复合 vs 共享图题 | COL-003、IMAGE-003、IMAGE-004 | 先裁决唯一视觉关系，再绑定题注；严格图片对仍用 1×2 布局表，表图复合以 image+table 为共同 subject，唯一题注作为同内容组的独立段落置于其后 | 图片同页成对、包含表图复合、题注只可见一次、无唯一主体时保全并提示复核 |
| 双栏 vs wide/局部单栏 | COL-001 | wide block 与真实单栏 gap 留在单栏 region；仅实际 band 进入双栏。只有短、纯文本且紧邻 wide 图片的视觉前导可降级为单栏连续组，并记录 evidence | OPA228/CM4112 首页内容顺序与表格宽度；SN54 机械图标签与主体同页 |
| 模板绝对样式 vs 源版式 | STYLE-001 | 模板决定纸张/边距/字体；源 IR 决定内容语义、相对布局和方向 | 模板版本测试 + PAGE/COL/FLOW 共同回归 |
| 模板/配置 decoration vs 源 decoration | STYLE-002 | 模板/配置是最终 owner；只有配置明确提供覆盖内容才重建 part，源 decoration 只留作证据，不写共享 section | 模板继承、空覆盖配置、自定义 footer/PAGE field、同向源 decoration 不覆盖 |
| 可编辑结构 vs 源像素外观 | TABLE-001、FIELD-001、FIELD-002 | 原生 table/TOC/SEQ/REF 优先，但不得改变内容顺序或静默丢失 | OOXML 结构 + Word/WPS 视觉检查 |
| 数学归一化 vs 普通正文保真 | TEXT-003、MATH-004 | 所有共享文本入口都会归一化，但只允许证据充分的 TeX 模式改写；OMML 限于数学边界/整段公式，仅表格内简单标识片段例外转普通富文本，普通路径/UNC 保持，失败按 MATH-003 可见 | CM4112 公式矩阵 + 表格简单/复杂正反例 + 普通反斜杠正文 |
| 富文本题注 vs 多条真实 annotation | TEXT-004 | flat rich-node list 是一条逻辑题注；string list/多个 nested groups 保持多条，renderer 不重猜边界 | v2 rich chart/table caption + 多题注负例 + COL-003 + WPS 图 33 |
| 可编辑表格 vs 包含该表的整图 | TABLE-001、IMAGE-001 | IMAGE-004 仅在唯一且完整证据下保留表格并用原生 `srcRect` 排除整图中的重复表区；否则失败关闭 | 唯一/歧义关系、精确互补、片段身份和顺序、SN54 external |
| 正式入口默认配置 vs 版本化配置 | STYLE-004 | 本地 adapter 省略参数时使用 Settings 当前默认；线上只用固化 Template Version，renderer 无全局 fallback | local 缺省/显式/no-template + 线上模板版本 + STYLE-003 四槽 |
| 尾页清理 vs 内容保真 | INPUT-003 | 实质内容保真优先；过滤必须同时满足末页、CTA、视觉资产和无实质结构 | 保守负例 + SC2167 external evidence |
| 同根 v2/legacy 兼容 vs 多套 MinerU 结果 | INPUT-001、IMAGE-001 | 同根唯一 v2 优先、无 v2 时 legacy fallback；跨结果根或同版本多候选不猜选，资产只在绑定根内解析 | 同根优先、多根/多同版本失败、layout/asset 同根、精确/唯一 basename/越界回归 |
| MinerU 源角色 vs 可见内容 | IR-005、QUALITY-004 | source role 只是候选；明确内容损坏失败关闭，语义/版式证据冲突时保留 body 并记录非阻断降级 | decoration 正反例 + `sn54ac244` 免责声明 external 回归 |
| 源 title vs 竞争角色 | IR-005、TEXT-001 | 源 title 默认保留 heading；仅明确 caption、revision range、局部分组等竞争角色降级，普通 `text_level` 不晋升 | 无章节号真标题 + revision/group/caption 负例 |
| 源目录页码 vs Word 目录 | FIELD-001 | 明确 TOC 区域只提供 source/anchor；字段缓存来自最终 headings 且不带源页码，客户端更新后生成 Word 页码 | TOC anchor/cache + 普通点线正文负例 |
| 翻译覆盖 vs 公式保真 | TEXT-005、MATH-002 | captions/footnotes 必须翻译，但 provider 只接收普通文本段；明确公式片段原样拼回 | caption/footnote mixed-math target 回写 + OMML |
| 模板数学字体 vs WPS 直立文本可见性 | STYLE-004、MATH-002 | 当前 DOCX settings 保持唯一 `m:mathFont` owner；模板值优先，缺失/空值补 `Cambria Math`。变量 run 继承数学斜体，数字/运算符/标点与显式 `mathrm/mathsf/text` 才派生同值直立字体。模板字体与客户端不兼容时记录边界，不安装、探测或静默替换 | template mathFont 保留/缺失/空值并发隔离 + standalone/inline/table + WPS 纯数字/运算符/复杂候选 |
| OOXML 指标 vs 实际视觉质量 | QUALITY-001 | QUALITY-003 的当前 commit 真客户端验收决定视觉结论 | CM4112 21→23 页负例；表格/栏/图片实际排版 |

## 8. 规则回归矩阵

“自动测试”列只列正式 converter/renderer/pipeline 证据；legacy characterization 不计入。

| 规则 | 正式 owner 层 | 自动测试层 | Committed 样本 | External/人工证据 | 当前缺口 |
|---|---|---|---|---|---|
| PIPE-001、INPUT-001、INPUT-004 | formal adapter、MinerU package/converter | conversion sandbox、converter layout、component runner | OPA228 P1 最小 MinerU v2 包 | SN54、SC2167 单根正式重跑 | fixture 不含多结果根真包；runner 只断言可打开 |
| INPUT-005、FLOW-003 | layout signals、共享占位符规则、converter | converter layout | 无 | `docjob_cfcdfa737312` external failure ZIP | 无 committed 真 MinerU 包；原用户 ZIP 仅作临时只读回归 |
| PIPE-002、IR-001 | models、layout plan、renderer | IR contract、converter/renderer layout | 无复杂 IR 基线 | 线上合成 worker | 无当前真样本 IR snapshot |
| INPUT-002 | package extraction、formal adapter | 仅入口正常/缺路径 | OPA228 P1 正常包 | 无 | 无正式 ZIP traversal/坏 JSON 定向测试 |
| INPUT-003 | shared content rule、converter | conservative/filter converter tests | 无 | SC2167 historical | 无 committed 宣传尾页包 |
| IR-002、PAGE-001、PAGE-002 | layout signals、section setup | converter/renderer layout | OPA228 PDF 仅作为输入资产 | CM4112 external | 没有当前真实纵横向/页数视觉基线 |
| IR-003、IR-004、IR-005、QUALITY-004 | semantic normalization、integrity、converter、renderer evidence、正式发布边界 | converter/IR contract/renderer/formal adapter/document job | 无 | CM4112 当前对账；`sn54ac244` decoration/title external 回归 | 无 committed 含 chart/复杂 decoration 的 MinerU fixture；实际分页不属于阻断计数 |
| TABLE-004 | shared table parser、source integrity、table renderer、renderer evidence | converter/renderer layout | 无 | SN54、SC2167 external 合法表格回归 | 无效输入确定性失败已闭环；无效路径不需要客户端视觉门禁 |
| FLOW-001、FLOW-002 | layout plan 页面组/源页出处、renderer 自然续排与目录语义起页 | renderer layout | 无 | CM1348 v10、SC2167、CM4112 external | 无自动客户端落页断言；CM1348 图 11/12 后仍有一处明显空白 |
| FLOW-003、TABLE-001、TABLE-002、TABLE-003 | layout signals、layout plan、table renderer | converter/renderer table tests | OPA228 P6/P7 PDF 未执行 | CM4112、SC2167 external | continuation height 只用于页面组续接；无表格挤压/跨页视觉门禁 |
| COL-001、COL-002 | layout plan、renderer columns | renderer layout | OPA228 P1/P2 PDF 未执行 | CM4112 当前 LibreOffice/WPS、SC2167 external | 无自动 Word/WPS 栏平衡断言；WPS 分页仍与 LibreOffice 不同 |
| COL-003、IMAGE-001、IMAGE-002、IMAGE-003、IMAGE-004 | layout plan、image renderer、DOCX analyzer/evidence、converter/source integrity | renderer/converter/layout contract image tests | 无真实图片 MinerU fixture | SC2167、`sn54ac244` external | 仅 1×1 PNG；损坏图片 fallback、DPI/清晰度无直接基线；裁剪后的最终流式排版仍需 Word/WPS 复核 |
| TEXT-001、TEXT-002、TEXT-003、TEXT-004、TEXT-005 | converter caption owner、translator、text renderer、shared semantics | converter/translator/renderer layout、shared text characterization | OPA228 P1 最小包 | CM4112 当前 heading 18/18；图 33 单题注与 WPS GUI 关键页；OPA228 historical signoff | component runner 未断言 heading/list/unit focus；无 committed 富文本 caption 或翻译真样本包 |
| FIELD-001、FIELD-002 | text renderer、render context | renderer layout | OPA228 P2 PDF 未执行 | FIELD-002 最小候选已由 WPS 12.1.26055 更新字段验证；SC2167 external | TOC 更新后的整文档内容仍依赖客户端；LibreOffice 会删除 SEQ 的 `\\r`，不能替代 Word/WPS 合同 |
| FIELD-003、STYLE-002 | renderer header/footer、formal adapter | template/custom/pure PAGE/removed-switch tests | 无 | SC2167 historical | PAGE field 与 decoration 视觉位置仍需 Word/WPS 验收；不支持同 section 逐源页不同 decoration |
| MATH-001、MATH-002、MATH-003、MATH-004 | converter、shared semantics、table/text renderer、OMML parser | converter/renderer formula matrix、表格简单标识正反矩阵、mathFont 并发隔离 | 无 MinerU 公式 fixture | D8 WPS 简单富文本/纯数字/运算符/复杂 OMML 候选；CM4112、RS2G04 external | 非完整 TeX；无真实输入包；预 renderer 降级可能漏 flag；tag 只保证同公式可见括号编号，不承诺右对齐原生编号 |
| STYLE-001、STYLE-003、STYLE-004 | formal adapter、renderer/template config/fonts | template schema、formal adapter、renderer layout | 模板 seed 与 OPA228 PDF | CM4112 当前四槽边界；R-08 模板 mathFont/WPS 证据；Golden old-commit signoff | 目标系统字体安装仍由客户端负责；STIX Two Math 的直立 OMML 在当前 WPS 中不稳定 |
| QUALITY-001、QUALITY-002 | analyzer/evidence、sample governance、component 签字协议 | Golden/component governance | 4 个 OPA228 PDF + 1 个最小 MinerU 包 | 历史/外部样本分层 | Analyzer 不测实际分页；Golden 当前不离线 deterministic；external/historical 分类仍依赖 reviewer 纪律 |
| QUALITY-003 | component runner 当前版本/输入/输出/客户端签字协议；视觉判断仍归 Word/WPS | component governance 协议测试 | OPA228 最小 MinerU 包当前 WPS 条件签字 | SN54AC244 两个分页缺陷修复后的有界 `conditional` 记录；OPA228 P1/P2/P6/P7 当前 WPS 记录；CM4112 有界记录 | 无整文档视觉自动门禁；SN54 50 页未逐页签字；真实布局 external evidence 不能离线重复 |

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
| legacy static TOC/caption/page number | 静态点线、普通题注或静态页码 | FIELD-001/002/003 已取代 | 不恢复静态字段；页码始终使用原生 PAGE field |
| legacy 每源页硬分页 | 物理页与 Word 页一一硬切 | FLOW-001/002；历史行为为 `superseded` | commit `5d4a02d7` 删除逐页硬分节；同向源页不再设置 `pageBreakBefore`，方向变化仍由 PAGE-002 处理 |
| legacy 固定/最小图片宽度 | 以固定尺寸提高可见性 | IMAGE-001；历史行为为 `superseded` | 正式 renderer 使用 bbox 相对宽度；清晰度问题应通过真实图片样本处理 |
| legacy 1×2 布局表格 | 用表格模拟正文双栏或图片对 | COL-002/003；普通正文包装行为为 `superseded` | 普通正文用原生栏；严格图片对仅用带标记的无边框 1×2 布局表 |

## 11. 已确认但本任务不修复的产品缺口

- heading-like paragraph 的样式推断不会获得显式 heading 的 `keep_with_next` 和页顶语义分页。
- v2 TOC 使用显式 source/anchor，只保留一个原生字段并以最终 headings 提供无源页码缓存，但尚无 Word/WPS 更新后目录内容的当前验证。
- 翻译已覆盖 captions/footnotes 并保护 `$...$`/`\\(...\\)`，但旧 IR 若已丢失数学边界仍只能作为普通文本处理；尚无启用翻译的 Word/WPS 当前真样本验收。
- `build_docx_quality_flags()` 只记录结构风险；线上任务当前不会仅因这些 flags 自动失败。
- component runner 已绑定当前版本、输入/输出哈希和 Word/WPS 人工签字，但仍没有整文档页数、空白页、实际落页、表格挤压、栏平衡和图片清晰度自动断言；SN54AC244 已提供真实布局 external 长文档验收，committed runnable fixture 的覆盖不足只限制离线重复性，不能否定或替代该真客户端结论。
