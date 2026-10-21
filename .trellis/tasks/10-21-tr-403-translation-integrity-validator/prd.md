# TR-403：TranslationIntegrityValidator 需求与验收

2026-10-21 人工验收完成：用户已接受实现、测试证据和残余风险，确认限定 commit plan 并授权当前任务提交/归档。最终状态 done/implemented，收尾见 [closeout](closeout.md)；下文规划/实施记录保留各自历史时点，不再表示待验收。不 push、不开始后续任务。

## 1. 目标与业务结果

在正式 DocumentJob/DocumentIR 翻译的任何译文回填前，确定性核对 ID、占位符、数字、单位、地址、位字段、公式和型号。模型篡改必须被拒绝，不能变成技术参数错误的目标 IR/DOCX。Operator/Admin 可通过既有批次诊断及脱敏审计定位失败，不必查看全文。

2026-10-21 实施状态：用户已明确批准 revision 3 并授权实现；实际分支 md2word/TR-403，已准确 start，完成停 manifest=review/Trellis=in_progress。以下“当前事实”和规划修订记录保留原调查时点，不代表仍未授权。范围和 AC1–AC12 不变，实际证据见 [实施验证](implementation-validation.md) 和 [实现复核](implementation-review.md)。不提交、不 push、不 archive，待人工验收。

## 2. 身份、依赖与当前事实

- 发布阶段：R4（翻译完整性）；父任务：datasheet-docx-delivery-quality。
- 子任务：.trellis/tasks/10-21-tr-403-translation-integrity-validator。
- 建议实施分支：md2word/TR-403；本轮实际分支 md2word/TR-402，HEAD=c8fd2afc7dfea349b7fbc3e1f516d85adcb57536；未切分支。
- 2026-10-21：TR-403 原为 todo；唯一直接依赖 TR-402=done/implemented，归档 task.json=completed，closeout 有人工验收，工作提交 24ed6a717ca86cf5ed086f2eda58030e4af66810 是当前 HEAD 祖先。
- 正式 translator 只比较 ID 序列，Worker 有独立调用入口；integrity.py 尚不存在。TR-402 Codec 已实现，但未接线，也不拒绝“合法占位符之外额外添加 999 V”的响应。
- Provider 解析会强转和 strip ID/text；既有审计只有通用摘要，没有完整性结论。源码锚点、只读反例和 35 项基线见 [调查证据](research/current-state.md)。存在真实实现差距，不建议 skipped_existing。
- 首次 fresh architect 规划审查确认 P1（生成件新 file_id 仍复用物理路径）和 P2（正文 DTO 默认 repr 与排除 models.py 的写范围冲突）；revision 2 的 fresh 复审确认 P1 已在规划覆盖，P2 仍遗漏上游 _TermMatch.context_snippet。本次 revision 3 只补这一残留规划，决定和证据见 [审查修订记录](research/architect-review-revisions.md)；本版尚未再次独立复审，不代表业务实现已修复。

## 3. 范围与要求

R1：复用已有 Codec，给每个实际 Provider 请求绑定原始有序 items、编码 items 和仅内存的 ledger。把 codec metadata 与 Provider result 逐 item 对账，保持 ID 数量、集合、唯一性及顺序；不得强转、裁剪、排序、补项或忽略额外项后宣称通过。

R2：所有占位符必须属于原 item、恰好出现一次，未知、缺失、重复、损坏、跨 item 移植均失败。通过后一次非递归恢复，再按相同检测规则比较逐 item 技术片段多重集，拒绝新增、丢失、替换或次数变化，包括“占位符完整但额外注入裸技术内容”。不做单位本地化、OCR 修正、公式改写或模型输出自动修复。

R3：失败原子性以实际 Provider batch 为单位：一个 item 失败，该批次没有任何可消费 replacement，也不登记成功 batch result。同步入口不得调用 apply_replacements；Worker 不得让该批次结果进入 fan-in。其余 item 的源文本、ledger、已有合法结果不可被失败 item 改写；不做同批部分成功回填。

