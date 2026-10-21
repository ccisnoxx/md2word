# TR-403 规划校验记录

日期：2026-10-21（Asia/Shanghai）。本轮仅规划，不代表业务实现或验收完成。

前文保留初次规划及 revision 2 的历史校验记录；最新 revision 3 残留 P2 修订及 context 数量以末节为准，不将旧基线测试重复计为本次执行。

## 准入与产物

- TR-403 原 todo；唯一直接依赖 TR-402=done/implemented，归档 completed，有人工验收，工作提交 24ed6a717ca86cf5ed086f2eda58030e4af66810 是当前 HEAD 祖先。
- 未找到重复子任务；使用 task.py create --parent .trellis/tasks/10-12-datasheet-docx-delivery-quality --no-start 创建 .trellis/tasks/10-21-tr-403-translation-integrity-validator。
- prd.md、design.md、implement.md、research/current-state.md 已完成，PRD 已收敛并从头检查，无 TBD 或未决产品问题；三件套包含 AC1–AC10、冻结不变量、失败原子性、API/DB/权限/代次/不可变/隐私影响及回滚点。
- implement/check context 各 5 条真实 spec/research；没有源代码文件、整个仓库目录或 seed 示例项。
- manifest TR-403=planning，记录实际 task path；Trellis=planning、implementation_authorized=false、planning_review=pending。
- 实际分支仍 md2word/TR-402，HEAD=c8fd2afc7dfea349b7fbc3e1f516d85adcb57536；建议 md2word/TR-403 只在 meta/规划记录，未创建或切换分支。

## 实际执行的验证

| 检查 | 结果 |
|---|---|
| pwd / git status --short | 工作目录正确；原 dirty 已识别并保留。 |
| 三个内联只读反例 | 均复现现有缺口：ID-only 放过技术篡改、Codec decode 不拦额外裸技术值、Provider 强转/trim；外部调用 0。 |
| unittest tests.test_document_ir_translation tests.test_protected_tokens | 35 tests / OK，退出 0；现有基线，不是未来 Validator 通过。 |
| task.py validate .trellis/tasks/10-21-tr-403-translation-integrity-validator | 最终退出 0，implement 5 / check 5，All validations passed，无 warning。首轮曾因未创建的建议分支 metadata 警告，改为 branch=null、建议仅记 meta 后消除；未为消警告创建分支。 |
| git diff --check | 通过。 |
| 本任务文档/JSON/JSONL/相对链接/UTF-8/行尾空白 | 通过；新增未跟踪文档使用直接文本检查。辅助脚本起初把 git diff --no-index 的正常差异退出 1 误当校验失败，诊断后改用直接检查，无业务或文档错误。 |
| 既有 dirty 哈希 | 384/384 非共享文件完全不变；2 个共享文件单独对账。 |
| 共享文件增量 | 父 task.json 仅追加当前 child；manifest 仅 TR-403 stanza 变化，其他 44 个任务对象及其文本完全不变。 |
| 业务写范围 | app/tests/scripts/.trellis/spec 相对启动状态完全不变；新增文件仅当前任务目录。 |
| task.py current --source | Current task: (none), Source: none；未激活实施。 |

## 未执行与保留风险

没有运行 task.py start、实现/独立代码复核、提交、push、archive、add_session 或部署；没有新增业务代码、Python 注释/docstring/开发者错误文本，也没有执行 release、完整 component/Golden、P1、真实模型、DB/浏览器/Microsoft Word 验证。

规划以现有有限 Codec 识别语法为边界；重检测邻接误报、编码膨胀、Prompt/术语冲突、Worker/local/fan-in 绕过和隐私风险必须在后续实施测试/独立复核关闭。现有四方向正式样本/translation-core 不齐不能伪报通过；批次最终失败主任务语义及目标语言检测保持范围外。

本任务的临时基线快照位于系统临时目录，只用于证明原 dirty 未覆盖；收尾核对后删除，不作为交付物。未启动后台进程或端口监听器。最终保留的非业务文件均为当前任务正式规划/context/证据，停在人工规划评审门。

## P1/P2 规划修订校验（2026-10-21，revision 2 历史版本）

