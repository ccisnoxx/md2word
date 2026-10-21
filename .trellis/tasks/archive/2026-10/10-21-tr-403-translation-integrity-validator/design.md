# TR-403：回填前完整性技术设计

2026-10-21 人工验收完成：用户已接受实现、测试证据和残余风险，确认限定 commit plan 并授权当前任务提交/归档。最终状态 done/implemented，收尾见 [closeout](closeout.md)；下文规划/实施记录保留各自历史时点，不再表示待验收。不 push、不开始后续任务。

2026-10-21：用户已批准 revision 3，当前实现与本地验证已完成；以下现状/方案保留规划时点。实际接线、source IR 创建代次与消费代次的兼容区别、P2 修正及未验边界见 [实施验证](implementation-validation.md) 和 [实现复核](implementation-review.md)。未扩大原 AC 或相邻任务范围。

## 1. 现有实现和目标边界

调查基线为 c8fd2af（md2word/TR-402），不是所有父任务子项已整合的发布候选。证据见 [current-state.md](research/current-state.md)。

| 当前 owner | 真实行为与差距 |
|---|---|
| document_ir_translator.py:114–154、:519–528 | 同步深拷贝、拆批、调用 Provider、比较 ID、累计 replacements 后 apply；未 encode/decode/技术对账。 |
| protected_tokens.py:214–293 | 已有 collision-safe encode、逐 item 次数/归属检查和非递归 decode；不检查新增裸技术片段。复用，不复制正则。 |
| provider.py:219–270 | 可容忍 Markdown/外层自由文本；item 会 str/strip；不符合固定 id/text、禁止修正的目标边界。 |
| execution.py:1154–1277、:1553–1576、:1655–1728 | Worker 独立调用和验证，结果先落盘后 fan-in；loader 只合并 items，不核对完整性 evidence/来源 envelope。 |
| audit.py:61–170 | ai-call-log/v1 元数据审计与可选全文 debug；没有完整性码/类别/结论。 |
| formal_mineru_conversion.py:71–107、:220–305 | 本地响应按 dict 覆盖、过滤并重排成请求顺序；导出的源文计划与实际请求不是同一编码边界。需要最小适配。 |
| files/service.py:375–428、:771–807 | 每次分配新 file_id，但 key 仅含 tenant/job/type/filename；S3 put/local replace 可覆盖同名对象。记录级 CAS 发生在对象写入后，不能保护字节。 |
| translation/models.py:199–238 | TextItem 与 Provider Request/Result 默认 dataclass repr 含正文、译文和 Prompt；新增结果 repr 隐藏不能替代既有 DTO 的表示控制。 |
| document_ir_translator.py:85–93、:310–320、:398 | 真实术语匹配生成 _TermMatch.context_snippet，再原值传给 trace；该上游 frozen dataclass 也默认 repr。仅隐藏下游 trace 会遗漏该正文上下文载体。 |

目标为 ADR-008 和 translation-design §7/§11：同一正式链路内，代码拥有技术完整性，不靠 Prompt 自觉。保留现有模块化单体、提取/回填、批次仓储和 Artifact；不创建第二套流水线。

## 2. 唯一 owner 与内部接口

- protected_tokens.py 继续拥有类别、检测规则、跨度、占位符、ledger 和恢复。需要检测技术 inventory 时复用 encode 的 occurrences，不拷贝正则、不调用 legacy runtime 的 protect_text。
- 新 integrity.py 拥有 TranslationIntegrityValidator、稳定错误码及不可变 evidence：验证 envelope、调用 Codec、恢复后 inventory 对账、生成安全摘要。它不调用 Provider、数据库、文件或 apply_replacements。
- document_ir_translator.py 拥有原文批次→编码/匹配术语→Provider request 的准备过程和预算，以及中间匹配载体 _TermMatch.context_snippet 的字段级 repr 控制；同步/Worker 共用该准备过程及 Validator，移除原有 ID-only 校验分支。
- execution.py 仅适配批次调用、错误映射、已验证结果落盘和 fan-in gate；不重构其调度、lease/CAS 或主任务终态。
- audit.py 复用现有 recorder，在 ai-call-log/v1 增加可选 integrity 摘要；不新建审计基础设施。
- files/service.py 是生成件物理身份的唯一 owner：在新生成件 key 中使用本次登记的 file_id，而不是让翻译各入口自行拼唯一文件名。此最小共享修正也作用于共用该方法的 direct 生成件，仅改变新对象的 opaque key，不改变上传、转换或结果选择合同。
- translation/models.py 仅承担正文 DTO 的字段级 repr 控制，不新增字段/类型/序列化转换，也不改变快照内容。

