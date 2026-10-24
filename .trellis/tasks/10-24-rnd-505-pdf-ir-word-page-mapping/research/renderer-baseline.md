# Research: RND-505 的 renderer、来源与锚点基线

- Query: 当前根工作区及已验收 RND-501 的 source span → IR block → Word anchor 能力、兼容边界和 RND-505 最小复用方案。
- Scope: internal
- Date: 2026-10-24
- 当前任务：`.trellis/tasks/10-24-rnd-505-pdf-ir-word-page-mapping`；仅规划，不集成或修改业务代码。

## Findings

### 1. 证据来源及首要结论

当前根工作区代码经直接读取。已验收代码由主会话使用只读 Git 操作导出，研究者读取导出内容；以下 `69906a5e:<path>:<line>` 均指该提交内行号，不能误解为当前根工作区已有的文件。临时导出位置不作为持久 context 依赖。`f51edf7e` 的验收/收口身份由主会话核实，本研究未独立读取该提交内容。

**RND-501 与 RND-504（8fa11d97）的统一基线集成是 RND-505 实施前置门。** 当前根不是可直接开始本功能的完整基线；同时必须保留根工作区已经存在的 RND-502 公式报告和 RND-503 图片组语义。RND-501 原始 renderer 文件不能整份覆盖根工作区。

RND-501 已提供“源 block → 同次最终 OOXML 对象”的可靠桥梁，但未提供通用物化 bookmark 或真实 Word 页码。`BlockRenderRecord.word_page: None = None` 是显式 v1 合同，不是待填的普通整数字段。RND-505 应以独立版本化 mapping 消费已有 trace；不得向严格 v1 模型偷偷填页码/任意新增字段，也不能回填已经选定的主件 metadata。

### 2. 文件定位

| 文件 | 作用与当前差异 |
|---|---|
| 当前 `app/services/document_ir/models.py:55` | 布局页、bbox、归一化 source_index；当前没有 typed SourceSpan/LogicalTableGroup。 |
| 当前 `app/services/document_ir/mineru_converter.py:165` | 归一化数组生成 block ID；派生 table context 使用源 block 引用。 |
| 当前 `app/services/document_ir/artifact_validator.py:62` | MinerUSourceLocator：原数组 JSON pointer、页号、页内序号、源序号、源类型。 |
| `69906a5e:app/services/document_ir/models.py:19` | typed SourceSpan、TableFragment、LogicalTableGroup；来源账本模型。 |
| `69906a5e:app/services/document_ir/logical_table_group.py:263` | 原始表格片段到渲染 owner 的来源账本构建；同模块重读校验。 |
| `69906a5e:app/services/renderer/render_plan.py:194` | build_render_plan；确定性策略、逻辑 anchor、有效输入 hash；当前根无此模块。 |
| `69906a5e:app/services/renderer/block_evidence.py:244` | provenance_for；RenderCollector / PackageIndex 保存后目标实证；当前根无此模块。 |
| `69906a5e:app/services/renderer/evidence.py:143` | 同次 result 的 binding/coverage/owner/target 验证；历史 aggregate 与完整 trace 分离。 |
| 当前 `app/services/renderer/word_renderer.py:45` | DocumentIRRenderResult 只含 content/formula_report/image_layout_report，与 RND-501 WordRenderResult 需要在统一基线合流。 |
| 当前 `app/services/renderer/image_renderer.py:82` | RND-503 真实无边框图片布局表及 cell 内目标，不能用旧 paired_tabs 采集逻辑代替。 |
| 当前 `app/services/renderer/table_renderer.py:33` | 原生表、展开表及 fallback；可见表内容继续归原 writer。 |
| 当前 `app/services/renderer/text_renderer.py:281` | RND-502 公式来源绑定和专用 bookmark。 |
| `69906a5e:tests/test_renderer_render_plan.py:37` | 确定性计划、有效配置、同次资源与并发隔离等现有测试。 |
| `69906a5e:tests/test_renderer_block_evidence.py:49` | 多类型真实目标、TOC、图片对/数学题注、页眉页脚与伪造负例。 |
| 当前 `tests/test_image_group_rendering.py:411` | 三图 cell/题注/内容表计数及报告防篡改；统一基线必须保持。 |

