# TR-403：实施顺序、验证与评审门

2026-10-21 人工验收完成：用户已接受实现、测试证据和残余风险，确认限定 commit plan 并授权当前任务提交/归档。最终状态 done/implemented，收尾见 [closeout](closeout.md)；下文规划/实施记录保留各自历史时点，不再表示待验收。不 push、不开始后续任务。

## 1. 当前阶段与授权

2026-10-21 实施轮：用户已明确批准 revision 3 并授权实现。实际分支 md2word/TR-403，准确子任务已 start；manifest 完成停 review，Trellis 保持 in_progress，不 archive、提交或 push。详细结果、逐 AC 证据及未验门禁见 [实施验证](implementation-validation.md)，独立候选复核/P2 闭合与审计限制见 [实现复核](implementation-review.md)。后续规划历史文字仅记录当时授权，不覆盖本次批准。

开始时已保护 386 个既存 dirty/untracked 文件；共享 manifest/父 task.json 只追加当前任务。不得 stash、覆盖或提交原有其他任务、journal、backlog/CON-104 改动。

2026-10-21 修订轮：revision 2 已按 architect P1/P2 纳入 files/service.py 的生成件物理身份及 translation/models.py 的 repr；fresh 复审确认 P1 在规划中已覆盖、P2 遗漏 _TermMatch.context_snippet。本次 revision 3 仅补该既有 translator 中间载体的 repr 和真实术语匹配路径测试、必要 context 及任务内证据。该授权不包含业务实现；本版仍待人工审核，尚未再次独立复审。

## 2. 有序实施清单

