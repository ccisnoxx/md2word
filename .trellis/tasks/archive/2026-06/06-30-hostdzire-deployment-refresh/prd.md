# Hostdzire deployment refresh

## Goal

将当前本地 `main` 分支上已经完成并提交的变更同步到 `hostdzire`，按仓库既定的 release 目录部署流程重新部署项目，并确认基础运行状态可用。

## Confirmed Facts

- 仓库现行部署方式是“先推送到 GitHub，再在 `hostdzire` 上用 release 目录部署”，而不是直接在运行目录 `git pull`。
- `README.md` 和 `docs/deploy/online-first-validation-workflow.md` 已定义线上优先验证边界与 hostdzire 发布步骤。
- 当前本地工作区存在未提交脏改动，其中多数是已归档 Trellis 任务目录的删除痕迹，也存在至少一个代码文件 `frontend/src/components/PdfUploadPanel.vue` 的未提交改动。
- 部署应基于一个明确的已提交 commit；未提交工作区改动不能自动带上线。

## Requirements

- R1. 部署前先确认将要发布的 commit，并确认该 commit 已推送到远端仓库。
- R2. 不把未提交的本地工作区改动直接带到线上。
- R3. 按 `hostdzire` release 目录流程部署，不直接在历史运行目录上做不可追踪覆盖。
- R4. 部署后至少完成基础可用性确认：容器状态、health 接口或等价运行检查。
- R5. 如果部署被阻断，明确记录阻断点和下一步，而不是做不透明的半完成操作。

## Acceptance Criteria

- [x] 明确本次部署的目标 commit，并确认它已存在于远端仓库。
- [x] `hostdzire` 上创建或更新对应 release，并按既定方式重启/更新服务。
- [x] 部署后至少完成一轮基础运行检查，并把结果记录清楚。
- [x] 若因未提交改动、远端权限、服务器状态或配置问题无法完成部署，输出明确阻断说明和下一步建议。

## Completion Notes

- 实际发布 commit：`b167e61482bc5caa7c693cd33c548db6414bd8be`（`b167e61`）。
- 新 release 目录：`/root/md2word-releases/b167e61`。
- 发布后 `APP_VERSION=b167e61`，`DEPLOYMENT_ID=hostdzire-20260630T092256Z-b167e61`。
- `md2word-p0-api-1` 和 `md2word-p0-worker-1` 已切到新 release；内网与公网 `health/live`、`health/ready` 均返回 `200 OK`。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