### 3. source span 与 stable ID 的真实能力

当前 `DocumentIRBlock.id` 是显式字符串，但 converter 用归一化数组位置生成 `block_{index + 1:04d}`（`mineru_converter.py:165-179`）；派生表格上下文使用 `<block_id>_context_<序号>` 和 `metadata.source_block_id`（同文件216-234）。因此 block ID 在固定 IR 内稳定，不保证源输入增删块或重新归一化后跨产物稳定。不能用相同 block ID 独自跨 generation/不同 IR 合并映射。

RND-501 的 `SourceSpan`（`models.py:19-28`）保存原始 JSON pointer、source_index、source_index_in_page、source_type、page_index、bbox；它与归一化后的 `layout.source_index` 明确分开，没有字符 offset、PDF 像素 rect 或 Word 页码含义。`TableFragment` 有 `block_id: str | None` 和必需 `render_owner_block_id`（同文件38-53），可表达被归并的空表片段仍指向实际输出表的 owner。

表片段稳定身份是 `table-fragment:` + canonical SHA-256(`["table-fragment/v1", content_list_sha256, json_pointer]`)，逻辑组身份是 `logical-table:` + digest(`[VERSION, first_fragment_id]`)（`logical_table_group.py:39-49`）；来源内容 checksum 与原指针参与身份，不能改为仅 block 序号。

`provenance_for`（`block_evidence.py:244-264`）默认以布局存在与否给 `legacy_layout` / `unavailable`，即便只有 block.page_index 也不自动获得 verified。仅验证通过的 `logical_table_groups` 被投影成 `verified_ir205`，聚合每个 fragment 的 typed span 到真实 owner。自由 `metadata.source_spans` 不进入 verified 投影。**现有强 source span 覆盖主要是 IR-205 表格，不是全类型块已具备统一 verified 来源。**

建议 RND-505 先保留并消费这三档来源，普通块使用现有可信 locator/布局的受控投影并标明来源质量；若要扩成全类型 verified span，应在设计中显式列明输入边界和校验责任，不能靠字段同名升级证据。

### 4. 逻辑 anchor、实际 bookmark 与对象目标

`build_render_plan` 在创建 Word 对象前检查空/重复 ID（`render_plan.py:194-200`），然后构造：

- `decision_id = "render-decision:" + content_hash(["render-decision/v1", block.id])`。
- `anchor_ref = "render-block:" + content_hash(["render-block/v1", block.id])`。
- hash 使用 UTF-8、ensure_ascii=false、sort_keys=true、紧凑 separators、allow_nan=false（同文件22-28、207-212）。

anchor_ref 只是逻辑身份，不是合法 bookmark 名的既定转换规范。`BlockRenderRecord.bookmark_name` 仅取实际 targets 中已有 bookmark 的首个名称；`WordTarget.bookmark_names` 保留全部实际名称（`block_evidence.py:31-63, 368-369`）。RND-501 并未把每个 anchor_ref 写入 DOCX。

当前根已有三类不同用途书签，RND-505 不能覆盖或改名：

| 类别 | 名称/数字 ID | 当前证据 |
|---|---|---|
| 唯一题注 | `_md2word_{figure/table}_{number}`，ID 从1起 | `image_evidence.py:53-70`；重复编号不建唯一引用。 |
| 公式 occurrence | `md2w_formula_{occurrence:06d}`，ID为1000000+occurrence | `text_renderer.py:281-310`；绑定 block/field/source hash，而非通用 block 锚点。 |
| 图片/注释 | `md2w_img_` + SHA-256(`block_id/field`)前28位，ID从2000000起 | `image_evidence.py:42-43`、`image_renderer.py:127-170`；同一图片各annotation独立。 |

通用 bookmark 的命名/碰撞/ID分配应由 RND-505 明确制定并通过真实最终 XML 校验。可用专用前缀加确定性 digest 的方案，但它在本轮仅是设计建议，不是现存合同。应扫描最终待写文档已占用名称和ID，处理模板残留及上述命名空间，不通过增加可见占位段落来放锚点。

### 5. 原生表格、图片组和嵌套目标

