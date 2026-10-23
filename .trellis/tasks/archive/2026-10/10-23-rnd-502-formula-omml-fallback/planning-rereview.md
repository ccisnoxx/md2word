# RND-502 v2 全新 architect 独立复审

日期：2026-10-23（Asia/Shanghai）；规划版本：2；状态：planning，等待人工审核，未授权实施。

## 结论与审查身份

本轮未发现新增确认的 P1、P2 或 P3 规划缺陷。上轮 P1 翻译数学边界、P2 预期输出绑定均在 v2 规划层闭合。主会话对照相关真实代码核实后，保持 prd/design/implement 的 v2 技术内容及原字节不变，不为复审机械增加分支、接口或任务。

用户明确要求再派一位全新 architect。实际代理为 `/root/rnd502_v2_fresh_architect_rereview`（Ramanujan），角色 architect，`fork_turns=none`；未继承主会话，不复用上轮代理。它独立读取三件套、根 AGENTS、相关 Spec、真实源码与测试源码，执行三组纯内存探针后返回完整报告。

被审 HEAD=`c56e12832ff30212cc067d0909430cf5f091f79b`，实际分支=`codex/pre-rnd501-local-wip`。输入 SHA-256：

| 文件 | SHA-256 |
|---|---|
| prd.md | bf71350842457fae84be7f80cdb6d70c45507f4feadebe0e38b5774f589abbde |
| design.md | 207980e2ab95006ae3f3f4a91b6df574986322d042006b4c291927ce5c0f7346 |
| implement.md | 5c099b8a6a39c79283c212d2af0e70c97194c08d7c3184781e5c9b715546c7e9 |

此结论只评价规划的边界、可实施性与既有合同相容性。业务代码尚未实现 v2，不能据此声称 scanner、输出投影、恢复接线、并发、Word 输出或正式验收已通过。

## 上轮 P1：翻译数学边界已在规划层闭合

真实 `_append_table_text_nodes`（`app/domains/translation/document_ir_translator.py:523`）会抽取数学标签内部的非空 text node；Codec 数学规则（`protected_tokens.py:118`）没有裸 `<eq>`，Validator（`integrity.py:255`）只核对已有技术 inventory。

v2 design.md:44–48 与 implement.md:17 已明确：converter 保留可保护数学表示；明确数学 DOM 子树不抽作翻译目标；其余已识别数学片段须检查原 Codec 真实覆盖；无法完整保护则在 Provider 前安全拒绝，顶层沿用 translation_failed。排除数学节点仍按全部非空节点递增原 index，和现有 `_replace_html_text_nodes` 的 :583–589 相容，不让后续普通正文 ID/回填位置漂移。

复审代理用真实 extract→prepare→validator→apply 复现旧触发机制：表格含 Before、`<eq>\text{High Low}</eq>`、After，当前 ID/index 为 0/1/2，FORMULA Token 为 0，fake 改 High→Changed 后仍 passed。它没有把当前业务仍存在的缺口重新当作 v2 新规划问题；v2 的主动篡改、HTML 交错、普通正文和调用前拒绝门禁正针对这一机制。

主会话再次读取同步入口 `document_ir_translator.py:149`、计划抽取入口 :207 及回填 :580，确认共同准备边界和原索引规则可承载该方案。无需修改 Codec、Provider 或建立第二套翻译流水线；识别精度仍须实施后验证。

## 上轮 P2：预期输出绑定已在规划层闭合

现有 `renderer/evidence.py:49`–70 主要记录通用计数，`docx_quality.py:191` 的文字投影不保留脚本结构。复审代理独立生成 x=1 的 DOCX、加入固定书签、仅将值改为 x=2，确认现 evidence 相等；这说明旧问题真实存在，并非 v2 已经实现。

v2 design.md:80–86、PRD AC5 与 implement.md:62 已将预期基准与最终写入区分：写 document DOM 前从转换结果确定 `formula-output/v1` 投影与哈希，最终按完整书签范围重建比较 literal 原式/提示、semantic 文字/上下标、OMML 节点/次序/值/数学语义属性/显式样式及 tag 编号。

主会话核对 v2 合同包含相同 source/anchor/mode/count 下的数字改值、脚本错位、原式截断、提示遗漏负例；它不再仅以源哈希或计数证明实际输出，也没有将写入一致性哈希替代 parser 数学语义测试。该 P2 在规划层闭合，不需追加 TeX 引擎。