拟定核心内部合同（非 HTTP API）：

~~~python
TranslationIntegrityValidator.validate(
    source_items: tuple[TranslationTextItem, ...],
    encoded_batch: EncodedTokenBatch,
    result: TranslationProviderResult,
) -> ValidatedTranslationBatch
~~~

ValidatedTranslationBatch 含全部恢复 items 与 TranslationIntegrityEvidence；文本成员不进入默认 repr。失败抛 TranslationIntegrityError（ValueError 子类），只含稳定 code、安全 message 和同形 evidence，不提供 partial replacements。Evidence 不含 ledger；Provider Request/Result 不添加原文映射。整批成功后才按本地预期 ID 构造 dict。

已有 build_provider_request 的内部调用方很少，可改造成返回 request/EncodedTokenBatch 的准备接口，统一真实生命周期；不保留“无 ledger 时跳过验证”的兼容默认值，不增加纯转发 wrapper。最终函数命名可随现有代码风格确定，以上输入输出和所有权不可省略。

## 3. 数据流与验证顺序

~~~text
源 IR（只读）→ 现有稳定 ID 抽取
→ 按实际编码成本确定完整有序 Provider batch
→ encode 原文；ledger 留在本次调用内存
→ 从未保护的原文跨度匹配术语；构造 encoded request
→ Provider JSON/DTO shape 校验
→ ID envelope → codec metadata 对账 → decode 整批
→ 按原 item 比较恢复后的技术 inventory
→ 全部成功：恢复 items + evidence
   同步：所有批次通过后一次 apply
   Worker：成功 batch result（恢复文本+evidence）→ 当前 generation fan-in gate → 一次 apply
失败：安全错误与 evidence → 原有失败通道；无可消费 replacements
~~~

顺序固定：

1. 校验本地源 ID 唯一、batch 来自该有序源输入（可用确定性 encode 的 envelope/ledger 一致性检验），拒绝错配的 metadata；不信任任意重建 ledger。
2. Provider JSON 必须是约定的对象与 items 数组；item 仅 id/text 字符串，ID/text 非空，不做 str、strip、排序、补齐、忽略字段。非约定包装文本/额外字段/重复 JSON key 不修复。保留字符串原字符，仅用非空白判断拒绝空值。
3. ID 按 duplicate → missing → extra → order 的固定优先级报首个确定错误；计数可一并汇总。错误仅引用本地预期 item 序号/ID；恶意返回 ID 不直接写异常或审计。
4. 用既有 decode 验证语法、归属、每次出现及次数；源占位字面量合法，恢复只一次，不能再对恢复文本执行占位符解码。
5. 源 batch occurrences 与对恢复 items 重新 encode 得到的 occurrences，逐 item 比较 Counter((kind, original_text))。因此已保留占位符之外新增裸数字、数量单位、地址、位字段、公式、型号仍失败；同值重复按次数比较，禁止只比集合或全批总量。
6. 所有检查完成后才返回 ValidatedTranslationBatch；校验时不得逐 item 更新外部 dict。一个失败 item 不会改动源输入、其他 item、ledger 或已经验证的其他批次。

技术保持以 TR-402 已接受的有限识别语法为边界，包括其单位/符号/URL/邮箱/版本/信号等类别；不宣称解析任意自然语言公式或识别任意型号。复用同一检测器保持保守拒绝，不用 Unicode/空白/单位规范化放宽。若翻译文字变化使邻接类别改变，必须显式拒绝并保留类别/计数证据，不能猜测等价。同 item 内 Token 语序移动可通过，参数语义关联正确性仍需人工复核。

## 4. 编码预算、术语与 Prompt

### 批次与预算

现有同步按源字符拆批，Worker plan 按源页/字符拆批。改为共同的确定性预算规则：候选有序 batch encode 后的 text 字符总量不超对应 max_chars，item/page 限制仍生效。namespace/ordinal 必须在最终实际 batch 上生成；估算后若边界变化须重编码确认，禁止直接裁断 item 或复用父批 ledger。单 item 编码后超限：Provider 调用前报 translation_request_budget_exceeded；不追加无限拆分/模型降级。预算为现有 items text 字符限额，不声称是含 Prompt/glossary 的 tokenizer 总 token 上限。

