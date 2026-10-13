# DOC-001 执行计划

## 顺序

1. 核对初始工作树、分支、manifest、父子任务和冲突任务；记录前提不符及本轮补建授权。
2. 保存当前文件哈希和 README 原文；补建父子任务与最小 context，将 DOC-001 恢复 planning。
3. 基线执行 `git diff --check`、本任务 `check_docs.py`；报告坏链接和包缺失项。原 implement.md 不存在，无可声称已遵循的旧基线命令。
4. `task.py validate` 后对准确子任务执行 `task.py start`，manifest 改 in_progress。
5. 增量补充根 README、docs/README、DOCUMENTATION-MANIFEST、backlog 状态说明；必要时修正文档包相对链接。不修改运行说明或业务文件。
6. 复验文档链接、文件完整性、README 保全、五类事实文档和业务文件哈希、非目标 manifest 项不变、空白与 Trellis context。
7. 将证据写入 validation.md，DOC-001 改 review；子任务保持 in_progress。交付准确 commit plan，等待人工验收与提交授权。

## 计划修改文件

- README.md：新增导航段落。
- DOCUMENTATION-MANIFEST.md：补全可点击清单、状态与执行入口、权威关系。
- docs/README.md：总入口和现有事实文档导航。
- docs/implementation/codex-task-backlog.md：引用 manifest 为唯一执行状态，不改任务需求或依赖。
- docs/implementation/codex-task-prompts-all-in-one.md：仅修复顶部索引 46 个相对路径，正文保留。
- docs/implementation/codex-task-manifest.yaml：仅 DOC-001 状态、路径、notes/resolution。
- 当前父子任务的 task.json、prd/design/implement、context、检查脚本与验证证据。
- 现有未跟踪文档包按当前内容纳入提交计划，不重新生成或覆盖。

## 定向验证与门禁

`python3 .trellis/tasks/archive/2026-10/10-12-doc-001-documentation-package-index/check_docs.py`：只读检查 Markdown 路径/锚点、清单、prompt 文件、空白；列出全部失败并以非零退出。
`python3 .trellis/scripts/task.py validate .trellis/tasks/archive/2026-10/10-12-doc-001-documentation-package-index`：验证 context 路径与格式，不等于产品验收。
`git diff --check`；另外对未跟踪文档检查空白。
文件哈希比较：五类旧 docs 和全部未授权业务文件不变；README 删除新增段落后与初始原文一致；manifest 其他项深比较一致。
无业务变更，不运行 unittest、前端 build/smoke、全量 closure、check_release 或远程发布。这些属于 BAS-001 或相应后续行为任务，不以 DOC-001 替代。

## 文档和 Spec

更新上述导航与状态职责；API/运行事实和 .trellis/spec 没有新增稳定代码合同，不作无关修改。

## 回滚点与完成定义

初始文件哈希与 README 原文是回滚核对点，只撤本轮增量，保留既有文档包和 .gitignore 改动。
完成定义：逐项满足 PRD AC1–AC7，验证报告区分已跑/未跑；manifest review、Trellis in_progress，等待人工验收；无提交/push/archive。

## 人工验收后的收尾

2026-10-12 用户已授权：核验 AC1–AC7 和已有证据，manifest review → done；不更新无变化的 API 或 Spec。使用 `task.py archive --no-commit` 禁止自动 bookkeeping commit，更新归档路径后按已确认的 92 文件清单统一提交。不 push、不开始后续任务。
归档只改变任务位置；check_docs.py 的仓库与父任务定位改为不依赖子任务目录深度，保持相同检查范围，确保归档后仍可复验。
本文件上面的命令路径在归档后同步更新；历史验收命令仍保留在 validation.md。
