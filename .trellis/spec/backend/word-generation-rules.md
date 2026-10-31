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
- 预期输出：先由 `MinerUToDocumentIRService.convert_zip()` 生成并持久化 DocumentIR，再由 `DocumentIRWordRenderer.render_to_result()` 一次生成 DOCX 和公式报告，再构建 renderer evidence（旧 `render_to_bytes()` 保持 bytes 兼容）；所有正式修复都落在该链路的唯一 owner。
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
- 输入信号：MinerU 包内一个或多个目录中的 `content_list_v2.json` / `*_content_list_v2.json` 及对应 legacy 候选；文件命名识别方式保持原合同。
- 正式 owner：`app/services/document_ir/mineru_package.py::find_content_list`、`::load_content_blocks`。
- 预期输出：所有候选的父目录必须唯一；在该结果根内优先 v2，仅无 v2 时选择 legacy；被选版本必须恰有一份。唯一 v2 允许忽略同根重复 legacy。支持顶层 list、`content_list` 字段和嵌套 page list。
- 失败合同：`find_content_list(package_root: Path) -> Path` 抛出 `MinerUPackageError`；缺失保留 `mineru_content_list_missing / missing_content_list`，多根为 `mineru_content_list_ambiguous / multiple_result_roots`，被选版本多份为同 code、`multiple_content_lists`。正式 converter 沿现有有界报告传播，不把绝对路径放入 code/reason。
- 冲突/例外：此规则不读取 `full.md`；legacy JSON 只是输入兼容，不等于切换旧 runtime。
- 禁止：多根或被选版本多份时按路径深度/名称静默择首；因 v2 JSON 或字段非法而偷偷改用 legacy；按绝对文件名或 PDF 型号硬编码选择。
- 自动验证：`tests.test_mineru_result_root_uniqueness` 直接覆盖单根版本选择、多根/所选版本重复、缺失与正式 converter 的坏 v2 不回退及脱敏报告；既有输入形态入口为 `tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_prefers_v2_content_and_keeps_legacy_only_fallback`、`.test_convert_zip_accepts_nested_v2_pages_and_rich_content_fields`。
- 样本证据：已提交 `ti-opamp-opa228-p1-smoke` 使用 `component_content_list_v2.json`；没有已提交的 v2/legacy 双份真包。
- 来源/取代：归档任务 `08-18-fix-mineru-first-page-layout`；取代 legacy-first 选择导致 CM4112 读取错误产物的历史行为；任务 `10-31-mineru-root-heading-minimal` 仅适配 `c9b1e6a9` 的唯一性策略，取代多根择首行为。

### INPUT-002 MinerU 包边界与显式失败

- 状态：`enforced-tested`（已接受依赖输入合同的本地集成验证，不代表线上/Word验收）。
- 输入信号：ZIP 条目、目录路径、选中 content list 原始 JSON、页面/bbox、资产及 HTML。
- 正式 owner：`app/services/document_ir/mineru_package.py` 拥有包路径/限额/精确资产寻址；`artifact_validator.py` 拥有原始结构/资产/HTML和 `mineru-artifact-validation/v1` 报告；converter 只消费已验证视图；本地 adapter 进入同一服务。
- 预期输出：全包展开前拒绝绝对/穿越/Windows路径、symlink/特殊条目、覆盖/祖先冲突及超限，按实际字节有界展开；选中JSON非法不得回退其它结果。必需图片真实解码且可被Word消费；显式非法/非有限bbox在映射前失败。资产不按basename猜测，合法HTML保持原生表格。源包只读，失败带有界结构报告，不返回伪成功。
- 冲突/例外：目录输入由正式 adapter 物化成 ZIP 后进入同一服务；旧 runtime 的路径穿越 characterization test 不能证明这里已覆盖。
- 禁止：猜测邻近文件、静默返回空文档、以宽泛异常吞掉输入错误。
- 自动验证：`tests.test_mineru_artifact_validator` 的ZIP预检/碰撞/CRC/限额、路径歧义/穿越、Unicode/坏JSON、非有限bbox、坏图/不支持格式、raw/effective inventory与报告边界；converter/IR contract和正式adapter入口负例保持。
- 样本证据：RND-503依赖集成174项通过；component/direct/真实客户端以本轮validation分层记录，不借历史结果声称新样本通过。
- 来源/取代：已接受IR-201/IR-204最终17cde1f的有边界集成，见RND-503 dependency-integration记录；不由本条推导未接入的其它Worker事件/仓储能力。

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