plan/record/API 的既有 char_count 保持源文本字符统计语义，不借类型相同悄悄改变公开字段含义；预算切分独立使用实际编码成本，integrity 摘要明确记录 source_char_count/encoded_char_count。本地 v2 请求可显式增加 encoded_char_count；审计 request.char_count 继续统计实际发送 items。不改持久化字段形状；已存在批次不重写，执行时按对应 Profile 限额重新检查实际编码成本，超限明确失败，不静默加大预算。

### 术语

在原始 items 上按既有最长/优先级匹配，但排除与 protected occurrences 相交的匹配；合法自然语言术语保留原 source offset/trace。仅将未保护跨度命中的术语注入 glossary，避免技术型号/单位映射与保真冲突；不向 glossary 放 ledger 或生成 placeholder，不实现术语后验 QA。

### Prompt 快照兼容

四份 seed 仍点名 PH_###，en2zh 允许 PACKAGE 内自然词变化，ru2zh 允许部分单位本地化；这些低层提示不能覆盖冻结技术完整性要求。沿用现有 _system_prompt 的“绑定正文校验后追加运行协议”方式，追加固定、带版本的完整性协议，明确 MD2W_PT_v1 占位符逐项原样保留、不生成新的技术值，不改已绑定正文、Prompt ID/hash、published seed/Profile。

Evidence 记录协议版本与追加片段 SHA-256；原 prompt_content_hash 继续表示原快照，不伪称有效完整 Prompt hash。公式/单位已被编码，Provider 没有原值可本地化；返回不合法仍由代码拒绝。无需新配置键/feature flag；rollout 的开关是建议，当前并不存在。技术内容丢失直接 fail-closed，不能提供绕过验证的 flag。

## 5. 稳定错误与 batch evidence

| 条件 | 计划机器码 |
|---|---|
| 本地源输入/错批 ledger | translation_integrity_invalid_input / translation_integrity_metadata_mismatch |
| DTO shape 不合法（含 fake Provider） | translation_integrity_invalid_response |
| ID 重复/缺失/额外/顺序错误 | translation_integrity_item_duplicate / item_missing / item_extra / item_order（均带 translation_integrity_ 前缀） |
| 占位符缺失/重复/未知/错 item/损坏 | translation_integrity_placeholder_missing / duplicate / unknown / wrong_item / malformed（统一前缀） |
| 恢复后技术 inventory 不一致 | translation_integrity_technical_mismatch |
| 活跃 fan-in 缺失/不匹配证据 | translation_integrity_evidence_missing / evidence_mismatch（统一前缀） |
| 单项或既存批次编码后超限 | translation_request_budget_exceeded |

Provider JSON/传输错误保留 translation_provider_invalid_response / translation_provider_truncated / translation_provider_failed；原 shape 异常需带安全诊断元数据，不能因转换异常而泄漏返回值。JSON 截断仍按既有策略拆批，完整性异常不伪装成截断。

同步外层仍抛 DocumentIRTranslationError，但保留结构化 cause/code/evidence；Worker 先识别 TranslationIntegrityError 再走通用 ValueError 映射，不能全部压成 invalid_response。现有 error_code 是字符串，不扩展 HTTP ApiErrorCode 或改变顶层 translation_failed。当前重试上限、call budget、split、主任务失败策略保持；重新请求不是自动修复，任何新响应仍须完整验证。

对外部 Provider 抛出的任意异常，调用边界使用固定错误描述及允许的类型/状态/usage/hash 元数据，不直接把 str(error) 或异常链写入普通审计、job event/log。仅截断或替换已知 Prompt 字符串不能保证脱敏；内部 cause 可保留用于测试追踪，但不序列化正文或打印原异常链。

安全 evidence schema 采用 translation-integrity/v1，内容包括：

- validator/codec/instruction 版本；status、stage、error_code、checked/failed item count。
- 预期/实际 item count，source/encoded/response/restored 字符计数及规范化 JSON SHA-256；不存在的响应/恢复阶段用 null，不伪造通过。
- 分类 Token 的预期/实际计数；必要时仅本地预期 item ID/序号与差异计数，不保存 original_text、placeholder→原文表或恶意响应值。
- batch_id/root/parent、attempt、generation、source_document_ir_file_id/source checksum 和已有 Profile/Prompt/term hash，由调用方补充绑定；纯 Validator 不查询仓储。

复用 ai-call-log/v1 的可选 integrity 字段、失败 error.code 和 batch.error_code；每次真实 Provider 调用只生成一份成功或失败审计，验证失败也算失败调用。Provider 前失败只记已有批次失败事件/evidence，不伪造 AI 调用。审计写入失败不能被吞掉后继续标记成功。

