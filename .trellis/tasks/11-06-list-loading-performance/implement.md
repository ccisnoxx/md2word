# 实施计划

状态：实施已获用户明确批准，允许 task.py start、实际耗时调查、必要本地修复和定向验证。提交、推送和生产变更另行确认。

## 顺序

1. [已完成] 核对 root main、公开 ready 版本、部署记录、两个页面及后端路径、并行 worktree 范围；写 research/findings.md。
2. [已完成] 收敛 PRD/design 和两个 context 清单，提出明确性能目标；只校验文档及清单，不运行应用测试。
3. [已完成] 重新确认 git 状态和并行候选身份；为实施使用隔离 checkout。冻结基线，不覆盖任何未提交候选。
4. [已完成 API/主要后端阶段；页面精确计时未取得] 取得合法认证会话的串行列表计时；必要时只读核对 API 日志/阶段/SQL 数据；无会话或原始性能证据时记录阻塞，不伪造用户、JWT 或数据库测试权限。
5. [已完成] 评估并接入已稳定的 list-ready-once 候选，测量同条件收益；选择确切补丁/文件清单后再交给 trellis-implement，不在原 worktree 上写入。
6. [补充方案已批准并完成本地实施/验证] 异常列表按阶段测量决定局部修复。涉及新持久化或观察合同的方案回到规划；普通局部修复由 trellis-implement 负责 service/incidents 和直接测试，主会话负责文档。
7. [已完成本地整合和真实 MySQL 定向验证] list-key-columns 仅在仍需其收益时整合其已有候选；真实 MySQL 与迁移前置不足时记录未验证，线上动作单独授权。不得重写迁移方案或自动操作业务库。
8. [已完成，无待修复产品发现] trellis-check 独立只读检查实际候选，关注权限、统计域、到期观察、错误优先级及共享 SQL 合同。若未改相应合同且无新风险，复用既有审查。
9. [已完成本地检查，等待下一阶段范围确认] 检查最终 diff/status，更新 AC 表。提出准确 commit 计划等待确认；不自动提交/推送/归档/add_session。
10. [另行授权后] 上线和真实页面验收，再按 AC-2 判断是否达标；未发布只能报告本地候选完成。

## 验证选择

以下是候选命令，不是本轮已运行结果。根据实际改动选择目标；不机械全跑，已有未变输入结果复用。

- 列表服务或发布读取：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_list_query_v2_service tests.test_document_job_list_publish_light_check`
- 异常分类/读取时序：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_incident_publish_light_check`；新增测试必须冻结改前逻辑，不能让候选和期望共用已改变的观察实现。
- ready-once 整合后：相应 checkout 的 `tests.test_document_job_list_query_readiness` 与直接受影响的 v2 SQL 用例，重点核对仅统计域、无关坏文件、NULL、错误版本及首次成功后损坏。
- 若接入拆列：依其 validation.md 选择交叉影响测试；真实 MySQL 只接受明确独立实例/UUID 测试库的运行结果，fake/SQLite 不作替代。
- 前端无改动不跑完整前端测试；若有 loading 修复，选择既有对应 smoke 用例或请求失败可视验证，不启动全套应用作为常规门禁。
- 本轮计划检查：`python3 .trellis/scripts/task.py validate .trellis/tasks/11-06-list-loading-performance`、任务文档占位符检查、`git diff --check`、`git status --short`。

## 完成证据

分别记录静态发现、继承的候选测试、本轮新运行结果、线上验收四种来源。默认首页三次中位数 <=2 秒、页面 <=3 秒是已批准的验收目标；若实际环境无法达到，不通过降低口径关闭任务。未获得认证时，公开 ready 测量仅用于版本与基本连通性。

并行所有权：本会话拥有独立 worktree 中本任务的产品/直接测试/迁移/Spec与任务文件；root 仅同步本任务记录，其他 worktree 及其文件/任务状态只读。本轮不运行 archive/add_session，不产生记账提交。

## 实施结果及后续边界

普通列表已完成本地候选、99 个离线不同用例最终通过、MySQL 模块 12 项通过（含 8 项实际引擎用例）、完整结果差分和性能测量；精确命令及首次失败修复见 research/key-integration.md。独立只读 trellis-check 发现的唯一坏文档链接由主会话修复，未发现可确认产品缺陷。此为普通列表阶段结果；后续service/incidents读取会话及直接交叉回归已完成，不跑无关前端构建/全仓/发布门禁。

拟提交范围仅包含本任务后端 SQL/派生存储/writer、两入口迁移与直接测试、两份 Spec 和脱敏任务文档；不含其他来源候选worktree、凭据、忽略的原始测试数据或生产操作。尚未请求或取得提交许可，所有改动留在工作区。整体任务仍未完成，本地修复已完成，等待另行确认提交/推送/生产安排。

## 2026-11-07 异常读取会话实施

用户已明确批准incident-read-session-plan.md的本地实施和定向验证，保持原事务边界/错误/观察；commit、push、生产变更依旧不在授权内。

1. trellis-implement冻结当前组合候选涉及文件，完成七模块读取会话及直接回归；已有普通列表改动必须保留。
2. 重建专属隔离MySQL，执行真实RR两连接可见性、连接生命周期、完整异常列表差分及阶段计时；仅最小直接目标，不复跑所有已通过111项。
3. trellis-check独立复核候选错误顺序/并发隔离/事务/资源清理；主会话更新Spec和AC证据。
4. 清理本轮专属验证资源，同步任务记录；线上API/浏览器验收继续未完成，不自动提交或归档。

## 本地实施最终状态

异常新增阶段35项离线+2项真实MySQL直接用例全部通过；8对完整正常响应和4对错误差分一致，完整合成调用中位0.542135→0.116432秒。分类68get+24保护和逐次commit保留，物理连接92→1，完整请求107→16。独立审查未发现产品缺陷，审查后七模块源码未变。具体命令、夹具、基准首次计数错误修复见research/incident-session-implementation.md；未机械复跑此前111项，计数不简单相加。

run2临时库、容器、卷、VM/profile/context与凭据已最终清理；原profiles/context保持。已同步Spec、AC和脱敏任务记录。拟提交范围见commit-plan.md，未stage/commit/push/archive/add_session。当前用户授权的本地工作已完成，线上AC-2仍待部署后验收，任务保持in_progress。

## 2026-11-07 本地提交授权

用户批准按commit-plan.md核对并提交本任务改动。提交前核对七模块及普通列表SQL与验证时SHA一致，继续复用已通过检查；补齐直接受影响的运维文档版本/游标/回退描述，不新增应用验证。推送、发布分支集成、生产切换另行确认，任务仍待线上验收。
