# TR-406 实施交付与验收说明

日期：2026-10-22。分支：`codex/tr-406-partial-batch-failure-semantics`。用户已接受 revision 2 并授权实施，随后明确同意整合 CON-103/104 已验收基线及其原有 schema bootstrap；授权原文与边界见 [实施授权](implementation-authorization.md)。

本地实施、计划内验证和独立复审已完成，候选冻结并停人工验收。第三轮三项缺口均已修复，最终限定复审没有新增或残留 P1/P2/P3；见 [最终独立复审](implementation-review-final.md)。用户已明确验收通过并确认两笔业务提交，human_acceptance_status=accepted；随后授权仅TR-406 manifest done、归档和本次会话记录。业务与bookkeeping阶段的授权按时间分别保留。

## 实施范围与结果

- 先整合 CON-102 阶段、原子 retry、first-valid-receipt 和文件身份基线，保留 TR-403 evidence、真实字节/checksum、脱敏及唯一物理路径。按追加授权整合 CON-103 质量/复核/交付状态及原有 bootstrap，以及 CON-104 下载分类/批准发布可用性。没有设计 TR-406 额外 DDL，也没有连接或迁移生产数据库。
- workflow 唯一归约本代根树、有效叶子、attempt/lease/调用预算与停止原因。任一有效叶子终败即收口任务；成功兄弟不重调，在途结果不能越过停止闸门晋升。
- file、SQLite、MySQL 适配器提供同 job 原子根集合安装、领取、提交、split、回收与一致快照；迟到初始化不覆盖现态，残缺树失败关闭。MySQL 使用 job→batch 当前读与同连接事务；真实 InnoDB 和部署文件锁证据另列。
- 全叶子、覆盖与 evidence 通过后才 fan-in/apply。partial 不成为目标 IR、主 DOCX、下载或 QA/发布来源。用户 retry 原子换代，从权威 source 重建全部批次；同代自动恢复才复用成功兄弟。
- API 返回同一授权快照的 execution/叶子分类；UI 展示自动重试、最终失败和停止的兄弟，防止旧 job/旧请求/旧代响应覆盖，动作沿后端 available actions。
- batch terminal 已落库而 job 尚 running 的故障窗口可由终态自身或排队兄弟幂等收口，重复消息不产生新调用或重复终态事件。调用、Artifact 和条件提交的错误保持明确归属。

## 验证证据

AC1–13 的行为与测试入口逐条列于 [验收证据映射](acceptance-evidence.md)。后端精确命令、数量与前后修复证据以 [质量验证](quality-validation.md) 为准；不同分组包含复用或重复模块，不将数量相加为独立总量。

- 核心、仓储、执行、完整性、模式、receipt：第三轮修复后的九模块126/126通过，其中三个新增核心模块42/42，预算与完整性窄组合30/30；这些组合互有重复，不累加。
- FastAPI 失败/split/retry/debug/下载：12项通过；QA/workbench/direct/action：另5项通过。
- 状态/下载/迁移/结果：68项通过。数据库仓储整模块14项通过、2项既有失败；两项 SQLite/MySQL callback fake renderer 失败已在原始 HEAD 的独立 checkout 复现，不放宽真实 IR/渲染校验以通过。更早宽回归中的10项既有失败及精确 selector 见 [原始 HEAD 复现](research/original-head-regression.md)。
- 前端：完整 unit 152项、build/vue-tsc、翻译批次 mock smoke通过；覆盖 operator/admin、375/768/1024/1440、dark、键盘与旧代响应。完成态提示仅改文案后，8项定向 unit 再次通过；见 [前端验证](frontend-validation.md)。
- OpenAPI：164 paths / 324 schemas 的生成与 check通过。release聚合检查在第三轮执行器修复后再次通过，包含36个 targeted unittest target，OpenAPI check也已再次通过。
- 正式本地转换入口：OPA228 component 1/1、direct phase2-core 5/5、P0=0；TR-406 测试另通过公开/合成表格的真实 converter→batch→fan-in→renderer 成功/失败对照。direct矩阵仍有3份文档的既有标题样式 flags，phase3_entry_ready=false；不等同于完整阶段准入，见 [样本验证](sample-validation.md)。

## 独立复审与工作区保护

前两轮复审修复了 MySQL RR 旧视图、原子停止闸门、快照换代、停止投影、claim 拒绝、旧代异常归属及正常 split 中间读取等问题。第三轮独立39项通过，另以真实 fixture 窄探针发现预算返回值、树异常分类和 Artifact metadata 驱动异常三项缺口；见 [第三轮复审](implementation-review-round3.md)。三项均已修复；最终独立执行3个新增selector及五组窄探针对照通过，开始/结束源码hash一致，候选已冻结。

初始 HEAD 为 `596a2de7ed29edb7fdb378d91c17bda09b7f1066`。原始1428路径哈希及 index/worktree 差异已保存；中途保护检查确认332个非本任务原始 dirty 文件字节、原 index、父任务原有删除及 manifest 的 TR-406 区块之外保持不变。最终保护检查再次通过，见 [保护结果](workspace-protection-final.json)。两份被测试改写的已跟踪浏览器产物已按原始哈希还原，本次截图/trace另保留为证据。

本轮触及的 Python 注释、docstring、开发者可见错误和邻近说明已按中文规则检查并更新；机器字段、协议和测试合同字面量保持原值。目标设计/API/状态机和 Spec 已同步。

## 保留门与停止位置

真实 MySQL/InnoDB 并发/断连、部署文件系统跨进程锁、真实 Provider 四方向语言质量、S3/线上 API、旧写者排空/新写者启用以及 LibreOffice/Word 人工签字均未运行。这些证据由对应上线或人工门拥有，本地 fake 不替代。没有新增真实外调或部署授权。

实施交付时先停人工验收，随后用户批准并确认两笔业务提交：依赖0946326b0f457ef4b4f60895f17feb915d657c14、TR-406增量6d89c7e012a5086114a739a9dfd1b067556237ce。用户再授权本次仅将TR-406标记done/implemented、归档至.trellis/tasks/archive/2026-10/10-22-tr-406-partial-batch-failure-semantics并记录会话；保留所有其他未提交改动，不push、不部署、不启动下一任务。