1. [x] **准入复核**：读取三件套、research、backend specs 与 manifest；重新确认 TR-402 done/人工验收、工作提交可达、分支/dirty 和唯一子任务。若完整能力已由其他变更交付，转验证收口，建议 skipped_existing，不重复建设。当前根非父任务全阶段集成候选，不主动整合其他任务。
2. [x] **评审/状态门**：用户在后续消息明确批准最新规划后才执行 task.py start 的准确子任务路径；只改 TR-403 状态。确认脚本/Worker/source 文件无并行写冲突。业务实现通过 Trellis implement/check 流程完成，不在规划会话派发实现。
3. [x] **先确立核心合同**：在 tests/test_translation_integrity.py 写最小“保留占位符但附加裸 999 V 必须失败且没有 partial 结果”的回归，确认对现状因缺失能力/行为缺口失败；新增 integrity.py，复用 Codec，不复制 detector。
4. [x] **完整验证、evidence 与 DTO/匹配载体 repr**：实现 typed shape、固定顺序 ID 检查、ledger 归属、整批 decode、逐 item 技术 inventory、多重计数和安全错误；返回值不可变。按 design.md 的 P2 字段清单调整既有 models.py、新结果和 document_ir_translator.py::_TermMatch.context_snippet 的 repr，覆盖直接/嵌套正文、Prompt、context 和未经验证的 item ID；先以真实术语匹配路径用例确认现状因上游 repr 泄露而失败，再验证字段级控制，不改真实值、字段、序列化、相等性或冻结快照。稳定码/摘要见 design.md §5。
5. [x] **共享准备和同步接线**：按实际 encoded 字符拆批、单项超限拒绝、每个最终请求独立 encode；原文术语排除保护跨度。替换 ID-only 校验，同步所有批次成功后才 apply。测试失败第二项/失败后续批次都零 apply，不保留可消费 partial replacements。
6. [x] **Provider 边界**：拒绝类型强转、ID/text strip、额外字段和非约定 JSON 包装；保留既有安全响应元数据及截断识别。追加固定版本占位符协议，验证绑定 Prompt hash 不变；不修改资源 seed/Profile/snapshot。
7. [x] **先补生成件物理身份（P1）**：在 files/service.py 中复用当前登记的 file_id，为 register_generated_content 的新对象 key 增加独立 file_id 层；保留原 filename、S3 prefix、安全片段、上传 key 和按记录读取历史对象。覆盖 source IR、batch result、目标 IR 和 DOCX，不用 generation/attempt 字符串单独充当唯一身份；不新增开关/存储 wrapper，不改默认后端和 CAS。
8. [x] **Worker 与 fan-in**：独立执行入口调用同一准备/Validator；只登记恢复后的成功 result + integrity envelope；优先保留专用错误码。加载校验 Artifact checksum/来源/代次/ID/源与恢复 hash，重新核对技术 inventory，全部叶子合格后才 apply。验证新物理路径与现有 CAS 的组合：旧执行被拒绝后，胜出记录所指的实际字节及历史 Artifact 不变。不更改调度/主任务终态/CAS owner 语义。
9. [x] **审计接线**：扩展 recorder 的内部可选 integrity 参数/错误 evidence，更新对应 Protocol/fake；每次真实调用只记录一次成功或失败。Provider 前失败用批次事件摘要；审计失败不吞掉。默认摘要不含原文/译文/Prompt/ledger/恶意 ID；DTO repr 隐藏不能代替此脱敏边界。
10. [x] **本地 adapter 必要兼容**：使用共享计划导出真实 encoded request（v2），严格检查有序本地响应与请求 envelope，不通过 dict 覆盖/过滤/排序修复。同步到工具文档；无 Token 合法响应继续可用，旧技术响应需重新导出，不猜测改写。
11. [x] **测试、文档与 touched-scope 中文检查**：补齐 AC1–AC12，特别是下述物理字节交错与 DTO repr/序列化对照；调整现有 fake 使它们保留实际收到的 placeholder，而非返回未经验证的原始数字。保留独立预期文本/结构断言，不用待测 Validator 生成预期。更新指定设计/Spec，不实施相邻任务。
12. [x] **稳定候选集中验证**：先检查实际 diff，再运行下列最小核心门和直接受影响集成门；成功证据输入不变则复用，失败先诊断再重跑。项目 release 门仅在候选稳定后运行一次，不为每个文件重复执行。
13. [x] **候选独立只读复核**：生产回填边界、共享生成件物理身份及 batch Artifact 合同存在实质变更，必须取得 independent critical_reviewer，聚焦双入口绕过、整批原子性、metadata 归属、迟到写/物理覆盖、fan-in错代、DTO嵌套repr、不可变/隐私和稳定错误码；不得把自审或本轮规划修订当作实现独立审查。按编排 skill 生成并校验 SUBAGENT_EXECUTION_DIGEST；无法获取时明确缺口，不能宣称完整验收。
14. [x] **review 收口**：逐 AC 记录实现/验证/未验；task.py validate、JSON/JSONL 路径和 final diff 检查；清理本任务临时产物/进程。只将 manifest TR-403 改 review，Trellis 保持 in_progress；人工验收前不 done/skipped_existing、archive、提交或 push。

## 3. 计划修改文件与写边界