## 6. Worker 成功 Artifact 与最后一道回填门

translation-batch-result/v1 保持 items 为恢复后的文本，增加可选 integrity envelope；新 reader 对活跃 fan-in 要求其存在且通过。Artifact 完整文本属于已有业务中间结果，不是普通审计；不把 ledger 写进去。

落盘前验证成功；成功登记及 fan-in 消费前重读当前 job 并核对 generation，继续使用现有 status/generation CAS。Fan-in 加入以下局部门：

- 仅处理当前 job.retry_count/generation 的成功叶子；不改变旧 generation 的业务状态，不把旧结果纳入当前目标。
- 从本地 batch、job 和 source IR 获得权威预期，核对 Artifact 的 job/batch/generation/source 引用、文件 checksum、完整有序 ID、evidence 版本/通过标志、源 items hash 和恢复 items hash；不能仅凭 payload.status=passed 自证。
- 对加载后的恢复 items 再按该 source 子集做技术 inventory 比较；合并时拒绝重复、缺失和额外项。旧/缺少证据的中间结果拒绝用于新回填，不给历史结果补写“已通过”标记。
- 所有叶子通过后才 apply。源/目标 IR、batch result 和 DOCX 的新登记对象须先具备下述独立物理路径，再按现有 job/batch CAS 绑定。CAS 仅选择当前记录，不能作为共享对象字节的隔离手段；CAS 失败时不能影响胜出或历史对象。

这些是数据消费边界检查，不更改“最终失败主任务如何 failed/blocked”、重试/lease 所有权、跨服务事务或新 generation 编排。不能据此宣称修复了所有既有并发窗口；如实现需要改变 CAS/锁/仓储 API，停止扩大并先重新评审。

### 生成件唯一物理路径（architect P1 修订）

当前错误前提是“新 file_id 等于新物理文件”：_generated_object_key_for 不使用 file_id，同名目标 IR、DOCX 或同 batch 不同 attempt 的 JSON 都会复用路径。旧执行即使重读 generation，仍可在重读后暂停，等新代结果登记后覆盖字节，再在 CAS 失败时留下已被破坏的新代对象。

最小方案在 FileUploadService.register_generated_content 已分配本次 file_id 后，将它交给既有 _generated_object_key_for；新生成件逻辑路径采用：

~~~text
document-jobs/<safe tenant>/<safe job>/<safe file_type>/<safe file_id>/<safe filename>
~~~

- 沿用既有 file_id 的唯一身份分配，不再引入第二个随机 ID、工厂、开关或翻译专用存储 wrapper。新记录不得复用另一登记的 file_id/key；安全路径片段和 S3 prefix 继续由现有 owner 规范化。
- 跨 generation、同批不同 attempt、同 attempt 重复投递后的不同登记均由各自 file_id 目录隔离；只追加 generation/attempt 不能隔离同一次尝试的迟到重复写。generation/attempt/source/hash 仍在既有记录 metadata/evidence 绑定，不以路径字符串替代归属验证。
- register_generated_content 的外部调用签名和 original_filename 不必改变；_generated_object_key_for 的内部参数增加 file_id。下载展示名继续用原 filename，用户仍只有 CAS 选中的一份主 DOCX；不同物理对象不等于多主输出。
- 此规则适用于该共享方法后续登记的生成件，覆盖 source DocumentIR、translation_batch_result、目标 DocumentIR、generated_word 及现有审计生成件；不改源 PDF 上传 key、Provider、bucket 选择、读写适配器或默认后端。不按类型留下可覆盖的翻译旁路。
- 文件写入仍先于记录绑定；文件写入/登记失败不得被当成成功。被 CAS 拒绝的执行只可能留下自身未选中的新对象，按既有保留/清理机制处理；不得立即删除胜出文件、搬迁历史对象、追加补偿事务或重构 lease/CAS。
- 读取、签名下载、保留/删除均按记录中的 object_key，不从新模板推导历史路径。历史记录/key/字节原样保留，新旧布局可共存，无 backfill 或 DB 迁移。

AC11 的最低证据不是“生成了新 file_id”，而是实际读回两个不同登记的字节/hash：新代胜出后恢复旧代写入并使旧 CAS 失败，新代和历史对象均不变；同批同 generation 的迟到旧 attempt 也有该断言。这里只保证现有 CAS 已拒绝的迟到写不覆盖对象，不声称解决 CAS 本身全部并发/lease fencing 问题。

