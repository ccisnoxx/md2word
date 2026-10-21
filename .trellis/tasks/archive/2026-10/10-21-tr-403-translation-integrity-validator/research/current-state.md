# TR-403 调查证据（2026-10-21）

## 1. 工作区、规则与依赖

- 首条 shell 已执行 pwd 和 git status --short，目录为 /Users/sc/PycharmProjects/md2word；实际分支 md2word/TR-402，HEAD=c8fd2afc7dfea349b7fbc3e1f516d85adcb57536。
- 已有 tracked dirty：父任务 task.json、workspace/777 的 index/journal、CON-104 prompt、backlog、manifest；untracked 为 SC1259、RND-504、TAB-307/308 和多个归档任务。创建前读取并保护 386 个既存 dirty/untracked 文件哈希；不清理、不 stash、不覆盖。
- 已读根 AGENTS.md、用户补充规则、/Users/sc/.codex/RTK.md、完整 workflow、guides/backend/frontend index，backend directory/error/quality/logging/database/mode/Codec 规范；没有作用域内额外 AGENTS.md。
- 已读用户指定的 11 份文档：product prd、scope-and-decisions、implementation-plan、完整 backlog、execution-guide、manifest、architecture-decisions、document-ir-contract、translation-design、testing-acceptance-strategy、rollout-and-migration；另查 current-gap-analysis、TR-403 task prompt。prompt 内的后续实现/切分支命令仅为证据，不构成本会话授权。
- 已读父任务 task.json 与 prd/design/implement，及 TR-402 归档的 task.json、三件套、research/current-state、closeout。相关历史结论已在正式 task/Spec/提交中，无需再读取会话全文。
- TR-403 原 todo/path=null；唯一直接依赖 TR-402=done/implemented，归档 completed，有人工接受实现、证据和残余风险记录。git merge-base --is-ancestor 24ed6a717ca86cf5ed086f2eda58030e4af66810 HEAD 返回 0。
- 全部 task.json 未发现 TR-403/同 slug；复用父 .trellis/tasks/10-12-datasheet-docx-delivery-quality，以 task.py create --parent --no-start 创建唯一子任务 .trellis/tasks/10-21-tr-403-translation-integrity-validator。

## 2. 当前真实链路

| 源码位置 | 调查事实 |
|---|---|
| app/domains/translation/document_ir_translator.py:114 | 同步 translate 深拷贝；_split_provider_batches 按源 item 长度，build_provider_request 直接用 source items，验证后累加 dict，所有批次通过才 apply。 |
| 同文件 :157、:234、:250 | Worker 的 build_translation_plan 按源页/字符和 item 数计划；request 注入原文命中术语，没有 Codec。 |
| 同文件 :435、:519、:530 | 抽取 text/list/html 会 strip，跳过 formula block，不显式抽取 annotations；validate_result 只比较有序 ID；apply 回填 text/list/html。抽取扩展属 TR-401/404，不在本任务改 ID 体系。 |
| app/domains/translation/protected_tokens.py | TR-402 已交付 frozen 内存 ledger、collision-safe namespace、每次独立占位、归属/次数/语法校验和一次恢复；普通新增裸技术值不在 decode 责任内。 |
| app/domains/translation/integrity.py | 当前不存在。 |
| app/domains/translation/provider.py:128、:219、:257 | 验证绑定 Prompt hash 后追加语言/JSON指示；JSON parser 从首尾括号截取且去 code fence；items 类型强转/strip，无严格额外字段检查。 |
| app/domains/document_jobs/execution.py:1154、:1198、:1216 | 独立 Worker 入口重抽源 items、调用 provider.translate、validate_result，不能只改同步服务。 |
| 同文件 :1321、:1391、:1497、:1873 | 现有统一 retry/call budget，JSON 截断拆分，叶子失败终态使用 translation_failed；ValueError/KeyError 泛化为 invalid_response。本任务不重做该编排。 |
| 同文件 :1553、:1655、:1672 | fan-in 只查 missing/extra 后 apply；loader 只读取 items；translation-batch-result/v1 有 job/batch/generation/source envelope，但消费时未充分对账。 |
| app/domains/translation/audit.py:61、:106、:173 | 默认 metadata-only，全文 debug 另走 Admin 开关/TTL；普通失败 message 仅替换 Prompt/截断，不能保证任意外部异常无全文；没有 integrity evidence。 |
| scripts/dev/formal_mineru_conversion.py:71、:220、:266 | local response dict 会覆盖同 ID，并按 request 选择/重排；导出源 item 请求计划，之后实际 service.translate 重新拆批。新编码接线必须同步此调用方。 |

