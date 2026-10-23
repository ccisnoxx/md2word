# RND-504 修订 3 独立规划审查与修订追踪

日期：2026-10-23。用户授权一位全新 architect 独立只读审查，主会话核实并修订确认的问题；本轮仍只规划，不改业务代码、不 start、不提交/push。

## 审查身份、输入与只读证据

- 原生子代理：`/root/rnd504_v3_architect_review`，角色 architect，昵称 Plato，`fork_turns=none`；未继承父会话结论，也未安排其他代理。没有把平台配置当作额外模型运行遥测。
- 输入：修订 3 prd/design/implement、当前 owner/Spec/产品合同、源 `931d2f65738f7592a5b3e2dd4c528f9e1b2a0e19`、归档 `48818e9`、37 路径清单。原三件套已按字节保存在 `research/review-v3/`，下列行号均指该快照。
- 审查范围：历史实现复用、当前 CON-104/TR-406/RND-502/503 与独立对象键、质量合成、幂等/租约/中断、Artifact 与权限/回滚。
- 子代理报告前后及主会话修改前，986 个 tracked/non-ignored 受控文件的 hash 变化 0、新文件 0；HEAD/分支/cached diff SHA-256 不变。独立 probe 只在内存加载源函数和模型，使用内存文件服务/模拟时钟，无真实引擎或存储外呼。详 `research/architect-review-protection.json`。
- 原独立审查确认 2 项 P2；37 路径 Git source/source-parent/target blob 核对 mismatch=0。没有将生产 disabled、S3 已签 URL 有限 TTL、既有迟到对象回收限制列为缺陷。

## R1 / P2：登记中断后的预算耗尽缺少存储结果分类

原规划定位：`research/review-v3/prd.md:29`、`research/review-v3/design.md:78`、`research/review-v3/implement.md:62`。源依据：`931d2f6:app/domains/document_jobs/preview_state.py:151-158` 与 `preview.py:97-98`。

触发：initial 消费最后 attempt，Provider 返回后在 PDF/page/manifest 的 metadata 插入、对象写入或 uploaded 确认中进程退出，lease 过期恢复。源 exhausted 分支直接写 failed/blocked，应用将任何非 claimed/busy/stale disposition 当作完成；即使当前 manifest 为 null，也可进入主执行 completed CAS。账本没有区分当前 attempt 的登记阶段；前次失败 manifest 也可能被保留。

独立审查 probe：内存模拟 pending metadata 与对象已写、uploaded 确认前用 BaseException 表示进程退出。`max_attempts=1`，恢复观察为 `preview_finished=true / run.status=failed / manifest=null / quality=blocked / pending_files=1`；对照明确 Provider 失败则有 uploaded failure manifest。不是实际磁盘崩溃实验。

主会话独立核实：仅内存 Git loader 加载源原模型/claim/ensure_initial，最后一次 claim 后推进到 lease 过期，观察 `failed / manifest=null / preview_finished=true / blocked / preview_timeout`，恢复 Provider 调用 0。该 probe 只证实纯规则与应用 disposition；“登记中断”路径另由原 I/O 顺序和子代理的内存故障注入支持，没有伪称真实文件系统中断证据。历史 implementation-review 保护即时异常传播，未明确接受该 crash→exhausted 窗口。

影响：违背 P7 的“已可靠留证才可 succeeded+blocked，存储不可确认不得完成”，即时抛异常测试无法保护重启路径。

修订 4：design §6.1 明确当前 attempt 的最小登记阶段/确认归属与副作用前窄 CAS；未进入登记的 lease 接管和可靠终态复用继续支持，登记未知不因额度耗尽或历史重放变为完成。普通失败收口仅在原截止内登记并确认当前失败 manifest，不能再开 Provider/延长 deadline。登记未知采用原 storage failure 失败关闭，不引入通用事务或自动对账；独立重试不能改变原 execution 终态。PRD P7/AC3/AC5 和 implement 的恢复步骤/组合负例已同步。

