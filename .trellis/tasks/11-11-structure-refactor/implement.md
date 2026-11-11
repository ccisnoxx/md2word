# 实施计划（父任务：集成）

父任务本身不改代码，只负责编排子任务和最终集成。

## 顺序

1. 并行启动：sr-1（本会话/后端主线）、sr-4、sr-5（各自在独立 worktree 中）。
2. sr-1 合入后开始 sr-2；sr-2 合入后开始 sr-3。
3. sr-4 与 sr-1/sr-2 的 import 行冲突，由后合入的一方在 rebase 时解决。

## 每个子任务的完成条件

子任务 `implement.md` 中的清单全部勾选，`trellis-check` 通过，并在得到用户确认后按提交计划提交。推送遵循"系列完成后统一推送"的约定，不自动推送。

## 最终集成检查

- [ ] 所有子任务合入同一分支后，运行后端定向测试的并集（sr-1 至 sr-4 `implement.md` 中的集合）和 `tests.test_openapi_export`。
- [ ] 前端：`npm run test:unit`、`npm run build`、smoke 全集。
- [ ] sr-4 的渲染等价性对比在最终分支上再跑一次。
- [ ] 检查 `git diff main...HEAD --stat`，确认没有越界改动或生成产物。
- [ ] 更新 spec 后归档子任务和父任务（归档前说明可能产生的 Trellis 记录提交）。