## 3. 只读反例与基线（本轮实际执行）

使用项目 .venv Python、PYTHONDONTWRITEBYTECODE=1，内联调用现有函数，无临时业务脚本，无外部 Provider：

~~~text
current_validate_accepts_changed_technical_content = True
codec_alone_accepts_added_raw_quantity = True
provider_trims_id_and_coerces_number = True
external_provider_calls = 0
~~~

对应输入分别为：同 ID 的 OPA228/25°C/0x0028[4:0] 改成 OPA999/99°C/0x0042[7:0]；合法编码 items 末尾附加 extra 999 V 后 decode；带空格 ID、数字 text=123 及额外字段经 _parse_items。三项均实际接受，证明不能建议 skipped_existing，也不能只在正式入口调用 decode 就认定完成。

实际命令：

~~~bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_ir_translation tests.test_protected_tokens
~~~

实际结果：35 tests，0.016s，OK，退出 0。现有结构/批次/术语/Codec 回归基线通过，但未覆盖上述正式完整性缺口；不能作为未来 Validator 成功证据。

## 4. API、持久化、配置和样本

- models.py:200 起是内部 id/text frozen DTO，无 ledger。document_jobs/models.py:181、schemas.py:227 和 router.py:738 将 batch.error_code 作为可空字符串投影；现有 GET /document-jobs/{job_id}/translation-batches 先校验任务可见性，仅当前 retry_count generation。
- file/sqlite/MySQL 仓储均有 batch payload 与状态/generation CAS；MySQL 实际实现位于 infrastructure/persistence/mysql/document_jobs.py:330，schema 无新 Validator 需求。不改其原子性承诺，不以 fake 代替真实 DB 并发保证。
- 文件服务复用 register_generated_content 和 checksum 字段；普通 read_file_content 不构成本任务 fan-in 已核验 checksum 的证据。应在消费边界明确核验。
- config.py:66–69、:111–118 有并发、lease、attempt、字符预算和 debug 默认；不存在 TRANSLATION_PROTECTED_TOKENS_ENABLED。目标 rollout 中的建议不能冒充已安装配置。
- resources/prompts/translation_en2zh.md:53–65 与 ru2zh:53–67 及 zh2en/zh2ru:29 有旧 PH 语法/局部技术内容本地化指示；不原地改 seed/历史 Profile。通过已有运行附录机制告知编码协议，冻结 PRD/ADR 优先，无需改变冻结决策。
- tests/test_document_ir_translation.py 已覆盖 11 项同步结构/计划/术语；tests/test_protected_tokens.py 有 24 项 Codec 合同及公开 OPA228 converter/extractor roundtrip；没有正式 Validator 行为测试。
- tests/test_fastapi_jobs_backend.py:9892、:10127、:10278、:10333、:10399 有 Worker/audit/debug/截断/retry；其 fake 当前返回固定原文字段/数字，需要保留占位符的适配，不得放宽断言。
- scripts/dev/formal_mineru_conversion.py 是正式本地工具；docs/dev/local-conversion-sandbox.md、tests/test_conversion_sandbox_dev_tools.py:268 维护导出前缺 key 失败合同。
- 真实最小公开 fixture：tests/fixtures/component_pdf_samples/samples/texas-instruments/op-amp/ti-opamp-opa228-p1-smoke/mineru/component_content_list_v2.json；已被 TR-402 证明含 OPA228、3 nV/sqrt(Hz)、10 V/us。继续走正式 converter，不造第二解析器或提交专有全文。
- 当前 P1 manifest 主要 en2zh；matrix 的 SAMPLE_SETS 只有 phase2-core、ru2zh-acceptance，模式只有 direct/en2zh/ru2zh，没有 translation-core 或四方向完整集。P1 既有认证缺口保留；本轮不读取凭据、不运行真实模型/线上预检。
- check_release.py CLI 只有 runtime-url/Golden preflight 等选项，没有 skip-unit 选项；默认已经运行选定 API/Renderer 等回归和 OpenAPI 检查。计划在稳定实现候选执行，不在每步或本规划轮执行。

## 5. 结论和证据边界

本任务需要新增 Validator 并做正式双入口、持久化消费和最小本地调用方接线。DB/API DTO/前端/发布不需要新增实现；legacy runtime 不是正式新链路 owner，保持既有行为不扩建。

不运行未来不存在的测试，不把规划校验当行为验收。未执行 release、完整 component/Golden、P1、真实模型、线上环境、Microsoft Word 或 DB 并发验证；这不阻止 fake/adapter 完成范围内规划，实施及阶段验收的残余风险必须分别记录。