| 文件 | 计划变更 |
|---|---|
| app/domains/translation/integrity.py（新增） | Validator、安全错误/证据模型、恢复后技术 inventory 对账。 |
| app/domains/translation/document_ir_translator.py | 共享编码准备/预算/术语跨度过滤，替换 ID-only 校验和同步接线，更新审计 Protocol；_TermMatch.context_snippet 仅字段级 repr 隐藏，匹配及上下文传递语义不变。 |
| app/domains/translation/provider.py | 严格 JSON/id/text 边界，固定版本完整性协议及安全解析错误。 |
| app/domains/translation/audit.py | ai-call-log/v1 可选 integrity 摘要和稳定错误码，保留 debug 授权/TTL。 |
| app/domains/translation/models.py | 仅 P2 列明的正文/Prompt/context/嵌套成员 repr 控制；不变更 DTO 字段、序列化、实际值或快照 hash。 |
| app/domains/document_jobs/execution.py | Worker 调用、错误码保持、已验证 Artifact 与 fan-in gate；仅相关方法，不整体重构。 |
| app/domains/files/service.py | 仅新生成件的 object_key 绑定本次 file_id；保留调用签名、用户 filename、安全规则、上传/历史读写和既有保留策略。 |
| scripts/dev/formal_mineru_conversion.py | 同一核心的 encoded request v2 和严格有序离线响应。 |
| tests/test_translation_integrity.py（新增） | 核心 shape/ID/Token/技术内容/安全原子性及既有/新增 DTO repr 与真实值/序列化对照；真实术语匹配生成 _TermMatch，验证上游直接/容器 repr 与下游 trace 隐私、原上下文保留。 |
| tests/test_translation_integrity_execution.py（新增） | fake/eager Worker、审计、Artifact、fan-in/generation 与同代迟到 attempt 物理字节定向集成。 |
| tests/test_generated_artifact_identity.py（新增） | FileUploadService 的 local_file/local_object/fake S3 新对象唯一性、历史记录可读、原 filename/路径安全/前缀保留。 |
| tests/test_document_ir_translation.py | 实际 encoded 请求、预算/术语/失败零 apply、既有 fake 适配及 OPA228 组件测试。 |
| tests/test_fastapi_jobs_backend.py | 仅受影响 Provider fake 和既有 translation/audit 断言适配，保留原回归强度。 |
| tests/test_translation_profile_prompts.py | 固定完整性附录与快照原文/hash 不变、无全文审计。 |
| tests/test_conversion_sandbox_dev_tools.py | 本地实际请求格式、严格响应、失败不生成目标及 direct 不变。 |
| docs/design/translation-design.md | 如实同步生产接线、错误/evidence、预算/术语顺序与仍未实现的邻接任务。 |
| .trellis/spec/backend/protected-token-codec.md | 更新“仅原语未接线”阶段描述，保持已接受检测/恢复语义。 |
| .trellis/spec/backend/translation-integrity-validator.md（新增）、backend/index.md | 固化调用、稳定码、整批失败、fan-in/隐私及必要测试合同。 |
| .trellis/spec/backend/error-handling.md | 当前生产 Validator 的专用失败码与顶层兼容映射。 |
| .trellis/spec/backend/database-guidelines.md | 生成件新 key 的 file_id 身份、按记录读取历史对象、CAS与文件字节隔离的职责边界；无 schema 迁移。 |
| docs/dev/local-conversion-sandbox.md | 已有本地调试文档：更新请求/响应 v2 的边界与重新导出方式。 |
| 当前子任务与 manifest | 仅 TR-403 证据、context、状态；不更新其他任务状态。 |

protected_tokens.py 作为已接受只读算法依赖，优先直接用 encode/decode，不为本任务改检测语法。models.py 仅允许上述 repr，files/service.py 仅允许生成件物理身份修正；不得借共享 owner 修改上传路径、转换模式、下载名、权限、保留策略或既有 CAS。DB/schema/repository、API DTO/router、前端、资源 Prompt/术语/模板、legacy runtime、release runner 仍非计划业务写目标。若必须扩大这些边界，先重新评审；仅增加定向测试目标不等于修改其实现。

## 4. 验收测试矩阵

