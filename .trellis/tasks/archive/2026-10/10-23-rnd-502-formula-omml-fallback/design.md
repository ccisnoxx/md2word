# RND-502 技术设计

版本：2；2026-10-23；仅规划，未授权实施。独立审查发现与主会话核实见 `planning-review.md`。

## 当前实现和真源

当前 HEAD=`c56e12832ff30212cc067d0909430cf5f091f79b`，分支=`codex/pre-rnd501-local-wip`。建议实施分支 `md2word/RND-502` 只记录，本轮不切换。工作区原有 302 项暂存删除、5 项未暂存修改及未跟踪任务目录；只修改本子任务、父任务 children 关系和 RND-502 manifest 条目。

正式链路为 MinerU→DocumentIR→`DocumentIRWordRenderer`→renderer evidence→选定 receipt→主 DOCX。在线 owner 是 `app/domains/document_jobs/execution.py`，本地 owner 是 `scripts/dev/formal_mineru_conversion.py`。`semantic_text.py` 是共享规则兼容导出，不能再建立第二套解析器。

已有 `_OmmlParser` 和 shared text path 可复用。当前失败路径重新调用 `normalize_formula_text`，没有结构化失败原因；`_render_mixed_math` 看见 frac 就把整段解析为公式；caption 先归一化，table HTML 先术语替换；parser 会吞掉 tag，扩大裸上标参数、压缩 text wrapper 的空格。完整事实、探针和测试见 `research/current-state.md`。

现有 `build_renderer_evidence` 只统计一般 OOXML/残留，不做公式出现次数对账。`blocking_quality_flags` 是致命完整性异常，不能把普通降级 warning 塞入该列表。当前 execution 完成不聚合公式质量，四状态与 `quality_summary` 容器已经存在，不需要新表或列。

## 目标边界和责任

| Owner | 本任务职责 |
|---|---|
| 新 `app/conversion/docx_rules/formula.py` | 统一数学片段识别、支持子集解析和明确结果。迁移现有有限 OMML parser，不另造 TeX 引擎或通用 AST 框架。结果区分 `omml`、`semantic_runs`、`text_fallback`，失败只用允许枚举 reason。 |
| `text_renderer.py` | 按原 DOM/run 顺序写普通文本和公式；数学片段先识别后决定解析/降级，公式不经过 terminology。保留普通文本样式、SEQ/REF 和引用边界。 |
| `table_renderer.py` | 继续原生表格和现有 span 路径，只将 cell/annotation 的内容送到共享入口，移除会先改写公式的整表术语预处理；普通文本替换只做一次。 |
| `mineru_content.py` / `mineru_converter.py` | 仅修必要的 semantic inline/annotation 边界保留；不在 extraction 阶段把公式提前压平成普通文本，不改变 ID、order、layout、HTML span 或翻译 Token 规则。 |
| `document_ir_translator.py` | 在现有翻译准备/回填 owner 内复用数学边界：明确数学 DOM 子树不抽作普通 text node；其余数学片段检查现有 Codec 覆盖，不能安全保护时在调用前拒绝。保持非数学正文单元和回填索引，不修改 Codec、Provider 或术语策略。 |
| `word_renderer.py` | 单次调用持有公式诊断，复用已有 `_RenderContext` 生命周期；不在 renderer 实例或全局存 collector。 |
| `docx_quality.py` / `evidence.py` | 校验实际 XML 锚点、输出模式和出现次数；输出版本化私有报告与安全摘要，区分受控原式和未登记残留。 |
| execution / formal adapter | 消费同一次渲染的 DOCX 与报告，保存不可分离的候选元数据；事件只输出安全摘要。 |
| `result_state.py` | 在现有同 job 锁内完成结果绑定时，从已选 receipt 派生公式摘要，合并既有摘要且不提升质量；不扩展 generation/receipt 协议。 |

`text_semantics.py` 的现有 legacy API 继续可用；正式数学路径不再依赖会删边界/改值的普通文本归一化。只调整与当前公式验收直接相关的映射或导出，不改 legacy 编排。

## 数学识别和保真规则