R4：同步 translate、独立 Worker batch 以及最终 fan-in 均有验证门；不能只测纯 Validator。编码后的预算、术语匹配顺序和 Prompt 占位语法告知属于必要接线。正式本地 adapter 使用同一核心规则，不能通过本地响应文件绕过验证。

R5：输出稳定机器错误码和 batch evidence，至少含版本、通过/失败、检查阶段、item/Token 分类计数、内容哈希及 batch/attempt/generation 关联。正常审计、事件、异常及默认 repr 不包含原文、译文、Prompt 正文或 ledger。

R6：复用既有失败映射、审计 Artifact、存储权限和快照；不新增数据库表列、路由、前端状态推断或完整性开关。历史已完成任务/发布件不重跑、不覆盖；新代码不能把缺证据的旧成功中间结果直接当成已校验结果。

R7：每次生成件登记必须拥有独立物理对象路径，不能把新 file_id 或最终 CAS 误当作文件字节隔离。不同 generation、同批不同 attempt，甚至同 attempt 的重复登记均不能覆盖彼此的对象；覆盖范围包含 source IR、batch result、目标 IR 和主 DOCX。共享文件服务负责新生成件的唯一物理身份，generation/attempt 和内容哈希继续绑定现有 metadata/evidence；用户下载名、主结果选择、历史记录读取及路径安全保持不变。CAS 拒绝的迟到执行最多留下自身未选中的新对象，不能破坏胜出结果或历史 Artifact。

R8：正式翻译调用中承载正文、译文、Prompt 和正文上下文的既有 DTO、中间载体 _TermMatch.context_snippet 与新增验证结果均须有安全默认 repr；不能只隐藏新 evidence/ledger 或下游 trace。仅调整必要字段的表示行为，运行值、dataclass 字段、相等性、序列化及不可变快照内容不变；未经验证的 Provider item ID 也不能经默认 repr 回显正文。

## 4. 非目标

- 批次最终失败后的主任务 failed/blocked 产品策略、部分 debug Artifact、跨代重试编排及调度算法收口（TR-406）；保留当前策略，只保证本任务验证边界不接受失败结果。
- 目标语言检测、源语言残留、mandatory/forbidden term 后验检查（TR-405）。
- caption/footnote 新抽取与回填（TR-401）、表格行列上下文/新 run ID（TR-404）、四方向正式样本体系和总门禁（TR-407）。
- 新增技术语言通用解析器、模型修复、语义等价/量纲换算、判断同 item 内移动技术值后的语义关联。
- 改造 legacy conversion runtime、第二套翻译链路、Renderer/表格算法、QA/发布功能、部署和真实付费模型调用。

## 5. 验收条件

