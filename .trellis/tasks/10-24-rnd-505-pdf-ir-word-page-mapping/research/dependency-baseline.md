# 依赖准入与统一基线门

核查日期：2026-10-24（Asia/Shanghai）。本轮只做规划；原用户已明确授权任务创建及RND-501完成状态同步，未授权业务集成/start/提交/push。

## 已验收身份

| 依赖 | 工作提交 | 完成证据 | 结论 |
|---|---|---|---|
| RND-501 | 69906a5e1e4b676a3e775fa50a94cef0ebc799c9 | f51edf7e8fa1ffd05bb2de5b21c3f5f0436e9cb6归档；1b24738c763d8918e4155785866d47a9bd8d8246记账；codex/tr-406-partial-batch-failure-semantics | done/implemented；人工接受实现与披露限制 |
| RND-504 | 8fa11d9779ce05e9cba1cfb7afee34ecbd58a4cf | 本地归档task.json completed、human_acceptance=true；codex/rnd504-current-integration与md2word/RND-503指向7f8ab827 | done/implemented；生产disabled/production_ready=false |

RND-501原会话ID `01a164ac-f547-7d81-a4d1-70c0d6f03eae`，标题“规划 RenderPlan 与 block evidence”。用户明确说“我接受 RND-501 当前实现及已披露的验证限制”，随后批准工作提交及快进，再批准两笔归档/记账收尾。30个已验收业务/测试路径在69906a5e与最终目标分支全部hash匹配。

归档权威路径 `.trellis/tasks/archive/2026-10/10-17-rnd-501-render-plan-block-evidence` 已从f51edf7e逐字恢复69文件；未运行archive、未重新验收。原本地规划目录全部保留，仅task.json同步completed/工作提交/权威归档引用，原task.json完整字节保存在本目录rnd501-local-task-before.json；旧meta描述历史规划及根工作区未集成，不是新的任务验收状态。RND-504状态不改。

## 当前根基线

- 分支 `codex/preserve-rnd503-dirty-20261023`，HEAD `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`。
- 进入本轮时311条git status记录。只读保护快照 `/var/folders/m5/j06tv2sn1hn93d6f33j559jm0000gn/T/rnd505-planning-2o1wa1sp` 保存1030路径hash、完整index及状态；该临时快照不作为实施持久context。
- RND-501验收19业务路径：3相同、11不同、5缺失。缺失logical_table_group.py、services/tables/__init__.py和models.py、renderer/render_plan.py和block_evidence.py；不同不等于错误，包含后续RND-502/503增量。
- 当前根无app/services/preview，69906a5e与8fa11d97均非HEAD祖先。当前已检查分支没有同时包含两验收提交者。
- 两依赖直接共同触及execution.py/router.py；RND-501旧图片对collector还需与当前RND-503布局表/cell和RND-502公式报告共存。禁止用19/38文件整包覆盖现根。

## 实施前置门 G0（本轮不执行）

1. 人工批准RND-505三件套及统一基线准备范围后，选定适合的隔离目标并保存明确base SHA、来源SHA、工作区差量及受保护路径。建议分支md2word/RND-505仅记录，不在本轮创建/切换。
2. 复用已验收RND-501、RND-504及其必要依赖；保留现根RND-502/503、TR-402/403/406、CON-103/104、独立file_id对象key、receipt/三恢复入口和所有原完整性门。不得顺带实施其他backlog任务。
3. 建立文件级合入/适配清单、最终代码指纹，核对两合同；解决共享模块冲突需独立只读审查。若变为重新设计依赖、冻结规则变化或超出必要集成，停下回规划，不把依赖完成状态倒退。
4. 在同一基线上运行RenderPlan/block evidence、preview provider/application/persistence、公式/图片、执行/结果恢复/下载、TR/CON定向共存与release/OpenAPI门。对原基线失败保留原样、复现对照，不削弱断言。
5. 集成证据齐全并经批准，才进入RND-505新行为实现；不以各分支历史测试替代组合基线。当前G0=not_satisfied，规划可继续，实施不可开始。

## 验证边界

历史RND-501：171/56/151及release202组通过，各组重叠；API7项原基线同签名失败。Word/WPS、Golden、真实InnoDB/部署存储/容量未验且用户接受。RND-504历史结果和已接受基线失败以其closeout/implementation-validation为准；本轮没有重跑任何业务测试，不推导新组合基线或生产可用。