1. block 公式、MinerU 明确 semantic formula 是强数学信号；inline 支持现有 `$...$`、`\(...\)`，并明确处理 `$$...$$`、`\[...\]`、`<eq>` 边界，不能全局删除 dollar/backslash。
2. HTML 先按 DOM 识别文本、上下标、样式和数学片段，再写 Word；不能把含标签的整段送给 OMML。混合正文分数不把自然语言一并吞入数学对象。
3. 既有无分隔符的简单变量/上下标和已知 TeX 符号，仅在证据充分的片段内识别；金额、UNC/文件路径、普通 underscore 标识符不靠宽泛“有反斜杠就是公式”规则判断。
4. 保留原式；只进行已证明语义等价的输入修复，例如当前已知命令双转义折叠。text/mathrm 中显式文字空格、数字顺序、符号、上下标作用域、公式编号均不可因预处理消失。
5. 无花括号的上下标遵循当前支持的明确 token 语法；原标准输入 `x^2+3` 的加法在上标外。对有歧义的 MinerU 扩展写法使用受控降级，不能猜测技术含义。既有提炼公式矩阵必须保留通过，任何必要语义修正同时补精确结构断言。
6. 现有矩阵内合法简单 `\tag{...}` 保留数学主体 OMML，并在原位置输出可见编号；不新增公式自动编号体系，不把已支持主体整体降级来绕过矩阵回归。畸形或更复杂且不能安全表达的 tag 才整式降级。`\vee` 使用正确等价符号或整式降级，禁止成功输出错误字母。

## 翻译准备边界（P1 修订）

共享数学扫描结果同时供 renderer 和翻译准备消费；不能只在渲染时识别 `<eq>`，却让 translator 把其内文作为裸文本发送。当前 `_append_table_text_nodes` 无差别抽取所有非空 DOM text node，Codec 不识别 `<eq>`，这是已复现的改值路径。

- converter 对其本来就组装的 plain rich formula 保留完整原式，并使用现有 Codec 可识别的数学分隔符；不改写表格 raw HTML 的标签、span 和来源事实。
- 对表格 HTML 中明确数学容器（此次包括 `<eq>`）的整个数学子树，translator 不生成可翻译目标，所有后代文字/样式保持在原 DOM。遍历时仍按原来所有非空 text node 的次序递增 index，避免后续普通正文 ID/回填位置偏移；`apply_replacements` 只更新已有目标，不碰数学节点。
- 对普通文本单元内的数学片段，现有 `$...$`、`$$...$$`、`\(...\)`、`\[...\]` 继续由原 Codec 整体保护。用共享扫描的源 span 对照其实际保护覆盖，不以“一个技术 Token 都没找到”当作公式安全。普通正文不因同 cell 出现公式而整格跳过翻译。
- 对跨 HTML text node、无法完整纳入数学子树或原 Codec 覆盖的已识别数学片段，在翻译准备阶段拒绝本次调用；不得自行拆散公式、遗漏相邻正文、临时添加不可追溯占位符或扩大 Codec 规则。内部码为 `translation_formula_boundary_unprotected`，使用固定中文描述及位置/计数等安全摘要，沿用现有 `DocumentIRTranslationError` 和顶层 `translation_failed`。同步、Worker、本地 fake 入口均在 Provider 前检查；execution 在既有失败事件的 `formula_protection` 安全子对象保留内部码/计数，不伪造 Codec integrity passed、batch 或 AI 调用日志。
- 已安装根计划和同代批次 ID 不重写；现有 Worker 会重建 expected plans，抽取差异必须按既有树/来源合同失败关闭，不向缺失 item 静默填原文。部署前排空相关在途翻译或保留兼容执行器；不匹配旧代保留账本，只有合法的新代重建计划，不回填历史目标 IR 或发布件。无需新 DB 字段或 feature flag。

这是一处当前公式任务必需的最小 translator 接线，不承接 annotation 翻译覆盖、TableContextBuilder 或其他翻译 backlog。不改变 TranslationTextItem/Target DTO 和批次持久格式；数学目标的排除可能改变旧计划 item 集合，按上一条处理在途兼容。若实现证明还需改变已有单元/批次持久化合同，先修订规划重新评审，不在本任务暗中扩大。

## 降级合同

| 情形 | 输出 | 诊断/错误 |
|---|---|---|
| 支持结构且完整消费输入 | 原位置 OMML | 正常公式回执 |
| 明确 semantic sub/sup | 原生 Word run | 正常 semantic 回执，不是未知公式降级 |
| unknown command / malformed / unsupported structure / 无法证明保真 | 原位置提示 + 原始文本 run | `formula_text_fallback` warning，reason 分别为 `unsupported_command` / `invalid_syntax` / `unsupported_structure` / `unsafe_normalization` |
| 源数学内容为空 | 不伪造空公式 | 既有 Source→IR 完整性错误；直传 IR 的空公式显式失败 |
| 新渲染的输出缺失、锚点/输出绑定不符 | 不登记最终主件 | quality_checking 的既有 `render_failed` 完整性错误 |
| 已选 receipt/历史新报告在恢复时损坏 | 保留选择与诊断，不换件 | 既有 uploading/`oss_failed` 恢复错误，不重新渲染以掩盖 |
| 文件/XML/存储程序异常 | 不转换为文本降级 | 保持原阶段错误映射 |