### IR-005 严格题注关系与原始证据

- 状态：`enforced-tested`；正式ZIP/OOXML和定向证据仅证明结构与内容，未代表Word视觉。

- caption 统一由 document_ir/caption_reconciler.py 负责逻辑分组、可靠换行拆分、严格编号和关系回执；converter 只消费最终结果，禁止再递归读回旧 nested 字段。
- 自动修复限同页、原源索引连续、同对象族、标签一致、编号唯一连续、数量相等及原分布失衡；image/chart/figure 与 table 分族，已有一对象一题注保持。
- flat rich nodes 仍是一个逻辑题注，仅完整标签/编号起始的可靠显式换行或既有逻辑组可以拆分；无边界连写图5/6不猜拆。原始值/runs/locator 保留在专用 metadata，不使用可见 caption 别名。
- 独立 paragraph 不搬移或复制可见文本，仅在唯一相容对象、同页直接邻接和有效 bbox 下建立 evidence-only；歧义记录 caption_binding_uncertain，普通无候选对象不全局误报。
- 表题/条件保持 TABLE-002 的唯一 classifier，明确边界分别处理，混合边界不明保留原 annotation 并标不确定；合法 HTML 继续原生表格。
- 原始证据只由主源块保存，table_context 派生块不复制；renderer 摘要不包含原文。拟自动修复必须守恒且唯一消费，损坏按 QUALITY-004 失败关闭，普通 uncertainty 不升级 fatal。最终可见caption列表也纳入守恒门禁；重复条件保留出现次数，重复编号表题保持原annotation并uncertain，防止下游既有去重静默丢次。范围/共享标签续号不按首号绑定。
- 自动验证：`tests.test_caption_reconciler`、converter 的 nested/sequence/accepted redacted/table/paragraph/damage/legacy 联合测试、IR contract roundtrip 与 translation metadata 保真。真实Word/WPS和字段更新结果仍未验证；FIELD-002 的跳号限制不由本任务修复。

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

### TEXT-001 原生标题语义与内容组保持

