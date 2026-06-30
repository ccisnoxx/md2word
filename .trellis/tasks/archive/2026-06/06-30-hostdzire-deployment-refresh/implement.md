# Hostdzire Deployment Refresh Implementation Plan

## Scope

完成一次受控线上部署：确认目标 commit、推送远端、更新 `hostdzire` release、重启服务并做基础检查。

## Checklist

1. 确认本地发布目标。
   - 查看 `git status --short --branch`
   - 记录 `git rev-parse HEAD`
   - 判断工作区脏改动是否影响“已部署内容”判断

2. 确认远端状态。
   - 查看 `git remote -v`
   - 确认目标 commit 是否已推送
   - 若未推送，先 `git push`

3. 按既定流程连接 `hostdzire`。
   - 读取 `docs/deploy/online-first-validation-workflow.md`
   - 使用既定 SSH/profile 方式进入目标机器

4. 更新 release 并部署。
   - 创建或更新 release 目录
   - 执行 compose build/up 或等价部署命令
   - 保留关键输出

5. 基础运行检查。
   - 检查 compose/container 状态
   - 检查 health/live、health/ready 或等价接口

6. 记录结果。
   - 成功：记录 deployed commit、release 目录、关键检查结果
   - 失败：记录阻断点、错误输出、下一步建议

## Suggested Validation Commands

本地：

```bash
git status --short --branch
git rev-parse HEAD
git remote -v
```

线上：

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml ps
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/live
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/ready
```

## Review Gate Before Start

- 部署目标 commit 已明确
- 未提交工作区改动的影响已说明
- 远端部署流程与回退边界已明确