RND-501 的 `WordTarget` 持 `part + child_path + element_kind + role + item_index + actual`（`block_evidence.py:31-40`），`PackageIndex` 一次深度遍历真实包内 document/header/footer XML（同文件132-159）。整数路径可深入表格 cell；并非仅 body 顶层索引。路径只在绑定的 docx_sha256 下有效，任何后续插入 bookmark 都可能改变 child_path，必须在最终保存前完成物化，再统一 freeze，不能事后 patch DOCX 仍沿用旧 hash/locator。

RND-501 原生表 writer 返回多目标列表：caption/context、table、note/fallback；一个源 table 块不应被压成单一段落或假定只占一页（`table_renderer.py:73-105`，其后原生 table 目标）。表格跨多页时一个起点 bookmark 只足以定位起点，无法单凭该点声称完整页范围或末页。

RND-501 老图片策略为 `paired_tabs`（`render_plan.py:72`），其 writer 采集每侧 drawing、共享题注内 run/bookmark/OMML 子目标和实际片段范围；`_ImagePairOwnership`、`LocalImagePair` 与 `RenderCollector.freeze` 用内部不可变事实约束左右归属（`block_evidence.py:77-125,303-343`）。这些内部事实不能从待验 metadata 自行重建。

当前根 RND-503 已改为真实布局表/cell：`_image_layout_cells` 建表（`image_renderer.py:82-116`），`_write_image` 在各自 cell 放图片和全部 annotation 段落（同文件118-158）。统一基线必须让 collector 从这些实际写入点取得对象引用，保留图片/注释独立 owner。不能把布局表误归为一个内容表，也不能把整个共享布局表当成各图片相同的精确目标。

TOC coalesced 需解析真实代表（`block_evidence.py:354-363`）；superseded 页眉页脚记录有 replacement；suppressed/not_emitted 无实际目标（同文件287-301）。映射应保留这些原因，不能给它们伪造精确页。header/footer 物理 part 可被多个 section/页面复用，必须允许多候选或明确不可精确定位。

### 6. hash、generation 与旧 artifact 兼容

`RenderPlan` 绑定 input_ir_sha256、有效资源身份与 plan_sha256；资源含模板、有效配置、符号规则、Logo hash和语言（`render_plan.py:40-45,107-122`）。`BlockRenderEvidence` 再绑定 docx_sha256（`block_evidence.py:66-74`）。`validate_render_result` 重验 bytes/IR/资源/plan/内部 ownership及覆盖，不允许新 trace 不符时降级为旧 aggregate（`evidence.py:143-166`）。

这些 renderer 合同自身没有 job generation 字段；generation 由外层 result/candidate/receipt 负责。RND-501执行器在登记前完成同次验证（`execution.py:3133-3178`），候选保存 source/IR/template/retry_count（3212-3229），prepare 用 expected retry_count + IR（3231-3234）；receipt 后仅 materialize，同 generation/IR/结果ID做完成CAS（3261-3279）。当前 `DocumentJobPreparedResult` 同样含 generation、document_ir_file_id、不可替换 file descriptor（`app/domains/document_jobs/models.py:98-113`）。

RND-505 建议在 mapping 身份中显式关联源文件/IR身份、主DOCX file ID+hash、plan hash、预览派生件身份/hash和预览 generation；job.retry_count 与 preview generation 不能混用。预览生命周期、候选提交和 CAS 由主会话结合 RND-504 owner 落设计，不把 renderer 引入 job/repository 依赖。

历史兼容不能简化成“没有 mapping 就失败”：RND-501 `build_renderer_evidence(...,render_result=None)` 明确 `render_trace_status=unavailable`（`evidence.py:346-355`）；旧主件只比较稳定 LEGACY_RENDERER_EVIDENCE_KEYS 原全部23键（同模块17及`execution.py:3420`），继续做原身份/hash/保留期/归属检查，不回填 trace。当前根 RND-502/503 又有其专用新报告与历史可选摘要兼容，集成时必须保持两套已接受旧件判定，不能直接恢复早于RND-502/503的reader。

