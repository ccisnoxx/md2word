# TR-403 architect P1/P2 规划修订依据

日期：2026-10-21。只修订规划，不修改业务代码，不启动任务或提交/push。

## 1. 审查来源与状态

用户明确指定 fresh architect 独立只读审查，主会话核对后确认 P1、P2。原审查 Bundle 已关闭并验证通过，audit_id 为 20261021T052924Z-tr-403-fresh-architect-planning-review-bc8603e9；本轮不修改或重新生成历史审计。

revision 2 按这两项修订三件套和 context；随后 fresh architect 复审的已关闭并校验 Bundle 为 20261021T055033Z-tr-403-revised-fresh-architect-review-701c160f。复审确认 P1 在规划中已覆盖，P2 仍遗漏 _TermMatch.context_snippet，未确认其他新增问题。本次用户仅授权 revision 3 补这一残留 P2、必要 context 并重跑规划校验，不修改历史审计。

当前状态为“残留 P2 规划已补充、待人工审核”；revision 3 尚未再次独立复审或取得实施批准，不能标成业务实现已修复。

## 2. P1：记录身份不等于物理对象身份

### 已确认事实

- app/domains/files/service.py:391 每次分配 file_id，但 :396–402 调用 _generated_object_key_for 时没有传入；:771–790 的 key 仅含 tenant/job/type/filename。
- 同文件 :792–807 以 S3 put_object 或本地 replace 写入相同 key；不同记录可以指向同一物理字节。
- execution.py:954 使用固定 source IR 名；:1593–1623 目标 IR 固定 document_ir_v2.json，先写入再 job CAS；:1701 batch result 只按 batch.id 命名，同批不同 attempt 不隔离；:2270–2305 DOCX 同样先登记后 CAS。
- 因此重读 generation 后仍存在写入窗口；迟到旧执行的 CAS 失败只能保护记录指针，不能撤回对相同路径的覆盖。新 file_id、generation 过滤及 checksum gate 不能代替物理隔离。

### 最小方案与边界

唯一 owner 保持 FileUploadService。对 register_generated_content 新登记的生成件，在现有 key 的 type 和 filename 之间加入本次已分配的安全 file_id；不改变外部调用签名或 original_filename，不增加第二身份分配器/feature flag/wrapper。每次登记的唯一目录同时隔离跨 generation、跨 attempt 和同 attempt 的重复执行，代次/来源继续由 metadata/evidence 校验。

共享方法的新生成件统一采用这一内部 key，不按翻译类型保留覆盖旁路；source IR、batch result、目标 IR、DOCX 及既有审计生成件自然覆盖。direct 仅得到同样的物理安全身份，不改变模式、Provider调用、主 DOCX 数量、下载名或发布资格。源 PDF 上传、旧记录/key/字节、S3 prefix、安全片段规范化、仓储协议和 DB schema 均不改。

读取和下载仍使用记录保存的 key，新旧布局共存；不搬迁、backfill、覆盖或删除历史件。CAS 仍负责选取当前结果，迟到写只留下自身未被选中的新对象，沿用既有保留机制。不能借此扩展到 TR-406 的 lease fencing、调度或终态产品策略。

### 必需验证

- 新 tests/test_generated_artifact_identity.py 直接通过 FileUploadService，对 local_file/local_object 的真实临时目录及 fake S3 put/get 验证：同业务 filename 多次登记后，key 不同、原下载名不变，分别读回旧/新实际字节和 checksum；旧固定路径记录继续可读，安全路径/S3 prefix 不变。
- tests/test_translation_integrity_execution.py 使用确定性屏障/回调，不靠 sleep：旧执行在重读后暂停，新代完成登记并绑定，旧执行恢复写入后 CAS 被拒绝。新 IR/DOCX 与历史对象的实际字节/hash 不变，不能只断言 file_id 指针。
- 同 batch 同 generation 的新 attempt 已成功后，旧 attempt 迟到写且被现有 CAS 拒绝，也须保持胜出结果及 evidence 的字节/hash。
- 现有 direct 单主件和下载/权限回归作为共享 owner 影响检查；fake 不冒充真实 S3/数据库并发验证。

