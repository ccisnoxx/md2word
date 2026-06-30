# Hostdzire Deployment Refresh Design

## Architecture

这不是产品功能实现任务，而是一次受控发布操作。

发布路径应保持：

1. 确认本地目标 commit
2. 推送到远端仓库
3. 连接 `hostdzire`
4. 通过既定 release 目录流程更新代码
5. 重新部署容器/服务
6. 执行基础运行检查

## Deployment Boundary

- 本次部署只发布 **已提交** 的代码。
- 未提交的本地工作区改动只用于风险判断，不自动进入部署包。
- 如果本地 `HEAD` 尚未推送到远端，必须先推送，再让 `hostdzire` 基于该 commit 创建 release。

## Source Of Truth

- 代码真源：当前本地 `main` 的目标 commit 和 GitHub 远端对应 commit。
- 部署流程真源：`README.md` 与 `docs/deploy/online-first-validation-workflow.md`。
- 运行检查真源：`docs/runbooks/backend.md` 中的 health / compose 检查步骤。

## Risk Model

主要风险：

- 误把未提交本地改动当成“已部署内容”。
- `hostdzire` release 目录创建失败、权限失败或 compose 更新失败。
- 服务虽然完成重启，但 health / readiness 未恢复。

控制策略：

- 部署前显式记录 `HEAD` SHA。
- 部署后显式记录运行检查结果。
- 不在遇到阻断时做隐式回滚或隐式覆盖。

## Rollback

如果新 release 部署后检查失败：

- 优先保留失败现场和日志；
- 使用已有上一个 release 或当前运行目录作为回退基线；
- 仅在确认回退命令和目标目录后执行回退。

本次任务的默认目标是完成正常部署；回退只在部署失败时按需执行。
