# RND-503 技术设计 v2

> 2026-10-23，规划评审稿。全新 architect 独立审查后，主会话核实并修订两项 P2：非 IR 渲染输入绑定、兼容回退构建。基线、当前实现位置和实际探针见 [调查](research/current-state.md)，审查与修订见 [planning-review.md](planning-review.md)；需求及不变量见 [PRD](prd.md)。本稿不授权实现。

## 1. 基线与责任边界

当前 HEAD=1835263，最终接受 IR-204=17cde1f 尚未集成。实施前须以获授权的依赖集成结果重新核对 IR-201 原始输入安全、IR-204 caption 来源与不确定证据、当前 RND-502 公式报告、TR-406/CON-104 结果身份合同。只移植已接受依赖，不在 RND-503 修复/扩展依赖，不覆盖共享文件。若合入后接口实质变化，更新三件套并重新提交规划评审。

依赖集成验收必须分别覆盖原 IR 缺验证字段、字段显式 None、原始 IR 已有非空验证/回执但旧 reader 当时忽略的形态，以及旧 evidence 已保存非空摘要的形态；三种恢复入口均保持原文件证据语义和必要键。IR-204 固定新增 None 键与旧 metadata.get() 的缺键结果相等，本身不是确认缺陷；非空形态是需构造的兼容验收输入，不宣称已有生产记录。集成不能把所有旧件重解释为最新摘要，也不能删除旧必需字段或把校验失败改为成功；无法闭合时先停在依赖集成门，不转为 RND-503 重做依赖。

保持现有模块：

| owner | 职责 |
|---|---|
| `document_ir/caption_reconciler.py`（接受依赖） | 题注语义、可靠边界、重关联与来源；RND-503 只消费 |
| `renderer/layout_plan.py` | 唯一图片几何组判定，产生不可变的单次图片布局计划与受控拒绝原因 |
| `renderer/image_renderer.py` | 读资产、按有效宽度/比例插入 inline、创建图片布局表格、逐图注释；不再次猜组/绑定 |
| `renderer/word_renderer.py` | 现有页面/section 编排与单次 RenderContext；消费图片计划，返回同次 bytes/公式/图片报告 |
| `renderer/evidence.py`、`docx_quality.py` | 从最终 IR、计划、资产绑定和实际 OOXML 交叉校验；布局表格分类和安全摘要 |
| `docx_rules/terminology.py` | 为实际生效的格式规则提供最小冻结/重放入口，复用既有顺序、匹配和作用域，不改变翻译 owner |
| `document_jobs/execution.py`、本地 formal adapter | 报告接线、登记前/恢复验证和事件投影；不实现图片算法或新状态机 |

不新增 service/port/策略注册器/配置中心字段或依赖。新的少量 frozen dataclass 放在现有 layout owner；普通正文栏与数据表 writer 不被替换。替代当前 `_split_two_column_image_rows()` 与制表位图片 writer，删除失去调用者的对应图片 helper，不留第二套分组规则。

## 2. 确定性图片计划与阈值

规则版本为 `image-group/v1`。阈值是本规划的可评审工程选择，尚非真实样本校准结论；实施若需调整，修改同一 owner、边界测试及本稿，不能按型号特判或悄悄放宽。

### 输入边界与源顺序

只处理最终 IR 的 body image（chart/figure 已由 converter 映射为 image）。按 block.order 的稳定源序列扫描，同页连续图片构成候选 run；非图片块、页/真实 section 边界中断 run。有效 source_index/IR-204 locator 用于溯源，不能拿 bbox y/x 重建源阅读顺序。两个 order 冲突或页/layout page 不一致时拒绝归组，不能用 ID 排序掩盖异常。

v1、缺页/布局/尺寸及单图保持顺序兼容；孤立单图记正常 single，不制造 grouping warning。多图候选缺必要几何时标记不确定。来自历史外部 Artifact 的 bbox 必须为有限数，且 0≤x0<x1≤page.width、0≤y0<y1≤page.height；无效几何只禁用并排，不修订源坐标。