## 3. P2：既有 DTO 与中间匹配载体 repr 必须纳入写范围

### 已确认事实

translation/models.py:199–238 的 TextItem、Provider Request/Result 是默认 repr 的 frozen dataclass，承载正文、译文、Prompt、嵌套术语及 context trace。TranslationPromptSnapshot.markdown 和 trace.context_snippet 也会在直接或嵌套表示中显示。原 implement.md 排除 models.py，无法满足 PRD R5 的表示隐私要求。

revision 2 已补上述 DTO，但 document_ir_translator.py:85–93 的 _TermMatch 同样是默认 repr 的 frozen/slots dataclass；:310–320 的真实 _match_request_terms 把源文截取为 context_snippet，:398 再原值复制到下游 trace。复审用不含技术 Token 的普通术语匹配证明实际生成对象的 repr 包含合成正文标记；这是默认表示合同缺口，未证明现有普通日志已打印该对象。

### 最小方案与验证

将 models.py 纳入字段级 repr 控制：隐藏 TextItem 的 text/未经验证 id，Request 的 items/system_prompt_markdown/terms/term_traces，Result 的 items，PromptSnapshot 的 markdown 与 trace 的 context_snippet；嵌套 Profile 依赖安全 Prompt 表示。保留实际值、dataclass字段/序列化/相等性/冻结约束，不清空业务数据、不改 Prompt hash、不引入通用脱敏框架。

revision 3 在已经计划修改的 document_ir_translator.py 内，将 _TermMatch.context_snippet 明确为 field(repr=False)；不新增模块或扩大到术语后验规则。保留真实上下文、匹配区间、筛选/去重、术语注入及向 trace 传值，维持字段/序列化/相等性/frozen/slots 语义。只隐藏下游 trace 不足以验收。

tests/test_translation_integrity.py 用不同的合成源文、译文、Prompt、context、恶意 ID 标记检查上述直接/嵌套 repr 和新增验证结果/异常；同时从真实字段及现有序列化读回原标记，比较 Prompt hash 与相等性/冻结行为，防止靠修改数据来“脱敏”。日志/审计仍需自身安全摘要，repr 隐藏不代替该边界，也不承诺 asdict 自动脱敏。

新增定向用例仍归入该测试文件：用真实条目/版本快照和无技术 Token 的短源文，使独有正文标记位于普通术语附近且不在术语或 ID 内；请求准备必须经过真实 _match_request_terms、上下文截取、筛选/去重和 trace 构造。仅用观察并转调真实方法的 spy 捕获上游 _TermMatch，证明有真实命中，验证术语/匹配位置和上游/下游上下文原值；上游直接/列表 repr 及 trace 直接/嵌套 repr 均不能出现正文标记，真实字段/asdict 仍保留该值，并保持相等性/冻结约束。不能用直接构造对象、mock 匹配/context 或零命中替代该用例；现状应因上游 repr 泄露而失败，不需 Provider/网络或新测试框架。

## 4. 三件套与验收映射

| 发现 | 需求 | 设计 owner | 实施及证据 |
|---|---|---|---|
| P1 | R7、AC11，补足 R6/AC10 的不可变与代次保证 | files/service.py 的新生成件物理身份；execution.py 保留现有 CAS 选择 | 存储真实读回、跨代及同代迟到 attempt 交错、历史路径/下载名/安全兼容；Spec 更新 database-guidelines。 |
| P2 | R8、AC12，补足 R5/AC7 默认表示隐私 | translation/models.py 的必要字段 repr、document_ir_translator.py::_TermMatch.context_snippet；新 Validator 结果继续安全表示 | 既有/新增/嵌套 DTO 及真实术语匹配生成的上游对象表示，与真实值/序列化和 trace 传值对照；不改字段或快照。 |

revision 2 的 implement/check context 已增加本文件及 backend/database-guidelines.md；revision 3 仅更新本文件的既有注入理由，各保持 7 条，沿用原有 Codec、错误、日志与质量规范，不注入源码或整个仓库。三件套均须重新人工审核后才可实施；本轮不运行未来测试或宣称 P1/P2 已有实现证据。