## 7. API、DB、前端、迁移与本地适配

| 边界 | 影响 |
|---|---|
| OpenAPI | 不增路由/DTO；既有批次 error_code 只增加字符串值。须验证快照不漂移，不手改生成 JSON。 |
| DB/仓储 | 不增表列/索引，不 backfill，不改 repository 协议、原子性或 schema bootstrap；复用现有 batch/error 与 document_files metadata。 |
| Artifact storage | 新登记生成件的 opaque object_key 增加 file_id 层，local_file/local_object/S3 共用同一安全 key owner；上传 key、历史记录与字节、original_filename、读取/下载权限和保留规则不变。 |
| 内部 DTO | 仅 repr 隐藏必要敏感字段；dataclass 字段、实际值、相等性、序列化与快照 hash 均不变。 |
| 状态机/权限 | 保留当前 checkout 的阶段和终态；不顺手接 CON-102、QA 或 TR-406。owner/admin、download/review/publish/available actions 不变。 |
| 前端 | 无改动；已有失败码按通用错误展示，不增加前端发布资格推断。 |
| 幂等/并发 | 编码纯确定性、ledger 每次调用新建；保留重复投递/lease/CAS；不以占位编号作为跨 batch/attempt 唯一业务键。 |
| 不可变 | 不改变已发布文件、既有 IR、Prompt/Profile/term 快照或审计。新生成件按 file_id 唯一物理路径登记，现有 CAS 只绑定记录，二者共同防止迟到写覆盖当前或历史字节。 |

正式本地 adapter 通过同一 Service 得到相同验证。必要的 scripts/dev/formal_mineru_conversion.py 适配仅限：导出真实编码请求批次、严格读取有序响应且禁止 duplicate/extra/强转/重排、复用同一计划而非第二套预算。导出格式版本化为 document-ir-local-translation-request/v2，不静默改变 v1 的源文本含义；按旧 v1 源文手填的技术响应不自动改为新占位符，需重新导出/提供符合当前请求的响应。无 Token 文字仍能通过；旧文件不修改。补 focused 测试与本地工具说明，不扩展矩阵或离线翻译产品。

历史已完成 IR/DOCX 和审计仍可读/下载，旧 reader 可忽略可选字段；活跃旧中间结果缺证据时安全拒绝，允许通过既有人工重试/新任务重新运行。滚动部署应先暂停翻译入队、排空旧 Worker/活跃旧代、同步部署调用端与 Worker，再恢复；不允许新旧 Worker 交错产生被当作合格的新结果。此为上线约束，本会话不部署。

### 正文 DTO 与中间匹配载体的默认表示（architect P2 修订）

将 models.py 的必要字段及 document_ir_translator.py::_TermMatch.context_snippet 纳入精确写范围，优先用现有 dataclass 的 field(repr=False)；不使用 asdict 删除字段、业务值替换、定制序列化或通用脱敏框架。

- TranslationTextItem：隐藏 text；id 也可能来自未经验证的 Provider 响应而夹带正文，不在默认 repr 回显。诊断若需要 ID，只通过安全 evidence 使用本地预期 ID。
- TranslationProviderRequest：隐藏 items、system_prompt_markdown、terms、term_traces，阻止嵌套正文、Prompt、术语上下文绕过。TranslationProviderResult 隐藏 items。
- TranslationPromptSnapshot 隐藏 markdown，使其直接 repr 或经 TranslationProfileSnapshot.prompt 嵌套表示时均不泄漏 Prompt；TranslationTermMatchTraceRecord 隐藏正文 context_snippet。其余不承载正文的配置字段保持原表示，不对整个翻译资源域做无关清理。
- _TermMatch 在 document_ir_translator.py 内将 context_snippet 设为 field(repr=False)，覆盖真实匹配过程生成对象的直接 repr 及列表等现有容器的嵌套表示；不能仅隐藏下游 TranslationTermMatchTraceRecord。匹配区间、排序、去重、术语注入、上下文实际值和向 trace 的原值传递不变，不改该 frozen/slots 载体的字段或业务语义。
- 新增 ValidatedTranslationBatch、异常、evidence 与现有 Codec ledger 继续遵守原隐私合同。安全 repr 是默认诊断保护，不能替代日志边界脱敏，也不能把 dataclasses.asdict/vars 的真实正文输出当作“已脱敏”。