### 同排判定（全部成立）

设 page.width=W，page.height=H，每图高度 hi、中心 cyi：

| 项目 | v1 接受条件 |
|---|---|
| 行交集 | `common_overlap = min(y1)-max(y0)`，`common_overlap / max(hi) >= 0.80` |
| 高度一致性 | `min(hi) / max(hi) >= 0.80` |
| 中心对齐 | `(max(cyi)-min(cyi)) / min(hi) <= 0.10` |
| 顶边偏移 | `(max(y0)-min(y0)) / H <= 0.015` |
| 横向分离 | 源顺序必须与 x0 严格递增一致；相邻 `next.x0 - prev.x1 >= 0` |
| 横向间隔 | 每个相邻间隔 `/ W <= 0.08`；整个组在页面边界内 |
| 最小成员 | N≥2，不假定只存在左右两图；每个成员只属于一组 |

阈值等号接受，超出拒绝，不增加没有证据的 epsilon。比较保持原浮点值，只有 OOXML 长度落盘时舍入。

### 唯一归组与拒绝

先按纵向条件在候选 run 内建立可能同行关系的连通分量。对每个分量重新检查全组共同交集/中心/高度/顶边条件；不能只凭相邻 pair 成功而传递合并。分量不是全组一致时整个竞争分量顺序单图，不挑某个贪心子集。独立的其它确定行可以保留。

分量成员必须在源 run 中连续且源序与横向序一致；不接受 column-major 数组经过全局重排形成 row-major。各行保留原源序，不能在不确定时按 y 排队。跨越非图块/正文 region 或真实 section 的组拒绝；纯图片连续 span 可以作为原子图片单元渲染，不吞并旁边正文。

新图片计划作为现有 LayoutPlan 的**附加图片决策**：不为新 writer 变更旧 LayoutPlan 的 aggregate 字段含义、排序算法或历史恢复默认结果。writer 从常规 region 消费中抽出候选源连续图 span，一次消费组或顺序单图；其余内容继续既有 COL-001/002。这样既避免新组被旧 y 排序拆散，也避免恢复旧 DOCX 时因新 region 数量而误判历史证据。

caption 不用于猜测几何。IR-204 对成员有 uncertain、未解候选/共享题注竞争，或仅有 external paragraph 的 evidence-only 关系而不能在不搬段落的前提下绑定时，拒绝并排。历史 IR 无回执可使用现有每块 annotations，但不宣称重新校验/修复了其语义归属；全局 caption_binding_uncertain 无法定位到具体块时，对本次候选保守拒绝。正常多 caption/footnote 本身不是拒绝理由。

原因使用固定枚举：`geometry_unavailable`、`geometry_invalid`、`page_or_section_boundary`、`source_order_conflict`、`row_alignment_insufficient`、`horizontal_overlap`、`gap_too_large`、`competing_row_membership`、`caption_binding_uncertain`、`external_caption_binding`、`asset_unavailable`、`image_size_unfit`。单图无需不确定原因。为避免多算法，writer 只可因实际资产/尺寸不可用将已确认组降为 single_sequence，不能临时重新分组。

## 3. 无边框 Word 布局表格

每个确认行单独生成 1×N Word Table，组 ID 由规则版本、页及有序 block ID 的稳定 hash 派生，不使用随机 ID/时间。table.autofit=False，tblLayout=fixed；显式 tblW、tblGrid、tcW，总宽不超过当前有效内容宽度。外侧四边及 insideH/insideV 均显式 nil，覆盖模板样式继承；无填充、tblHeader 或浮动 tblpPr。

表格宽按源组 bbox union/W 映射到当前有效页/栏宽；各列按源宽和相邻间隔中点划分 slot，margin 在 slot 内承载半间隔，所有 slot 宽之和等于表格宽，间隔不得重复相加。每张图 width 限于 cell 内宽，height 由原图片尺寸等比得出，仅一个统一比例，不分别拉伸宽/高。横向/纵向图、嵌套当前栏和非默认模板页宽都要实测。原图字节直接嵌入，不 OCR、不重采样、不翻译。

