# TR-406 revision 2 审查处理决策

日期：2026-10-22。来源：revision 1 的 fresh architect 独立审查，审计 `20261022T021032Z-tr-406-revision1-fresh-architect-review-3ca8901c`；用户已确认两项 P2 并授权本轮只修订规划。

## 处理状态与边界

两项 P2 已在 revision 2 的规划层补充明确合同及验收，不表示实现已修复、候选竞态测试通过或新稿已获独立复审。三件套仍待人工审核，Trellis/manifest 保持 planning，implementation_authorized=false。

不新增持久字段、安装标记、事务日志、扫描器、通用事务/队列框架或外部 Provider 测试；继续使用既有 job 锁/事务、batch 字段、确定性计划与 generation reducer。依赖兼容基线准入和生产写者启用门保持；本轮不恢复已删除父任务文件。

## P2-1 初始根计划一次性安装

原问题：两个初始化调用都先判空，迟到的调用可用相同确定性 ID upsert 覆盖 status/attempt/lease/result；单条 create 加锁不能保护完整计划及调用预算账本。

修订决定：

- 安装单位为同 job/generation 的完整根集合。锁外从已验证不可变 source/config 计算 expected plans，锁内重核父 job/generation 与实际根集合，预期完整性不能由当前记录自证。
- 完整既存根集合只能返回权威现态；create 不得覆盖已有 ID 的可变状态。已 split 的根仍保留原计划身份，子树另核；既有成功/运行账本及结果身份不重置。
- sqlite/MySQL 一次事务安装完整根集合或回滚；file 同 job 锁内逐文件原子写，安装完成前不投递/领取。非空但残缺/多根/不一致的集合在恢复和消费前明确 tree_invalid、主任务失败，不补根、不消费部分计划。
- 已换代、已终态的迟到初始化不得安装或推进；零计划仅在权威 source 确认为零 items 时成立。

映射：PRD R3、AC12；design 3.1.1；implement B 节的根计划端口、入口核验与测试矩阵。AC12 必须有“双初始化 B 判空暂停→A 一根成功/另一根运行→B 恢复”barrier、数据库 rollback 和 file 部分写入中断，不以简单重复 create 代替。

## P2-2 终态窗口的消费入口闸门

原问题：终态叶子 CAS 已提交而 job.failed 尚未写入时，只核父 job 和当前 batch 的 claim 仍能新领取兄弟；终态自身重放被拒绝后直接返回，无法完成本次失败收口。

修订决定：

- 持久化终态叶子或 tree_invalid 本身即为本代停止依据。enqueue/claim 在同 job 锁内从完整当前代快照计算停止结论，再决定是否允许新工作；不能只看父 job.status。
- 同代因停止结论拒绝后，释放锁并调用幂等 finalizer；终态自身和排队兄弟的消息都必须走此路径，不依赖额外主任务 replay。不在锁内调用 Provider/对象 I/O，不新增跨域 exactly-once 承诺。
- 区分普通合法 claim 竞争（不误记失败）、同代停止（收口后返回）、已换代/终态（不改新代、不复活）及真正存储异常（保持可见）。
- 终态前已合法领取的在途请求不承诺强制取消，真实调用审计保留，但停止结论出现后不得晋升其成功结果。只有成功推进 job 终态的执行者写 stage_failed，重复收口不重复终态事件。

映射：PRD R1、AC13；design 3 的立即失败边界和 3.2；implement B/C 节及测试矩阵。AC13 在 terminal CAS 后、job 更新前中断，分别重放终态自身与排队兄弟，再重复重放，断言零新增 Provider、主任务失败和零重复终态事件；包含普通竞争、换代交错对照。

## 验证口径

本轮验证规划结构、映射、JSON/JSONL、context 路径及变更范围，并运行 task.py validate。revision 1 的37项测试和fake探针仍是历史证据，AC12/13 是计划中的候选验收，未在本轮运行。旧审查 Bundle 已关闭，不改写其任何证据；本记录表达对旧审查的处理，不声称有第二轮独立审查。