AC12 用互不相同的合成源文/译文/Prompt/context/恶意 ID 标记直接检查上述 DTO、嵌套 Profile 和新结果的 repr；同时检查实例字段和现有 dataclass 序列化仍包含原值、相等性/冻结行为及 Prompt 内容哈希不变。测试不能通过清空正文或只检查新增 evidence 来获得通过。

残留 P2 的定向测试位于 tests/test_translation_integrity.py：用真实 TranslationTextItem、TermVersionSnapshot 和可发布的普通术语条目，经请求准备过程调用真实 _match_request_terms；源文在术语附近带独有合成正文标记，术语本身及 ID 不带该标记，且样本文字不含技术 Token，避免保护跨度过滤使测试空跑。在 _select_non_overlapping_matches 或 _build_trace_record 的既有边界用只观察并转调真实方法的 spy 捕获实际生成的 _TermMatch，不替换匹配、上下文截取、筛选、去重或 trace 构造逻辑。

该用例须证明至少一次真实匹配，独立断言捕获对象的 context_snippet 和返回 trace.context_snippet 均保留预期原文标记，返回术语及匹配位置仍正确；repr(match)、repr([match]) 和返回 trace 的直接/嵌套 repr 均不含该标记。读取真实字段及 dataclasses.asdict 仍得到原上下文，并沿用上述相等性/冻结断言。当前默认 repr 应令该用例因泄露而失败，不能以未匹配、只手工构造 _TermMatch、mock context 返回值或仅测下游 DTO 获得通过。此测试不调用 Parser/Provider/网络，不引入新公开 API 或术语后验规则。

## 8. 安全、隐私与可观测性

- 本轮零外部调用；未来实现测试用 fake/mock 和现有公开 fixture。无需新供应商、授权数据或新增依赖；真实 Provider 仍沿用现有显式配置，不读取/展示 secret。
- Ledger 只在当前函数调用内存，生命周期随请求结束；不得持久化或在默认 repr/traceback 中打印原值。URL/公式均作文本，不请求 URL、不执行公式。
- 默认审计只有哈希、计数、版本和本地标识。恶意 ID/响应、模型异常中的全文不得经 error_message 进入 job event/log；新异常使用固定中文消息，保留安全元数据。
- 正文 DTO 的 repr 规则覆盖复用对象、上游 _TermMatch 与嵌套 Prompt/context；Artifact 物理身份不依赖用户 filename，不能用重命名或覆盖历史 key 来规避不可变性。二者不增加查看全文的权限或新的 debug 出口。
- 现有 Admin debug 仍默认关闭、短 TTL、按既有授权访问；记录实际编码请求/原始响应，不新增原文映射转储。debug 中出现占位符是实际调用事实，不伪装成恢复后的译文；规范源/目标仍来自各自 IR。
- 本地请求导出仍是显式文件输出，可能含未保护自然语言；不把“技术占位”宣传为全文匿名化，不默认新增全文 trace/report。
- 不增加 metrics/dashboard/全文 debug 新入口；机器码和摘要通过既有 artifacts/events 关联定位。

## 9. 风险与回滚

主要风险是遗漏 Worker/本地入口、Codec 以外新增技术内容漏过、重检测邻接误报、编码字符膨胀、术语覆盖技术片段、错误码被通用异常吞没、fan-in 消费错代/缺证据结果、共享物理路径覆盖和既有 DTO repr 泄漏。由 implement.md 的 AC1–AC12 定向测试及候选独立只读复核覆盖；修订规划不等于这些实现风险已关闭。

本任务不能以关闭 Validator 或恢复未验证回填作为安全回滚。实施回滚点为暂停翻译入队/沿用现有 disabled Provider 关闭翻译执行、撤回本任务代码后只恢复经安全评审的执行版本；direct 可继续服务。无 DB 逆迁移；保留新旧审计和结果，不覆盖已发布文件。规划回滚只移除本次新增文档、manifest TR-403 增量和父 children 链接，不回退原有 dirty。

共享生成件路径修正与 DTO repr 控制可以单独保留，不得因撤回 Validator 而恢复固定路径覆盖或默认正文 repr。回滚仍按记录读取新旧 object_key，不搬回旧目录、不删除未选中对象以外的数据；若必须回退文件服务旧写策略，先停止相关生成件写入并重新评审，不能让并行 Worker 重新覆盖已登记对象。

停止条件以 prd.md §8 为准；若需要新增开关/快照字段、改变冻结规则或仓储并发协议，先更新三件套并重新评审，不能实现后补授权。