复用已安装 python-docx 的图片解码及现有 InlineShape writer，不引入 Pillow 等新依赖。写入 wp:inline，沿用 doNotAutoCompressPictures。cell 的 section 宽度不能靠 `_content_width_and_columns(cell)` 的默认值推测；root document、有效宽度和单次 context 显式传到图片 helper，公式来源始终绑定真实 block/field。

cell 顶对齐：图片 paragraph → captions 原顺序的独立 paragraph → footnotes 原顺序的独立 paragraph。metadata.caption 兼容别名及已接受的去重方式复用唯一 annotation owner，不复制 raw evidence 原文或把独立 paragraph 再渲染一次。统一注释遍历保留字段路径（captions/i、metadata/caption、footnotes/i），不再依赖 `annotations[0]`。同一串合法注释的既有来源/次数合同不可因新 cell 去重被削弱。

图片及其后续注释链 keep_with_next，最后一条不连接下一图组；行加 cantSplit，不设置精确 row height、不把多行图组一起锁为一页。没有注释时不跨组 keep。超出单页的图片按可用宽高同比收缩，若组无法在有效尺寸约束下输出，则整组单图并记录 image_size_unfit；不增加估算全书页高/字体排版引擎。超长注释最终分页仍须 Word 人工验收，不承诺 OOXML 属性可保证客户端绝不拆页。

读图缺失/损坏时不留下半张布局表格：进入组前完成本组资产解码/尺寸准备，失败整组按源序单图。missing/invalid 单图显示已有可见诊断并输出全部 caption/footnote；最终 expected inline count/源资产门禁仍失败，不能登记缺图成功主件。意外 I/O/异常继续抛到原 stage 分类，不 blanket catch 成空图。

## 4. 图片报告和最终证据

### 同次输出与事实来源

`DocumentIRRenderResult` 在现有 content/formula_report 之后增加兼容默认值的 `image_layout_report`；`render_to_bytes()` 仍返回同一核心的 bytes。新正式调用将同次图片报告传入 `build_renderer_evidence(..., image_layout_report=...)`，不改变公式报告合同。

报告 schema=`image-layout/v1`，记录规则版本/阈值、源 block ID/page/order/bbox、判定指标/拒绝原因、实际 mode、组 ID、table marker、cell index、inline/annotation bookmark、asset_ref/已加载图片 SHA-256、annotation 源 field 和源/预期可见投影 hash、实际宽高，以及下述不可变 `render_inputs` 与其 hash。图片 checksum 与 IR 资产已有 checksum 匹配时必须核对；历史资产没有 checksum 时仅证明本次 loader→嵌入字节一致，不把它描述成外部资产身份已认证。正式文件仍使用既有 file_id/owner/checksum 来源，不能以新报告替代文件授权。

marker 使用 Word tblCaption 的内部前缀及确定性组 ID，drawing/bookmark 使用稳定 block/field ID；不把原文、路径或技术参数写入 marker。每张图和 annotation 有独立实际位置，重复相同图片或相同注释不能只按 hash 猜 block。

### 生成时输入与投影版本绑定（P2-1）

仅最终 IR 不能确定 caption 的可见投影或实际宽度。新报告的 `render_inputs` 使用 `image-render-inputs/v1`，由既有配置加载 owner 在写 DOM 前固定实际采用的值，不另建资源版本系统、数据库实体或外部上下文服务：