- 状态：`enforced-tested`
- 输入信号：MinerU 显式 heading 的可见文字与源层级、IR schema version、显式 IR heading、v1 heading-like paragraph、配置的 heading Word style 和层级。
- 正式 owner：源层级由 `app/services/document_ir/mineru_converter.py::_heading_level` 与 `app/conversion/docx_rules/text_semantics.py::infer_source_heading_level` 负责；输出由 `app/services/renderer/word_renderer.py::_render_block`、`app/services/renderer/text_renderer.py::_fill_heading_paragraph` 负责；旧三级兼容推断仍由 `text_semantics.py::infer_heading_level` 负责。
- 预期输出：显式 heading 使用 Word heading 样式并 `keep_with_next`；`document-ir/v2` paragraph 不根据文本升级 heading，`document-ir/v1` 顺序兼容才允许可靠 heading-like 推断。编号图/表题注和正文引用不属于 heading-like。配置存在时使用配置的 named style。
- 源标题层级：仅对已分类 heading 调用 `infer_source_heading_level(text: str, *, source_level: int) -> int`；`source_level` 来自 converter 既有字段解析和 1–6 级裁剪。十进制编号按深度取 1–6 级，超过六层仍取 6；现有章/节/附录格式为 1；无编号返回原源层级。仅探测文字，不重写原文、ID、顺序或源定位。
- 冲突/例外：页顶分页由 FLOW-002；v1 推断得到的 heading-like paragraph 不设置 `keep_with_next`，也不能触发 FLOW-002。v2 paragraph 仍保留 TOC/list/bullet 识别，不因禁止标题推断而降级这些显式或可靠语义。旧 `infer_heading_level` 的三级兼容行为保持，不将该上限套到源 heading。
- 禁止：只加粗/放大而不使用标题语义；所有短句均升级；按“工作原理”等具体标题硬编码；用编号规则升级普通 paragraph，或把源标题四至六级压到旧三级上限。
- 自动验证：编号层级、无编号源层级、普通段落和源记录保真由 `tests.test_document_ir_numbered_heading_levels` 经过正式 converter 直接验证，并保护旧三级兼容；既有渲染入口为 `tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics`、`.test_render_to_bytes_keeps_v1_heading_like_paragraph_compatibility`、`.test_render_to_bytes_uses_explicit_v2_semantics_without_heading_guessing`、`.test_render_to_bytes_uses_configured_heading_word_style_when_available`；图/表反例见 `tests.test_text_render_characterization.TextRenderingCharacterizationTests.test_looks_like_heading_text_rejects_english_sentence`。
- 样本证据：OPA228 最小 fixture 包含 heading，但 runner 只断言标题文本可见；CM4112 当前 external 样本显式 heading 为 18，DOCX heading 段落为 18；WPS 实际观察“工作原理”从新页开始。
- 来源/取代：commit `32edca58` 正式 renderer 语义化；任务 `10-31-mineru-root-heading-minimal` 仅适配源标题编号层级，不引入整套语义重分类。

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
- 正式 owner：`app/services/document_ir/caption_reconciler.py::reconcile_captions`；现有文本/公式清理 helper 只作为片段归一化依赖。
- 预期输出：一个没有可靠换行标题边界的 flat `text/equation_inline/text` 节点数组形成一个完整 `DocumentIRBlock.captions` 元素；可靠显式换行拆分只按 IR-005 的严格规则执行，进入 Word 后只占一个题注段落；string list 和多个 nested rich groups 继续形成多条独立题注。可见 inline 语义、SEQ/bookmark、fallback、table context 和 COL-003 annotation 数量判断均基于完整逻辑题注。
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

RND-502 补充：`formula_text_fallback` 是内容完整、可见、可审计的 warning，不是 fatal。新报告中的源/锚点/预期输出投影不一致属于确定性完整性失败，必须阻断新候选；receipt 后损坏按 uploading/oss_failed 保留选件，不重渲染掩盖。详细版本合同见下方 RND-502 场景。

## 7. 冲突优先级矩阵