受控原式必须直接用 literal Word run 写入；不再走 BeautifulSoup、公式归一化或符号替换，`<`、`&` 等由 XML writer 转义。提示文案不参与源内容哈希。暂不使用图片：当前 formula block 并没有正式登记图片资产，新增裁图/TeX subprocess 不必要且会扩大范围。

## 数据流与结果接口

```text
源 IR（语义、原式及 HTML 保留）
 → 同一个公式识别/解析入口
 → 单次 RenderContext：DOCX + formula report
 → 实际 OOXML 公式锚点/回执对账
 → metadata 私有逐公式报告 + 安全 formula_summary
 → 既有候选/receipt（generation + 最终 IR + 文件/hash）
 → 同锁完成主件绑定并合并公式质量摘要
```

内部新增 `render_to_result(...) -> DocumentIRRenderResult(content, formula_report)`，现有 `render_to_bytes(...) -> bytes` 保持参数和返回兼容并委托同一实现。该兼容入口有现存大量测试/调用者，不形成第二个渲染核心。正式在线和本地调用改为消费 result；无独立“重新解析渲染一遍生成报告”的流程。

私有报告标识 `formula-render/v1`，每次出现记录 block/子位置（list item、cell row/column、annotation index、DOM/text span、occurrence）、源原式 SHA-256、mode、稳定 reason、唯一 Word bookmark anchor、`output_projection_version` 和 `expected_output_sha256`；不记录原式全文或临时路径。锚点采用与源内容无关的确定性 ordinal 名称，例如 `md2w_formula_000001`，不会暴露源标识。报告在 generated_word 的既有 metadata 内保存，保留现有认证访问边界。

`build_renderer_evidence(..., formula_report=...)` 对新报告检查 schema、IR 源公式哈希、锚点实际存在且唯一、输出模式、expected/actual 次数及逐式预期输出绑定，不把 parser 声称成功当作 OOXML 已写入。bookmarks 不改变可见排版，公式计数包含重复出现；不套用“一个 OMML 等于一个 IR formula block”的错误计数。

预期绑定在 FormulaRenderResult 确定后、写入 document DOM 前计算，不能从最终实际 XML 自己生成“预期”再比较自身。固定的 `formula-output/v1` 投影保留有序的值与语义结构：text_fallback 包括完整原式字符及可见提示；semantic_runs 包括文字和上下标属性；omml 包括数学节点、参数次序、数学语义属性和值，以及 tag 的可见编号。排除 namespace 前缀、bookmark ID、rsid、段落/表格容器和非语义字体尺寸等易变样式；不得排除数字、脚本位置或显式数学样式。

最终 analyzer 从匹配 bookmark 的完整范围重建同版本投影并比较 SHA-256；这拒绝相同 anchor/mode/count 下的改值、上下标错位、原式截断及提示遗漏。源哈希和输出哈希一同归属不可变候选描述。该机制验证预期转换结果是否完整写入最终字节，不证明 parser 本身数学语义正确；parser 的 tag/作用域/符号等仍由精确语义测试保护，不新增 TeX 解释器。

`formula_summary` 只含 schema、公式/OMML/semantic/fallback 次数、warning code/reason count 和非可逆报告哈希。现有 `quality_checking`/`file_registered` 事件不能展开私有逐式报告；对其 metadata 展开位置做定向安全投影，同时移除 `docx_quality.latex_residue_examples` 的原式出口，保留既有计数/flag 和非公式事件合同。不给普通日志或异常塞原式、文档正文、绝对路径或任意命令文本。

这里“私有”表示同 tenant/company 的 owner/admin 可读取的内部文件 metadata，不表示服务器专有或新增隐私权限。现有 `/files/{file_id}` 会返回完整 metadata；本任务保留其授权边界，报告不得放原式全文。任务文件列表继续使用现有安全摘要白名单；不为报告新增公开查询端点。

## 模型、API、DB 和前端