- 固定 `image-group/v1`、`image-annotation-output/v1`、writer/相关文本语义版本和文档语言；投影版本包括当前 caption 标签/SEQ cached result、普通文本归一化、符号替换、富文本与数学分段的解释，不能随当前默认实现静默变化。
- 保存所用模板版本身份（正式任务须与外层 generated_word metadata 的 template_version_id 一致）、模板 DOCX/config 的原始内容 hash，以及实际生效的最小几何/annotation 配置快照。符号规则单列实际加载内容 hash，不以运行时绝对路径作为身份；不能假设 subscript_config_path 已经是任务版本快照。无外部文件的本地调用显式记 builtin/source kind、实现版本和生效值，不能把缺输入默认为某个当前模板。
- 对注释投影，快照只使用当前格式规则的白名单规范化字段：有序 enabled 规则的 pattern/replacement、regex flags、apply_scope 及影响执行次序的值；不存任意 YAML、路径、Settings、翻译术语、Prompt 或凭据。读取端从该规范化快照重放实际适用于 annotation 的规则，不读取当前设置文件。不新建另一套替换算法，复用现有规则语义；实现时在现有 owner 形成最小可序列化输入，避免复制 parser。
- 对每个图片 span，固定写入前实际采用的页面方向、页宽高、边距、栏数/间距和有效宽高。首次检查按这些输入及源 bbox 重算 slot/尺寸，再独立读取 DOCX 中该 span 所属 section 的实际属性、table/cell 和 inline extent 对照。DOCX 提供 actual 几何，不能反过来从最终 section 生成 expected。不从全书当前最后一个 section 猜每个 span 的栏宽。
- 保存规范化输入的 canonical hash 并绑定同一报告；首次登记同时核对外层原始 IR/file/template/generation 身份、实际加载输入与报告。首次 writer/checker 共享同一份冻结输入，不重复加载可能变化的运行时文件；生成后输入和报告进入同一个不可变 candidate descriptor/receipt，不允许晚到 worker 修改胜出上下文。

历史重验读取**原文件**的 render_inputs 和原始 IR，从源 annotation+该版本格式规则重建 expected，再从实际 OOXML 提取 actual。当前默认模板、模板指针、语言默认值或符号文件改变不得改变既有文件的验证结果。报告里的 expected hash 只作为被比对的写前结果，不能代替源与冻结输入重算。原模板/配置内容 hash 用于追溯；恢复使用已冻结的最小有效值，无需重新打开原临时路径或依赖原资源继续可下载。

render_inputs 缺失、版本未知、规范化输入 hash 不符、原文件身份不符或必要配置无法重放，均按新报告损坏失败；禁止套当前配置、只信 expected hash 或回退 legacy。无图片报告旧件不要求补此快照，保持原有公式报告/aggregate 恢复合同。

### 独立核验

evidence 从权威最终 IR、冻结 render_inputs 和相同版本纯计划重建期望成员/模式候选，严格校验报告版本、覆盖、唯一消费和允许的尺寸/资产降级。实际包解析独立读取 table/cell、关系目标、wp:inline、图像字节、annotation bookmark 范围与内容/字段顺序。几何计划不可替代实际 writer evidence；writer 报告也不可自证。

注释预期投影在写 DOM 前由源 annotation 及冻结版本的 semantic/格式规则/field 输入确定，验证时再从同一源和冻结输入重建，最终 XML 只生成 actual；不从输出自身生成 expected hash。复用 RND-502 已有数学投影/来源验证，保证 cell 中的相同公式仍按正确 field 登记。图片互换、caption 互换、漏 footnote、伪 marker、多 marker、多图/漏图、w:anchor、图宽超 cell 均拒绝。

### 表格分类与旧指标

`docx_quality.table_count/table_shapes` 继续描述原始 DOCX 全部表格，`expected_table_count` 继续为 IR table 数，既有 `table_count_delta` 原始差值也保留，不能悄悄重解释历史值。新报告分支增加 expected/actual layout_table_count、content_table_count、expected_total_table_count 及相应 delta；只有通过上述成员、内容和结构核验的标记表格才能计入 layout。完整性要求 content count=IR table count，total=content+verified layout，且每个 layout 与预期图片组一一对应。不以简单 `actual>=expected` 或“带 marker 即豁免”替代门禁。