| AC | 定向证据 |
|---|---|
| AC1–4 | 合法自然语翻译与同 item Token 移动；各类别正例；missing/duplicate/extra/order、shape/type/空值/额外字段/重复 JSON key/包装自由文本；错误 ledger、每个占位异常、跨 item 交换、重复技术值计数、零 Token 注入及裸技术片段追加。 |
| AC5 | 两项中仅第二项坏、同步后续批次坏：输入/ledger 不变，异常无 items/dict，apply spy 调用零；Worker 无成功 result，无该批 replacements；独立合法批次不被修改。 |
| AC6 | eager/fake Worker 成功→恢复文本落盘→fan-in；失败→专用码/审计且零 apply；缺证据、换 source/batch/generation/hash、重复合并 ID、旧代迟到返回不能绑定新主件。测试不扩成并发锁重构。 |
| AC7 | 成功/失败日志摘要 schema/code/count/hash；敏感源文、Prompt、译文、恶意 ID、ledger 在默认日志/事件/repr 中均不可见；debug 默认关、Admin 开启/TTL 的现有测试保持；Provider 前预算失败零调用/无伪造 AI 成功记录。 |
| AC8 | 编码膨胀跨阈值、多 item 确定性拆批、单项超限拒绝、源前缀碰撞/重试拆批重新编码；既有 batch.char_count 保留源文统计、evidence 分别记录两种长度；术语跨保护跨度被排除而普通术语保留；四方向绑定 Prompt 原文/hash 不变、追加协议可追溯。 |
| AC9 | 公开 OPA228 fixture 经正式 converter/extractor/fake Provider/Validator/apply，独立断言 OPA228、3 nV/sqrt(Hz)、10 V/us 保持，IR结构/DOM/span/公式块不变；不提交专有资料或生成 DOCX。 |
| AC10 | direct 零加载/调用/单 DOCX；既有 Provider 传输失败/截断拆分/retry generation/debug/owner 权限；本地 v2 正常、旧技术响应拒绝、无技术文字可用；OpenAPI 无漂移。 |
| AC11 | FileUploadService 实际重复登记同 tenant/job/type/filename、内容不同的生成件：source IR、batch result、目标 IR、DOCX 各自读回旧/新字节和 checksum，断言 key 不同而 original_filename 相同。local_file/local_object 用 TemporaryDirectory，S3 用通过真实 service put/get 的内存对象 fake，不只断言调用参数或新 file_id。另保留旧固定 key 记录，验证按原记录可读，上传 key/安全规范化/S3 prefix 不变。 |
| AC11（交错） | 不用 sleep：在旧执行通过 generation 检查但尚未登记对象处用受控回调/屏障暂停；让新 generation 成功登记并绑定，再恢复旧写且令其现有 CAS 失败，实际读新 IR/DOCX/历史对象断言字节和 checksum 未变。另覆盖同 batch 同 generation 的新 attempt 已胜出、旧 attempt 迟到写且被 CAS 拒绝；不只断言 current file_id 不变，也不顺手改变 lease fencing。 |
| AC12 | 分别构造 TextItem、Provider Request/Result、Prompt/Profile 快照、正文 context trace、新验证结果/异常；源/译/Prompt/context/恶意 ID 合成标记不出现在直接或嵌套 repr。另用真实条目/快照和带相邻标记、无技术 Token 的源文，经请求准备→真实 _match_request_terms→筛选/去重→trace；仅观察并转调既有方法捕获实际 _TermMatch，至少一项命中，独立验证术语/匹配位置和上游/下游 context 原值，repr(match)、repr([match])、trace 直接/嵌套 repr 均不含标记。实例字段、dataclasses.asdict 等现有序列化仍含原值，Prompt hash、相等性、冻结约束仍成立；不清空数据、不 mock 匹配/context、不仅手工构造匹配对象或只测下游 DTO/新 evidence。 |

## 5. 命令与回归门禁

### 本规划轮已执行

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_document_ir_translation tests.test_protected_tokens
~~~

结果：35 tests / OK；另有三个零外部调用的内联只读反例，证实 ID-only 接受技术篡改、Codec 单独不拦截额外裸技术值、Provider 强转/trim。只证明现状，不是未来 Validator 已通过。

### 实施稳定候选的核心门

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_translation_integrity \
  tests.test_document_ir_translation \
  tests.test_protected_tokens \
  tests.test_translation_profile_prompts
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_translation_integrity_execution \
  tests.test_generated_artifact_identity \
  tests.test_document_job_modes \
  tests.test_conversion_sandbox_dev_tools
