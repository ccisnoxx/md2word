# 运维材料与任务记录本地提交计划（2026-11-09 已获批准）

日期：2026-11-09。用户已明确批准按本计划新建本地分支并形成两个工作提交，保留验收证据、复用验证；不推送、不归档、不改生产。旧[commit-plan.md](commit-plan.md)已对应产品提交`1a821110`落地，其批准不扩展到本批新增运维材料。

## 当前基线与执行范围

- 提交准备时分支main，HEAD `b8b2779a9ee678f778ddb95890cebc3a0faff55e`；开始整理时index为空，初始29个实际文件差异均已识别为本任务。
- 已按批准从上述HEAD新建本地分支`codex/list-loading-ops-records`；原产品分支与其他worktree保留。
- 最终拟纳入35个路径，按下面两个完整文件批次顺序提交，不按hunk拆分。精确路径、当前SHA及字节数见[输入清单](research/ops-materials-inventory.json)。
- 整理阶段未暂存或提交；本次批准后执行两个本地提交。任务completed及2026-11-07完成日期保留；不推送，不连接或改动生产，归档和journal自动提交不属于本批。

## 提交一：运维载体与共享合同（16个文件）

建议标题：`chore: preserve list loading release tooling`

内容：实际迁移/快照/完整router差分载体、窗口辅助实现与直接测试、已执行窗口脚本快照、冻结身份、对应审查和共享Spec。Spec只澄清已有运维合同、工具归属和已完成验收时态，不改变产品实现。

```text
.trellis/spec/backend/document-job-list-query-v2.md
.trellis/tasks/11-06-list-loading-performance/research/release_ops/README.md
.trellis/tasks/11-06-list-loading-performance/research/release_ops/common.py
.trellis/tasks/11-06-list-loading-performance/research/release_ops/migrate.py
.trellis/tasks/11-06-list-loading-performance/research/release_ops/query_diff.py
.trellis/tasks/11-06-list-loading-performance/research/release_ops/snapshot.py
.trellis/tasks/11-06-list-loading-performance/research/release_ops/test_release_ops.py
.trellis/tasks/11-06-list-loading-performance/research/release_ops/window_helpers.py
.trellis/tasks/11-06-list-loading-performance/research/release_ops/test_window_helpers.py
.trellis/tasks/11-06-list-loading-performance/research/release-ops-manifest.json
.trellis/tasks/11-06-list-loading-performance/research/release-ops-review.md
.trellis/tasks/11-06-list-loading-performance/research/window-lib.py
.trellis/tasks/11-06-list-loading-performance/research/window-production-switch.py
.trellis/tasks/11-06-list-loading-performance/research/window-helpers-review.md
.trellis/tasks/11-06-list-loading-performance/research/window-switch-review.md
.trellis/tasks/11-06-list-loading-performance/research/window-readiness.md
```

已执行脚本及原6文件保持原字节，不能为提交而整理格式、重命名、import或运行。`window-lib.py`是远端`window_lib.py`的证据副本，固定路径及状态依赖由索引说明。

## 提交二：发布过程、验收证据与任务记录（19个文件）

建议标题：`docs: record list loading production acceptance`

内容：构建/审批时快照与最终执行结果一起留存，任务AC/状态、集成交接、独立材料审计、当前输入索引及原字节裁剪截图。把构建/审批材料及切换方案与最终结果放在同一提交，便于审阅授权和时间线；它们不改变提交一工具字节。

```text
.trellis/tasks/11-06-list-loading-performance/design.md
.trellis/tasks/11-06-list-loading-performance/implement.md
.trellis/tasks/11-06-list-loading-performance/prd.md
.trellis/tasks/11-06-list-loading-performance/production-switch-plan.md
.trellis/tasks/11-06-list-loading-performance/task.json
.trellis/tasks/11-06-list-loading-performance/local-commit-handoff.md
.trellis/tasks/11-06-list-loading-performance/production-execution.md
.trellis/tasks/11-06-list-loading-performance/ops-records-commit-plan.md
.trellis/tasks/11-06-list-loading-performance/research/approval-package-manifest.json
.trellis/tasks/11-06-list-loading-performance/research/production-acceptance-result.json
.trellis/tasks/11-06-list-loading-performance/research/production-browser-acceptance.json
.trellis/tasks/11-06-list-loading-performance/research/production-build-manifest.json
.trellis/tasks/11-06-list-loading-performance/research/production-build.md
.trellis/tasks/11-06-list-loading-performance/research/production-execution-plan.md
.trellis/tasks/11-06-list-loading-performance/research/verification-summary.md
.trellis/tasks/11-06-list-loading-performance/research/ops-materials-index.md
.trellis/tasks/11-06-list-loading-performance/research/ops-materials-audit.md
.trellis/tasks/11-06-list-loading-performance/research/ops-materials-inventory.json
.trellis/tasks/11-06-list-loading-performance/research/production-acceptance.jpg
```

## 保留与排除

- 保留历史manifest的false和SHA。审批包3/4文档仍匹配；当前切换方案不同于历史审批SHA，索引明确记录变化时点及未取得原审批正文，不伪报4/4。
- 原始浏览器JSON含首次受控采样、自动等待上界试验和最终有效三次采样，全部保留；截图复制前后SHA相同。主机收尾时间与浏览器证据时间分别记录。
- 原SQL/RDB/对象与配置归档、完整env/inspect、身份/cases/业务响应、忽略的research/data、镜像归档及其它worktree不纳入Git；不复制、清理或重建这些资产。
- 不再次提交既有产品源码、应用直接测试、锁文件或原commit-plan；其他任务、分支归档、journal和生产操作均不属于本批。
- 当前没有未识别的dirty路径。若实际提交前出现额外文件或清单内字节变化，重新说明该差异，不扩大暂存范围；不使用git add -A。

## 复用验证与仅本地核对

原产品111项及异常补充37项分别复用、不相加；原运维12项/5文件AST/6次镜像CLI导入、窗口辅助10项及执行器静态复核按记录SHA复用。生产8.4.9的O/C/R、迁移及线上验收只作为11月7日历史执行事实，不描述为11月9日新跑或当前生产现状。

本轮只核对冻结SHA、35路径归属、JSON/采样统计、截图字节、文档时态/相对链接及空白。implement/check两份JSONL输入未变，复用各6条的既有上下文验证。没有运行pytest/unittest、镜像构建、CLI导入、数据库、浏览器或生产探测。

## 已批准的本地执行顺序

1. 核对HEAD、空index、清单SHA和路径集合；保留原产品分支及worktree。按计划创建新的本地记录分支。
2. 逐路径暂存第一批，核对staged差异，形成第一个常规提交。
3. 逐路径暂存第二批，核对staged差异，形成第二个常规提交。
4. 报告两个实际提交SHA、文件统计与剩余dirty状态，继续保留本地，不push。

不amend、不改历史，不执行archive/add_session。它们分别可能自动生成bookkeeping提交，archive还移动原任务目录；需要时另给具体收尾范围。第一批实际提交为`38f686d0fcc6358a105e3f585212e9ae60219f73`；第二批包含本次交接说明，最终提交SHA以Git记录和完成回复为准。

批准后的本地执行只更新本计划、task.json和local-commit-handoff.md中的批准/交接事实，以及当前输入清单。原冻结脚本、历史manifest、验收JSON、截图保持原字节；这三份管理记录的批准前/当前SHA单独记入输入清单，不扩大35路径。