- DocumentIR 保持 v2 和现有字段；原则上只保留原式/边界，不新增 mandatory IR 字段。不引入 Word 对象到 IR。
- DocumentJob、prepared result、file metadata、`quality_summary` 已有 JSON 容器，新增公式子对象为 additive，不新增文件类型、数据库表/列、状态枚举、环境变量、配置开关或依赖。
- OpenAPI 不新增 endpoint/typed field，`quality_summary` 为现有 `dict[str, JsonValue]`；快照预期无 schema diff，仍须执行 export/release 检查。没有新 publish/quality/review API。
- 前端零代码变更；沿用后端质量/下载/available actions，完整审核体验留在 QA 任务。本轮 DOCX 内的降级提示和既有事件摘要提供可见性。
- `result_state.patched_job` 仅在完成且绑定当前选定 receipt 时，从其报告摘要合并 `quality_summary.formula`；锁内读取既有质量，不覆盖别的摘要键。pending/blocked 保持；passed 遇 warning 降 warning；不自动 approved/ready_to_publish。
- file/sqlite/MySQL adapter 复用共用纯 owner 与当前状态列投影，验证其往返，不修改 schema 或迁移/backfill 历史任务。

## 兼容、幂等、并发与不可变

- 老 `render_to_bytes` 调用继续可用；新增上下文状态只活在单次 render 内，shared renderer 并发不串报告。
- 新结果把 DOCX、报告、源 IR 指针和 retry_count 一起写入候选，选定 receipt 后只使用该候选；不能从某个迟到渲染的内存报告更新获胜结果的质量。
- 完成状态/公式摘要在既有同 job 条件更新内原子绑定；保持 CAS、timeout/cancel 优先、新代隔离、first-valid-receipt 和不可变文件身份。
- 老文件无 `formula-render/v1` 时沿用旧 evidence 重算与逐项相等路径；不得给旧 evidence 添加默认公式字段后误判不一致。absence 仅代表历史无报告，不代表公式已通过新验收。
- 新标记一旦存在即严格验证，损坏/缺失必要条目不能落回 legacy。新增文件正常恢复时从已存候选报告及实际字节重建核验；旧 `_get_existing_result_file` 的 hash/size/owner/IR/期限验证全部保留。
- 恢复入口逐一落地：无明确指针的 legacy 扫描保留原有唯一性、checksum 和 evidence 逐字段比较；明确历史 `result_file_id` 保留当前允许跨代复用的身份/期限规则，不能强制历史文件等于当前代 IR/generation，也不把旧报告导入当前代质量摘要；已有 receipt 的恢复核验该选定描述和对应字节，不能仅修改 legacy 扫描分支。新报告的源绑定始终属于该文件原来记录的 IR，恢复时不能用当前代 IR 重新解释历史结果。
- 新报告的输出绑定校验及必要文件读取在 job 锁外完成；成功提交仍用既有 generation/最终 IR/receipt 条件，锁内只消费已经选定且版本有效的安全摘要。恢复损坏沿原 uploading/oss_failed 收口，保留 receipt/历史件；老文件无报告不伪造新报告或改变既有成功恢复合同。
- 已发布件不重新生成或补写 metadata；新 renderer 只作用于新任务或合法 retry generation，不回写历史批准、DOCX 或审计。

## 安全、外部边界和可观测性

不执行 TeX、shell、宏或任意 HTML；不下载公式图片、不增加 AI/网络调用。沿用 MinerU 和 Artifact 路径校验。公式文本按数据转义，不转换为 Word 指令或外链。预期解析失败用固定枚举，内部未知错误显式传播。report 只在授权内部产物可读，public event/日志只用汇总；哈希不能视为可匿名发布的许可，不向外部发送。

## 迁移、回滚和相邻任务

无 DB 迁移或历史回填。回滚撤回本任务公式渲染/证据/接线增量并保留新字段、已生成 DOCX、receipt 和审计，不做清理式回滚，不把表格改为图片。回退版本必须认识并保留既有 receipt/原子写合同，以及其继续处理的新公式报告/抽取计划版本；未证明兼容时先暂停 DocumentJob 消费和内联执行，排空或切到兼容执行器，不以“旧 reader 忽略新字段”承诺可安全处理新在途任务。

若 RND-501 后来先落地，实施前协调 `word_renderer.py`、`evidence.py`、execution 和 formal adapter 的同文件改动，复用其已接受的 result/context/report owner；不得在本任务预先引入 RND-501、IR-205、TAB-301 业务或覆盖 TR-402/403/406、CON-104 合同。需要改变本设计结果接口或验收边界时重新评审。

本轮没有必须用户先选择的外部系统或阻塞性产品冲突；本方案及 warning 文本降级政策由本次规划评审整体确认。实现后的数据/并发/权限接线需独立只读复核，不能把本轮规划通过当作实施安全证据。