RND-505 的“允许降级”只作用于映射派生结果：缺锚点/引擎不提供位置可以最近页或 unavailable；错误主件身份、串代或已存在 trace 伪造不能降级成成功依据。缺mapping不改变内容、原完整性、发布资格或已有receipt。

### 7. 最小 RND-505 复用建议

1. 前置门固定统一基线及其回归证据，先确认同次结果同时保留 plan/block evidence/formula/image reports，正式与本地 caller 使用同一个结果。此轮不实施该集成。
2. 复用 RND-501 的原 block ID、anchor_ref、provenance、target role/item/disposition，renderer 内用真实 LocalTarget 放置通用锚点。所有非可见锚点写入在最终 save/freeze前完成，不改内容布局策略，不为旧主件补写。
3. 独立 mapping 合同记录精确命中、近邻候选或不可用及 confidence/reason；保留一对多 targets/page candidates。与 v1 的 `word_page: None` 分离，避免重定义其含义。
4. 精确物理页号必须有被绑定的实际预览/排版证据；首版可接受主会话提出的“经验证page_count + 源跨度/输出顺序”确定性估计，但字段和reason必须明确这是estimated/low confidence。源PDF page_index、LayoutPage.index、section_index、分页符或Word页号字段缓存均不能当实际预览页码。源码已明确同方向源页默认不强制Word换页，见当前`tests/test_document_ir_word_renderer_layout.py:387`。
5. 最近页只在同一已验证目标产物中选择。主会话首版方向为最近有来源输出块，再以输出顺序比例兜底；应明确距离准则、平局规则、估计公式及有界页范围，并给出不同受控reason，不能把近邻推断称为精确命中。无可用preview/page_count时返回null。输出顺序优先用同次plan.operations/最终body targets，不能以IR.order替代实际双栏/图片组顺序；跨part的child_path不能直接全局排序。跨表多页只给估计起点，不能推出全部范围。
6. 来源置信度与目标定位置信度宜保留分项或合成原因：verified表来源+真实锚点定位、legacy布局+真实锚点、近邻推断是不同证据。成功映射不是视觉或发布质量判定。
7. 完整 source/block/target trace仅在受控载体；公开诊断仍投影计数、状态、受控reason和必要身份，不回显原文/路径/自由metadata。保持现有授权和下载边界，不增加三栏前端。

### 8. 最小测试建议与现有证据

本轮仅定位测试并阅读断言，**没有运行测试**。既有已验收结果不代签未来统一候选。

| 范围 | 可复用现有测试 | RND-505 新断言 |
|---|---|---|
| 稳定ID与重复调用 | `69906a5e:tests/test_renderer_render_plan.py:37,62,121,136` | 同IR重复产生相同锚名；不同产物hash不可混用；并发无共享计数；模板既有书签不冲突。 |
| 真实所有者 | `69906a5e:tests/test_renderer_block_evidence.py:49,99,115,172` | 保存后真实XML中锚点配对、唯一、目标role正确；不漏空段/公式/多item；嵌套cell、共享段落左右不串。 |
| 当前图片组 | `tests/test_image_group_rendering.py:411,479,499,596`，`tests/test_document_ir_word_renderer_layout.py:346` | 三图及每图多注释分别定位；布局表不增加内容表；保留RND503专用anchor/report验证。 |
| 来源账本 | `69906a5e:tests/test_renderer_block_evidence.py:258` | 空片/跨页表source spans指向真实owner；自由source_spans不能升级verified；legacy缺bbox/页号可读。 |
| 多页/归并/装饰 | `69906a5e:tests/test_renderer_block_evidence.py:81,217,244` | 跨页表只支持起点时显式降级；TOC指代表；复用页眉页脚不伪单页；suppressed无精确命中。 |
| 降级 | 无现成页映射测试 | 部分锚丢失、全部无锚、重复/歧义、非单调页、源页不等Word页、无可信邻居、最近距离平局；confidence/reason确定。 |
| 身份与恢复 | `69906a5e:tests/test_renderer_block_evidence.py:272`及既有result persistence测试 | 主DOCX/IR/plan/preview hash错绑、旧preview generation不得安装；只映射失败不改变主job发布资格；旧artifact无新字段不回填不重渲染。 |
| 产物不变性 | 原RND501结构parity、RND502/503报告负例 | 加锚点后移除新增非可见bookmark的规范化OOXML对比，内容/段落表格结构/尺寸/样式保持；真实引擎样本页数/可见布局另记证据。 |

