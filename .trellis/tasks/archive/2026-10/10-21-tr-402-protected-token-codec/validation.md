# TR-402 实施验证与交付记录

日期：2026-10-21（Asia/Shanghai）。实际分支 md2word/TR-402，基线 HEAD 4c40e6c52bde072a7ad3afab67eb425f757bd33c。

## 1. 验证限制先行

用户要求的 P1 preflight 已执行但退出 1：p1_auth_missing、p1_runtime_unreachable。精确 runtime 错误为“请设置 P1_TRANSLATION_PASSWORD，或设置 P1_TRANSLATION_BEARER_TOKEN。”认证会话建立即失败，没有证据证明服务宕机，也没有发起真实模型调用。未补填凭据、启动服务或重试。

现有本地 matrix 的 SAMPLE_SETS 只有 phase2-core 与 ru2zh-acceptance，没有 translation-core；用户要求为样本存在时执行，故未伪造该矩阵命令或通过记录。Codec 可由 fake/公开 fixture 完成范围内验证，不满足“必要授权缺失且无法用 fake 完成”的 blocked 条件；保留环境/样本缺口，manifest 进入 review，不标 done。

## 2. 实际变更和不变边界

- 新增 app/domains/translation/protected_tokens.py：标准库纯函数 encode/decode、局部 frozen/slots ledger、固定检测优先级、实际源文前缀碰撞扫描、逐 item 次数/归属验证和一次精确恢复。
- 新增 tests/test_protected_tokens.py：24 个测试方法，包括 fake Provider、真实公开最小 OPA228 converter/extractor roundtrip、恶意占位符和整批失败负例。
- 更新 docs/design/translation-design.md；新增 backend protected-token-codec.md 并加入 index，明确尚无生产接线。
- 当前子任务记录用户规划批准、实际分支、实施和复核证据；implement/check context 各 4 条。只更新 manifest 的 TR-402 段落。
- 没有修改 models.py、正式 translator、legacy runtime、Provider、Worker、Prompt/Profile/配置、OpenAPI、数据库/schema/migrations、前端、Renderer 或发布行为。无新增依赖/feature flag，无第二套流水线。
- 无事务、锁、lease、全局计数或 generation 变化；同一有序输入确定性相同，不承诺重复 encode 幂等。ledger 仅在内存且只归属该批次，不改历史 IR/DOCX、快照或发布件。
- URL/公式只是字符串；不执行/访问，不传原文映射到 Provider、日志、审计或错误消息。新增 docstring、非明显分支注释和开发者错误消息为中文。

## 3. 实际执行的测试

| 阶段 | 命令/结果 |
|---|---|
| 本轮实施前基线 | PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_ir_translation tests.test_translation_runtime_characterization：21 tests / OK。 |
| 最小 TDD 红灯 | 实现代理在新模块尚不存在时执行首个 roundtrip，因 ModuleNotFoundError 精确失败；随后新增模块。 |
| 首个候选边界修复 | 主代理探针暴露普通括号及 URL 尾部 roundtrip 问题；实现代理修复并新增回归。其最终定向用例+全模块共 24 次执行 / OK（当时模块为 23 个测试，额外执行一个刚修复用例）。 |
| 既有回归 | 实现代理执行 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_ir_translation tests.test_translation_runtime_characterization tests.test_document_job_modes：32 tests / OK，只有既有 Starlette/httpx 弃用警告。 |
| 独立复核反例红灯 | 主代理运行 test_partial_reserved_prefix_is_not_left_bare_by_higher_priority_structures：1 个测试，4 个子例按预期失败，证实保留前缀部分重叠问题。 |
| 修复后的最终候选 | 主代理执行 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_protected_tokens：24 tests / OK，0.090s。 |
| 用户要求 P1 | PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ops/run_p1_translation_regression.py --preflight --preflight-output <本任务系统临时目录>/p1-preflight.json：退出 1，原因见 §1。样本 manifest 3 available / required 1，PDF 无缺失。 |
| Context | python3 .trellis/scripts/task.py validate .trellis/tasks/10-21-tr-402-protected-token-codec：implement 4 / check 4，All validations passed，退出 0。 |
| 差异 | git diff --check 通过；另检查新增文件的行尾空白、文档链接、JSON/JSONL 与写边界。 |

未重复已通过且相关输入未变的 32 项既有回归；它们不导入新 Codec，后续修复仅在新增模块/测试内，最终完整 Codec 模块已重跑。没有统一 Python lint/type 配置，未安装新工具，也不虚报 lint/type 门通过。

## 4. AC 逐项映射