| ID | 可观察结果 |
|---|---|
| AC1 | 正确编码响应仅改变自然语言时可回填；同 item 内完整占位符移动合法；已识别技术片段及其重复次数逐 item 一致。 |
| AC2 | 缺失/额外/重复/乱序 ID，非法 id/text 类型、空值、额外字段或非约定 JSON 均显式拒绝；不修剪 ID 或把数字强转成 text。 |
| AC3 | 占位符缺失、重复、未知、损坏、跨 item 交换和错误 ledger 被拒绝；空 Token ledger 也拒绝新增保留占位符。错误分类和优先级稳定。 |
| AC4 | 数字、符号/范围、数量单位、地址、位字段、公式、型号及 Codec 已支持的其他类别逐 item 对账；保留占位符同时附加裸 999 V/新地址/型号/公式等也被拒绝。 |
| AC5 | 两个 item 中仅第二项失败时，整批不返回 replacements；原输入/ledger/其他项不变。同步及 Worker 均证明 apply_replacements 未被调用，失败批次没有成功 result Artifact。 |
| AC6 | 同步与 Worker 均经过同一保护/验证核心；Worker 持久化的是验证后恢复文本；fan-in 校验来源、generation、ID 和 evidence，缺失/不匹配证据不回填。失败路径仍用当前重试/拆分和主任务映射。 |
| AC7 | 正常/失败审计均有脱敏 integrity 摘要和稳定码；预检失败未调用 Provider 不伪造 AI 成功调用；含敏感正文的恶意响应/ID 不泄漏到错误、事件和日志。 |
| AC8 | 按实际编码文本计字符预算；多项越界确定性拆批，单项编码后超限在 Provider 调用前显式失败；受保护跨度不被翻译术语覆盖；保留 Prompt 快照 hash，追加可追溯的固定完整性协议。 |
| AC9 | 用既有公开 OPA228 最小 MinerU fixture 经正式 converter→抽取→fake Provider→Validator→目标 IR 验证；结构、pages/layout/assets、表格 DOM/span 及公式块不变。中英俄混合向量不冒充四方向实译验收。 |
| AC10 | direct 零 Provider/Prompt/翻译术语调用、一任务一主 DOCX、已有角色/下载规则、历史 Artifact 可读、旧 generation 不进入新目标、既有截断重试回归不变；文档和 Spec 明确当前保证与未验证范围。 |
| AC11 | 对 source IR、batch result、目标 IR、主 DOCX 重复登记相同业务 filename 时，每次物理对象键不同，原文件字节/checksum 和用户下载名保持不变；已胜出新 generation/attempt 后，旧执行登记并被现有 CAS 拒绝，不得改写胜出或历史对象。local_file/local_object 的真实临时存储与 fake S3 均有直接证据，历史固定路径仍可按原记录读取。 |
| AC12 | TranslationTextItem、TranslationProviderRequest/Result、Prompt/Profile 快照、含正文 context 的 trace、真实术语匹配产生的 _TermMatch，以及新增验证结果/异常的直接或嵌套 repr 不含合成正文、译文、Prompt、上下文或恶意返回 ID 标记；_TermMatch.context_snippet 及其传递给 trace 的实际上下文保持原值。真实字段和序列化内容、Prompt hash、相等性及冻结性质保持原有行为；不得只手工构造匹配对象或 mock 匹配/context 逻辑代替真实路径测试。 |

## 6. 权限和失败语义

Validator 是内部领域能力，无 HTTP 入口或新角色。批次诊断沿用 owner/admin；全文 debug 沿用现有 Admin 显式开关、短保留期及下载审计，不新增 ledger 导出。普通 batch evidence 不含全文；业务 batch result 中的恢复文本继续只在既有受控 Artifact 边界使用。

必须 fail-closed。ID/Token/技术片段/evidence/预算验证失败不降级 warning、不补原文、不自动修复；失败批次不回填。已有自动重试可重新请求并重新验证，不能复用失败项。当前主任务 translation_failed 和现有阶段不因本任务改变；批次最终失败主任务语义仍明确范围外。

## 7. 必须保持的不变量

- 一次只实现 TR-403，不提前实现清单其他任务。
- 保持模块化单体；不引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；其他语言新建或克隆任务。
- direct_pdf_to_word 不调用 AI Provider、不加载翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口；不增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格；不以截图作为默认简化。
- quality blocked 和翻译 unreviewed 均可内部下载，但不得批准或发布。
- 前端只能消费后端权威状态或 available actions，不自行推断发布资格。
- 不新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 必须 fail-closed，不自动修复模型篡改；一个失败 item 不能污染同批其他 replacement。

## 8. 评审门与停止条件

当前 manifest/Trellis 均停 planning；不存在尚待用户决定的产品范围问题。三件套提交规划评审，不视为实施已获授权。

2026-10-21 修订：用户授权的是修订 P1/P2 及 context，不是接受修订稿或授权实施。P1/P2 已落为 R7/R8 与 AC11/AC12 的规划要求；revision 3 按复审残留 P2 补 _TermMatch 的上游表示控制和真实匹配路径定向测试，不改已确认的 P1 方案或扩展术语后验检查。后续仍须人工审核和实际实现证据；不得标成实现缺陷已关闭。

实施前重新核验依赖和工作区。以下情况停止并将当前任务标记 blocked：依赖未 done 或未人工接受 skipped_existing；PRD/冻结决策/已接受 ADR 存在无法消解的冲突；需要未批准破坏性 DB 迁移、覆盖发布件或删除历史审计；必须改变冻结模式、表格原生化、下载或发布规则；必要样本/外部系统/人工安全授权缺失且 fake/adapter 无法完成范围内实现。
