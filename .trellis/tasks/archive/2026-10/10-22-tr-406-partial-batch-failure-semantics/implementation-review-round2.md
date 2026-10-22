# TR-406 独立实现复核：第二轮

日期：2026-10-22。独立 critical_reviewer 只读复核，主会话依据最终报告整理。审查中源文件持续修订，**本轮不出具最终候选通过结论**；后续须对冻结候选做第三轮闭合验证。

## 首轮问题状态

- R1：源码已移除写事务内的前置普通读，采用事务外 job 定位、事务内 job→batch FOR UPDATE 当前读，原 RR 旧视图路径已消除；未实测真实 InnoDB。
- R3：service 改为按同一快照返回的 job.retry_count 过滤，原 API 换代混合窗口关闭。
- R4：终败时 stopped 优先于 retrying；终态 job 没有原始 terminal batch 的残留也已修。独立探针得到 failed/active=0/row=stopped。
- R5：计数从本次 disposition 得出；独立运行 workflow 模块11项通过。
- R2 曾残留P1：reason_code=call_budget_exhausted且lease有效的特殊放行，可让真实终败兄弟之后的结果晋升。修订已删该例外；独立探针对照为终败兄弟 promotion_accepted=false、仅合法running占最后预算 outcome=running。该探针不代替整组仓储/执行复审。

## 新增确认问题与必要回归

| ID | 严重级别、审查时锚点 | 具体触发与解除条件 |
|---|---|---|
| R6 | P1，execution.py 原1420/1450 | 旧代TreeInvalidError释放锁后，其他执行者先失败收口0并用户retry到1；旧catch重读latest并把它当错误owner传_mark_failed，实际探针把新代1标failed/tree_invalid。失败条件必须保留原claimed generation；换代只观察，不重绑错误。 |
| R7 | P1，execution.py 中间版本1593–1596 | claim None分支返回reconcile的BatchRecord，上层把非None当取得执行权，普通loser或停止拒绝可继续Provider。claim必须reconcile副作用后明确return None；其他结果返回合同另行处理。 |
| R8 | P2，execution.py 原1549/1398/1690 | 锁外summary正常后兄弟持久终败，真实claim/CAS拒绝；直接返回导致job仍running、finalizer_count=0。None后须同代一致快照归约和必要finalizer，普通竞争/旧代不误失败。原测试先手工job.failed，不是真正AC13中断窗口；必须保留重放前job.running断言。 |
| R9 | P2，execution.py 原1187/1844/2305 | file正常持锁写parent→child1→child2时，执行侧无锁list读到半树并误判损坏，等待writer完成后仍把健康job失败。所有执行读必须走同job job+batch快照，区别真正崩溃残树；不能只修API。 |
| R10 | P2，execution.py 原1429/1662/2494–2501 | Provider成功及成功审计后，Artifact或仓储I/O被宽catch当成retryable translation_provider_failed。独立探针见Provider1、batch retryable=true、job running。须在实际I/O owner边界按原代次收口oss_failed，不伪造第二审计或重调Provider；Artifact及后续CAS/数据库异常都需覆盖。 |

Owner 已收到所有反例并交付修订：execution 的新验证记录为15项新模块、合并45项通过；storage 当前10项方法及组合34项通过。以上是owner记录，尚不等于第三轮独立验收。

审查还追踪了权威source/config计划、根消费核验、attempt/lease、fan-in来源与evidence、物理身份、下载allowlist与QA文件选择，未发现新增 partial 直接晋升路径。未运行大套件、真实DB或Provider。代理未修改文件。

## 审查结束时源哈希

本轮开始/结束时 repository、workflow、execution 和三 adapter 均有变化，不能将阅读旧版本的结论套到结束版本；service/router/schemas在本轮内一致。以下结束哈希仅作复审输入锚点：

| 路径 | SHA-256 |
|---|---|
| app/domains/document_jobs/repository.py | 1d4d1d7041d74a4da6dc686bd0af455394624ca2c4700a75d3a1d3e1bc986a9d |
| app/domains/document_jobs/workflow.py | 8b9cba3987c0b303a583fe66c5979ab323264b60aeabdfef9ada795b394bebce |
| app/domains/document_jobs/execution.py | 21788eb333abee666ac58ce194a076db12b2c773ff0b622680c195857e4a78e3 |
| app/domains/document_jobs/service.py | 759bba99d37204ea9282d7cfbd293152edfb5983171bd11cfae6ec96b9335294 |
| app/domains/document_jobs/router.py | 3006677804e202f505ff337167c6c65e0ac35ab24ba5569044058bf03ada6040 |
| app/domains/document_jobs/schemas.py | 84e5397f6231ade3749d310678713b1da79c4516b843f96027a97c3b1fabb47d |
| app/infrastructure/persistence/file/document_jobs.py | a4c28eea96dca3c2f37d3d8c3e1a71e03f0d916c3b3e0a2bf5399d7dfea90978 |
| app/infrastructure/persistence/sqlite/document_jobs.py | 3928dc6babab82d5ca75effcc68249210201757dc308dfaacf10be22a082851c |
| app/infrastructure/persistence/mysql/document_jobs.py | 783c29b05d44a8f0592d7586588fc7b9e6b307595e341061eb08d2ec0ddc161a |