## 三类恢复入口与 receipt/generation

| 入口 | 真实合同 | v2 与主会话核验 |
|---|---|---|
| 无明确指针的 legacy 扫描 | execution.py:3367–3390 限同代/最终 IR、检查唯一性、保留期、实际 checksum/size，重算 evidence 逐字段比较 | design.md:106–109 保留无报告旧证据形状；有新标记严格核验，不能以缺损报告退回 legacy。 |
| 明确历史 result_file_id | execution.py:3360–3366 按任务归属、类型、uploaded/期限复用，:3067 的兼容完成不要求旧文件等于当前代最终 IR；test_document_job_execution_stages.py:417 保护跨代复用 | v2 保留该例外，用文件原绑定 IR 解释报告，不强制当前代 IR/generation，不把历史报告导入新代质量摘要。 |
| 已有 receipt 的物化恢复 | execution.py:3052/:3243 绕过 legacy 扫描，:3257–3262 使用 generation/最终 IR/receipt ID 条件完成 | v2 要求该入口也核验选中描述、字节和新报告；I/O 在锁外，恢复损坏沿 uploading/oss_failed 收口，保留 receipt，不换件或重渲染掩盖。 |

主会话重读上述执行路径，确认三入口确实不能用一个扫描分支替代。`result_state.py:43` 优先保留先选 receipt，`files/result_registration.py:16` 比较不可变描述/metadata；file、SQLite、MySQL 的同 job 序列化点读取最新记录后调用 patched_job，适合锁内从选中 receipt 合并安全摘要。换代清质量和复核由 delivery_state_patch，清 receipt 由 retry_job 负责，v2 不绕过这些 owner。

没有新增数据库表/列、第二状态 owner 或扩大 receipt 协议的必要证据。并发/真实 DB/存储结果仍需实施期验证。

## 在途计划、错误映射与诊断出口

复审代理使用真实树 validator，对“排除数学目标但保留普通目标”和“新计划变零单元”两种新 expected plans 与旧根集合比较，均返回 `translation_batch_tree_invalid`。

主会话独立读取 `app/domains/document_jobs/workflow.py:377`：空计划只有同时没有 batches 才是 zero-unit；存在旧 batches 的空计划直接拒绝，已有根必须与 expected plan 的不可变字段和 item 集合相符。仓储 wrapper 在 repository.py:97 将无效树转为稳定异常，execution.py:2555–2575 重建/传入计划并按既有失败语义收口。因此 v2 的不覆盖旧代计划、排空或使用兼容执行器有实际落点，不是新增持久化格式的借口。

`DocumentIRTranslationError` 沿 execution.py:3479 映射 translation_failed；v2 分开新渲染的 quality_checking/render_failed 与恢复期 uploading/oss_failed，没有要求吞异常、伪造 batch 或 AI 调用日志。

质量/文件登记事件目前展开 metadata，docx_quality.py:153 有旧 latex_residue_examples；v2 design.md:88 同时要求过滤旧原式出口与新逐式报告。files API 的完整 metadata 仍受 tenant/company owner/admin 限制，任务文件列表沿原白名单；“私有”没有被扩大解释为新权限。复审未确认新增出口缺陷。

## 实际验证、只读与剩余门禁

- 代理执行三组 `.venv/bin/python -B` 纯内存探针：旧 P1、旧 P2、两种旧根集合与新计划不匹配。全部正常完成，无外部 Provider/服务调用。
- 主会话独立核对上述关键源码及 v2 验收，不重复未变的旧基线测试，也不把业务现状探针当成未来实现的通过证据。
- 复审完成、主会话写记录前：913 个已有文件 SHA-256、完整 git status、index tree 与启动快照一致，未观察到仓库文件新增/修改/删除；包括既有 `.serena` 文件均保留。
- 本轮只补审查记录、研究状态、task metadata、RND-502 manifest 记录；三件套保持上表哈希，不升 v3，不改业务或其他任务状态。最终 task validate/工作区保护结果见 planning-validation.md。
- 未运行实施后测试、完整回归、真实 MySQL/S3、线上 Provider/MinerU、外部样本或 Microsoft Word 人工验收；这些仍为 implement.md 的实施门禁。
- 未激活任务、未提交/push/归档。planning_approval.accepted 仍为 false，等待人工审核 v2；本轮独立复审不替代用户实施授权。
