# TR-406 规划校验

> 最新规划为 revision 2；本文件先保留 revision 1 原校验记录，其中“本轮”指初始规划轮；revision 2 的实际结果与证据边界见文末。

日期：2026-10-22；历史修订：1；当时状态：planning / 待人工审核。

## 本轮已完成

- 工作目录、初始 dirty、父任务与唯一性检查完成；创建使用 `create --parent --no-start`。`task.py current --source` 返回 `(none)` / `none`，未执行 start。
- TR-403 与 CON-102 均 done/归档 completed/人工已接受。TR-403 业务提交在当前 HEAD；CON-102 验收提交不在当前 HEAD。设计/执行计划已将兼容基线整合作为实施前门禁，本轮未合并或切分支。
- 已完成必读产品/冻结决策/实施/合同/翻译/测试/迁移文档及真实源码、测试、API、三存储、配置、脚本和历史任务调查，见 research/current-state.md。
- 37 项既有定向基线通过，退出0；三个只读 fake 反例证明仍有增量，不能判 skipped_existing。业务行为测试和规划静态校验分开报告。
- prd/design/implement 完整。PRD 已按最终结构进行一次收敛复读，保留事实锚点、R1–R4、AC1–11、全部用户不变量与非目标；没有遗留临时问答或未解决的阻塞产品问题。技术方案待人工接受不等于实现授权。
- implement/check context 只纳入相关 Spec、翻译设计和本任务研究，不加入业务源码目录或整个仓库；代码/测试导航由研究与 implement.md 给出。

## 验证结果

- `python3 .trellis/scripts/task.py validate .trellis/tasks/10-22-tr-406-partial-batch-failure-semantics`：通过，implement=8、check=8；最终元数据将未创建的实施分支保留为 `branch=null`，建议名仅在 meta，不存在分支警告已消除。
- `git diff --check`：退出0；另检查本任务未跟踪 Markdown 的空白与 JSON/JSONL 可解析性。
- 创建前417个既存 dirty/untracked 文件逐项对比：仅manifest与父task.json发生本轮允许的修改；其余原文件哈希均相同。manifest在TR-406区块之外的原字节完全相同，其他任务对象/状态未变；父JSON仅children末尾增加当前子任务，状态和其他字段未变。
- 无本轮额外业务/测试/前端/配置文件修改。分支/HEAD保持 `md2word/TR-403@596a2de7ed29edb7fdb378d91c17bda09b7f1066`；current task仍none。
- task.py validate仅证明context文件/路径有效，不等于技术方案已获批或AC1–11实现验收。

## 本轮未做

没有修改业务代码/前端/测试/配置/API快照/全局Spec，没有执行 task.py start、提交、push、archive、add_session、生产部署或外部Provider。未运行 release、前端/浏览器、component/matrix、真实 MySQL/S3/部署 FS 或 Word 人工验证；本轮无业务变更，采用37项窄基线、fake探针与规划/路径/差异校验，实施与上线检查见 implement.md。

## 保留风险与评审门

- 当前分支缺依赖代码，不能直接实现；CON-102/103/104 与 TR-403 的正确整合是实施准入，不能以 manifest done 代替。
- 本方案增加局部批次原子性和 attempt 约束；同代并发、split中断、跨代回流与partial访问须在候选上验证并独立复核，规划通过不证明风险已关闭。
- file 无多文件事务：残缺split恢复明确失败；真实MySQL/InnoDB及部署FS启用门继续pending。
- TR-404/405存在共享文件写范围；本任务不实施相邻需求，整合前须协调。
- 本轮停在规划评审门。未请求或取得实现、提交、push、归档或生产写者授权。


## revision 2 修订校验（2026-10-22）

- 用户确认 revision 1 独立 architect 审查两项 P2，并授权仅修订规划。三件套均已更新为 revision 2；PRD 做最终结构收敛复读，R1/R3 规则与 AC12/13、design 3.1.1/3.2、implement B/C/测试矩阵一一对应，AC1–11 与既有不变量保留。
- P2-1：本代完整根计划一次性安装，锁内重核、已有 ID 不覆盖、已成功/运行账本不重置、DB 原子安装/rollback、file 部分根中断失败关闭，新增 AC12。
- P2-2：持久化终态驱动 enqueue/claim/结果晋升停止闸门，同代拒绝走幂等 finalizer，区分普通竞争/旧代；终态 CAS 后故障注入分别重放终态自身/排队兄弟，新增 AC13。
- planning-review.md 保留 revision 1 历史发现并标注旧行号，追加 revision 2 处理表；research/review-decisions.md 记录新合同与验收。未派发 revision 2 独立复审，不能把规划补充记成风险已验证关闭。
- implement/check context 各在原8条基础上增加1条本任务修订研究；无业务代码目录或整个仓库注入。task.meta revision=2、implementation_authorized=false，manifest 仅 TR-406 notes 追加记录，status 仍 planning。
- 本轮从已有子任务继续，未 create/start/切分支，不修改业务代码/测试/API快照/配置/全局Spec，不提交/push/归档。父任务既存删除保持，不据此恢复文件或创建重复任务。
- 未重跑 revision 1 的37项业务基线或fake探针，也未运行新的 AC12/13 候选测试、release/前端/线上/真实Provider；这次仅修改规划。历史结果只作为已记录证据，实施/上线验证门不变。

revision 2 实际检查结果：

- `python3 .trellis/scripts/task.py validate .trellis/tasks/10-22-tr-406-partial-batch-failure-semantics`：成功，implement=9、check=9，无缺失路径或示例条目。
- `task.py current --source`：Current task=(none)，Source=none；`git diff --check`退出0。另逐个检查任务未跟踪Markdown的空白、JSON/JSONL可解析、9+9路径有效且无重复、三件套修订号和AC1–13映射，均通过。
- 修改前1426个tracked/untracked路径核对：仅本任务8个原有规划/元数据/context文件与manifest的TR-406 notes改变；新增仅research/review-decisions.md。其他原文件字节与既存删除状态均未变，manifest在TR-406区块外原字节及其他任务对象/状态完全保持。
- PRD原非目标/不变量段落逐字保留；AC1–11保留，新增AC12/13。分支和HEAD保持md2word/TR-403@596a2de7ed29edb7fdb378d91c17bda09b7f1066。
- validate只证明规划context路径/格式有效，不能证明AC12/13实现正确或新稿已获批准。revision 2停人工评审；旧独立审计Bundle未修改，本轮未新派子代理。