先做纯映射与实际OOXML目标定向测试，再按统一基线和本任务implement.md规定的门禁验证。若未来宣称bookmark→真实预览页，需要真实引擎证明；首版采用主会话确定的页数/顺序估计时，测试只证明公式、身份、有界性与降级合同，不代签物理分页。fake provider仅证明接口/失败降级，OOXML本身不证明Word动态分页，不启动未授权外部服务或安装Office。

### 9. 主会话最新首版方向的兼容性核对

主会话在研究中明确首版：复用anchor_ref、新建实际通用block bookmark；mapping作为`word-preview/v1` manifest内可选版本化`page_mapping`，不加file type/DB/state/API；由已验证preview.page_count和来源/输出顺序给低置信估计，不扩展sandbox exec、不做PDF文本匹配或LLM。此方向不要求修改`BlockRenderRecord.word_page=None`，与renderer边界相容。manifest reader/存储/CAS的具体兼容由预览专项核实，本报告不宣称已通过。

补充验收约束：单页preview可证明有真实body target的块只能位于page0，但不能将suppressed/not_emitted变为精确目标，也不能提升来源span的真实性；coalesced要解析真实代表，页眉页脚是重复part，不宜直接混入body比例。给定N页和T个实际有序候选，比例公式、T=1、N=1、空target、稀疏源页、多源表片归一owner、跨section及边界clamp都要有固定示例。不存在足够证据时，估计存在也不表示质量或发布通过。

## Related Specs

- 当前 `.trellis/workflow.md`：研究落盘、任务规划与实施门分离。
- 当前 `.trellis/spec/backend/index.md`、`quality-guidelines.md`：真实结构和可见内容证据；本地最小定向检查与线上门禁分开。
- 当前 `.trellis/spec/backend/word-generation-rules.md`：源事实与Word策略分离、分页/表格/字段、RND-502及RND-503专用报告及历史兼容（664、716起）。
- 当前 `.trellis/spec/backend/document-job-mode-contract.md`：generation、结果身份、当前发布/交付边界。
- `69906a5e:.trellis/spec/backend/render-plan-evidence-contract.md`：计划/同次trace/真实target/旧aggregate/安全投影。应在统一基线形成正式可读取Spec；当前根未具备。

## External References

无外部API建议或未核验引擎能力声明。本研究依据本地实现与主会话导出的已验收源码；Word/LibreOffice bookmark保留、页定位API及版本兼容由预览专项研究提供证据，未在此假定可用。

## Caveats / Not Found

- RND-501 69906a5e源码已读，f51edf7e未独立导出核验；验收身份与统一分支结果须由主会话记录。
- 当前根存在RND502/503，但无RND501 render_plan/block_evidence模块；根工作区的同名render_to_result不等于已集成RND501。
- 当前可见IR-205强来源跨度不覆盖全部类型；不能宣称全链精准source mapping已经具备。
- 通用bookmark命名/位置策略、页候选及confidence合同尚待本任务设计决定；本研究不给像素级分页承诺。
- 未运行代码、单测、真实Word/WPS、预览引擎或生产验证；未读取implement.jsonl/check.jsonl；未修改业务/Spec/其他任务，未执行Git操作。

## 2026-10-24 独立审查后的修订2约束

指定69906a5e源码核实：block_evidence.py:19、50–63为封闭Reason与v1记录；240仅提取target后代书签；evidence.py:207–219限定图片targets类型/role/数量，282–284固定bookmark_name为后代去重首名。drawing同段的marker并非drawing后代，模板同名也不能证明本次创建。修订2保留上述原语义，增加同次collector创建的独立可选block_anchor_evidence，通过原主件登记链固定；preview只消费认证证明。当前根execution.py:3307的黑名单尚不包含新键，实施必须精确补全公开出口剔除；B1保留、绑定、隔离及三恢复入口为新写入前门。以上是规划，不是现有能力或验证通过声明。
