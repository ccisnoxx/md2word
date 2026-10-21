# TR-403 人工验收与收尾

日期：2026-10-21；实际分支 md2word/TR-403，实施基线 c8fd2afc7dfea349b7fbc3e1f516d85adcb57536。

## 授权与结论

用户已明确人工审查并接受当前实现、测试证据和残余风险，并确认当前 commit plan，授权仅 TR-403 提交、完成状态及 Trellis 归档/记录；不 push，不开始后续任务。准入时 manifest=review、Trellis=in_progress，TR-402=done/implemented 且工作提交为当前祖先，无冲突实施任务。

存在新 Validator、正式双入口与本地接线、严格 Provider 边界、安全 evidence、生成件物理身份和 repr 隐私的实际业务/测试增量，结论为 done/implemented，不适用 skipped_existing。AC1–AC12 对应证据已在 implementation-validation.md 逐项复核，无新增功能或放宽验收条件。

## AC 收口核对

| 验收 | 已核验证据及人工接受边界 |
|---|---|
| AC1 | 合法自然语言、同 item Token 移动及重复技术值恢复。 |
| AC2 | ID 缺失/额外/重复/乱序、shape/类型/空值/额外字段/JSON 包装拒绝，不强转或 trim。 |
| AC3 | metadata/ledger 归属和占位次数/语法/错项等反例拒绝。 |
| AC4 | Codec 已识别的各技术类别逐项多重对账，包括合法占位符外新增裸技术值。有限语法边界保留。 |
| AC5 | 第二 item 或后批次失败零 apply、无 partial 结果，原输入不变；失败批次重新请求可恢复。 |
| AC6 | 同步/Worker 共用核心、恢复文本持久化、fan-in 权威来源/字节/代次/尝试/evidence 重核，旧结果拒绝。 |
| AC7 | 正常与失败安全审计、首次建批预算事件、安全错误、零假调用及审计失败可见；复核 P2 已闭合。 |
| AC8 | 实际编码预算、确定性拆批、预检超限、保护跨度与术语、固定协议及原 Prompt hash 保持。 |
| AC9 | 公开 OPA228 fixture 经正式 converter→fake Provider→Validator→目标 IR，结构/表格/公式等保持；未冒充四方向实译。 |
| AC10 | direct、主 DOCX、权限下载相关回归、历史读取、旧代拒绝及截断重试，已接受既有 release 证据。 |
| AC11 | local_file/local_object 真实临时字节、fake S3、历史 key，以及迟到旧代/旧 attempt 被 CAS 拒绝后的胜出与历史字节保真。 |
| AC12 | 既有 DTO/新结果与真实匹配产生的 _TermMatch/context repr 隐私；业务值、序列化、相等性、冻结约束保留。 |

## 本次最终轻量验证

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_translation_integrity tests.test_document_ir_translation \
  tests.test_protected_tokens tests.test_translation_profile_prompts \
  tests.test_translation_integrity_execution tests.test_generated_artifact_identity \
  tests.test_artifact_retention.DocumentFileRetentionTests
```

89 tests / OK，退出 0（0.782 秒）。本轮仅收尾元数据，业务代码不改；复用已人工接受的主会话 128 项、修正后 50 项及单测、最终 release 202/OpenAPI 一致性证据，不重复完整 release/矩阵。

`git diff --check` 通过；活动任务 context validate 通过（implement/check 各 8 entries）。关闭的独立复核 audit-verify 通过，14 artifacts、无错误/警告。本轮没有新派发子代理，不把历史审计汇总作为新的执行次数。

Spec update 已核对：Validator Spec 的七节合同、稳定错误/首次预算映射、真实匹配 repr、文件身份/历史读取及索引均已同步，不重复增加指南或功能。收尾没有 Python 修改，也不改注释/docstring/开发者运行文本。

## 仍保留的风险

用户已接受 P1 preflight 缺认证退出 1、translation-core 未注册未运行、真实模型/真实 S3/MySQL 并发/Word 人工效果未验，以及完整实现子代理审计因配置指纹漂移未能聚合。独立实际候选及 P2 增量复核的审计有效，不能替代缺失的全部实现审计。人工接受不改写任何未运行项为通过，也不代表部署授权。

有限 Codec 语法、参数语义关联、完整 lease fencing、批次最终失败主任务产品语义、目标语言/术语 QA 和正式四方向矩阵仍不在本任务保证范围。不启动或实现 TR-404/405/406/407。

## 提交、归档与共享文件保护

脚本默认 archive/add_session 会自动提交。为保护已有共享文件改动，本轮使用 --no-commit 后手动审核限定路径或补丁，顺序为工作提交→归档提交→本次日志提交。

- 工作提交包含当前业务/测试、设计/Spec、当前子任务及仅 TR-403 的 manifest 和父任务 child 登记；不整体暂存共享文件。
- 归档只迁移本子任务，脚本写 completed 并清理指向本任务的 session；同步本任务 context 与 manifest 的准确归档路径。不修改父任务或其他任务状态。
- 日志用 add_session --no-commit 生成，再仅暂存本次新日志与索引补丁。既有 CON-102 等未提交 journal/索引、manifest/父任务其他条目及其他任务文件保留，不带入提交。
- 起始 1474 文件已保存临时保护快照；收尾检查业务 15 文件、其他任务文件及共享文件非当前片段不变。无 stash、覆盖、删除用户文件或 push。

工作提交：`f46a3bcf148e6abc16a0011b6e7079d7f723130b`，37 个文件/限定补丁。Trellis 已由准确子任务 archive --no-commit 写为 completed 并移至 `.trellis/tasks/archive/2026-10/10-21-tr-403-translation-integrity-validator`，旧活动目录已不存在、指向本任务的 session 已清理；manifest 的实际 task path 与 implement/check context 已迁移。归档及本次日志由后续独立限定记账提交承载，不修改其他任务状态。日志仅引用工作提交，不引用归档提交。正式记录保留，临时保护快照在最终检查完成后清理。

工作提交前 git diff --cached --check 曾发现两份新任务文档有多余空白末行，已仅修正文档 EOF 并复核通过，未改业务。父任务无最终换行使自动生成的局部 patch 无法解析，改用精确 index blob 暂存 HEAD 加本 child 的版本；磁盘原 parent 文件未改，其他 child 未带入。

归档后的 context、状态、链接、字节保护及 git diff --check 在归档记账前再次核对；最终检查和提交 hash 以本次收尾回复及 git log 为准。