- 用户本轮只授权按已确认 architect P1/P2 修订三件套、context 并重跑 task.py validate。复用当前子任务，无 create/start/实施/提交/push；manifest/Trellis 继续 planning，planning_review=pending、implementation_authorized=false。
- P1：R7/AC11 明确 files/service.py 为新生成件唯一物理 key 的 owner，复用本次 file_id 目录隔离 source IR、batch result、目标 IR、DOCX 及同方法其他新生成件；保留 filename、上传/历史 key、安全规则及既有 CAS。补足真实字节读回、跨 generation/同代迟到 attempt 的确定性交错测试，不只测指针或新 file_id。
- P2：R8/AC12 将 models.py 的必要正文/Prompt/context/嵌套 repr 控制纳入精确实施范围；测试同时覆盖直接/嵌套 repr 和真实字段/序列化/hash/相等性/冻结行为，禁止靠清空数据通过。
- implement/check 各从 5 条更新为 7 条，只增加 backend/database-guidelines.md 与 research/architect-review-revisions.md。后续计划新增 tests/test_generated_artifact_identity.py；本轮未创建业务测试或执行未来用例。
- 已重新运行 task.py validate .trellis/tasks/10-21-tr-403-translation-integrity-validator：退出 0，implement 7/check 7，All validations passed，无 warning。
- 已检查本次实际文档 diff、完整 PRD 收敛、AC1–AC12 映射、JSON/JSONL、Markdown 相对链接、UTF-8/行尾空白及 git diff --check，均通过。辅助占位检查曾将历史描述“无 TBD”误认占位，已诊断为检查脚本误报并改为仅匹配实际占位行，无文档缺陷。
- 启动时 1465 个 tracked/untracked 文件中，8 个当前任务/manifest 文件为授权修订，其余 1457 个字节不变；仅新增当前任务 research/architect-review-revisions.md。manifest 仅追加 TR-403 说明，其他 44 项任务的文本/状态不变，父任务/journal/其他 dirty 不改。
- 业务代码、tests、scripts、实际 Spec 和 API 快照未修改；HEAD 和实际分支不变。临时修订快照核对后删除，未启动进程/服务或产生模型外部调用。
- 修订只表示规划层回应 P1/P2，未重新派发独立审查，不声明实现风险已关闭；三件套 revision 2 等待人工审核。初次规划的 35 项基线证据继续保留，本次未重跑测试、release 或线上验证。

## 残留 P2 规划修订校验（2026-10-21，revision 3 当前版本）

- revision 2 的 fresh architect 复审（audit_id=20261021T055033Z-tr-403-revised-fresh-architect-review-701c160f）确认 P1 在规划中已覆盖，P2 仍遗漏上游 _TermMatch.context_snippet。本轮按用户授权只补该残留，不修改既有审查 Bundle，不另派独立审查或声明本版已经复审。
- prd.md R8/AC12、design.md 和 implement.md 已统一纳入 _TermMatch.context_snippet 的 field(repr=False) 计划。只隐藏默认表示，保留实际上下文、字段/序列化、匹配区间、筛选/去重、术语注入、trace 传值及相等性/冻结语义；P1 路径方案及其他冻结范围不变。
- 定向测试计划加入 tests/test_translation_integrity.py：真实条目/版本快照与无技术 Token 的短源文，经请求准备进入真实术语匹配和 trace 构造；仅用观察并转调真实方法的 spy 捕获实际 _TermMatch。必须真实命中，上游直接/列表 repr 和下游 trace 表示不含独有正文标记，同时真实字段/asdict/trace 保留原上下文、术语及匹配位置正确；不能仅构造对象、mock 匹配/context、零命中或只测下游 DTO。该未来用例本轮未创建、未执行。
- 更新现有 research/architect-review-revisions.md 及其 implement/check 注入理由，各仍 7 条，无新增 context 路径、源码目录或测试套件。task.json 记 planning_revision=3、最新复审来源及残留处理；manifest 仅追加 TR-403 备注，状态保持 planning，planning_review=pending、implementation_authorized=false。
- 已重新运行 python3 .trellis/scripts/task.py validate .trellis/tasks/10-21-tr-403-translation-integrity-validator：退出 0，implement 7/check 7，All validations passed，无 warning。
- 本轮未改业务代码、tests、scripts、实际 Spec 或 API 快照，未执行 task.py start、实现测试、release、提交或 push；未启动服务/后台进程，也未调用外部模型。初次 35 项测试只是历史基线，不重复计为本次通过；停在人工规划评审门。
- 最终检查通过：三件套实际 diff、AC12 映射、JSON/JSONL 路径与去重、Markdown 相对链接、UTF-8/行尾空白及 git diff --check；本轮 1466 个 tracked/untracked 文件中仅 9 个当前任务/manifest 文件为授权规划修订，其余 1457 个字节不变，无新增/删除。manifest 的其他 44 项文本与状态、父任务及其他 dirty、HEAD、分支和 git status 均不变。临时快照仅用于范围对账，核对后删除。