| AC | 具体通过证据 |
|---|---|
| AC1 | category_vectors 的精确原始跨度/类别向量：25°C、0x0028[4:0]、[4:0]、VCC1_VCO、型号、URL/email/version、公式、复合/西里尔单位等。 |
| AC2 | overlap_selection 断言优先级、非交叠、原始跨度和相同输入 batch 相等。 |
| AC3 | namespace_scans_all_items、reserved_literal_scanner、1007 次唯一编号、外括号/URL 及 partial_reserved_prefix 回归。 |
| AC4 | assert_roundtrip 同时比较字符串和 UTF-8 字节；空输入、CRLF、NBSP、µ/μ、组合字符、负号及每类正例均覆盖。 |
| AC5 | item 缺失/额外/重复/乱序、Token 缺失/重复/未知/篡改/跨 item；entire_batch 还验证失败前未调用还原对象构造，异常无正文。 |
| AC6 | fake_provider 修改自然语言后恢复，且同 item 移动完整 Token 正常。 |
| AC7 | natural_language 保护普通中英俄文、Typical/Reserved/High/Low/NOTE 和 a/in/at；unselected_characters 保持未选字符顺序。 |
| AC8 | 原 OPA228 fixture → 临时 ZIP → convert_zip → 正式 extractor → Codec；IR 不变，Provider mock 禁止调用，命中 OPA228/3 nV/sqrt(Hz)/10 V/us。 |
| AC9 | frozen 成员、repr 隐藏、交错调用/同输入相等、fake 成败和 32 项既有回归；无共享状态或生产接线。 |
| AC10 | 翻译设计/唯一 Codec Spec/context 已同步，独立复核问题闭环，最终范围与工作区保护核对。 |

## 5. 独立复核与剩余风险

两轮 fresh 只读合同复核详 implementation-review.md。首次确认一个 P1 部分重叠 roundtrip 问题，已按真实失败测试修复；最终 fresh 复核确认关闭，无新的确认阻断。两次复核前后仓库文件集合和哈希一致，未观察到写入。

最终模块 SHA-256：fa3f254c1e453413c2ba6a8f0094b670b77a92c05df50351d4d1872ad2ee31c7；测试 SHA-256：a1a909bb504bc262af02346622b3bc842ae799dffb9940d0b2b8df401f92ad31。

有限静态语法只保证已识别 Token 的字符级恢复，不做译文语义、未编码数字或术语后验判断；未闭合/无明确边界的未知公式语法不声称获得完整保护。Prompt 中公式词翻译/俄文单位本地化差异、编码字符预算、术语顺序与同步/Worker 双入口接线，留给 TR-403 版本化集成，不能原地改历史 Prompt。

未运行 release/full suite、四方向正式实译、真实模型、在线 Worker/DB、浏览器、Renderer/Golden 或 Word 签字：本任务不改变相应运行边界，采用纯函数/fake/公开最小 fixture/既有定向回归/独立合同复核作为替代。不能报告生产 Token 保持率或正式翻译验收已通过。

## 6. 状态、回滚与提交计划

依赖 BAS-001=done；本轮 task.py start 已激活准确子任务。最终 manifest=review、resolution=implemented，Trellis=in_progress；等待人工接受实现、上述验证和残余风险，不 archive、不提交、不 push。

无迁移/backfill；新模块尚未接生产，可独立撤销当前任务的新增模块/测试/文档增量；不得删除历史审计或发布件，不触碰其他任务/dirty。

建议单个工作提交：feat(translation): add collision-safe protected token codec。

精确提交范围：

- 新 Codec 和 tests/test_protected_tokens.py；
- Codec Spec、backend index 的本任务新增入口、translation-design 的本任务增量；
- 当前 TR-402 目录全部正式规划/调查/验证/context/元数据；
- manifest 仅 TR-402 stanza；父 task.json 仅前一规划轮新增的 TR-402 child 链接。

manifest 和父 task.json 早已有其他任务的 dirty，必须按本任务 hunk 精确选取，不能全文件混入。排除 workspace journal/index、backlog、CON-104 prompt、SC1259/RND-504/TAB-307/308、其他归档目录及所有非任务改动。未执行任何 git add/commit/push，等待用户确认。

本任务一次性快照和 P1 JSON 仅用于核对，正式结论已固化于本记录，结束前清理；测试 ZIP 已自动清理，无本任务后台进程或端口。Trellis 当前会话指针是待审核任务的有效运行状态，保留。

审计 Bundle：20261021T041920Z-tr-402-protectedtokencodec-implementation-de863c8c；SUBAGENT_EXECUTION_DIGEST、audit-finalize、audit-verify 均通过，无异常或残留活跃 Worker。代理责任验收不是用户对功能的人工验收。

## 7. 2026-10-21 人工验收

用户随后明确接受实现、测试证据和残余风险，并确认当前提交计划，授权本任务提交、归档与会话记账，不 push。本节之前的 review 状态为实施交付时的历史事实；最新收尾状态及轻量复核见 [closeout.md](closeout.md)。