standalone analyzer 可识别候选 layout marker 并保守从“数据表带来的可编辑性”中剔除，输出候选计数；它不认证图片绑定。正式 evidence 传递已核验分类并拒绝未解释 marker。纯图布局表格不能仅因 w:tbl 存在就获得 editable_content_available，wide/table-header 等内容表指标也不能被布局表格虚增。无报告、无 marker 的历史文档保留旧 evidence 字段集合及严格旧校验。

### QA、隐私和持久化

报告/安全摘要追加到既有 generated_word metadata，不新增独立 Artifact 种类或数据库实体。完整报告不复制文档正文/原图/绝对路径；render_inputs 的必要格式配置值属于私有证据，按原文件 owner/Admin 授权访问，不投影任意配置或凭据。ordinary events 只投影 `image_layout_summary` 的版本、accepted/single/uncertain 数和 reason counts，有界 examples 至多40项并给 omitted count；配置快照、逐图报告不自由展开进事件或 API。router 白名单保持，现有 quality_flags 可显示普通 uncertainty。

多图拒绝新增 `image_group_uncertain`；已有 caption_binding_uncertain 保留。它是非阻断质量 evidence，不自动提升/降级未知质量、复核或交付状态。本任务不新增统一 QA 聚合、QualityRun、发布资格或前端计算。确定性差错进入 blocking_quality_flags/既有完整性异常；新报告损坏不得删字段回退 legacy。

## 5. 数据流、恢复与并发

MinerU 唯一入口 → 已接受 IR-201/IR-204 → 最终 IR（direct 或既有已验证翻译结果）→ 原 LayoutPlan + 图片计划 → 同次 writer/context → bytes/formula_report/image_layout_report → 最终 OOXML/evidence → 原 candidate → 原 first-valid receipt → 物化/完成。

新报告验证扩展现有三恢复入口的共享报告校验责任，必要时将 `_validate_formula_result_file()` 改成准确覆盖多报告的名称，不增加纯转发 wrapper：

- legacy 无指针发现：沿用同代/最终 IR/唯一性、有效期、checksum 条件；有任一图片报告字段必须完整重验。
- 明确历史 result_file_id：以**该文件原始 IR**重验，不能用当前代 IR 解释旧件，沿用允许的历史跨代指针行为。
- prepared receipt：仅物化/完成同一选中身份，重新读取实际字节核验；损坏保留 receipt/候选及审计，不能换同代主件。

缺新报告旧件保持旧恢复字段和布局解释，不能因部署新图片分组器自动重排或回填旧报告。新字段存在但版本未知/缺配对摘要/校验失败则明确拒绝；报告与 DOCX 标记不一致也拒绝。三个入口共用相同边界，不只测正常首次渲染。

首次与三个恢复入口使用相同的源+冻结输入验证责任；明确历史指针跨代复用时，render_inputs、模板身份与投影版本同样跟随原文件，不把当前 job 的配置或本代输入导入旧报告。新输入缺失在登记前归 quality_checking/render_failed，已保存件损坏在恢复时归 uploading/oss_failed；正常 generation/receipt 竞争仍按原 CAS 语义返回权威结果。

所有 collector/已消费集合/asset 准备仅属于单次 RenderContext，不写 renderer 实例或全局。原子条件、generation、最终 IR、receipt ID、review/result hash 与不可变文件 descriptor 均沿原合同。渲染/读对象/OOXML 检查在 job 锁外；本任务不改锁、事务、仓储写协议或 file/sqlite/MySQL DDL。迟到 worker、取消/重试竞争继续返回原权威状态，不能把新报告的失败用于覆盖胜出结果。

## 6. 模型、API、数据库与兼容影响