~~~

### 直接受影响的既有 Worker 回归

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_worker_translates_ir_and_saves_ai_audit_artifacts \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_debug_full_text_is_admin_only
~~~

项目执行指南/父任务要求的候选收口门（不在规划轮运行）：

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ops/check_release.py
git diff --check
python3 .trellis/scripts/task.py validate .trellis/tasks/10-21-tr-403-translation-integrity-validator
~~~

check_release 已包含 OpenAPI 一致性和选定回归，不再重复以独立 export 检查同一 schema；若 release 揭示既有失败须分类，不能更新快照掩盖无授权漂移。没有项目统一 Python lint/type 门，不安装新工具制造门禁；需要时使用内存 compile。

P1 触及共享生成件 key，故新增 FileUploadService 定向存储测试，并复用已有 direct 一主 DOCX/下载与权限回归；不运行无关 legacy S3 adapter 全套或以 fake S3 宣称真实服务已验证。P2 的验证在 DTO/Validator 单元层及真实 translator 术语匹配路径的组件层完成，均归入上述 tests.test_translation_integrity 核心门，不增加测试套件、网络、前端或数据库验证。

样本门以 AC9 的公开 fixture fake 组件测试和 direct 定向证据为本子任务离线基础。P1 preflight/真实实译、完整 P0 Golden、Word 人工签字和四方向矩阵属于在线/阶段验收，运行前核验对应样本/认证/授权；未取得证据必须明确未验，不能以 fake 替代实译。当前 translation-core 集合不存在，matrix 仅 direct/en2zh/ru2zh，不能照目标文档执行不存在的四方向命令；TR-407 负责补齐。

不启动本地 API/MySQL/Redis/Celery/浏览器/模型，不跑全仓库全套或浏览器矩阵。API DTO/DB/schema/前端未改，不添加迁移/前端 build/E2E 作为重复门；若实际补丁改变这些边界，先返回规划，不先扩大实现后补验证。

## 6. 文档、回滚点和完成定义

- 三份规划及调查记录用中文；后续 Python 注释/docstring/开发者错误文本按 touched-scope 中文要求处理，机器字段/错误码保留约定格式。
- Spec 更新由 Trellis 主会话收口；Codec检测、Validator、文件服务物理身份与 DTO/中间匹配载体 repr 各有唯一 owner。database-guidelines 增补新生成件 key/历史读取合同，Validator Spec 增补复用 DTO 与 _TermMatch 的表示隐私及真实匹配路径验收；不得把有限识别/纯 fake 证据写成全语法/四方向/生产实译全通过。
- 规划回滚：只回退本任务新增文件、TR-403 manifest stanza 与父 task.json 新 child；不覆盖原 dirty。
- 核心/接线回滚：代码差异可独立撤回，先暂停翻译入口或使用已有 disabled Provider，不能通过恢复无校验回填来回滚。文件身份隔离及 DTO repr 可单独保留；回滚不得恢复固定路径覆盖或正文 repr，也不得迁回新对象/删除历史数据。若不能保留安全写策略，暂停相关生成件写入后重新评审。无 DB 逆迁移、历史重写或审计删除。
- 完成定义：AC1–AC12 有逐项证据，尤其不能以“新 file_id/CAS 未绑定”替代真实字节保真，或以“新 evidence/下游 trace 无全文”替代既有 DTO 和真实匹配产生的 _TermMatch repr 检查；范围内门禁通过或失败/环境阻断如实分类；独立只读复核与 Spec 同步；临时资源清理、真实 diff 只含本任务；manifest=review/Trellis=in_progress，待人工验收。任何相邻任务与剩余线上/Word 风险须明确保留。
- 本规划阶段停止：三件套、最小 implement/check context 和 task.py validate 合格后立即停在评审门，不执行实现或收尾提交。
