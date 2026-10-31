# TR-406 revision 2 独立架构复审

日期：2026-10-22。对象：revision 2 的 prd.md、design.md、implement.md。

本轮使用另一位全新 architect，fork_turns=none，不复用 revision 1 代理或其上下文。独立只读核对三件套、修订记录、相关 Spec/产品合同、实际源码/测试及 CON-102 验收提交。主会话核对关键文档锚点并接受复审交付；本报告由主会话根据子代理最终答复整理落盘。

审计 ID：`20261022T025037Z-tr-406-revision2-fresh-architect-rereview-65579610`。

## 结论与严重级别

两项原 P2 均已在 revision 2 的规划层闭合，AC12/13 覆盖原交错反例。未发现新增或残留的确认 P1、P2、P3 规划问题，可以进入人工实施准入评审。

本结论不等于用户批准三件套或授权实施，也不代表未来候选竞态测试通过。三件套正文保持 revision 2；其中“尚未独立复审”表达发稿时状态，本报告提供发稿后的复审证据，不改写原稿。

## 原 P2-1：完整根计划一次性安装——规划层闭合

| 位置 | 闭合依据 |
|---|---|
| design.md:66、:68、:69 | 安装单位为job_id+generation完整确定性根集合；锁外基于已验证的source/config计算expected plans，锁内重读父job/generation及全部当前代批次；已有记录不能自证计划完整性。 |
| design.md:71 | 区分不可变计划字段与可变状态，完整既存集合返回权威现态，不覆盖status/attempt/lease/result；已split的根保留原计划身份，所有在用create入口服从不可覆盖合同。 |
| design.md:70、:72 | sqlite/MySQL同连接事务安装完整集合或回滚；file整次安装共享job锁，各文件原子替换；非空残缺集合在恢复/消费前拒绝并失败，不补根、不消费部分计划。 |
| prd.md:84（AC12） | 精确覆盖B判空暂停、A安装并使一根成功/另一根运行、B恢复；账本及结果身份逐项不变，成功兄弟零重调；包含DB回滚和file中断。 |
| implement.md:22、:23、:76、:77 | 端口、入口接线、真实barrier、数据库回滚和file部分安装验收均已落实，不以单条加锁代替。 |

architect对照当前execution.py:1072/:1144和三adapter create/upsert，并通过git show核对CON-102验收实现，确认原风险来自“判空→逐条写入”的整体边界。revision 2在正确仓储owner补齐合同，无须安装标记或事务框架；没有把当前代码尚未实现新合同当作新增规划缺陷。

## 原 P2-2：终态失败窗口消费闸门——规划层闭合

| 位置 | 闭合依据 |
|---|---|
| prd.md:29、design.md:56 | 已持久化terminal/tree-invalid本身就是停止新工作的依据，不等待父job.failed。 |
| design.md:80、:86 | enqueue/claim在同job锁/事务内检查完整根计划和全代停止结论，再核状态/attempt/retryable/上限/预算；停止检查与领取的线性化点明确，结果晋升同受约束。 |
| design.md:84 | 同代停止拒绝后释放锁并调用幂等finalizer；终态自身及排队兄弟均覆盖，不依赖另一次主任务replay；普通竞争、旧代/已终态、真实存储异常分别处理。 |
| design.md:88 | 主任务终态推进使用预期generation的原子更新，只有成功推进者写stage_failed，重复收口观察现态。 |
| prd.md:85（AC13）、implement.md:32、:33、:78 | terminal CAS后中断、两类消息分别重放及再次重放、零新增调用/完整失败收口、普通竞争与并发换代对照均有明确验收。 |

architect对照当前execution.py:1176的claim拒绝返回及:1388到:1427的分步失败路径，并核查CON-102验收实现，确认revision 2已补足消费入口合同。验收可区分真正闭合与只调整finalizer顺序。

## 新增问题检查与保留边界

- 模块与状态owner清楚：workflow拥有纯判定，仓储/adapter拥有账本和事务，execution拥有编排/锁外I/O/finalizer，service拥有用户retry和权限。未出现第二条翻译链路或第二个发布资格owner（design.md:25）。
- attempt/lease：唯一claim身份、预期attempt/lease、观察到的lease到期回收、job→batch锁序、同连接事务及运行期绕写限制完整（design.md:80）。
- partial/跨代retry/不可变：源IR可从权威指针继承，新代重建批次，不重包旧译文；中间evidence不得晋升目标IR/主件，普通下载/显式file_id/QA latest/debug与历史字节保护均已进入验收（design.md:94、:100）。
- 无DDL/backfill；停入队、排空旧Worker后同步部署，不混跑新旧attempt写者；回退须保持generation/attempt/完整性门，否则保持停执行（design.md:136）。
- 兼容依赖基线仍是实施门：当前HEAD=596a2de7ed29edb7fdb378d91c17bda09b7f1066；TR-403验收提交可达、CON-102两个验收提交不可达。未将manifest done误当源码已整合；未来实施须保留两者stage/原子retry/receipt与完整性/evidence/脱敏/物理身份合同。

已接受的局限：file残缺安装明确失败并由用户新代retry；无消息时不新增主动扫描；终态前合法claim的在途请求不强制取消；不承诺job/batch/event跨域exactly-once。这些已写明且不与AC12/13冲突，未列为新增缺陷。

## 证据、只读保护与当前状态

- 子代理完成后、主会话保存本报告前，对派发前1427个tracked/untracked路径核验：无字节变化、无新增路径、HEAD未变；三件套哈希与派发前一致。父任务六个既存删除保持，未恢复。
- 子代理仅做文档、源码及验收提交只读核验，未重跑历史37项测试、未执行AC12/13候选测试、task.py validate、真实MySQL/InnoDB、部署FS、Provider或浏览器验证；主会话也未重复这些行为验证。上轮context校验9+9只作为既有结果，不冒充新验收。
- 本轮主会话仅新增planning-rereview.md和仓库外审计记录；三件套、task.json、manifest、context和业务文件未改，不start、提交、push或部署。
- 实际实施仍须组成兼容已验收基线、获得最新规划的人工接受与明确实施授权，候选并发测试/独立实现复核及生产写者启用门继续保留。
- 审计工具的independent_review字段只支持reviewer/critical_reviewer，本轮按用户要求使用另一位fresh architect，独立实现复核计数为0；“验收通过”仅指复审报告交付被接受，不表示规划获批。