| 边界 | 影响 |
|---|---|
| DocumentIR | 无新增必填字段/block type/v3；source metadata 不改、不把 Word 决策持久化回 IR |
| 内部 Python 合同 | Layout owner 增加图片计划；现有配置 owner 形成最小冻结输入；单次 result/evidence 携带可选图片报告及输入绑定，相关正式调用者同步 |
| OpenAPI/前端 | 无端点/响应 schema、generated types、路由/query key 改动；普通已有 flags 可能出现新机器值 |
| DB/迁移 | 无 DDL/backfill/新状态列；沿既有 file metadata payload 保存增量证据，不修改仓储 |
| 状态/权限 | 无模式/stage/角色/下载/批准/发布规则变化；blocked/unreviewed 内部下载及禁止批准发布保持 |
| 配置/外部系统 | 无新配置/feature flag、Provider、OCR、网络调用、付费模型或预览实现；沿固化模板与符号规则 |

配置中心/已发布模板 seed 不可原地改写。已有 SEQ/REF 更新后跳号风险不在本任务修复，必须在验收中单列；图片绑定仍以 block/field evidence 为准，不能靠更新后显示数字猜图。

## 7. 风险、回滚和停止点

1. 依赖/共享文件：当前未集成 IR-204，RND-501 规划也触及共享 owner。实施前基线硬门，变更后重评当前三件套，不提前实现其它任务。
2. 误分组：v1 阈值保守，真实图高差异可能被拒绝，这是允许的安全顺序回退；不能为了覆盖率放宽到当前仅纵向相交的规则。
3. Word/预览差异：nil borders、固定宽度、cantSplit 仍需真 Word 和已部署预览验证；长注释/行高度不由纯 XML 证明。
4. 元数据兼容：新增报告与旧恢复字段严格分支；丢字段不能成功降级。若实施不能在现有合同内保留历史读行为，应停止并补设计。
5. 回滚分清开发差异基线和可部署回退构建，具体合同如下；不能仅排空当前队列后回到不识别新图片文件的执行器。

### 可部署回退构建（P2-2）

- **B0：开发差异基线。**指获授权依赖集成后的实际 HEAD，用于明确哪些 diff 属于 RND-503。尚未生成任何新图片产物前可撤销开发 diff；B0 不是已有新图片候选/receipt/历史文件后的安全部署版本。
- **B1：兼容回退构建。**保留 image-layout/v1、image-render-inputs/v1、marker 与经核验的 layout/content 分类、投影版本 reader、三恢复入口、RND-502 公式/receipt 接线、安全摘要；生成侧仅使用已存在的顺序单图 writer。实施时记录实际构建/commit/hash和恢复证据，不能把尚不存在的B1写成已完成。
- 新报告的冻结输入携带代码构建确定的生成策略身份：正常构建为 grouped/v1，B1 为 single-only/v1。B1仍产出同一图片报告，只将新生成件的图片按源序单图写入；验证该原始策略及完整性，不把明确单图策略伪装成几何不确定。不是任务参数、配置开关、前端入口或第二套转换链。首次登记核对当前构建策略，历史重验消费文件原策略，故B1仍严格接受合法grouped/v1旧文件。
- 产生新图片产物后，只能回退生成侧到B1，不能卸载 reader、报告/输入版本解释或恢复接线，不能清理、改写旧报告或强制重新渲染已有主件。暂停/排空在途工作仍需执行，但不能替代未来明确历史指针、跨代复用和receipt恢复兼容。
- 上线新生成侧前，应对B1运行新 grouped 报告的legacy发现/明确历史指针/receipt恢复、原文件上下文在当前配置变化后的恢复、旧公式报告恢复及损坏拒绝测试；记录结果。没有该兼容构建证据时不得宣称回滚就绪。

规划回滚仍只撤销本次明确文档、RND-503 条目和父 children 新链接，保留原 dirty。B1不回第二解析链、截图正文或放宽表格计数；不覆盖发布件，所有版本均受原权限/状态规则约束。

PRD 停止条件全部适用；无需数据库破坏迁移、专有原图或外部服务选择。合成/已接受去标识 fixture 足以实施范围内算法；缺真客户端仅限制视觉结论，不允许虚报通过。