状态：主会话确认并完成规划修订；同一 architect 定向复核确认 R1 在规划层闭合，不代表业务修复或实现验收。

## R2 / P2：成功复用未检查当前 Artifact 可用性

原规划定位：`research/review-v3/prd.md:27`、`research/review-v3/design.md:76`、`research/review-v3/implement.md:63`，生命周期见原 design:110。源依据：`931d2f6:app/domains/document_jobs/preview_state.py:127-136` 与 `preview.py:192-234`。

触发：初次成功后，按类型保留策略令 manifest 1 天、主 DOCX/PDF 90 天；第 2 天主件有效而 manifest 过期。新 UUID 内部重试仍只按 run.status=succeeded 建 alias，下载正确拒绝旧 manifest，却无恢复路径；继续请求只耗 key 额度。

独立审查 probe：内存应用链观察 expired 后 `preview_file_is_current=false`、新 UUID 返回 succeeded/同 run/同过期 manifest，Provider 调用总数仍 1、key 数 2；当前保留策略类型集合由 DocumentFileType 动态派生，允许分类型期限。

主会话独立核实：原 claim/finish 生成成功 run，使用 source 90 天/manifest 1 天描述符推进到第 2 天；原 authorization guard=false，新 key claim=reused、run=succeeded、同 run/同过期 manifest、keys=2。此 probe 使用真实源纯函数与到期 guard，无引擎或对象 I/O；完整读取链由审查者的内存文件服务 probe 补充。

影响：P5 的单独重试不能恢复失效预览，被迫依赖重生成 DOCX 或人工改状态，与本项边界不符。

修订 4：design §8.1 将 alias 限于当前完整有效证据，应用锁外核对 manifest/PDF/所需 pages 与 source/描述符/期限/实际可读性，窄 claim 锁内比较 source/current revision 与最早到期点；主件有效而预览生命周期失效时，新 key 有界新 run 并标自身 blocker。旧 key 只历史重放，未知存储不伪装缺失，hash/来源损坏不被再生成掩盖。明确跨仓储非原子及返回/下载复查，不回滚消费过的 key，也不复活旧文件、重渲染 DOCX 或恢复批准。PRD P5/P6/AC4/AC5/AC6 和 implement 已同步。

状态：主会话确认并完成规划修订；同一 architect 定向复核确认 R2 在规划层闭合，不代表业务修复或实现验收。

## 修订 4 的同一审查者定向复核

主会话修订后三件套再次交给同一位 architect，只复核 R1/R2 及修订本身可能产生的合同矛盾，没有另派代理或重新运行整套测试。

- R1：副作用前标记、当前 attempt 终态确认、耗尽失败收口不增加 Provider/预算/deadline、登记未知失败关闭，以及独立重试/历史重放不改变原 execution 的合同均已闭合；PRD 与 implement 的组合验收同步。
- R2：完整有效证据和绑定 current revision 的锁外观测/锁内 CAS、新 key 有界恢复、旧 key 仅历史、存储未知/完整性错误分流，以及跨域非原子与返回/下载复验边界均已闭合。
- 复核结论为“两项规划问题已闭合，未确认补充引入新的合同矛盾”；不是实现通过、生产可用或用户接受。
- 主会话在复核后、更新本记录前，核对 991 个受控文件变化 0、新文件 0；三件套与交给复核时字节一致。详 research/architect-review-protection.json。

## 其余覆盖与限制

独立审查未再确认需要改变方案的架构问题：当前公式 winner 摘要/三恢复入口、共享 file_id 键、CON-104 eligible/enabled、TR-406 锁、安全投影、legacy/published、停写者兼容回滚和 disabled 生产门均有明确规划保留合同。

本轮没有当前业务候选。历史源测试成功证据未重复运行，不能转作修订 4 已实现证明；真实引擎/隔离/MySQL/部署 FS/S3/Word 视觉未验证。修订 4 仍等待人工规划审核，依赖和其他任务状态不变。
