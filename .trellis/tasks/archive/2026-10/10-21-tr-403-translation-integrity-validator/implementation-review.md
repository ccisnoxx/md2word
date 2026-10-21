# TR-403 实际候选复核与审计

日期：2026-10-21。主会话已核对实际 diff、相关路径与回归，不以规划 architect 复审替代代码复核。人工验收尚未完成。

## 独立复核发现与闭合

首次 fresh critical_reviewer 对实际 15 个业务/测试候选文件及相关合同作只读高风险复核，确认一个 P2，无其他已确认 P0/P1/新增问题：首次无 batch 建批的编码预算错误从 execute_job 逃出后，因 TranslationIntegrityError 继承 ValueError，被归为 document_ir_failed，丢失翻译顶层分类与安全 evidence。批次执行阶段的预算用例不能覆盖该路径。

主会话增加真实 execute_job 的无 batch 测试，先得到 document_ir_failed 与 translation_failed 的断言失败，再做最小修正：

- execution.py 的 classifier 在通用 IR 错误之前识别 TranslationIntegrityError；顶层仍使用既有 translation_failed，不新增状态/HTTP 错误。
- execute_job 只从两种已知翻译领域错误传递 evidence；_mark_failed 的内部可选 integrity 参数默认为 None，有证据时才加到既有 stage_failed payload。保持原状态/阶段/expected_retry_count 条件更新，CAS 拒绝不写事件。
- 无 batch 时 binding=null，不虚构批次或 Provider 调用。摘要保留专码、stage、计数与哈希，不含全文；无成功 batch result、目标 IR、DOCX 或 apply。
- 新测试的文件类型断言采用真实 generated_word，并验证源 IR 数量和权威源/目标指针不变。最终单测及受影响 50 项回归通过；最终 release 202 项通过。

另一次 fresh、隔离上下文的 critical_reviewer 对本修正和调用影响独立增量复核，未发现新增/残留可确认问题，确认 P2 闭合。其实际运行的四组纯内存探针覆盖：真实 execute_job 首次计划、安全日志/事件且重复投递不重复记录、默认 payload 与旧代 CAS 拒绝、两类翻译错误及普通 ValueError 映射；限定 diff check 通过。其没有重跑主会话磁盘集成门、50 项或 release，也没有声称完成新的全 15 文件审查。

## 审计证据及限制

实施审计 bundle：20261021T073958Z-tr-403-implementation-65e44429。初始计划与派发门通过；执行中本机 Codex config 指纹发生变化，后续 summary 报 codex_config_evidence 不匹配，未取得覆盖全部实现工作的有效 SUBAGENT_EXECUTION_DIGEST。旧计划/执行记录保留，不恢复配置、不改写历史指纹。无法可靠报告整个实现阶段的聚合尝试数、验收数或写入证据状态；不得把子代理自报当作完整审计。本地业务证据由主会话直接命令、实际 diff 和起始工作树哈希保护核对提供，见 validation。

独立代码复核单独使用当前配置形成 bundle：20261021T080957Z-tr-403-independent-implementation-review-0e06a705。该 bundle 的两个 stage 仅覆盖上述候选审查和 P2 增量复核，不覆盖实现 Worker，不作为整个实现审计的替代。

已执行 summary、digest、render-digest、audit-finalize、audit-verify，退出 0；closed/passed，14 个审计 artifact，无错误/警告。该限定范围的 Digest 显示计划 2/2、复核交付物 2/2 accepted、独立复核 2、无残留活跃 Worker，写入观测 2 无写入。accepted 指复核交付物被主会话接受，不表示用户已验收业务实现。

业务/测试 15 文件在首次复核前后哈希完全一致；第二次复核期间主会话只把新增测试的错误文件类型断言改为 generated_word，逆向该已知精确改动后 15 文件哈希一致。此保护核对补充只读范围证据，不替代行为测试或 diff 审查。

## 残余风险与人工评审门

- P1 preflight 缺认证而退出 1；translation-core 样本未注册，矩阵未运行。未测真实外部模型、真实 S3/MySQL 并发、Word/WPS 人工效果或完整四方向实译。
- finite Codec 语法、同 item 内技术值语义关联、全局 lease fencing 与批次最终失败主任务产品策略没有因本任务而扩张保证。
- 上线需要暂停翻译入队并排空旧 Worker/活跃旧代，同步部署；不能消费缺 evidence 的活跃中间结果，历史完成件保持只读。回滚不恢复无校验回填、共享物理路径覆盖或正文 repr。
- manifest 仅 TR-403 改 review，Trellis 保持 in_progress；未提交、push、archive 或启动相邻任务。等待人工验收和明确 commit plan 授权。