| 冲突 | 基础规则 | 优先规则/裁决 | 必须共同保护的回归 |
|---|---|---|---|
| 同方向自然流 vs 章节/表格组起页 | FLOW-001 | FLOW-002 只对非首页页顶 heading、captioned table、table context 的真实段落设置 `pageBreakBefore` | SC2167 无 blank body pages；CM4112“工作原理”和独立表格组起页；整本文档页数变化须解释 |
| 自然流 vs 长表跨页 | FLOW-001 | FLOW-003 的 `tblHeader`/`cantSplit` 与 Word 自然分页；不得恢复逐源页硬分页 | CM4112 第 3/4 页、SC2167 长表不挤压且无空白页 |
| 源页方向 vs 宽表 | PAGE-001 | 源 page 宽高方向优先；宽表本身不触发横向 | OPA228 P7 portrait wide table；真实 landscape page |
| 普通原生双栏 vs 成对图片 | COL-002 | COL-003 对严格图片组使用无边框布局表格 | 左→右阅读顺序、多 annotation 不错配、SC2167 图片网格 |
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
| INPUT-005、FLOW-003 | layout signals、共享占位符规则、converter | converter layout | 无 | `docjob_cfcdfa737312` external failure ZIP | 无 committed 真 MinerU 包；原用户 ZIP 仅作临时只读回归 |
| PIPE-002、IR-001 | models、layout plan、renderer | IR contract、converter/renderer layout | 无复杂 IR 基线 | 线上合成 worker | 无当前真样本 IR snapshot |
| INPUT-002 | package extraction、artifact validator、formal adapter | 已接受依赖的ZIP/path/坏JSON/资产/报告边界及converter测试 | OPA228 P1 正常包与中性负例 | 无 | 不代表线上真实存储或Word视觉 |
| INPUT-003 | shared content rule、converter | conservative/filter converter tests | 无 | SC2167 historical | 无 committed 宣传尾页包 |
| IR-002、PAGE-001、PAGE-002 | layout signals、section setup | converter/renderer layout | OPA228 PDF 仅作为输入资产 | CM4112 external | 没有当前真实纵横向/页数视觉基线 |
| IR-003、IR-004、QUALITY-004 | integrity、converter、renderer evidence、正式发布边界 | converter/IR contract/renderer/formal adapter/document job | 无 | CM4112 当前 external 对账 | 无 committed 含 chart 的 MinerU fixture；实际分页不属于阻断计数 |
| TABLE-004 | 当前缺口 | 无 | 无 | 无 | 无效 HTML/空有效表格的失败策略待实现 |
| FLOW-001、FLOW-002 | renderer page loop、semantic break | renderer layout | 无 | SC2167、CM4112 external | 无实际落页和空白页自动断言；双栏重排可能使语义分页目标晚于左栏内容 |
| FLOW-003、TABLE-001、TABLE-002、TABLE-003 | layout signals、table renderer | converter/renderer table tests | OPA228 P6/P7 PDF 未执行 | CM4112、SC2167 external | continuation height 无消费者；无表格挤压/跨页视觉门禁 |
| COL-001、COL-002 | layout plan、renderer columns | renderer layout | OPA228 P1/P2 PDF 未执行 | CM4112 当前 LibreOffice/WPS、SC2167 external | 无自动 Word/WPS 栏平衡断言；WPS 分页仍与 LibreOffice 不同 |
| COL-003、IMAGE-001、IMAGE-002、IR-005 | image plan/writer/evidence、converter/reconciler | 阈值/比例/OOXML变换/注释/三恢复入口/B1及源安全负例 | 可靠图5/6、24/25合成ZIP、中性非方图、已接受去标识不确定caption-pair | SC2167 historical；本轮LO26.2.4.2辅助预览 | Microsoft Word更新字段前后及部署预览待验；无真实专有ZK全册签字，不承诺源图清晰度 |
| TEXT-001、TEXT-002、TEXT-003、TEXT-004 | converter caption owner、text renderer、shared semantics | converter/renderer layout、shared text characterization | OPA228 P1 最小包 | CM4112 当前 heading 18/18；图 33 单题注与 WPS GUI 关键页；OPA228 historical signoff | component runner 未断言 heading/list/unit focus；无 committed 富文本 caption 包 |
| FIELD-001、FIELD-002 | text renderer、render context | renderer layout | OPA228 P2 PDF 未执行 | SC2167 external | 字段更新和视觉仅客户端可确认；SEQ 更新可能重排非 1 起始/跳号编号 |
| FIELD-003、STYLE-002 | renderer header/footer | custom footer/template tests（部分） | 无 | SC2167 historical | 纯页码无 PAGE field；同 section source header 覆盖；adapter 开关未消费 |
| MATH-001、MATH-002、MATH-003 | converter、共享 formula owner、单次 render context、analyzer/evidence | 精确公式结构/输出篡改/翻译边界/三恢复入口与并发测试 | 合成 MinerU→IR→fake translation→原生表格 DOCX；无专有 MinerU 公式包 | CM4112、RS2G04 external；当前本地证据见 RND-502 validation | 有限 TeX 子集，复杂结构受控降级；合法简单 tag 已保留编号；当前真 Word 视觉签字仍待验 |
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
| legacy 1×2 布局表格 | 用表格模拟正文双栏或图片对 | COL-002/003；历史行为为 `superseded` | 普通正文用原生栏；严格图片组按RND-503使用无边框布局表格 |

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
- RND-502 已支持简单 tag 可见编号；复杂或不完整 tag 必须整式受控降级，不能静默消费编号。
- 可选翻译当前不处理 captions 和 footnotes，可能产生正文已翻译而题注/表注仍为原文的混合输出。
- `build_docx_quality_flags()` 只记录结构风险；线上任务当前不会仅因这些 flags 自动失败。
- 没有当前版本的整文档页数、空白页、实际落页、表格挤压、栏平衡和图片清晰度自动门禁；CM4112 最新 external 结果已证明局部测试不足。

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
