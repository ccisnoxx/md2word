# 实施计划（父任务：集成）

父任务本身不改代码，只负责编排子任务和最终集成。

## 顺序

1. 并行启动：sr-1（本会话/后端主线）、sr-4、sr-5（各自在独立 worktree 中）。
2. sr-1 合入后开始 sr-2；sr-2 合入后开始 sr-3。
3. sr-4 与 sr-1/sr-2 的 import 行冲突，由后合入的一方在 rebase 时解决。

## 每个子任务的完成条件

子任务 `implement.md` 中的清单全部勾选，`trellis-check` 通过，并在得到用户确认后按提交计划提交。推送遵循"系列完成后统一推送"的约定，不自动推送。

## 最终集成检查

- [x] 所有子任务合入同一分支后，运行后端定向测试的并集（sr-1 至 sr-4 `implement.md` 中的集合）和 `tests.test_openapi_export`。
- [x] 前端：`npm run test:unit`、`npm run build`、smoke 全集。
- [x] sr-4 的渲染等价性对比在最终分支上再跑一次。
- [x] 检查 `git diff main...HEAD --stat`，确认没有越界改动或生成产物。
- [ ] 更新 spec 后归档子任务和父任务（归档前说明可能产生的 Trellis 记录提交）。

## 集成检查记录（2026-11-12）

合并：sr-4 `refs/heads/claude/goofy-carson-0abba9` → `b9d599bd`；sr-5 `refs/heads/claude/trusting-aryabhata-ce4f6c` → `41195776`。

- sr-4 合并冲突只涉及 evidence 导入。`execution.py` 保留 sr-1 的删除；`service.py` 保留 sr-2 的删除，sr-4 对它的唯一一处导入改动同步到 `use_cases/review_writer.py`；`execution_support.py` 改为从 `render_event_summary` 导入。合并时，仓库卫生检查拦下了 sr-4 `validation/equiv.sh` 中的本机绝对路径，已改为 `MD2WORD_MINERU_RESULT_DIR` 环境变量。sr-5 自动合并，没有冲突。
- 后端：sr-1 至 sr-4 定向测试集合的并集，加上 9 个受影响的补充模块，共 50 个模块、902 项测试（清单见 `validation/backend-modules.txt`）。在原始基线 `0c9a7923`（`git archive` 导出的副本）和合并结果上分别运行。合并结果没有新增失败。差异只有 2 项：`test_pycharm_run_configs_reference_local_debug_configs` 在基线副本中失败，原因是 `.gitattributes` 把 `.run/` 标为 `export-ignore`，导出副本里缺少这些文件，属于环境差异，与代码无关。其余 223 项历史失败，在归一化运行时时间戳后与基线一致。
- 渲染等价性：在合并结果上运行 sr-4 的 `equiv.sh`，8 个样本（其中 1 个在基线上本来就以 `TableRenderError` 失败）的 DOCX 与原始基线逐 part 完全一致（`11-11-sr-4-renderer-evidence/validation/final-merged-parts.json`）。
- 前端（临时以软链接复用主仓库 `node_modules`，检查结束后已删除）：`test:unit` 45 个文件、299 项全部通过；`build` 成功；smoke 全集（`--workers=1`）53 项通过、7 项失败，7 项全部是 sr-5 基线记录的既有失败（基线 research 第 1–4、6、7、8 项），没有新增。
- 未覆盖：MySQL 真库（只有 fake MySQL 分支）、真实 Word 客户端、生产部署。各子任务 `trellis-check` 子代理没有运行，改为按各自 implement.md 的定向检查执行。
